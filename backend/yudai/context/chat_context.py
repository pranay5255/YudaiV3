"""Session-scoped repository context helpers.

The context builder intentionally avoids repository ingestion and semantic
search. Chat and issue generation receive only selected repository identity,
stored session metadata, context cards, recent conversation, probes, and user
answers.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from yudai.models import ChatMessage, ChatSession, ContextCard, Repository, UserQuestion
from sqlalchemy.orm import Session

from yudai.utils import utc_now

logger = logging.getLogger(__name__)


class ChatContext:
    """Build lightweight session context without repository indexing."""

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

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if not text:
            return ""
        compact = text.strip()
        if len(compact) <= limit:
            return compact
        return compact[: max(0, limit - 3)].rstrip() + "..."

    def _load_repository(self) -> Optional[Repository]:
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

    def _session(self) -> Optional[ChatSession]:
        if self.session_obj is not None:
            return self.session_obj
        if not self.session_id:
            return None
        return (
            self.db.query(ChatSession)
            .filter(
                ChatSession.session_id == self.session_id,
                ChatSession.user_id == self.user_id,
            )
            .first()
        )

    @staticmethod
    def _coerce_repo_context(raw_context: Any) -> Dict[str, Any]:
        if isinstance(raw_context, dict):
            return raw_context
        if isinstance(raw_context, str):
            try:
                parsed = json.loads(raw_context)
                return parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                return {}
        return {}

    def _repo_url(self, session: Optional[ChatSession]) -> Optional[str]:
        if self.repo_owner and self.repo_name:
            return f"https://github.com/{self.repo_owner}/{self.repo_name}"
        return getattr(session, "repo_url", None)

    def _repository_info(self, session: Optional[ChatSession]) -> Dict[str, Any]:
        repository = self._load_repository()

        owner = self.repo_owner or getattr(session, "repo_owner", None) or ""
        name = self.repo_name or getattr(session, "repo_name", None) or ""
        branch = getattr(session, "repo_branch", None) or (
            getattr(repository, "default_branch", None) if repository else None
        )
        repo_url = self._repo_url(session)

        return {
            "full_name": f"{owner}/{name}" if owner and name else "",
            "owner": owner,
            "name": name,
            "branch": branch or "main",
            "description": getattr(repository, "description", None)
            or getattr(session, "description", None)
            or "",
            "language": getattr(repository, "language", None) if repository else None,
            "html_url": getattr(repository, "html_url", None) or repo_url,
            "default_branch": branch or "main",
            "source": "session",
        }

    def _session_metadata_fragments(self, session: Optional[ChatSession]) -> List[str]:
        if session is None:
            return []

        fragments: List[str] = []
        if getattr(session, "title", None):
            fragments.append(f"Session title: {session.title}")
        if getattr(session, "description", None):
            fragments.append(f"Session description: {session.description}")

        repo_context = self._coerce_repo_context(getattr(session, "repo_context", None))
        for key, label in (
            ("summary", "Stored summary"),
            ("context_string", "Stored context"),
            ("description", "Stored description"),
        ):
            value = repo_context.get(key)
            if isinstance(value, str) and value.strip():
                fragments.append(f"{label}: {self._truncate(value, 700)}")

        snapshot = repo_context.get("session_snapshot")
        if isinstance(snapshot, dict):
            lines: List[str] = []
            trigger = snapshot.get("trigger")
            if isinstance(trigger, str) and trigger.strip():
                lines.append(f"- trigger: {trigger.strip().replace('_', ' ')}")
            github_refs = snapshot.get("github") or {}
            if isinstance(github_refs, dict):
                if github_refs.get("issue_number") is not None:
                    lines.append(f"- linked issue: #{github_refs['issue_number']}")
                if github_refs.get("pr_number") is not None:
                    lines.append(f"- linked PR: #{github_refs['pr_number']}")
            for item in (snapshot.get("messages") or [])[:3]:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "").strip()
                if text:
                    lines.append(
                        f"- {item.get('role', 'user')}: {self._truncate(text, 220)}"
                    )
            if lines:
                fragments.append("Session snapshot:\n" + "\n".join(lines))

        probe = repo_context.get("probe_context")
        if isinstance(probe, str) and probe.strip():
            fragments.append(f"Probe context: {self._truncate(probe, 700)}")

        return fragments

    def _recent_conversation_fragments(self, session: Optional[ChatSession]) -> List[str]:
        if session is None or not getattr(session, "id", None):
            return []

        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(8)
            .all()
        )
        if not messages:
            return []

        lines = []
        for message in reversed(messages):
            role = message.sender_type or message.role or "user"
            lines.append(f"- {role}: {self._truncate(message.message_text, 260)}")
        return ["Recent conversation:\n" + "\n".join(lines)]

    def _context_card_fragments(self, session: Optional[ChatSession]) -> List[str]:
        if session is None or not getattr(session, "id", None):
            return []

        cards = (
            self.db.query(ContextCard)
            .filter(ContextCard.session_id == session.id, ContextCard.is_active)
            .order_by(ContextCard.created_at.desc())
            .limit(8)
            .all()
        )
        if not cards:
            return []

        lines = []
        for card in reversed(cards):
            source = card.source or "chat"
            description = f": {self._truncate(card.description, 180)}" if card.description else ""
            content = self._truncate(card.content, 320)
            lines.append(f"- [{source}] {card.title}{description}\n  {content}")
        return ["Context cards:\n" + "\n".join(lines)]

    def _answered_question_fragments(self, session: Optional[ChatSession]) -> List[str]:
        if session is None or not getattr(session, "id", None):
            return []

        questions = (
            self.db.query(UserQuestion)
            .filter(
                UserQuestion.session_id == session.id,
                UserQuestion.answer_text.isnot(None),
            )
            .order_by(UserQuestion.answered_at.desc())
            .limit(5)
            .all()
        )
        if not questions:
            return []

        lines = []
        for question in reversed(questions):
            answer = str(question.answer_text or "").strip()
            if answer:
                lines.append(
                    f"- {self._truncate(question.question_text, 160)} -> "
                    f"{self._truncate(answer, 220)}"
                )
        return ["User answers:\n" + "\n".join(lines)] if lines else []

    async def ensure_github_context(self) -> Optional[Dict[str, Any]]:
        """Return selected repository identity and session-derived context."""

        if not self.repo_owner and not self.repo_name:
            return None

        session = self._session()
        summary = await self.build_combined_summary(persist=False)
        return {
            "repository": self._repository_info(session),
            "summary": summary or "",
            "context_string": summary or "",
            "recent_commits": [],
            "recent_issues": [],
            "branches": [],
            "source": "session",
            "generated_at": utc_now().isoformat(),
        }

    async def build_combined_summary(self, *, persist: bool = True) -> Optional[str]:
        """Construct a concise context string from session-owned data."""

        session = self._session()
        repo_info = self._repository_info(session)

        fragments: List[str] = []
        full_name = repo_info.get("full_name")
        if full_name:
            fragments.append(f"Repository: {full_name}")
        if repo_info.get("branch"):
            fragments.append(f"Branch: {repo_info['branch']}")
        if repo_info.get("description"):
            fragments.append(f"Description: {repo_info['description']}")
        if repo_info.get("language"):
            fragments.append(f"Language: {repo_info['language']}")

        fragments.extend(self._session_metadata_fragments(session))
        fragments.extend(self._context_card_fragments(session))
        fragments.extend(self._recent_conversation_fragments(session))
        fragments.extend(self._answered_question_fragments(session))

        combined = "\n\n".join(fragment for fragment in fragments if fragment).strip()
        if not combined:
            return None
        combined = self._truncate(combined, self.MAX_CONTEXT_STRING_LENGTH)

        if persist and session is not None:
            repo_context = self._coerce_repo_context(getattr(session, "repo_context", None))
            repo_context["summary"] = combined
            repo_context["context_string"] = combined
            repo_context["source"] = "session"
            session.repo_context = repo_context
            try:
                self.db.commit()
            except Exception as exc:  # pragma: no cover - defensive commit
                self.logger.debug(
                    "Failed to persist session repo_context update: %s", exc
                )
                self.db.rollback()

        return combined

    async def get_best_context_string(self) -> str:
        summary = await self.build_combined_summary()
        if summary:
            return summary
        if self.repo_owner and self.repo_name:
            return f"Repository: {self.repo_owner}/{self.repo_name}"
        return "Repository context unavailable"

    @staticmethod
    async def ensure_github_context_async(
        db: Session,
        user_id: int,
        session_obj,
        repo_owner: str,
        repo_name: str,
    ) -> Optional[dict]:
        context = ChatContext(
            db=db,
            user_id=user_id,
            repo_owner=repo_owner,
            repo_name=repo_name,
            session_obj=session_obj,
        )
        return await context.ensure_github_context()

    @staticmethod
    async def get_best_repo_context_string(
        db: Session,
        user_id: int,
        session_id: str,
        repo_owner: str,
        repo_name: str,
    ) -> str:
        context = ChatContext(
            db=db,
            user_id=user_id,
            repo_owner=repo_owner,
            repo_name=repo_name,
            session_id=session_id,
        )
        return await context.get_best_context_string()


__all__ = ["ChatContext"]
