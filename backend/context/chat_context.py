"""Utilities for consolidating chat-specific repository context management.

This module now relies exclusively on GitIngest to collect repository data. The
resulting payload is chunked, embedded, cached, and transformed into concise
context snippets that downstream chat flows can consume without touching the
GitHub API.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from models import ChatSession, Repository
from sqlalchemy.orm import Session

from utils import utc_now

from .cache_metadata import CacheMetadata
from .facts_and_memories import (
    EmbeddingChunk,
    EmbeddingPipeline,
    RepositoryFile,
    RepositorySnapshot,
    RepositorySnapshotService,
)

logger = logging.getLogger(__name__)


# Lightweight heuristic mapping from extensions to primary languages. This is
# intentionally small and only used to generate human-friendly summaries.
LANGUAGE_EXTENSION_MAP: Dict[str, str] = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".rs": "Rust",
    ".go": "Go",
    ".rb": "Ruby",
    ".php": "PHP",
    ".java": "Java",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".c": "C",
    ".cc": "C++",
    ".cpp": "C++",
    ".h": "C",
    ".hpp": "C++",
    ".cs": "C#",
    ".scala": "Scala",
    ".dart": "Dart",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".r": "R",
}


class ChatContext:
    """Central coordinator for fetching and caching repository context."""

    CACHE_ROOT = Path("/tmp/github_context_cache")
    CACHE_TTL_SECONDS = 86400  # 24 hours
    MAX_FILES_FOR_EMBEDDING = 25
    MAX_CHUNKS_FOR_CONTEXT = 6
    MAX_CONTEXT_STRING_LENGTH = 4000

    def __init__(
        self,
        db: Session,
        user_id: int,
        repo_owner: Optional[str],
        repo_name: Optional[str],
        session_obj: Optional[ChatSession] = None,
        session_id: Optional[str] = None,
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.repo_owner = (repo_owner or "").strip()
        self.repo_name = (repo_name or "").strip()
        self.session_obj = session_obj
        self.session_id = (
            session_id or getattr(session_obj, "session_id", "") or "session"
        )
        self._repository: Optional[Repository] = None
        self.logger = logging.getLogger(f"{__name__}.ChatContext")

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_component(text: Any) -> str:
        """Normalise text to a filesystem-safe component."""

        if text is None:
            return "unknown"
        return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(text))

    def _ensure_cache_dir(self) -> Path:
        """Ensure the cache directory exists and is writable."""

        target_dir = (
            self.CACHE_ROOT
            / self._safe_component(self.user_id)
            / self._safe_component(self.session_id)
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(target_dir, os.W_OK | os.X_OK):
            raise PermissionError(f"Cache directory {target_dir} is not writable")
        return target_dir

    def cache_path(self) -> Path:
        """Return the JSON cache path for the current repo/session tuple."""

        cache_dir = self._ensure_cache_dir()
        filename = f"{self._safe_component(self.repo_owner)}__{self._safe_component(self.repo_name)}.json"
        return cache_dir / filename

    def _compute_cache_metadata(self, path: Path) -> CacheMetadata:
        """Compute digest/size metadata for the cached JSON file."""

        size = path.stat().st_size if path.exists() else None
        sha256 = None
        if path.exists():
            import hashlib

            hasher = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(8192), b""):
                    hasher.update(chunk)
            sha256 = hasher.hexdigest()

        return CacheMetadata(
            cache_path=str(path),
            owner=self.repo_owner,
            name=self.repo_name,
            session_id=self.session_id,
            user_id=self.user_id,
            size=size,
            sha256=sha256,
            cached_at=datetime.now(tz=timezone.utc).isoformat(),
            version=2,
            source="gitingest",
        )

    def write_cache(self, data: Dict[str, Any]) -> CacheMetadata:
        """Persist GitIngest context JSON to disk and return metadata."""

        path = self.cache_path()
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        return self._compute_cache_metadata(path)

    def read_cache(
        self, meta: Optional[CacheMetadata] = None
    ) -> Optional[Dict[str, Any]]:
        """Attempt to read cached context JSON using provided metadata."""

        candidate_path: Optional[Path] = None
        if meta and meta.cache_path:
            candidate_path = Path(meta.cache_path)
        else:
            candidate_path = self.cache_path()

        if not candidate_path.exists():
            return None

        try:
            with candidate_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:  # pragma: no cover - defensive logging
            self.logger.warning(
                "Failed to read cached context from %s: %s", candidate_path, exc
            )
            return None

    # ------------------------------------------------------------------
    # Repository metadata helpers
    # ------------------------------------------------------------------
    def _load_repository(self) -> Optional[Repository]:
        """Fetch or cache the ``Repository`` row for this owner/name."""

        if self._repository is not None:
            return self._repository

        if not self.repo_owner or not self.repo_name:
            return None

        repository = (
            self.db.query(Repository)
            .filter(
                Repository.owner == self.repo_owner,
                Repository.name == self.repo_name,
                Repository.user_id == self.user_id,
            )
            .first()
        )
        self._repository = repository
        return repository

    # ------------------------------------------------------------------
    # GitIngest context collection
    # ------------------------------------------------------------------
    def _build_repo_url(self) -> str:
        return f"https://github.com/{self.repo_owner}/{self.repo_name}"

    async def _fetch_gitingest_snapshot(self) -> RepositorySnapshot:
        repo_url = self._build_repo_url()
        snapshot = await RepositorySnapshotService.fetch(repo_url=repo_url)
        return snapshot

    def _select_files_for_embedding(
        self, files: Sequence[RepositoryFile]
    ) -> List[RepositoryFile]:
        """Pick a manageable subset of files to embed, prioritising documentation."""

        def score(repo_file: RepositoryFile) -> float:
            path_lower = (repo_file.path or "").lower()
            size_score = len(repo_file.content or "")

            bonus = 0.0
            if "readme" in path_lower:
                bonus += 10_000
            if path_lower.endswith(".md"):
                bonus += 5_000
            if "/docs/" in path_lower or path_lower.startswith("docs/"):
                bonus += 2_500
            if (
                path_lower.endswith(".py")
                or path_lower.endswith(".ts")
                or path_lower.endswith(".tsx")
            ):
                bonus += 1_500
            if path_lower.endswith(".js") or path_lower.endswith(".jsx"):
                bonus += 1_200
            if repo_file.category:
                # Slight bump for documentation and configuration categories
                if "Documentation" in repo_file.category:
                    bonus += 2_000
                elif "Configuration" in repo_file.category:
                    bonus += 1_000

            return float(size_score + bonus)

        ranked = sorted(files, key=score, reverse=True)
        return ranked[: self.MAX_FILES_FOR_EMBEDDING]

    def _select_relevant_chunks(
        self, chunks: Sequence[EmbeddingChunk]
    ) -> List[EmbeddingChunk]:
        """Rank and select the most informative chunks for chat context."""

        def score(chunk: EmbeddingChunk) -> float:
            path_lower = chunk.file_path.lower()
            base = float(chunk.tokens or len(chunk.chunk_text) or 0)

            if "readme" in path_lower:
                base += 5_000
            if path_lower.endswith(".md"):
                base += 2_500
            if chunk.chunk_index == 0:
                base += 1_000
            if "/docs/" in path_lower or path_lower.startswith("docs/"):
                base += 750
            if (
                path_lower.endswith(".py")
                or path_lower.endswith(".ts")
                or path_lower.endswith(".tsx")
            ):
                base += 500

            return base

        ranked_chunks = sorted(chunks, key=score, reverse=True)
        return ranked_chunks[: self.MAX_CHUNKS_FOR_CONTEXT]

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if not text:
            return ""
        if len(text) <= limit:
            return text
        return text[: max(0, limit - 3)].rstrip() + "..."

    @staticmethod
    def _extract_summary(snapshot: RepositorySnapshot) -> str:
        raw = (
            snapshot.raw_response.get("raw_response")
            if isinstance(snapshot.raw_response, dict)
            else {}
        )
        summary = ""
        if isinstance(raw, dict):
            summary = raw.get("summary") or ""
        return summary.strip()

    def _infer_primary_language(self, files: Sequence[RepositoryFile]) -> Optional[str]:
        usage: Dict[str, int] = {}
        for repo_file in files:
            path = repo_file.path or ""
            ext = Path(path).suffix.lower()
            if not ext:
                continue
            size = repo_file.content_size or len(repo_file.content or "")
            usage[ext] = usage.get(ext, 0) + size

        if not usage:
            return None

        dominant_ext = max(usage.items(), key=lambda item: item[1])[0]
        return LANGUAGE_EXTENSION_MAP.get(dominant_ext)

    def _build_repository_info(
        self, summary: str, files: Sequence[RepositoryFile]
    ) -> Dict[str, Any]:
        """Construct a lightweight repository information block."""

        description = ""
        if summary:
            first_line = summary.splitlines()[0].strip()
            description = self._truncate(first_line, 280)

        return {
            "full_name": f"{self.repo_owner}/{self.repo_name}"
            if self.repo_owner and self.repo_name
            else "",
            "description": description,
            "language": self._infer_primary_language(files),
            "html_url": self._build_repo_url(),
            "default_branch": "main",
            "source": "gitingest",
        }

    def _compose_context_string(
        self, summary: str, chunks: Sequence[EmbeddingChunk]
    ) -> str:
        """Combine GitIngest summary and selected chunks into a single string."""

        parts: List[str] = []
        if summary:
            parts.append(f"GitIngest Summary:\n{summary.strip()}")

        for chunk in chunks:
            chunk_header = f"File: {chunk.file_path} (chunk {chunk.chunk_index})"
            snippet = self._truncate((chunk.chunk_text or "").strip(), 800)
            if snippet:
                parts.append(f"{chunk_header}\n{snippet}")

        combined = "\n\n".join(parts).strip()
        if not combined and self.repo_owner and self.repo_name:
            combined = f"Repository: {self.repo_owner}/{self.repo_name}"
        return self._truncate(combined, self.MAX_CONTEXT_STRING_LENGTH)

    def _chunk_payload(self, chunk: EmbeddingChunk) -> Dict[str, Any]:
        return {
            "file_path": chunk.file_path,
            "file_name": chunk.file_name,
            "chunk_index": chunk.chunk_index,
            "chunk_text": chunk.chunk_text,
            "embedding": chunk.embedding,
            "tokens": chunk.tokens,
            "metadata": chunk.metadata,
        }

    async def _build_gitingest_context(self) -> Dict[str, Any]:
        """Fetch GitIngest data, generate embeddings, and build cache payload."""

        snapshot = await self._fetch_gitingest_snapshot()
        summary = self._extract_summary(snapshot)
        files_for_embedding = self._select_files_for_embedding(snapshot.files)

        embeddings: List[EmbeddingChunk] = []
        try:
            pipeline = EmbeddingPipeline()
            embeddings = pipeline.process_many(files_for_embedding)
        except Exception as exc:
            self.logger.warning(
                "Failed to generate embeddings for %s/%s: %s",
                self.repo_owner,
                self.repo_name,
                exc,
            )
            embeddings = []

        selected_chunks = self._select_relevant_chunks(embeddings) if embeddings else []
        context_string = self._compose_context_string(summary, selected_chunks)

        payload: Dict[str, Any] = {
            "repository": self._build_repository_info(summary, snapshot.files),
            "context_chunks": [self._chunk_payload(chunk) for chunk in selected_chunks],
            "chunk_statistics": {
                "total_files_processed": len(snapshot.files),
                "files_embedded": len(files_for_embedding),
                "total_chunks": len(embeddings),
                "selected_chunks": len(selected_chunks),
            },
            "raw_response": snapshot.raw_response,
            "summary": summary,
            "context_string": context_string,
            "fetched_at": utc_now().isoformat(),
            "owner": self.repo_owner,
            "name": self.repo_name,
            # Retain legacy keys expected by prompt builder
            "recent_commits": [],
            "recent_issues": [],
            "branches": [],
            "source": "gitingest",
        }

        return payload

    async def ensure_github_context(self) -> Optional[Dict[str, Any]]:
        """Ensure cached repository context is available and up to date."""

        if not self.repo_owner or not self.repo_name:
            return None

        repository = self._load_repository()
        existing_meta = (
            CacheMetadata.from_dict(getattr(repository, "github_context", None))
            if repository
            else None
        )
        updated_at = (
            getattr(repository, "github_context_updated_at", None)
            if repository
            else None
        )

        if existing_meta and updated_at:
            age_seconds = (utc_now() - updated_at).total_seconds()
            if age_seconds < self.CACHE_TTL_SECONDS:
                cached = self.read_cache(existing_meta)
                if cached:
                    return cached
            else:
                self.logger.info(
                    "Cached GitIngest context for %s/%s is stale (%ds old); refreshing",
                    self.repo_owner,
                    self.repo_name,
                    int(age_seconds),
                )

        try:
            fetched_context = await self._build_gitingest_context()
        except Exception as exc:
            self.logger.warning(
                "Failed to fetch GitIngest context for %s/%s: %s",
                self.repo_owner,
                self.repo_name,
                exc,
            )
            return None

        cache_meta = self.write_cache(fetched_context)

        repo_url = self._build_repo_url()
        if repository is None:
            repository = Repository(
                user_id=self.user_id,
                owner=self.repo_owner,
                name=self.repo_name,
                full_name=f"{self.repo_owner}/{self.repo_name}",
                repo_url=repo_url,
                html_url=repo_url,
                clone_url=f"{repo_url}.git",
                github_context=cache_meta.to_dict(),
                github_context_updated_at=utc_now(),
            )
            self.db.add(repository)
        else:
            repository.github_context = cache_meta.to_dict()
            repository.github_context_updated_at = utc_now()

        try:
            self.db.commit()
        except Exception as commit_err:  # pragma: no cover - defensive logging
            self.logger.warning("Failed to commit repository metadata: %s", commit_err)
            self.db.rollback()

        return fetched_context

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------
    def _format_cached_context(self, cached: Dict[str, Any]) -> Optional[str]:
        """Format cached GitIngest context JSON into a summary string."""

        if not isinstance(cached, dict):
            return None

        context_string = cached.get("context_string")
        if isinstance(context_string, str) and context_string.strip():
            return context_string.strip()

        summary = cached.get("summary")
        parts: List[str] = []
        if isinstance(summary, str) and summary.strip():
            parts.append(f"GitIngest Summary:\n{summary.strip()}")

        chunks = cached.get("context_chunks")
        if isinstance(chunks, list) and chunks:
            for chunk in chunks:
                if not isinstance(chunk, dict):
                    continue
                file_path = chunk.get("file_path") or "unknown"
                chunk_index = chunk.get("chunk_index", 0)
                chunk_text = chunk.get("chunk_text")
                if isinstance(chunk_text, str) and chunk_text.strip():
                    snippet = self._truncate(chunk_text.strip(), 800)
                    parts.append(f"File: {file_path} (chunk {chunk_index})\n{snippet}")

        if not parts and self.repo_owner and self.repo_name:
            parts.append(f"Repository: {self.repo_owner}/{self.repo_name}")

        return "\n\n".join(parts) if parts else None

    def _session_context_fragments(self) -> List[str]:
        """Extract stored session context (facts/memories) for enrichment."""

        if not self.session_obj or not getattr(self.session_obj, "repo_context", None):
            return []

        fragments: List[str] = []
        repo_context = self.session_obj.repo_context
        if isinstance(repo_context, dict):
            summary = repo_context.get("summary")
            if isinstance(summary, str) and summary.strip():
                fragments.append(summary.strip())

            description = repo_context.get("description") or getattr(
                self.session_obj, "description", None
            )
            if isinstance(description, str) and description.strip():
                fragments.append(f"Description: {description.strip()}")

            context_string = repo_context.get("context_string")
            if isinstance(context_string, str) and context_string.strip():
                fragments.append(context_string.strip())

            fam = repo_context.get("facts_and_memories")
            if isinstance(fam, dict):
                facts = fam.get("facts") or []
                if isinstance(facts, list) and facts:
                    fragments.append(
                        "Key Facts:\n"
                        + "\n".join(f"- {str(fact).strip()}" for fact in facts[:3])
                    )
                highlights = fam.get("highlights") or []
                if isinstance(highlights, list) and highlights:
                    fragments.append(
                        "Highlights:\n"
                        + "\n".join(
                            f"- {str(highlight).strip()}"
                            for highlight in highlights[:3]
                        )
                    )

        return fragments

    async def build_combined_summary(self) -> Optional[str]:
        """Construct a repository summary sourced from cached GitIngest context."""

        cached_summary: Optional[str] = None

        repository = self._load_repository()
        if repository:
            cached = self.read_cache(CacheMetadata.from_dict(repository.github_context))
            if cached:
                cached_summary = self._format_cached_context(cached)

        if not cached_summary:
            cached = self.read_cache()
            if cached:
                cached_summary = self._format_cached_context(cached)

        if not cached_summary:
            latest_context = await self.ensure_github_context()
            if latest_context:
                cached_summary = self._format_cached_context(latest_context)

        if not cached_summary:
            if self.repo_owner and self.repo_name:
                cached_summary = f"Repository: {self.repo_owner}/{self.repo_name}"
            else:
                return None

        fragments = [cached_summary] + self._session_context_fragments()
        combined = "\n\n".join(fragment for fragment in fragments if fragment)

        # Persist combined summary back onto the session for downstream reuse.
        if self.session_obj is not None:
            repo_context = self.session_obj.repo_context
            if not isinstance(repo_context, dict):
                repo_context = {}
            repo_context["summary"] = combined
            repo_context["context_string"] = cached_summary
            self.session_obj.repo_context = repo_context
            try:
                self.db.commit()
            except Exception as exc:  # pragma: no cover - defensive commit
                self.logger.debug(
                    "Failed to persist session repo_context update: %s", exc
                )
                self.db.rollback()

        return combined

    async def gitingest_fallback(self) -> Optional[str]:
        """Expose legacy fallback hook for callers expecting a string summary."""

        context = await self.ensure_github_context()
        if not context:
            return None
        return self._format_cached_context(context)

    async def get_best_context_string(self) -> str:
        """Return the best textual representation of the repository context."""

        summary = await self.build_combined_summary()
        if summary:
            return summary
        return "Repository context unavailable"


__all__ = ["ChatContext"]
