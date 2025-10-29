"""Repository context utilities covering snapshots, embeddings, and facts & memories."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence

from backend.daifuUserAgent.llm_service import LLMService
from backend.repo_processorGitIngest.scraper_script import (
    categorize_file,
    extract_repository_data,
)
from backend.utils.chunking import create_file_chunker

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Repository snapshot utilities
# ---------------------------------------------------------------------------


@dataclass
class RepositoryFile:
    """Normalized representation of a file returned by GitIngest."""

    path: str
    content: str
    size: int
    content_size: int
    category: Optional[str]

    @property
    def file_name(self) -> str:
        return self.path.split("/")[-1] if self.path else ""

    def to_payload(self) -> Dict[str, Any]:
        """Return structure compatible with legacy `_process_gitingest_data`."""
        return {
            "path": self.path,
            "content": self.content,
            "size": self.size,
            "content_size": self.content_size,
            "type": self.category,
        }


@dataclass
class RepositorySnapshot:
    """Container for raw GitIngest data and normalized files."""

    files: List[RepositoryFile]
    raw_response: Dict[str, Any]

    def as_processed_payload(self) -> Dict[str, Any]:
        return {"files": [f.to_payload() for f in self.files]}

    def content_lookup(self) -> Dict[str, str]:
        return {f.path: f.content for f in self.files if f.content}


class RepositorySnapshotService:
    """Service to orchestrate GitIngest extraction and normalization."""

    @staticmethod
    async def fetch(
        repo_url: str,
        max_file_size: Optional[int] = None,
    ) -> RepositorySnapshot:
        raw_repo_data = await extract_repository_data(
            repo_url=repo_url, max_file_size=max_file_size
        )

        if not isinstance(raw_repo_data, dict):
            raise ValueError("Unexpected GitIngest payload format")

        if raw_repo_data.get("error"):
            raise ValueError(raw_repo_data["error"])

        files = RepositorySnapshotService._normalize_files(raw_repo_data)
        return RepositorySnapshot(files=files, raw_response=raw_repo_data)

    @staticmethod
    def _normalize_files(raw_repo_data: Dict[str, Any]) -> List[RepositoryFile]:
        files: List[RepositoryFile] = []
        for file_data in raw_repo_data.get("files", []):
            path = file_data.get("path", "")
            content = file_data.get("content", "") or ""
            size = int(file_data.get("size") or len(content))
            content_size = int(file_data.get("content_size") or len(content))

            category, include_type = categorize_file(path)
            if include_type == "exclude":
                continue

            files.append(
                RepositoryFile(
                    path=path,
                    content=content,
                    size=size,
                    content_size=content_size,
                    category=category,
                )
            )

        return files

    @staticmethod
    def build_directory_index(files: List[RepositoryFile]) -> Dict[str, Dict[str, Any]]:
        """Build nested dictionary representing directory hierarchy."""
        root: Dict[str, Any] = {}
        for repo_file in files:
            segments = [seg for seg in repo_file.path.split("/") if seg]
            cursor = root
            for segment in segments[:-1]:
                cursor = cursor.setdefault(segment, {"__files__": []})
            cursor.setdefault("__files__", []).append(repo_file)
        return root


# ---------------------------------------------------------------------------
# Embedding utilities
# ---------------------------------------------------------------------------


@dataclass
class EmbeddingChunk:
    """Represents a single chunk and its embedding."""

    file_path: str
    file_name: str
    chunk_index: int
    chunk_text: str
    embedding: List[float]
    tokens: int
    metadata: Dict[str, Optional[str]]


class EmbeddingPipeline:
    """Simple text embedding pipeline using the shared chunker & LLM service."""

    def __init__(
        self,
        max_chunk_size: int = 1000,
        overlap: int = 100,
    ) -> None:
        self._chunker = create_file_chunker(
            max_chunk_size=max_chunk_size, overlap=overlap
        )

    def process_file(self, repo_file: RepositoryFile) -> List[EmbeddingChunk]:
        """Chunk and embed a single repository file."""
        chunks = self._chunker.chunk_file(repo_file.path, repo_file.content)
        embeddings: List[EmbeddingChunk] = []

        for chunk in chunks:
            chunk_text = chunk["chunk_text"]
            embedding_vector = LLMService.embed_text(chunk_text)
            embeddings.append(
                EmbeddingChunk(
                    file_path=repo_file.path,
                    file_name=repo_file.file_name,
                    chunk_index=chunk["chunk_index"],
                    chunk_text=chunk_text,
                    embedding=embedding_vector,
                    tokens=chunk.get("tokens", 0),
                    metadata={
                        "file_type": chunk.get("file_type"),
                        "chunk_size": str(chunk.get("chunk_size")),
                        "is_complete": str(chunk.get("is_complete")),
                    },
                )
            )

        return embeddings

    def process_many(self, files: Iterable[RepositoryFile]) -> List[EmbeddingChunk]:
        """Chunk and embed a collection of repository files."""
        all_chunks: List[EmbeddingChunk] = []
        for repo_file in files:
            all_chunks.extend(self.process_file(repo_file))
        return all_chunks


# ---------------------------------------------------------------------------
# Facts & memories orchestration
# ---------------------------------------------------------------------------


@dataclass
class FactsAndMemoriesResult:
    """Structured result from the Facts & Memories generator."""

    facts: List[str] = field(default_factory=list)
    memories: List[str] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)
    raw_response: Optional[str] = None


class FactsAndMemoriesService:
    """Generates high-signal repository facts and conversational memories."""

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model

    async def generate(
        self,
        snapshot: RepositorySnapshot,
        conversation: Optional[Sequence[Dict[str, Any]]] = None,
        max_messages: int = 10,
    ) -> FactsAndMemoriesResult:
        prompt = self._build_prompt(snapshot, conversation, max_messages=max_messages)
        response = await LLMService.generate_response(
            prompt,
            model=self.model,
            temperature=0.2,
            max_tokens=1500,
        )
        return self._parse_response(response)

    def _build_prompt(
        self,
        snapshot: RepositorySnapshot,
        conversation: Optional[Sequence[Dict[str, Any]]],
        max_messages: int,
    ) -> str:
        summary = snapshot.raw_response.get("raw_response", {}).get(
            "summary", "No summary available."
        )
        tree = snapshot.raw_response.get("raw_response", {}).get("tree", "")
        files_preview = self._render_top_files(snapshot.files)
        convo_preview = self._render_conversation(
            conversation, max_messages=max_messages
        )

        prompt = f"""
You are an analytical assistant. Convert the repository information and recent chat into two buckets: FACTS (grounded, file-backed statements) and MEMORIES (useful conversation takeaways). Output valid JSON with keys "facts", "memories", and "highlights".

## Repository Summary
{summary}

## Repository Structure Snippet
{tree[:1200]}

## Key Files
{files_preview}

## Recent Conversation
{convo_preview}

## Instructions
- Use bullet-point style sentences.
- Facts MUST cite specific files when possible.
- Memories should capture goals or unresolved threads from the chat.
- Highlights can include noteworthy files or TODOs worth surfacing.
- Respond ONLY with JSON.
"""
        return prompt.strip()

    @staticmethod
    def _render_top_files(files: Iterable[RepositoryFile], limit: int = 10) -> str:
        items = []
        for repo_file in list(files)[:limit]:
            items.append(f"- {repo_file.path} (chars: {len(repo_file.content)})")
        return "\n".join(items) if items else "- No files returned"

    @staticmethod
    def _render_conversation(
        conversation: Optional[Sequence[Dict[str, Any]]],
        max_messages: int,
    ) -> str:
        if not conversation:
            return "- No prior conversation"

        recent = conversation[-max_messages:]
        lines = []
        for message in recent:
            author = (
                message.get("author")
                or message.get("sender")
                or message.get("role")
                or "user"
            )
            text = (message.get("text") or message.get("content") or "").strip()
            text = text.replace("\n", " ")
            if len(text) > 240:
                text = f"{text[:237]}..."
            lines.append(f"- {author}: {text}")
        return "\n".join(lines)

    @staticmethod
    def _parse_response(response: str) -> FactsAndMemoriesResult:
        try:
            data = json.loads(response)
            return FactsAndMemoriesResult(
                facts=list(data.get("facts", [])),
                memories=list(data.get("memories", [])),
                highlights=list(data.get("highlights", [])),
                raw_response=response,
            )
        except json.JSONDecodeError as exc:
            logger.warning("Facts & Memories JSON parsing failed: %s", exc)
            # Fallback: treat plain text as single highlight
            return FactsAndMemoriesResult(
                highlights=[response.strip()],
                raw_response=response,
            )
