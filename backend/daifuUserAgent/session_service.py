#!/usr/bin/env python3
"""
SessionService - Centralized Session Management Service

This module provides all session-related business logic and operations,
extracted from the router handlers for better separation of concerns.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from models import (
    ChatMessage,
    ChatMessageResponse,
    ChatSession,
    ContextCard,
    ContextCardResponse,
    FileEmbedding,
    FileEmbeddingResponse,
    FileItem,
    SessionContextResponse,
    SessionResponse,
)
from sqlalchemy.orm import Session

from utils import ensure_utc, utc_now

logger = logging.getLogger(__name__)


class SessionService:
    """
    Centralized service for session management operations.

    Provides business logic for:
    - Session ownership validation
    - Context retrieval
    - Message management
    - Statistics and analytics
    """

    @staticmethod
    def ensure_owned_session(db: Session, user_id: int, session_id: str) -> ChatSession:
        """
        Ensure session exists and belongs to the user.

        Args:
            db: Database session
            user_id: User ID
            session_id: Session ID to validate

        Returns:
            ChatSession: The validated session

        Raises:
            HTTPException: If session not found or access denied
        """
        db_session = (
            db.query(ChatSession)
            .filter(ChatSession.session_id == session_id, ChatSession.user_id == user_id)
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied"
            )

        return db_session

    @staticmethod
    def get_context(db: Session, db_session: ChatSession) -> SessionContextResponse:
        """
        Get complete session context including messages, context cards, and file embeddings.

        Args:
            db: Database session
            db_session: The ChatSession object

        Returns:
            SessionContextResponse: Complete session context
        """
        # Get session messages
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == db_session.id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )

        # Get context cards for this session
        context_cards = (
            db.query(ContextCard)
            .filter(ContextCard.session_id == db_session.id, ContextCard.is_active)
            .all()
        )

        # Get file embeddings for this session
        file_embeddings = (
            db.query(FileEmbedding)
            .filter(FileEmbedding.session_id == db_session.id)
            .all()
        )

        # Convert to response models
        session_response = SessionResponse(
            id=db_session.id,
            session_id=db_session.session_id,
            title=db_session.title,
            description=db_session.description,
            repo_owner=db_session.repo_owner,
            repo_name=db_session.repo_name,
            repo_branch=db_session.repo_branch,
            repo_url=db_session.repo_url,
            repo_context=db_session.repo_context,
            runtime_workspace_path=db_session.runtime_workspace_path,
            is_active=db_session.is_active,
            total_messages=db_session.total_messages,
            total_tokens=db_session.total_tokens,
            current_mode=db_session.current_mode,
            mode_status=db_session.mode_status,
            mode_updated_at=db_session.mode_updated_at,
            architect_issue_url=db_session.architect_issue_url,
            architect_issue_number=db_session.architect_issue_number,
            architect_completed_at=db_session.architect_completed_at,
            tester_status=db_session.tester_status,
            tester_completed_at=db_session.tester_completed_at,
            coder_pr_url=db_session.coder_pr_url,
            coder_pr_number=db_session.coder_pr_number,
            coder_completed_at=db_session.coder_completed_at,
            workflow_completed_at=db_session.workflow_completed_at,
            mode_metadata=db_session.mode_metadata,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
            last_activity=db_session.last_activity,
            generate_embeddings=db_session.generate_embeddings,
            generate_facts_memories=db_session.generate_facts_memories,
        )

        message_responses = [
            ChatMessageResponse(
                id=msg.id,
                message_id=msg.message_id,
                message_text=msg.message_text,
                sender_type=msg.sender_type,
                role=msg.role,
                is_code=msg.is_code,
                tokens=msg.tokens,
                model_used=msg.model_used,
                processing_time=msg.processing_time,
                context_cards=msg.context_cards,
                referenced_files=msg.referenced_files,
                error_message=msg.error_message,
                actions=msg.actions,
                created_at=msg.created_at,
                updated_at=msg.updated_at,
            )
            for msg in messages
        ]

        context_card_responses = [
            ContextCardResponse(
                id=card.id,
                session_id=card.session_id,
                title=card.title,
                description=card.description,
                content=card.content,
                source=card.source,
                tokens=card.tokens,
                is_active=card.is_active,
                created_at=card.created_at,
                updated_at=card.updated_at,
            )
            for card in context_cards
        ]

        file_embedding_responses = [
            FileEmbeddingResponse(
                id=fe.id,
                session_id=fe.session_id,
                repository_id=fe.repository_id,
                file_path=fe.file_path,
                file_name=fe.file_name,
                file_type=fe.file_type,
                chunk_index=fe.chunk_index,
                tokens=fe.tokens,
                file_metadata=fe.file_metadata,
                created_at=fe.created_at,
            )
            for fe in file_embeddings
        ]

        context_response = SessionContextResponse(
            session=session_response,
            messages=message_responses,
            context_cards=context_card_responses,
            repository_info={
                "owner": db_session.repo_owner,
                "name": db_session.repo_name,
                "branch": db_session.repo_branch,
                "full_name": f"{db_session.repo_owner}/{db_session.repo_name}",
                "html_url": f"https://github.com/{db_session.repo_owner}/{db_session.repo_name}",
            }
            if db_session.repo_owner and db_session.repo_name
            else None,
            file_embeddings_count=len(file_embeddings),
            statistics={
                "total_messages": db_session.total_messages,
                "total_tokens": db_session.total_tokens,
                # Normalize naive datetime from SQLite to UTC before subtraction
                "session_duration": int(
                    (utc_now() - ensure_utc(db_session.created_at)).total_seconds()
                )
                if db_session.created_at
                else 0,
            },
            user_issues=[],
            file_embeddings=file_embedding_responses,
        )

        return context_response

    @staticmethod
    def get_session_messages(
        db: Session, session_id: int, limit: int = 100
    ) -> List[ChatMessageResponse]:
        """
        Get chat messages for a session.

        Args:
            db: Database session
            session_id: Internal session ID
            limit: Maximum number of messages to return

        Returns:
            List of ChatMessageResponse objects
        """
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )

        return [
            ChatMessageResponse(
                id=msg.id,
                message_id=msg.message_id,
                message_text=msg.message_text,
                sender_type=msg.sender_type,
                role=msg.role,
                is_code=msg.is_code,
                tokens=msg.tokens,
                model_used=msg.model_used,
                processing_time=msg.processing_time,
                context_cards=msg.context_cards,
                referenced_files=msg.referenced_files,
                error_message=msg.error_message,
                actions=msg.actions,
                created_at=msg.created_at,
                updated_at=msg.updated_at,
            )
            for msg in messages
        ]

    @staticmethod
    def get_session_statistics(db: Session, db_session: ChatSession) -> dict:
        """
        Get comprehensive statistics for a session.

        Args:
            db: Database session
            db_session: The ChatSession object

        Returns:
            Dictionary with session statistics
        """
        from sqlalchemy import func

        # Get message statistics
        message_stats = db.query(
            ChatMessage.sender_type,
            func.count(ChatMessage.id).label('count'),
            func.sum(ChatMessage.tokens).label('total_tokens'),
            func.avg(ChatMessage.processing_time).label('avg_processing_time')
        ).filter(ChatMessage.session_id == db_session.id).group_by(ChatMessage.sender_type).all()

        # Get context card count
        context_card_count = db.query(func.count(ContextCard.id)).filter(
            ContextCard.session_id == db_session.id,
            ContextCard.is_active
        ).scalar()

        # Get file embedding statistics
        file_stats = db.query(
            func.count(FileEmbedding.id).label('total_files'),
            func.sum(FileEmbedding.tokens).label('total_file_tokens'),
            func.count(func.distinct(FileEmbedding.file_path)).label('unique_files')
        ).filter(FileEmbedding.session_id == db_session.id).first()

        # Calculate session duration
        session_duration = None
        if db_session.created_at and db_session.last_activity:
            session_duration = int((db_session.last_activity - db_session.created_at).total_seconds())

        # Build statistics response
        stats = {
            "session_id": db_session.session_id,
            "basic_stats": {
                "total_messages": db_session.total_messages,
                "total_tokens": db_session.total_tokens,
                "total_context_cards": context_card_count,
                "total_file_embeddings": file_stats.total_files or 0,
                "unique_files": file_stats.unique_files or 0,
                "total_file_tokens": file_stats.total_file_tokens or 0,
                "session_duration_seconds": session_duration,
                "is_active": db_session.is_active,
            },
            "message_breakdown": {
                sender_type: {
                    "count": count,
                    "total_tokens": total_tokens or 0,
                    "avg_processing_time": float(avg_processing_time) if avg_processing_time else None
                }
                for sender_type, count, total_tokens, avg_processing_time in message_stats
            },
            "timestamps": {
                "created_at": db_session.created_at.isoformat() if db_session.created_at else None,
                "last_activity": db_session.last_activity.isoformat() if db_session.last_activity else None,
                "updated_at": db_session.updated_at.isoformat() if db_session.updated_at else None,
            },
            "repository_info": {
                "owner": db_session.repo_owner,
                "name": db_session.repo_name,
                "branch": db_session.repo_branch,
                "full_name": f"{db_session.repo_owner}/{db_session.repo_name}" if db_session.repo_owner and db_session.repo_name else None,
            } if db_session.repo_owner else None,
        }

        return stats


class FileDepsService:
    """
    Service for file dependency operations.
    """

    @staticmethod
    def list_for_session(db: Session, db_session: ChatSession) -> List[dict]:
        """
        List file dependencies for a session.

        Args:
            db: Database session
            db_session: The ChatSession object

        Returns:
            List of file dependency dictionaries
        """
        # Get file items for this session (new approach)
        file_items = (
            db.query(FileItem)
            .filter(FileItem.session_id == db_session.id)
            .order_by(FileItem.created_at.desc())
            .all()
        )

        # Convert to response format
        return [
            {
                "id": item.id,
                "name": item.name,
                "path": item.path,
                "type": item.type,
                "tokens": item.tokens,
                "category": item.category,
                "is_directory": item.is_directory,
                "content_size": item.content_size,
                "created_at": item.created_at,
                "file_name": item.file_name,
                "file_path": item.file_path,
                "file_type": item.file_type,
                "content_summary": item.content_summary,
            }
            for item in file_items
        ]

    @staticmethod
    def get_file_items_for_session(db: Session, db_session: ChatSession) -> List[dict]:
        """
        Get file items for a session (for frontend display).

        Args:
            db: Database session
            db_session: The ChatSession object

        Returns:
            List of file item dictionaries
        """
        return FileDepsService.list_for_session(db, db_session)


class MemoryService:
    """
    Manages the three-tier memory taxonomy for session chat.

    Memory types (from the Google whitepaper / OpenClaw model):
      Semantic  → stable facts about the repo   → ``facts`` list
      Episodic  → conversational takeaways       → ``memories`` list + session snapshot
      Procedural→ (future) learned workflows

    Four mechanisms:
      M1  Bootstrap loading   – ``get_memories`` / ``get_bootstrap_context``
      M2  Accumulation        – ``accumulate`` (prefix-fingerprint dedup)
      M3  Session snapshot    – ``save_session_snapshot`` / ``get_session_snapshot``
      M4  "Remember this"     – driven by ``ChatSession.generate_facts_memories``
    """

    MAX_FACTS = 30
    MAX_MEMORIES = 20
    MAX_HIGHLIGHTS = 15
    SNAPSHOT_MESSAGE_LIMIT = 15

    # ------------------------------------------------------------------
    # M1 — Bootstrap loading
    # ------------------------------------------------------------------

    @staticmethod
    def get_memories(db_session: ChatSession) -> Dict[str, Any]:
        """Retrieve all stored memories for a session.

        Returns a structured dict suitable for both API responses and LLM
        context injection.
        """
        repo_context = MemoryService._ensure_dict(db_session.repo_context)
        stored = repo_context.get("facts_and_memories", {})
        if not isinstance(stored, dict):
            stored = {}
        return {
            "facts": stored.get("facts", []),
            "memories": stored.get("memories", []),
            "highlights": stored.get("highlights", []),
            "generated_at": stored.get("generated_at"),
            "snapshot": MemoryService.get_session_snapshot(db_session),
        }

    # ------------------------------------------------------------------
    # M2 — Accumulation / consolidation (deterministic safety net)
    # ------------------------------------------------------------------

    @staticmethod
    def accumulate(
        existing: Dict[str, Any],
        new_facts: List[str],
        new_memories: List[str],
        new_highlights: List[str],
    ) -> Dict[str, Any]:
        """Merge new F&M into existing without duplication.

        Uses a 60-char prefix fingerprint to detect near-duplicates.
        When entries collide the *new* entry wins — this handles preference
        updates ("I switched from dark to light mode").
        The list is capped at ``MAX_*`` to bound storage growth.
        """

        def _merge(old: List[str], new: List[str], cap: int) -> List[str]:
            result = list(old)
            for item in new:
                fingerprint = item[:60].lower().strip()
                collision_idx = next(
                    (i for i, e in enumerate(result) if e[:60].lower().strip() == fingerprint),
                    None,
                )
                if collision_idx is not None:
                    result[collision_idx] = item
                else:
                    result.append(item)
            return result[-cap:]

        return {
            "facts": _merge(existing.get("facts", []), new_facts, MemoryService.MAX_FACTS),
            "memories": _merge(existing.get("memories", []), new_memories, MemoryService.MAX_MEMORIES),
            "highlights": _merge(existing.get("highlights", []), new_highlights, MemoryService.MAX_HIGHLIGHTS),
        }

    # ------------------------------------------------------------------
    # M3 — Session snapshot
    # ------------------------------------------------------------------

    @staticmethod
    def save_session_snapshot(
        db: Session, db_session: ChatSession, max_messages: int = 15,
    ) -> Optional[Dict[str, Any]]:
        """Capture the last *N* meaningful messages as a session snapshot.

        Fires when a session is deactivated (``is_active`` set to False).
        Filters out very short messages and system noise so the snapshot
        contains only the substantive conversation — the same pattern as
        OpenClaw's ``/new`` hook.

        The snapshot is persisted in ``session.repo_context["session_snapshot"]``.
        """
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == db_session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(max_messages * 2)
            .all()
        )
        messages.reverse()

        meaningful = [
            msg for msg in messages
            if msg.sender_type in ("user", "assistant")
            and msg.message_text
            and len(msg.message_text.strip()) > 10
        ][:max_messages]

        if not meaningful:
            return None

        snapshot: Dict[str, Any] = {
            "messages": [
                {"role": msg.sender_type, "text": msg.message_text.strip()}
                for msg in meaningful
            ],
            "saved_at": utc_now().isoformat(),
            "message_count": len(meaningful),
        }

        repo_context = MemoryService._ensure_dict(db_session.repo_context)
        repo_context["session_snapshot"] = snapshot
        db_session.repo_context = repo_context

        return snapshot

    @staticmethod
    def get_session_snapshot(db_session: ChatSession) -> Optional[Dict[str, Any]]:
        """Retrieve a stored session snapshot (episodic memory)."""
        repo_context = MemoryService._ensure_dict(db_session.repo_context)
        snapshot = repo_context.get("session_snapshot")
        return snapshot if isinstance(snapshot, dict) else None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_dict(repo_context: Optional[Any]) -> Dict[str, Any]:
        if isinstance(repo_context, dict):
            return dict(repo_context)
        if isinstance(repo_context, str) and repo_context.strip():
            try:
                parsed = json.loads(repo_context)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return {}


class IssueService:
    """
    Service for issue operations - delegates to IssueOps.
    """

    @staticmethod
    async def create_issue_with_context(db: Session, user_id: int, session_id: str, **kwargs):
        """
        Create issue with context using consolidated IssueOps function.

        Args:
            db: Database session
            user_id: User ID
            session_id: Session ID
            **kwargs: Additional parameters for issue creation

        Returns:
            Created issue data
        """
        from .IssueOps import IssueService as IssueOpsService

        issue_ops = IssueOpsService(db)
        return await issue_ops.create_issue_with_context(
            db=db,
            user_id=user_id,
            session_id=session_id,
            **kwargs
        )

    @staticmethod
    async def create_github_issue_from_user_issue(
        db: Session,
        user_id: int,
        issue_id: str,
        context_bundle: Optional[Dict[str, Any]] = None,
    ):
        """
        Create GitHub issue from user issue using IssueOps.

        Args:
            db: Database session
            user_id: User ID
            issue_id: Issue ID
            context_bundle: Optional serialized context to enrich the GitHub issue body

        Returns:
            Created GitHub issue data
        """
        from .IssueOps import IssueService as IssueOpsService

        issue_ops = IssueOpsService(db)
        return await issue_ops.create_github_issue_from_user_issue(
            user_id,
            issue_id,
            context_bundle=context_bundle,
        )
