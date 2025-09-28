#!/usr/bin/env python3
"""
SessionService - Centralized Session Management Service

This module provides all session-related business logic and operations,
extracted from the router handlers for better separation of concerns.
"""

import logging
from typing import Dict, List, Optional

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

from utils import utc_now

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
            repo_context=db_session.repo_context,
            is_active=db_session.is_active,
            total_messages=db_session.total_messages,
            total_tokens=db_session.total_tokens,
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
                "session_duration": int(
                    (utc_now() - db_session.created_at).total_seconds()
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
        file_items = (
            db.query(FileItem)
            .filter(FileItem.session_id == db_session.id)
            .order_by(FileItem.created_at.desc())
            .all()
        )

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
