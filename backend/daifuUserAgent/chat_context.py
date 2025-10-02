"""Utilities for consolidating chat-specific repository context management.

This module exposes the :class:`ChatContext` helper which unifies the logic for
collecting repository context, caching it to disk, hydrating summaries from the
cache, and falling back to GitIngest summaries when GitHub lookups fail.

The helper is intentionally focused on the chat surface area so that context is
materialised during the chat endpoint call before dispatching a request to the
LLM.  Centralising the behaviour in this class keeps the caching discipline and
back-end updates consistent across the codebase.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models import ChatSession, Repository
from utils import utc_now

logger = logging.getLogger(__name__)


@dataclass
class CacheMetadata:
    """Lightweight metadata persisted alongside cached GitHub context."""

    cache_path: str
    owner: str
    name: str
    session_id: str
    user_id: int
    size: Optional[int] = None
    sha256: Optional[str] = None
    cached_at: Optional[str] = None
    version: int = 1

    @classmethod
    def from_dict(cls, payload: Optional[Dict[str, Any]]) -> Optional["CacheMetadata"]:
        if not payload or not isinstance(payload, dict):
            return None
        try:
            return cls(
                cache_path=payload["cache_path"],
                owner=payload["owner"],
                name=payload["name"],
                session_id=payload.get("session_id", ""),
                user_id=int(payload.get("user_id", 0)),
                size=payload.get("size"),
                sha256=payload.get("sha256"),
                cached_at=payload.get("cached_at"),
                version=int(payload.get("version", 1)),
            )
        except KeyError:
            logger.debug("Cache metadata payload missing required fields: %s", payload)
            return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cache_path": self.cache_path,
            "owner": self.owner,
            "name": self.name,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "size": self.size,
            "sha256": self.sha256,
            "cached_at": self.cached_at,
            "version": self.version,
        }


class ChatContext:
    """Central coordinator for fetching and caching repository context.

    The helper encapsulates all intermediate steps required for obtaining
    repository metadata (GitHub API, GitIngest scrape, cached JSON) and ensures
    the resulting information is cached in ``/tmp/github_context_cache``.  The
    cache is intentionally kept outside of the database so we only persist a
    tiny metadata pointer on the ``Repository`` row.

    Each public method is safe to call during the chat endpoint request cycle
    and will update the backing store (database metadata and/or cache files) as
    needed.  Downstream callers only need to work with high-level summaries.
    """

    CACHE_ROOT = Path("/tmp/github_context_cache")
    CACHE_TTL_SECONDS = 86400  # 24 hours

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
        self.repo_owner = repo_owner or ""
        self.repo_name = repo_name or ""
        self.session_obj = session_obj
        self.session_id = session_id or getattr(session_obj, "session_id", "") or "session"
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

        target_dir = self.CACHE_ROOT / self._safe_component(self.user_id) / self._safe_component(self.session_id)
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
            version=1,
        )

    def write_cache(self, data: Dict[str, Any]) -> CacheMetadata:
        """Persist GitHub context JSON to disk and return metadata."""

        path = self.cache_path()
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        return self._compute_cache_metadata(path)

    def read_cache(self, meta: Optional[CacheMetadata] = None) -> Optional[Dict[str, Any]]:
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
            self.logger.warning("Failed to read cached context from %s: %s", candidate_path, exc)
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
    # GitHub context collection
    # ------------------------------------------------------------------
    async def _fetch_comprehensive_github_context(self) -> Dict[str, Any]:
        """Fetch rich repository context via GitHubOps."""

        from .githubOps import GitHubOps

        github_ops = GitHubOps(self.db)
        repo_owner = self.repo_owner
        repo_name = self.repo_name
        user_id = self.user_id

        repo_data = await github_ops.fetch_repository_info_detailed(repo_owner, repo_name, user_id)
        branches = await github_ops.fetch_repository_branches(repo_owner, repo_name, user_id)
        contributors = await github_ops.fetch_repository_contributors(repo_owner, repo_name, user_id, limit=10)
        issues_data = await github_ops.fetch_repository_issues(repo_owner, repo_name, user_id, limit=5)
        commits_data = await github_ops.fetch_repository_commits(repo_owner, repo_name, user_id, limit=5)

        basic_info = await github_ops.fetch_repository_info(repo_owner, repo_name, user_id)

        return {
            "repository": repo_data,
            "branches": branches,
            "contributors": contributors,
            "recent_issues": issues_data,
            "recent_commits": commits_data,
            "context_string": self._build_context_string(basic_info or {}, issues_data or [], commits_data or []),
            "fetched_at": utc_now().isoformat(),
            "owner": repo_owner,
            "name": repo_name,
        }

    @staticmethod
    def _build_context_string(
        repo_info: Dict[str, Any], issues: List[Dict[str, Any]], commits: List[Dict[str, Any]]
    ) -> str:
        """Produce a concise textual summary from GitHub metadata."""

        parts: List[str] = []

        if repo_info.get("name"):
            owner_login = (
                repo_info.get("owner", {}).get("login") if isinstance(repo_info.get("owner"), dict) else None
            )
            full_name = repo_info.get("full_name") or (
                f"{owner_login}/{repo_info['name']}" if owner_login and repo_info.get("name") else repo_info.get("name")
            )
            parts.append(f"Repository: {full_name}")
            if repo_info.get("description"):
                parts.append(f"Description: {repo_info['description']}")
            if repo_info.get("language"):
                parts.append(f"Language: {repo_info['language']}")
            topics = repo_info.get("topics") or []
            if isinstance(topics, list) and topics:
                parts.append(f"Topics: {', '.join(topics[:5])}")

        if issues:
            parts.append(f"\nRecent Issues ({len(issues)}):")
            for issue in issues[:3]:
                if isinstance(issue, dict):
                    parts.append(f"- #{issue.get('number')}: {issue.get('title')}")

        if commits:
            parts.append(f"\nRecent Commits ({len(commits)}):")
            for commit in commits[:3]:
                sha = commit.get("sha") or commit.get("id")
                message = commit.get("message") or commit.get("commit", {}).get("message")
                if sha and message:
                    parts.append(f"- {sha}: {message}")

        return "\n".join(parts) if parts else "Repository context not available"

    async def ensure_github_context(self) -> Optional[Dict[str, Any]]:
        """Ensure cached GitHub context is available and up to date."""

        if not self.repo_owner or not self.repo_name:
            return None

        repository = self._load_repository()
        existing_meta = CacheMetadata.from_dict(getattr(repository, "github_context", None)) if repository else None
        updated_at = getattr(repository, "github_context_updated_at", None) if repository else None

        if existing_meta and updated_at:
            age_seconds = (utc_now() - updated_at).total_seconds()
            if age_seconds < self.CACHE_TTL_SECONDS:
                cached = self.read_cache(existing_meta)
                if cached:
                    return cached
            else:
                self.logger.info(
                    "Cached GitHub context for %s/%s is stale (%ds old); refreshing",
                    self.repo_owner,
                    self.repo_name,
                    int(age_seconds),
                )

        try:
            fetched_context = await self._fetch_comprehensive_github_context()
        except Exception as exc:
            self.logger.warning(
                "Failed to fetch GitHub context for %s/%s: %s", self.repo_owner, self.repo_name, exc
            )
            return None

        cache_meta = self.write_cache(fetched_context)

        if repository is None:
            repository = Repository(
                user_id=self.user_id,
                owner=self.repo_owner,
                name=self.repo_name,
                full_name=f"{self.repo_owner}/{self.repo_name}",
                repo_url=f"https://github.com/{self.repo_owner}/{self.repo_name}",
                html_url=f"https://github.com/{self.repo_owner}/{self.repo_name}",
                clone_url=f"https://github.com/{self.repo_owner}/{self.repo_name}.git",
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
    def _format_cached_context(self, cached: Dict[str, Any]) -> str:
        """Format cached GitHub context JSON into a summary string."""

        parts: List[str] = []
        repo_info = cached.get("repository", {}) if isinstance(cached, dict) else {}
        if repo_info:
            owner_login = repo_info.get("owner", {}).get("login") if isinstance(repo_info.get("owner"), dict) else None
            full_name = repo_info.get("full_name") or (
                f"{owner_login}/{repo_info.get('name')}" if owner_login and repo_info.get("name") else repo_info.get("name")
            )
            if full_name:
                parts.append(f"Repository: {full_name}")
            description = repo_info.get("description")
            if description:
                parts.append(f"Description: {description}")
            language = repo_info.get("language")
            if language:
                parts.append(f"Language: {language}")

        issues = cached.get("recent_issues") or cached.get("issues") or []
        if isinstance(issues, list) and issues:
            parts.append("\nRecent Open Issues:")
            for issue in issues[:3]:
                if isinstance(issue, dict):
                    number = issue.get("number", "N/A")
                    title = issue.get("title", "No title")
                    parts.append(f"- #{number}: {title}")

        commits = cached.get("recent_commits") or cached.get("commits") or []
        if isinstance(commits, list) and commits:
            parts.append("\nRecent Commits:")
            for commit in commits[:3]:
                message = commit.get("commit", {}).get("message") or commit.get("message") or "No message"
                author = (
                    commit.get("commit", {}).get("author", {}).get("name")
                    or commit.get("author", {}).get("login")
                    or "Unknown"
                )
                parts.append(f"- {message[:100]}... (by {author})")

        return "\n".join(parts) if parts else "Repository context available"

    async def gitingest_fallback(self) -> Optional[str]:
        """Use GitIngest scraper to generate a repository summary."""

        try:
            from .repo_processorGitIngest.scraper_script import extract_repository_data
        except Exception as exc:  # pragma: no cover - optional dependency failures
            self.logger.debug("GitIngest import failed: %s", exc)
            return None

        repo_url = f"https://github.com/{self.repo_owner}/{self.repo_name}"
        try:
            repo_data = await extract_repository_data(repo_url)
        except Exception as exc:  # pragma: no cover - network errors
            self.logger.debug("GitIngest scrape failed for %s: %s", repo_url, exc)
            return None

        if not repo_data or "raw_response" not in repo_data:
            return None

        parts: List[str] = [f"Repository: {self.repo_owner}/{self.repo_name}"]
        raw_response = repo_data.get("raw_response", {})

        summary = raw_response.get("summary", "")
        if summary:
            parts.append(f"Summary: {summary[:500]}...")

        tree = raw_response.get("tree", "")
        if tree:
            lines = tree.strip().split("\n")
            dirs = [line for line in lines if line.strip().endswith("/")]
            if dirs:
                parts.append(f"\nDirectory Structure ({len(dirs)} directories):")
                for dir_name in dirs[:10]:
                    parts.append(f"- {dir_name.strip()}")

        return "\n".join(parts)

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

            description = repo_context.get("description") or getattr(self.session_obj, "description", None)
            if isinstance(description, str) and description.strip():
                fragments.append(f"Description: {description.strip()}")

            context_string = repo_context.get("context_string")
            if isinstance(context_string, str) and context_string.strip():
                fragments.append(context_string.strip())

            fam = repo_context.get("facts_and_memories")
            if isinstance(fam, dict):
                facts = fam.get("facts") or []
                if isinstance(facts, list) and facts:
                    fragments.append("Key Facts:\n" + "\n".join(f"- {str(fact).strip()}" for fact in facts[:3]))
                highlights = fam.get("highlights") or []
                if isinstance(highlights, list) and highlights:
                    fragments.append(
                        "Highlights:\n" + "\n".join(f"- {str(highlight).strip()}" for highlight in highlights[:3])
                    )

        return fragments

    async def build_combined_summary(self) -> Optional[str]:
        """Construct a fallback repository summary sourced from cached context."""

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
            cached_summary = await self.gitingest_fallback()

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
                self.logger.debug("Failed to persist session repo_context update: %s", exc)
                self.db.rollback()

        return combined

    async def get_best_context_string(self) -> str:
        """Return the best textual representation of the repository context."""

        summary = await self.build_combined_summary()
        if summary:
            return summary
        return "Repository context unavailable"


__all__ = ["ChatContext", "CacheMetadata"]
