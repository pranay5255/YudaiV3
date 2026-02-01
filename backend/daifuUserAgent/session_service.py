#!/usr/bin/env python3
"""
SessionService - Centralized Session Management Service

This module provides all session-related business logic and operations,
extracted from the router handlers for better separation of concerns.
"""

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
from psycopg import Connection
from db.sql_helpers import execute_one, execute_query, execute_scalar

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
    def ensure_owned_session(conn: Connection, user_id: int, session_id: str) -> Dict[str, Any]:
        """
        Ensure session exists and belongs to the user.

        Args:
            conn: Database connection
            user_id: User ID
            session_id: Session ID to validate

        Returns:
            Dict: The validated session

        Raises:
            HTTPException: If session not found or access denied
        """
        query = """
            SELECT id, session_id, user_id, title, description,
                   repo_owner, repo_name, repo_branch, repo_context,
                   is_active, total_messages, total_tokens,
                   created_at, updated_at, last_activity,
                   generate_embeddings, generate_facts_memories
            FROM chat_sessions
            WHERE session_id = %s AND user_id = %s
        """
        db_session = execute_one(conn, query, (session_id, user_id))

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found or access denied"
            )

        return db_session

    @staticmethod
    def get_context(conn: Connection, db_session: Dict[str, Any]) -> SessionContextResponse:
        """
        Get complete session context including messages, context cards, and file embeddings.

        Args:
            conn: Database connection
            db_session: The session dict

        Returns:
            SessionContextResponse: Complete session context
        """
        # Get session messages
        messages_query = """
            SELECT id, session_id, message_id, message_text, sender_type,
                   role, is_code, tokens, model_used, processing_time,
                   context_cards, referenced_files, error_message, actions,
                   created_at, updated_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at ASC
        """
        messages = execute_query(conn, messages_query, (db_session['id'],))

        # Get context cards for this session
        context_cards_query = """
            SELECT id, session_id, user_id, title, description,
                   content, source, tokens, is_active,
                   created_at, updated_at
            FROM context_cards
            WHERE session_id = %s AND is_active = TRUE
        """
        context_cards = execute_query(conn, context_cards_query, (db_session['id'],))

        # Get file embeddings for this session
        file_embeddings_query = """
            SELECT id, session_id, repository_id, file_path, file_name,
                   file_type, chunk_index, tokens, file_metadata, created_at
            FROM file_embeddings
            WHERE session_id = %s
        """
        file_embeddings = execute_query(conn, file_embeddings_query, (db_session['id'],))

        # Convert to response models
        session_response = SessionResponse(
            id=db_session['id'],
            session_id=db_session['session_id'],
            title=db_session['title'],
            description=db_session['description'],
            repo_owner=db_session['repo_owner'],
            repo_name=db_session['repo_name'],
            repo_branch=db_session['repo_branch'],
            repo_context=db_session['repo_context'],
            is_active=db_session['is_active'],
            total_messages=db_session['total_messages'],
            total_tokens=db_session['total_tokens'],
            created_at=db_session['created_at'],
            updated_at=db_session['updated_at'],
            last_activity=db_session['last_activity'],
            generate_embeddings=db_session.get('generate_embeddings'),
            generate_facts_memories=db_session.get('generate_facts_memories'),
        )

        message_responses = [
            ChatMessageResponse(
                id=msg['id'],
                message_id=msg['message_id'],
                message_text=msg['message_text'],
                sender_type=msg['sender_type'],
                role=msg['role'],
                is_code=msg['is_code'],
                tokens=msg['tokens'],
                model_used=msg.get('model_used'),
                processing_time=msg.get('processing_time'),
                context_cards=msg.get('context_cards'),
                referenced_files=msg.get('referenced_files'),
                error_message=msg.get('error_message'),
                actions=msg.get('actions'),
                created_at=msg['created_at'],
                updated_at=msg.get('updated_at'),
            )
            for msg in messages
        ]

        context_card_responses = [
            ContextCardResponse(
                id=card['id'],
                session_id=card['session_id'],
                title=card['title'],
                description=card.get('description'),
                content=card['content'],
                source=card.get('source'),
                tokens=card.get('tokens'),
                is_active=card['is_active'],
                created_at=card['created_at'],
                updated_at=card.get('updated_at'),
            )
            for card in context_cards
        ]

        file_embedding_responses = [
            FileEmbeddingResponse(
                id=fe['id'],
                session_id=fe['session_id'],
                repository_id=fe.get('repository_id'),
                file_path=fe['file_path'],
                file_name=fe['file_name'],
                file_type=fe.get('file_type'),
                chunk_index=fe.get('chunk_index'),
                tokens=fe.get('tokens'),
                file_metadata=fe.get('file_metadata'),
                created_at=fe['created_at'],
            )
            for fe in file_embeddings
        ]

        context_response = SessionContextResponse(
            session=session_response,
            messages=message_responses,
            context_cards=context_card_responses,
            repository_info={
                "owner": db_session['repo_owner'],
                "name": db_session['repo_name'],
                "branch": db_session['repo_branch'],
                "full_name": f"{db_session['repo_owner']}/{db_session['repo_name']}",
                "html_url": f"https://github.com/{db_session['repo_owner']}/{db_session['repo_name']}",
            }
            if db_session.get('repo_owner') and db_session.get('repo_name')
            else None,
            file_embeddings_count=len(file_embeddings),
            statistics={
                "total_messages": db_session['total_messages'],
                "total_tokens": db_session['total_tokens'],
                "session_duration": int(
                    (utc_now() - db_session['created_at']).total_seconds()
                )
                if db_session.get('created_at')
                else 0,
            },
            user_issues=[],
            file_embeddings=file_embedding_responses,
        )

        return context_response

    @staticmethod
    def get_session_messages(
        conn: Connection, session_id: int, limit: int = 100
    ) -> List[ChatMessageResponse]:
        """
        Get chat messages for a session.

        Args:
            conn: Database connection
            session_id: Internal session ID
            limit: Maximum number of messages to return

        Returns:
            List of ChatMessageResponse objects
        """
        query = """
            SELECT id, session_id, message_id, message_text, sender_type,
                   role, is_code, tokens, model_used, processing_time,
                   context_cards, referenced_files, error_message, actions,
                   created_at, updated_at
            FROM chat_messages
            WHERE session_id = %s
            ORDER BY created_at ASC
            LIMIT %s
        """
        messages = execute_query(conn, query, (session_id, limit))

        return [
            ChatMessageResponse(
                id=msg['id'],
                message_id=msg['message_id'],
                message_text=msg['message_text'],
                sender_type=msg['sender_type'],
                role=msg['role'],
                is_code=msg['is_code'],
                tokens=msg['tokens'],
                model_used=msg.get('model_used'),
                processing_time=msg.get('processing_time'),
                context_cards=msg.get('context_cards'),
                referenced_files=msg.get('referenced_files'),
                error_message=msg.get('error_message'),
                actions=msg.get('actions'),
                created_at=msg['created_at'],
                updated_at=msg.get('updated_at'),
            )
            for msg in messages
        ]

    @staticmethod
    def get_session_statistics(conn: Connection, db_session: Dict[str, Any]) -> dict:
        """
        Get comprehensive statistics for a session.

        Args:
            conn: Database connection
            db_session: The session dict

        Returns:
            Dictionary with session statistics
        """
        # Get message statistics
        message_stats_query = """
            SELECT sender_type,
                   COUNT(id) as count,
                   SUM(tokens) as total_tokens,
                   AVG(processing_time) as avg_processing_time
            FROM chat_messages
            WHERE session_id = %s
            GROUP BY sender_type
        """
        message_stats = execute_query(conn, message_stats_query, (db_session['id'],))

        # Get context card count
        context_card_count_query = """
            SELECT COUNT(id) as count
            FROM context_cards
            WHERE session_id = %s AND is_active = TRUE
        """
        context_card_count = execute_scalar(conn, context_card_count_query, (db_session['id'],)) or 0

        # Get file embedding statistics
        file_stats_query = """
            SELECT COUNT(id) as total_files,
                   SUM(tokens) as total_file_tokens,
                   COUNT(DISTINCT file_path) as unique_files
            FROM file_embeddings
            WHERE session_id = %s
        """
        file_stats = execute_one(conn, file_stats_query, (db_session['id'],))

        # Calculate session duration
        session_duration = None
        if db_session.get('created_at') and db_session.get('last_activity'):
            session_duration = int((db_session['last_activity'] - db_session['created_at']).total_seconds())

        # Build statistics response
        stats = {
            "session_id": db_session['session_id'],
            "basic_stats": {
                "total_messages": db_session['total_messages'],
                "total_tokens": db_session['total_tokens'],
                "total_context_cards": context_card_count,
                "total_file_embeddings": file_stats['total_files'] or 0 if file_stats else 0,
                "unique_files": file_stats['unique_files'] or 0 if file_stats else 0,
                "total_file_tokens": file_stats['total_file_tokens'] or 0 if file_stats else 0,
                "session_duration_seconds": session_duration,
                "is_active": db_session['is_active'],
            },
            "message_breakdown": {
                stat['sender_type']: {
                    "count": stat['count'],
                    "total_tokens": stat['total_tokens'] or 0,
                    "avg_processing_time": float(stat['avg_processing_time']) if stat.get('avg_processing_time') else None
                }
                for stat in message_stats
            },
            "timestamps": {
                "created_at": db_session['created_at'].isoformat() if db_session.get('created_at') else None,
                "last_activity": db_session['last_activity'].isoformat() if db_session.get('last_activity') else None,
                "updated_at": db_session['updated_at'].isoformat() if db_session.get('updated_at') else None,
            },
            "repository_info": {
                "owner": db_session.get('repo_owner'),
                "name": db_session.get('repo_name'),
                "branch": db_session.get('repo_branch'),
                "full_name": f"{db_session['repo_owner']}/{db_session['repo_name']}" if db_session.get('repo_owner') and db_session.get('repo_name') else None,
            } if db_session.get('repo_owner') else None,
        }

        return stats


class FileDepsService:
    """
    Service for file dependency operations.
    """

    @staticmethod
    def list_for_session(conn: Connection, db_session: Dict[str, Any]) -> List[dict]:
        """
        List file dependencies for a session.

        Args:
            conn: Database connection
            db_session: The session dict

        Returns:
            List of file dependency dictionaries
        """
        # Get file items for this session (new approach)
        query = """
            SELECT id, name, path, type, tokens, category,
                   is_directory, content_size, created_at,
                   file_name, file_path, file_type, content_summary
            FROM file_items
            WHERE session_id = %s
            ORDER BY created_at DESC
        """
        file_items = execute_query(conn, query, (db_session['id'],))

        # Convert to response format
        return [
            {
                "id": item['id'],
                "name": item['name'],
                "path": item['path'],
                "type": item['type'],
                "tokens": item.get('tokens'),
                "category": item.get('category'),
                "is_directory": item.get('is_directory'),
                "content_size": item.get('content_size'),
                "created_at": item['created_at'],
                "file_name": item.get('file_name'),
                "file_path": item.get('file_path'),
                "file_type": item.get('file_type'),
                "content_summary": item.get('content_summary'),
            }
            for item in file_items
        ]

    @staticmethod
    def get_file_items_for_session(conn: Connection, db_session: Dict[str, Any]) -> List[dict]:
        """
        Get file items for a session (for frontend display).

        Args:
            conn: Database connection
            db_session: The session dict

        Returns:
            List of file item dictionaries
        """
        return FileDepsService.list_for_session(conn, db_session)


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
