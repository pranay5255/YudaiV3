#!/usr/bin/env python3
"""
Session Management Routes for DAifu Agent

This module provides FastAPI routes for session management,
including session creation, context management, messages, and file dependencies.

TODO: Complete Implementation Tasks
========================================

CRITICAL ISSUES:
1. LLM Service Integration
   - Chat endpoint uses ChatOps.process_chat_message() with LLMService.generate_response_with_stored_context()
   - Issue endpoints use IssueOps.create_issue_with_context() with LLMService.generate_response()
   - Add proper error handling for LLM service failures
   - Implement streaming responses for real-time chat

2. Frontend Integration (@Chat.tsx compatibility)
   - Ensure all API responses match frontend expectations
   - Implement proper error message formatting for UI display
   - Add real-time WebSocket support for chat updates
   - Support context card operations from frontend

3. Session Management Enhancements
   - Add session timeout and cleanup mechanisms
   - Implement session persistence across browser sessions
   - Add session export/import functionality
   - Implement session collaboration features

4. File Dependencies Integration
   - Complete the file extraction endpoint integration
   - Add support for large repository processing
   - Implement file dependency caching
   - Add file content preview and search capabilities

5. Database Optimization
   - Add proper indexing for all query operations
   - Implement database connection pooling
   - Add query result caching (Redis)
   - Optimize bulk operations for messages and context cards



7. Authentication & Authorization
   - Ensure all endpoints properly validate user access
   - Add role-based access control where needed
   - Implement proper session token validation
   - Add audit logging for sensitive operations

13. Session Context Management
    - Implement proper context window management
    - Add context relevance scoring
    - Support multiple context sources (files, chat, external)
    - Implement context persistence and retrieval

14. Message Management
    - Add message search and filtering capabilities
    - Implement message threading and conversation management
    - Add message export/import functionality
    - Support message attachments and rich content

17. Deployment & Configuration
    - Add environment-specific configuration
    - Implement proper logging configuration
    - Add health checks and startup validation
    - Support containerized deployment

"""

# Import file dependencies functionality
import asyncio
import logging

# Import chat functionality from chat_api
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from auth.github_oauth import get_current_user
from daifuUserAgent.githubOps import GitHubOps
from db.database import SessionLocal, get_db
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

# Import from filedeps.py
from models import (
    AISolveSession,
    APIError,
    ChatMessage,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSession,
    ContextCard,
    ContextCardResponse,
    CreateContextCardRequest,
    CreateSessionRequest,
    FileEmbedding,
    FileItem,
    FileItemResponse,
    FileTreeResponse,
    Repository,
    RepositoryRequest,
    SessionContextResponse,
    SessionResponse,
    UpdateSessionRequest,
    User,
    UserIssueResponse,
)
from pgvector.sqlalchemy import Vector
from repo_processorGitIngest.scraper_script import (
    categorize_file,
    extract_repository_data,
)
from sqlalchemy.orm import Session

from utils import utc_now
from utils.chunking import create_file_chunker

from .llm_service import LLMService
from .session_service import SessionService

router = APIRouter(tags=["sessions"])

# Configure logging
logger = logging.getLogger(__name__)


def create_standardized_error(
    status_code: int,
    error_code: str,
    message: str,
    detail: Optional[str] = None,
    path: Optional[str] = None,
) -> HTTPException:
    """
    Create a standardized HTTPException with consistent error format.
    """
    error_response = APIError(
        detail=detail or message,
        message=message,
        status=status_code,
        error_code=error_code,
        timestamp=utc_now(),
        path=path,
        request_id=str(uuid.uuid4()),
    )

    return HTTPException(status_code=status_code, detail=error_response.model_dump())


# ============================================================================
# GITHUB ENDPOINTS (ported under DAIFU router)
# ============================================================================


@router.get("/github/repositories", response_model=List[Dict[str, Any]])
async def daifu_github_list_user_repositories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List repositories accessible by the authenticated user using their GitHub token.
    """
    try:
        from daifuUserAgent.githubOps import GitHubOps

        github_ops = GitHubOps(db)
        repositories = await github_ops.get_user_repositories(user_id=current_user.id)
        return repositories
    except HTTPException:
        raise
    except Exception as e:
        raise create_standardized_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "GITHUB_REPOS_FETCH_FAILED",
            "Failed to fetch repositories",
            detail=str(e),
            path="/daifu/github/repositories",
        )


@router.get(
    "/github/repositories/{owner}/{repo}/branches",
    response_model=List[Dict[str, Any]],
)
async def daifu_github_list_repository_branches(
    owner: str,
    repo: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List branches for a specific repository the authenticated user can access.
    """
    try:
        from daifuUserAgent.githubOps import GitHubOps

        github_ops = GitHubOps(db)
        branches = await github_ops.fetch_repository_branches(
            owner, repo, current_user.id
        )
        # Normalize to match frontend's GitHubBranch type shape
        normalized = [
            {
                "name": b.get("name"),
                "protected": bool(b.get("protected", False)),
                "commit": {
                    "sha": b.get("commit_sha"),
                    "url": b.get("commit_url"),
                },
            }
            for b in branches
        ]
        return normalized
    except HTTPException:
        raise
    except Exception as e:
        raise create_standardized_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "GITHUB_BRANCHES_FETCH_FAILED",
            "Failed to fetch branches",
            detail=str(e),
            path=f"/daifu/github/repositories/{owner}/{repo}/branches",
        )


# CRITICAL PRIORITY ENDPOINTS


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Create a new DAifu session for a repository.
    This is a CRITICAL endpoint required for session initialization.
    """
    try:
        # Generate unique session ID
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Create new session in database
        db_session = ChatSession(
            user_id=current_user.id,
            session_id=session_id,
            title=request.title or f"Chat - {request.repo_owner}/{request.repo_name}",
            description=request.description,
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            repo_branch=request.repo_branch or "main",
            repo_context=None,
            is_active=True,
            total_messages=0,
            total_tokens=0,
            last_activity=utc_now(),
        )

        db.add(db_session)
        db.commit()
        db.refresh(db_session)

        # Kick off background indexing of the repository if requested
        if getattr(request, "index_codebase", False):
            try:
                repo_owner = request.repo_owner
                repo_name = request.repo_name
                repo_branch = request.repo_branch or "main"
                max_file_size = getattr(request, "index_max_file_size", None)

                async def _run_index():
                    await _index_repository_for_session_background(
                        session_uuid=db_session.session_id,
                        user_id=current_user.id,
                        repo_owner=repo_owner,
                        repo_name=repo_name,
                        repo_branch=repo_branch,
                        max_file_size=max_file_size,
                    )

                try:
                    # If inside event loop, schedule directly
                    asyncio.get_running_loop()
                    asyncio.create_task(_run_index())
                except RuntimeError:
                    # Fallback when no loop is active
                    background_tasks.add_task(lambda: asyncio.run(_run_index()))
            except Exception as e_bg:
                logger.error(f"Failed to schedule repository indexing: {e_bg}")

        return SessionResponse(
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
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}",
        )


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update session details (title, description, branch, etc.)
    This is a CRITICAL endpoint for session management.
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Update fields if provided
        if request.title is not None:
            db_session.title = request.title
        if request.description is not None:
            db_session.description = request.description
        if request.repo_branch is not None:
            db_session.repo_branch = request.repo_branch
        if request.is_active is not None:
            db_session.is_active = request.is_active

        # Update last activity
        db_session.last_activity = utc_now()
        db_session.updated_at = utc_now()

        db.commit()
        db.refresh(db_session)

        return SessionResponse(
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
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}",
        )


@router.get("/sessions/{session_id}", response_model=SessionContextResponse)
async def get_session_context(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get session context including messages, context cards, and repository info.
    This is a CRITICAL endpoint required for session loading.
    """
    try:
        from .session_service import SessionService

        # Ensure session exists and belongs to user
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )

        # Get complete session context
        return SessionService.get_context(db, db_session)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session context: {str(e)}",
        )


# HIGH PRIORITY ENDPOINTS


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def add_chat_message(
    session_id: str,
    message_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a new chat message to a session.
    This endpoint is used by the chat system to store messages.
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Create new message
        message = ChatMessage(
            session_id=db_session.id,
            message_id=message_data.get("message_id", f"msg_{uuid.uuid4().hex[:8]}"),
            message_text=message_data["message_text"],
            sender_type=message_data["sender_type"],
            role=message_data["role"],
            is_code=message_data.get("is_code", False),
            tokens=message_data.get("tokens", 0),
            model_used=message_data.get("model_used"),
            processing_time=message_data.get("processing_time"),
            context_cards=message_data.get("context_cards"),
            referenced_files=message_data.get("referenced_files"),
            error_message=message_data.get("error_message"),
        )

        db.add(message)

        # Update session statistics
        db_session.total_messages += 1
        db_session.total_tokens += message.tokens
        db_session.last_activity = utc_now()

        db.commit()
        db.refresh(message)

        return ChatMessageResponse(
            id=message.id,
            message_id=message.message_id,
            message_text=message.message_text,
            sender_type=message.sender_type,
            role=message.role,
            is_code=message.is_code,
            tokens=message.tokens,
            model_used=message.model_used,
            processing_time=message.processing_time,
            context_cards=message.context_cards,
            referenced_files=message.referenced_files,
            error_message=message.error_message,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add message: {str(e)}",
        )


@router.post(
    "/sessions/{session_id}/messages/bulk", response_model=List[ChatMessageResponse]
)
async def add_bulk_chat_messages(
    session_id: str,
    messages: List[dict],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add multiple chat messages to a session in bulk.
    This is a HIGH priority endpoint for bulk message operations.
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        created_messages = []
        total_tokens_added = 0

        for message_data in messages:
            # Create new message
            message = ChatMessage(
                session_id=db_session.id,
                message_id=message_data.get(
                    "message_id", f"msg_{uuid.uuid4().hex[:8]}"
                ),
                message_text=message_data["message_text"],
                sender_type=message_data["sender_type"],
                role=message_data["role"],
                is_code=message_data.get("is_code", False),
                tokens=message_data.get("tokens", 0),
                model_used=message_data.get("model_used"),
                processing_time=message_data.get("processing_time"),
                context_cards=message_data.get("context_cards"),
                referenced_files=message_data.get("referenced_files"),
                error_message=message_data.get("error_message"),
            )

            db.add(message)
            created_messages.append(message)
            total_tokens_added += message.tokens

        # Update session statistics
        db_session.total_messages += len(created_messages)
        db_session.total_tokens += total_tokens_added
        db_session.last_activity = utc_now()

        db.commit()

        # Refresh all messages to get IDs
        for message in created_messages:
            db.refresh(message)

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
            for msg in created_messages
        ]

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add bulk messages: {str(e)}",
        )


@router.get("/sessions/{session_id}/export", response_model=dict, deprecated=True)
async def export_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Deprecated: exporting sessions is no longer supported."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "message": "Deprecated: session export is no longer supported.",
            "error_code": "ENDPOINT_DEPRECATED",
            "path": f"/daifu/sessions/{session_id}/export",
        },
    )


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get chat messages for a session.
    This is a HIGH priority endpoint for chat history display.
    """
    try:
        from .session_service import SessionService

        # Ensure session exists and belongs to user
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )

        # Get messages for this session
        return SessionService.get_session_messages(db, db_session.id, limit)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat messages: {str(e)}",
        )


@router.post("/sessions/{session_id}/context-cards", response_model=ContextCardResponse)
async def add_context_card(
    session_id: str,
    request: CreateContextCardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a context card to a session.
    This is a HIGH priority endpoint for context management.
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Create new context card
        context_card = ContextCard(
            user_id=current_user.id,
            session_id=db_session.id,
            title=request.title,
            description=request.description,
            content=request.content,
            source=request.source,
            tokens=request.tokens,
            is_active=True,
        )

        db.add(context_card)
        db.commit()
        db.refresh(context_card)

        return ContextCardResponse(
            id=context_card.id,
            session_id=context_card.session_id,
            title=context_card.title,
            description=context_card.description,
            content=context_card.content,
            source=context_card.source,
            tokens=context_card.tokens,
            is_active=context_card.is_active,
            created_at=context_card.created_at,
            updated_at=context_card.updated_at,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add context card: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/context-cards", response_model=List[ContextCardResponse]
)
async def get_context_cards(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get context cards for a session.
    This is a HIGH priority endpoint for context display.
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Get active context cards for this session
        context_cards = (
            db.query(ContextCard)
            .filter(ContextCard.session_id == db_session.id, ContextCard.is_active)
            .order_by(ContextCard.created_at.desc())
            .all()
        )

        return [
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

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context cards: {str(e)}",
        )


# MEDIUM PRIORITY ENDPOINTS


@router.get(
    "/sessions/{session_id}/file-deps/session",
    response_model=List[FileItemResponse],
)
async def get_file_dependencies_for_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get file items for a session (matches frontend FileItem interface)"""
    try:
        # Ensure session exists and belongs to user
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )

        # Get file items for this session
        file_items = (
            db.query(FileItem)
            .filter(FileItem.session_id == db_session.id)
            .order_by(FileItem.created_at.desc())
            .all()
        )

        logger.info(f"[FileDeps] Found {len(file_items)} file items for session {session_id}")

        # Convert to response format
        response_items = []
        for item in file_items:
            response_item = FileItemResponse(
                id=str(item.id),
                name=item.name,
                path=item.path,
                type=item.type,
                tokens=item.tokens,
                category=item.category,
                isDirectory=item.is_directory,
                content_size=item.content_size,
                created_at=item.created_at.isoformat() if item.created_at else None,
                file_name=item.file_name,
                file_path=item.file_path,
                file_type=item.file_type,
                content_summary=item.content_summary,
            )
            response_items.append(response_item)

        logger.info(f"[FileDeps] Returning {len(response_items)} file items for session {session_id}")
        return response_items

    except Exception as e:
        logger.error(f"[FileDeps] Failed to get file dependencies for session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file dependencies: {str(e)}",
        )


# CHAT ENDPOINTS - Consolidated from chat_api.py
# =================================================================================


@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
async def chat_in_session(
    session_id: str,
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chat Endpoint within Session Context - Uses ChatOps for unified chat handling

    This endpoint processes chat messages within a specific session context using
    the ChatOps class for consistent processing and response formatting.
    """
    start_time = time.time()

    # Validate session exists and belongs to user
    db_session = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == session_id, ChatSession.user_id == current_user.id
        )
        .first()
    )

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Validate session_id matches request
    if not request.session_id or request.session_id.strip() != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session ID mismatch between URL and request body",
        )

    try:
        # Import ChatOps for unified chat processing
        from .ChatOps import ChatOps

        # Initialize ChatOps instance
        chat_ops = ChatOps(db)

        # Prepare repository information for ChatOps
        repository_info = None
        if (
            request.repository
            and request.repository.get("owner")
            and request.repository.get("name")
        ):
            repository_info = {
                "owner": request.repository["owner"],
                "name": request.repository["name"],
                "branch": request.repository.get("branch", "main"),
            }
        elif db_session.repo_owner and db_session.repo_name:
            # Fallback to session repository info
            repository_info = {
                "owner": db_session.repo_owner,
                "name": db_session.repo_name,
                "branch": "main",
            }

        # Process chat message using ChatOps
        chat_response = await chat_ops.process_chat_message(
            session_id=session_id,
            user_id=current_user.id,
            message_text=request.message.message_text,
            context_cards=request.context_cards or [],
            repository=repository_info,
        )

        # Get updated conversation history for the response
        history = _get_conversation_history(session_id, 50, db)

        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000

        # Map ChatOps response to ChatResponse format
        return ChatResponse(
            reply=chat_response["reply"],
            conversation=history,
            message_id=chat_response["message_id"],
            processing_time=processing_time,
            session_id=session_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat processing failed for session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}",
        )


# Helper functions for conversation history management
def _get_conversation_history(
    session_id: str, limit: int = 50, db: Session = None
) -> List[tuple]:
    """Get conversation history for a session from database"""
    if not db:
        return []

    try:
        # Get the session from database
        db_session = (
            db.query(ChatSession).filter(ChatSession.session_id == session_id).first()
        )

        if not db_session:
            return []

        # Get messages for this session
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == db_session.id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )

        # Convert to tuple format for compatibility
        history = []
        for msg in messages:
            sender = "User" if msg.sender_type == "user" else "DAifu"
            history.append((sender, msg.message_text))

        return history
    except Exception as e:
        print(f"Error getting conversation history: {e}")
        return []


def _add_to_conversation_history(
    session_id: str,
    sender: str,
    message: str,
    db: Session = None,
    current_user: User = None,
):
    """Add a message to conversation history in database"""
    if not db or not current_user:
        return

    try:
        # Get the session from database
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            print(f"Session {session_id} not found for user {current_user.id}")
            return

        # Create message record
        sender_type = "user" if sender == "User" else "assistant"
        message_obj = ChatMessage(
            session_id=db_session.id,
            message_id=f"msg_{uuid.uuid4().hex[:8]}",
            message_text=message,
            sender_type=sender_type,
            role=sender_type,
            is_code=False,
            tokens=len(message.split()),  # Rough estimation
        )

        db.add(message_obj)

        # Update session statistics
        db_session.total_messages += 1
        db_session.total_tokens += message_obj.tokens
        db_session.last_activity = utc_now()

        db.commit()
    except Exception as e:
        print(f"Error adding to conversation history: {e}")
        db.rollback()


# FILE DEPENDENCIES ENDPOINTS - Consolidated from filedeps.py
# =================================================================================


def _estimate_tokens_for_file(file_path: str, content_size: int) -> int:
    """Estimate tokens for a file based on its size and type."""
    # Get file extension
    ext = Path(file_path).suffix.lower()

    # Different ratios for different file types
    token_ratios = {
        ".py": 4,  # Python: ~4 chars per token
        ".js": 4,  # JavaScript: ~4 chars per token
        ".ts": 4,  # TypeScript: ~4 chars per token
        ".jsx": 4,  # React JSX: ~4 chars per token
        ".tsx": 4,  # React TSX: ~4 chars per token
        ".md": 3,  # Markdown: ~3 chars per token
        ".json": 5,  # JSON: ~5 chars per token
        ".yaml": 3,  # YAML: ~3 chars per token
        ".yml": 3,  # YAML: ~3 chars per token
        ".txt": 3,  # Text: ~3 chars per token
        ".html": 4,  # HTML: ~4 chars per token
        ".css": 4,  # CSS: ~4 chars per token
        ".sql": 4,  # SQL: ~4 chars per token
        ".sh": 4,  # Shell: ~4 chars per token
    }

    ratio = token_ratios.get(ext, 4)  # Default to 4 chars per token
    return max(1, content_size // ratio)


def _extract_repo_info_from_url(repo_url: str) -> tuple[str, str]:
    """Extract repository name and owner from GitHub URL."""
    parsed = urlparse(repo_url)
    path_parts = parsed.path.strip("/").split("/")

    if len(path_parts) >= 2:
        owner = path_parts[0]
        repo_name = path_parts[1].replace(".git", "")
        return repo_name, owner
    else:
        return "unknown", "unknown"


def _get_or_create_repository(
    db: Session,
    repo_url: str,
    repo_name: str,
    repo_owner: str,
    user_id: int,
    html_url: Optional[str] = None,
    clone_url: Optional[str] = None,
    description: Optional[str] = None,
    language: Optional[str] = None,
    stargazers_count: Optional[int] = 0,
    forks_count: Optional[int] = 0,
    open_issues_count: Optional[int] = 0,
    default_branch: Optional[str] = None,
    github_created_at: Optional[datetime] = None,
    github_updated_at: Optional[datetime] = None,
    pushed_at: Optional[datetime] = None,
) -> Repository:
    """Retrieve existing repository metadata or create a new record."""
    # First try to find existing repository by URL and user
    repository = (
        db.query(Repository)
        .filter(Repository.repo_url == repo_url, Repository.user_id == user_id)
        .first()
    )

    if repository:
        # Update existing repository with latest data if provided
        if html_url is not None:
            repository.html_url = html_url
        if clone_url is not None:
            repository.clone_url = clone_url
        if description is not None:
            repository.description = description
        if language is not None:
            repository.language = language
        if stargazers_count is not None:
            repository.stargazers_count = stargazers_count
        if forks_count is not None:
            repository.forks_count = forks_count
        if open_issues_count is not None:
            repository.open_issues_count = open_issues_count
        if default_branch is not None:
            repository.default_branch = default_branch
        if github_created_at is not None:
            repository.github_created_at = github_created_at
        if github_updated_at is not None:
            repository.github_updated_at = github_updated_at
        if pushed_at is not None:
            repository.pushed_at = pushed_at
        db.commit()
        return repository

    # Create new repository record
    repository = Repository(
        user_id=user_id,
        name=repo_name,
        owner=repo_owner,
        full_name=f"{repo_owner}/{repo_name}",
        repo_url=repo_url,
        html_url=html_url or repo_url,  # Default to repo_url if html_url is None
        clone_url=clone_url or repo_url,  # Default to repo_url if clone_url is None
        description=description,
        language=language,
        stargazers_count=stargazers_count or 0,
        forks_count=forks_count or 0,
        open_issues_count=open_issues_count or 0,
        default_branch=default_branch,
        github_created_at=github_created_at,
        github_updated_at=github_updated_at,
        pushed_at=pushed_at,
    )
    db.add(repository)
    db.flush()
    return repository


@router.post(
    "/sessions/{session_id}/extract", response_model=FileTreeResponse, deprecated=True
)
async def extract_file_dependencies_for_session(
    session_id: str,
    request: RepositoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileTreeResponse:
    """Deprecated: indexing now starts automatically after session creation."""
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail={
            "message": "Deprecated: use session creation with index_codebase flag.",
            "error_code": "ENDPOINT_DEPRECATED",
            "path": f"/daifu/sessions/{session_id}/extract",
        },
    )
    try:  # Unreachable legacy block retained for reference
        print(f"Starting session-based extraction for session: {session_id}")

        # First, verify the session exists and belongs to the user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Extract repository information from URL
        repo_name, repo_owner = _extract_repo_info_from_url(request.repo_url)
        print(f"Extracted repo info - name: {repo_name}, owner: {repo_owner}")

        # Extract repository data using GitIngest
        print("Calling GitIngest extract_repository_data...")
        raw_repo_data = await extract_repository_data(
            repo_url=request.repo_url, max_file_size=request.max_file_size
        )

        if "error" in raw_repo_data:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to extract data: {raw_repo_data['error']}",
            )

        # Process raw data into structured format
        repo_data = _process_gitingest_data(raw_repo_data)

        # Build file tree
        files_data = {"files": repo_data.get("files", [])}
        file_tree = _build_file_tree(files_data, repo_name)

        # Calculate statistics
        total_files = len(repo_data.get("files", []))
        total_tokens = sum(
            _estimate_tokens_for_file(f["path"], f["content_size"])
            for f in repo_data.get("files", [])
        )

        # Create root FileTree node
        root_file_item = FileTreeResponse(
            id="root",
            name=repo_name,
            type="INTERNAL",
            tokens=total_tokens,
            Category="Source Code",
            isDirectory=True,
            children=file_tree,
            expanded=True,
        )

        # Save to database with session integration
        try:
            # Fetch repository metadata from GitHub API
            github_ops = GitHubOps(db)
            try:
                repo_metadata = await github_ops.fetch_repository_info_detailed(
                    owner=repo_owner, repo=repo_name, user_id=current_user.id
                )
                print(
                    f"Fetched repository metadata: {repo_metadata.get('name', 'unknown')}"
                )
            except Exception as e:
                print(f"Failed to fetch repository metadata from GitHub API: {e}")
                repo_metadata = {}

            # Ensure repository metadata exists
            repository = _get_or_create_repository(
                db=db,
                repo_url=request.repo_url,
                repo_name=repo_name,
                repo_owner=repo_owner,
                user_id=current_user.id,
                html_url=repo_metadata.get("html_url"),
                clone_url=repo_metadata.get("clone_url"),
                description=repo_metadata.get("description"),
                language=repo_metadata.get("language"),
                stargazers_count=repo_metadata.get("stargazers_count", 0),
                forks_count=repo_metadata.get("forks_count", 0),
                open_issues_count=repo_metadata.get("open_issues_count", 0),
                default_branch=repo_metadata.get("default_branch"),
                github_created_at=repo_metadata.get("created_at"),
                github_updated_at=repo_metadata.get("updated_at"),
                pushed_at=repo_metadata.get("pushed_at"),
            )

            # Save analysis results
            _save_file_analysis_to_db(
                db=db,
                repository_id=repository.id,
                raw_data=raw_repo_data,
                processed_data=repo_data,
                total_files=total_files,
                total_tokens=total_tokens,
                max_file_size=request.max_file_size,
            )

            # Save file items and create embeddings linked to session
            saved_file_items, saved_embeddings = _save_file_items_and_embeddings(
                db, repository.id, file_tree, db_session.id
            )
            print(
                f"Saved {len(saved_file_items)} file items and {len(saved_embeddings)} embeddings"
            )

        except Exception as db_error:
            print(f"Database error during save: {db_error}")
            db.rollback()
            raise HTTPException(
                status_code=500, detail=f"Failed to save file data: {str(db_error)}"
            )

        print(f"Successfully completed extraction for session {session_id}")
        return root_file_item

    except HTTPException:
        raise
    except Exception as e:
        print(f"Unexpected error in extract_file_dependencies_for_session: {e}")
        raise HTTPException(status_code=500, detail=f"File extraction failed: {str(e)}")


# Helper functions for file processing (imported from filedeps.py)
def _process_gitingest_data(raw_repo_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process raw GitIngest data into structured format."""
    processed_data = {"files": []}

    if "files" not in raw_repo_data:
        return processed_data

    for file_data in raw_repo_data["files"]:
        processed_file = {
            "path": file_data.get("path", ""),
            "content": file_data.get("content", ""),
            "size": file_data.get("size", 0),
            "content_size": len(file_data.get("content", "")),
            "type": categorize_file(file_data.get("path", "")),
        }
        processed_data["files"].append(processed_file)

    return processed_data


def _build_file_tree(
    files_data: Dict[str, Any], repo_name: str
) -> List[Dict[str, Any]]:
    """Build hierarchical file tree from processed data."""
    file_tree = []

    if "files" not in files_data:
        return file_tree

    # Group files by directory
    dir_structure = {}

    for file_info in files_data["files"]:
        path_parts = file_info["path"].split("/")
        current_dir = dir_structure

        for i, part in enumerate(path_parts[:-1]):  # All parts except the filename
            if part not in current_dir:
                current_dir[part] = {"__files__": []}
            current_dir = current_dir[part]

        # Add file to the appropriate directory
        if "__files__" not in current_dir:
            current_dir["__files__"] = []

        file_name = path_parts[-1]
        file_item = {
            "id": file_info["path"],
            "name": file_name,
            "type": file_info["type"],
            "Category": file_info["type"],
            "tokens": _estimate_tokens_for_file(
                file_info["path"], file_info["content_size"]
            ),
            "isDirectory": False,
            "path": file_info["path"],
        }
        current_dir["__files__"].append(file_item)

    # Convert directory structure to FileItem format
    def convert_to_file_items(
        dir_dict: Dict[str, Any], current_path: str = ""
    ) -> List[Dict[str, Any]]:
        items = []

        for name, content in dir_dict.items():
            if name == "__files__":
                items.extend(content)
            else:
                full_path = f"{current_path}/{name}" if current_path else name
                children = convert_to_file_items(content, full_path)

                # Calculate total tokens for directory
                total_tokens = sum(
                    child.get("tokens", 0)
                    for child in children
                    if not child.get("isDirectory", False)
                )

                dir_item = {
                    "id": full_path,
                    "name": name,
                    "type": "INTERNAL",
                    "Category": "Directory",
                    "tokens": total_tokens,
                    "isDirectory": True,
                    "children": children,
                    "expanded": False,
                }
                items.append(dir_item)

        return items

    return convert_to_file_items(dir_structure)


def _save_file_analysis_to_db(
    db: Session,
    repository_id: int,
    raw_data: Dict[str, Any],
    processed_data: Dict[str, Any],
    total_files: int,
    total_tokens: int,
    max_file_size: int,
):
    """Log file analysis results instead of storing in database."""
    print(f"Repository analysis completed for repository {repository_id}:")
    print(f"  - Total files processed: {total_files}")
    print(f"  - Total tokens: {total_tokens}")
    print(f"  - Max file size: {max_file_size}")
    print(f"  - Files saved as embeddings: {len(processed_data.get('files', []))}")

    # No database storage - just logging
    return None


def _save_file_items_and_embeddings(
    db: Session,
    repository_id: int,
    file_tree: List[Dict[str, Any]],
    session_id: int,
    content_lookup: Optional[Dict[str, str]] = None,
) -> Tuple[List[FileItem], List[FileEmbedding]]:
    """Save file items and their embeddings separately.

    content_lookup maps file paths to full file contents for embedding creation.
    """

    saved_file_items = []
    saved_embeddings = []

    def process_recursive(items: List[Dict[str, Any]]):
        for item_data in items:
            # Create FileItem record
            file_item = FileItem(
                session_id=session_id,
                repository_id=repository_id,
                name=item_data.get("name", ""),
                path=item_data.get("path"),
                type=item_data.get("type", "INTERNAL"),
                tokens=item_data.get("tokens", 0),
                category=item_data.get("Category", "unknown"),
                is_directory=item_data.get("isDirectory", False),
                content_size=item_data.get("content_size"),
                file_name=item_data.get("file_name"),
                file_path=item_data.get("file_path"),
                file_type=item_data.get("file_type"),
                content_summary=item_data.get("content_summary"),
            )
            db.add(file_item)
            db.flush()  # Get the ID

            saved_file_items.append(file_item)

            # If it's a file (not a directory), create embeddings using content map
            if not item_data.get("isDirectory", False):
                fpath = item_data.get("path") or item_data.get("file_path")
                if content_lookup and fpath:
                    content = content_lookup.get(fpath)
                else:
                    content = None
                if content:
                    embeddings = _create_embeddings_for_file_item(
                        db,
                        session_id,
                        repository_id,
                        file_item.id,
                        fpath,
                        item_data.get("name", ""),
                        content,
                    )
                    saved_embeddings.extend(embeddings)

            # Process children recursively
            if item_data.get("isDirectory", False) and "children" in item_data:
                process_recursive(item_data["children"])

    process_recursive(file_tree)
    return saved_file_items, saved_embeddings


def _create_embeddings_for_file_item(
    db: Session,
    session_id: int,
    repository_id: int,
    file_item_id: int,
    file_path: str,
    file_name: str,
    content: str,
) -> List[FileEmbedding]:
    """Create embeddings for a specific file item using provided content."""

    saved_embeddings = []

    try:
        chunker = create_file_chunker()
        chunk_data = chunker.chunk_file(file_path, content)
        chunks = [chunk["chunk_text"] for chunk in chunk_data]

        for i, chunk in enumerate(chunks):
            # Generate embedding for chunk
            embedding_vector = LLMService.embed_text(chunk)

            embedding = FileEmbedding(
                session_id=session_id,
                repository_id=repository_id,
                file_item_id=file_item_id,
                file_path=file_path,
                file_name=file_name,
                chunk_index=i,
                chunk_text=chunk,
                embedding=Vector(embedding_vector),
                tokens=_estimate_tokens_for_file(file_path, len(chunk)),
            )
            db.add(embedding)
            saved_embeddings.append(embedding)

        db.flush()
        return saved_embeddings

    except Exception as e:
        print(f"Error creating embeddings for file item {file_item_id}: {e}")
        return []


async def _index_repository_for_session_background(
    session_uuid: str,
    user_id: int,
    repo_owner: str,
    repo_name: str,
    repo_branch: str = "main",
    max_file_size: Optional[int] = None,
) -> None:
    """Background task: extract the repository, chunk files, create embeddings and persist.

    This runs after session creation when index_codebase=True.
    """
    db = SessionLocal()
    try:
        logger.info(
            f"[Index] Starting indexing for session={session_uuid} repo={repo_owner}/{repo_name}"
        )

        # Verify the session exists and is owned by the user
        chat_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_uuid, ChatSession.user_id == user_id
            )
            .first()
        )
        if not chat_session:
            logger.warning(
                f"[Index] Session not found or not owned by user: {session_uuid}"
            )
            return

        repo_url = f"https://github.com/{repo_owner}/{repo_name}"

        # Extract repository content via GitIngest
        raw_repo = await extract_repository_data(
            repo_url=repo_url, max_file_size=max_file_size
        )
        if isinstance(raw_repo, dict) and raw_repo.get("error"):
            logger.error(f"[Index] GitIngest error: {raw_repo['error']}")
            return

        # Use raw_repo files directly since scraper_script.py now returns proper files array
        files_data = raw_repo.get("files", [])

        # Fetch repo metadata (best effort)
        try:
            gh = GitHubOps(db)
            meta = await gh.fetch_repository_info_detailed(
                repo_owner, repo_name, user_id
            )
        except Exception as e:
            logger.warning(f"[Index] Failed to fetch repo metadata: {e}")
            meta = {}

        repository = _get_or_create_repository(
            db,
            repo_url,
            repo_name,
            repo_owner,
            user_id,
            html_url=meta.get("html_url"),
            clone_url=meta.get("clone_url"),
            description=meta.get("description"),
            language=meta.get("language"),
            stargazers_count=meta.get("stargazers_count", 0),
            forks_count=meta.get("forks_count", 0),
            open_issues_count=meta.get("open_issues_count", 0),
            default_branch=meta.get("default_branch", repo_branch),
            github_created_at=meta.get("created_at"),
            github_updated_at=meta.get("updated_at"),
            pushed_at=meta.get("pushed_at"),
        )

        # Save file items directly from files_data
        saved_file_items = []
        saved_embeddings = []

        for file_data in files_data:
            try:
                # Create FileItem record
                file_item = FileItem(
                    session_id=chat_session.id,
                    repository_id=repository.id,
                    name=file_data.get("path", "").split("/")[-1] or "unknown",
                    path=file_data.get("path"),
                    type=file_data.get("type", "INTERNAL"),
                    tokens=_estimate_tokens_for_file(
                        file_data.get("path", ""),
                        file_data.get("content_size", 0)
                    ),
                    category=file_data.get("type", "unknown"),
                    is_directory=False,
                    content_size=file_data.get("content_size", 0),
                    file_name=file_data.get("path", "").split("/")[-1],
                    file_path=file_data.get("path"),
                    file_type=file_data.get("type"),
                )
                db.add(file_item)
                db.flush()  # Get the ID
                saved_file_items.append(file_item)

                # Create embeddings for the file content
                file_content = file_data.get("content", "")
                if file_content and len(file_content.strip()) > 0:
                    try:
                        embeddings = _create_embeddings_for_file_item(
                            db,
                            chat_session.id,
                            repository.id,
                            file_item.id,
                            file_data.get("path", ""),
                            file_data.get("path", "").split("/")[-1] or "unknown",
                            file_content,
                        )
                        saved_embeddings.extend(embeddings)
                    except Exception as embed_error:
                        logger.warning(f"[Index] Failed to create embeddings for {file_data.get('path')}: {embed_error}")
                        # Continue processing other files

            except Exception as file_error:
                logger.warning(f"[Index] Failed to process file {file_data.get('path')}: {file_error}")
                continue

        logger.info(f"[Index] Saved {len(saved_file_items)} file items and {len(saved_embeddings)} embeddings")
        db.commit()

        logger.info(f"[Index] Completed indexing for session {session_uuid}")
    except Exception as e:
        logger.error(f"[Index] Unexpected indexing error: {e}")
        db.rollback()
    finally:
        db.close()


# ============================================================================
# SOLVER ENDPOINTS - Consolidated under sessions context
# ============================================================================


@router.post("/sessions/{session_id}/solve/start", response_model=dict)
async def start_solve_session_for_session(
    session_id: str,
    request: Optional[dict] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start AI solver for a session - supports both database issues and direct content
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Extract parameters from request
        issue_id = request.get("issue_id") if request else None
        repo_url = request.get("repo_url") if request else None
        branch = request.get("branch", "main")
        issue_content = request.get("issue_content") if request else None
        issue_title = request.get("issue_title") if request else None
        ai_model_id = request.get("ai_model_id") if request else None
        swe_config_id = request.get("swe_config_id") if request else None

        # Validate required parameters
        if not repo_url:
            repo_url = (
                f"https://github.com/{db_session.repo_owner}/{db_session.repo_name}"
            )

        # Import solver adapter
        from solver.ai_solver import AISolverAdapter

        # Create solver adapter
        solver = AISolverAdapter(db)

        # Start solver with appropriate parameters
        session_id_num = await solver.run_solver(
            issue_id=issue_id,
            user_id=current_user.id,
            repo_url=repo_url,
            branch=branch,
            issue_content=issue_content,
            issue_title=issue_title,
            ai_model_id=ai_model_id,
            swe_config_id=swe_config_id,
        )

        return {
            "message": "AI Solver started successfully",
            "session_id": session_id_num,
            "solve_session_id": session_id_num,
            "status": "started",
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start solver: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/solve/sessions/{solve_session_id}", response_model=dict
)
async def get_solve_session_for_session(
    session_id: str,
    solve_session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get solve session details for a session - Consolidated from solve_router.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Get solve session with authorization check
        solve_session = (
            db.query(AISolveSession)
            .filter(
                AISolveSession.id == solve_session_id,
                AISolveSession.user_id == current_user.id,
            )
            .first()
        )

        if not solve_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solve session not found or access denied",
            )

        return {
            "id": solve_session.id,
            "user_id": solve_session.user_id,
            "issue_id": solve_session.issue_id,
            "ai_model_id": solve_session.ai_model_id,
            "swe_config_id": solve_session.swe_config_id,
            "status": solve_session.status,
            "repo_url": solve_session.repo_url,
            "branch_name": solve_session.branch_name,
            "started_at": solve_session.started_at,
            "completed_at": solve_session.completed_at,
            "error_message": solve_session.error_message,
            "trajectory_data": solve_session.trajectory_data,
            "created_at": solve_session.created_at,
            "updated_at": solve_session.updated_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get solve session: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/solve/sessions/{solve_session_id}/stats",
    response_model=dict,
)
async def get_solve_session_stats_for_session(
    session_id: str,
    solve_session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get solve session statistics for a session - Consolidated from solve_router.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Verify solve session exists and user has access
        solve_session = (
            db.query(AISolveSession)
            .filter(
                AISolveSession.id == solve_session_id,
                AISolveSession.user_id == current_user.id,
            )
            .first()
        )

        if not solve_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Solve session not found or access denied",
            )

        # Import solver adapter for stats
        from solver.ai_solver import AISolverAdapter

        solver = AISolverAdapter(db)
        stats = solver.get_session_status(solve_session_id)

        if not stats:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve session statistics",
            )

        return stats

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get solve session stats: {str(e)}",
        )


@router.post(
    "/sessions/{session_id}/solve/sessions/{solve_session_id}/cancel",
    response_model=dict,
)
async def cancel_solve_session_for_session(
    session_id: str,
    solve_session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a running solve session for a session - Consolidated from solve_router.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Import solver adapter
        from solver.ai_solver import AISolverAdapter

        solver = AISolverAdapter(db)

        # Attempt to cancel session
        cancelled = await solver.cancel_session(solve_session_id, current_user.id)

        if not cancelled:
            # Check if session exists to provide better error message
            solve_session = (
                db.query(AISolveSession)
                .filter(
                    AISolveSession.id == solve_session_id,
                    AISolveSession.user_id == current_user.id,
                )
                .first()
            )

            if not solve_session:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Solve session not found or access denied",
                )
            elif solve_session.status != "RUNNING":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot cancel session with status: {solve_session.status}",
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to cancel session",
                )

        return {
            "message": "Solve session cancelled successfully",
            "session_id": solve_session_id,
            "status": "cancelled",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel solve session: {str(e)}",
        )


@router.get("/sessions/{session_id}/solve/sessions", response_model=list)
async def list_solve_sessions_for_session(
    session_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List solve sessions for a session - Consolidated from solve_router.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Build query
        query = db.query(AISolveSession).filter(
            AISolveSession.user_id == current_user.id
        )

        # Apply status filter if provided
        if status_filter:
            from schemas.ai_solver import SolveStatus

            try:
                status_enum = SolveStatus(status_filter)
                query = query.filter(AISolveSession.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}",
                )

        # Apply pagination and ordering
        solve_sessions = (
            query.order_by(AISolveSession.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return [
            {
                "id": session.id,
                "user_id": session.user_id,
                "issue_id": session.issue_id,
                "ai_model_id": session.ai_model_id,
                "swe_config_id": session.swe_config_id,
                "status": session.status,
                "repo_url": session.repo_url,
                "branch_name": session.branch_name,
                "started_at": session.started_at,
                "completed_at": session.completed_at,
                "error_message": session.error_message,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
            }
            for session in solve_sessions
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list solve sessions: {str(e)}",
        )


@router.get("/sessions/{session_id}/solve/health", response_model=dict)
async def solver_health_for_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Health check for the AI solver system within session context - Consolidated from solve_router.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # TODO: Add actual health checks
        # - Check SWE-agent availability
        # - Check Docker daemon connection
        # - Check disk space for solve data
        # - Check AI model API connectivity
        # - Check database connectivity

        return {
            "status": "healthy",
            "service": "ai-solver",
            "version": "1.0.0",
            "timestamp": utc_now().isoformat(),
            "session_id": session_id,
            "checks": {
                "database": "ok",  # TODO: Actual DB health check
                "swe_agent": "ok",  # TODO: Actual SWE-agent health check
                "docker": "ok",  # TODO: Actual Docker health check
                "storage": "ok",  # TODO: Actual storage health check
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get solver health: {str(e)}",
        )


# ============================================================================
# DEBUG ENDPOINTS - For testing and debugging
# ============================================================================

@router.get("/debug/test-gitingest", response_model=dict)
async def test_gitingest_extraction():
    """Debug endpoint to test GitIngest extraction without requiring authentication."""
    try:
        from repo_processorGitIngest.scraper_script import extract_repository_data

        # Test with a simple public repository
        test_repo_url = "https://github.com/octocat/Hello-World"

        logger.info(f"[Debug] Testing GitIngest extraction for: {test_repo_url}")
        result = await extract_repository_data(test_repo_url, max_file_size=50000)

        if "error" in result:
            logger.error(f"[Debug] GitIngest extraction failed: {result['error']}")
            return {
                "success": False,
                "error": result["error"],
                "timestamp": result.get("timestamp")
            }

        files = result.get("files", [])
        logger.info(f"[Debug] Successfully extracted {len(files)} files")

        return {
            "success": True,
            "repository_url": test_repo_url,
            "files_count": len(files),
            "files": [
                {
                    "path": f["path"],
                    "type": f["type"],
                    "content_size": f["content_size"],
                    "has_content": len(f.get("content", "")) > 0
                }
                for f in files[:10]  # Show first 10 files
            ],
            "timestamp": result.get("extraction_info", {}).get("timestamp")
        }

    except Exception as e:
        logger.error(f"[Debug] Test endpoint failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": utc_now().isoformat()
        }


# ============================================================================
# ISSUES ENDPOINTS - Consolidated under sessions context
# ============================================================================


@router.post("/sessions/{session_id}/issues/create-with-context", response_model=dict)
async def create_issue_with_context_for_session(
    session_id: str,
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create an issue with context for a session using consolidated LLM generation and database storage
    """
    try:
        from .IssueOps import IssueService as IssueOpsService
        from .session_service import SessionService

        # Ensure session exists and belongs to user
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )

        # Use consolidated issue creation service
        issue_service = IssueOpsService(db)
        
        # Fall back to request repository_info if session repo data is incomplete
        repo_owner = db_session.repo_owner
        repo_name = db_session.repo_name
        
        if not repo_owner or not repo_name:
            repository_info = request.get("repository_info", {})
            if repository_info:
                repo_owner = repository_info.get("owner") or repo_owner
                repo_name = repository_info.get("name") or repo_name
        
        result = await issue_service.create_issue_with_context(
            user_id=current_user.id,
            session_id=session_id,
            title=request.get("title", ""),
            description=request.get("description", ""),
            chat_messages=request.get("chat_messages", []),
            file_context=request.get("file_context", []),
            repo_owner=repo_owner,
            repo_name=repo_name,
            priority=request.get("priority", "medium"),
            create_github_issue=False,  # We'll create GitHub issue separately in the modal
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create issue with context: {str(e)}",
        )


@router.get("/sessions/{session_id}/issues", response_model=List[UserIssueResponse])
async def get_issues_for_session(
    session_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None, alias="priority"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get issues for a session - Consolidated from issue_service.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Import issue service functionality
        from models import UserIssue

        # Build query
        query = db.query(UserIssue).filter(
            UserIssue.user_id == current_user.id, UserIssue.session_id == session_id
        )

        # Apply filters
        if status_filter:
            query = query.filter(UserIssue.status == status_filter)
        if priority:
            query = query.filter(UserIssue.priority == priority)

        # Apply pagination and ordering
        issues = query.order_by(UserIssue.created_at.desc()).limit(limit).all()

        return [
            {
                "id": issue.id,
                "issue_id": issue.issue_id,
                "user_id": issue.user_id,
                "title": issue.title,
                "description": issue.description,
                "issue_text_raw": issue.issue_text_raw,
                "issue_steps": issue.issue_steps,
                "session_id": issue.session_id,
                "context_card_id": issue.context_card_id,
                "context_cards": issue.context_cards,
                "ideas": issue.ideas,
                "repo_owner": issue.repo_owner,
                "repo_name": issue.repo_name,
                "priority": issue.priority,
                "status": issue.status,
                "agent_response": issue.agent_response,
                "processing_time": issue.processing_time,
                "tokens_used": issue.tokens_used,
                "github_issue_url": issue.github_issue_url,
                "github_issue_number": issue.github_issue_number,
                "created_at": issue.created_at,
                "updated_at": issue.updated_at,
                "processed_at": issue.processed_at,
            }
            for issue in issues
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get issues: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/issues/{issue_id}", response_model=UserIssueResponse
)
async def get_issue_for_session(
    session_id: str,
    issue_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific issue for a session - Consolidated from issue_service.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Import issue service functionality
        from models import UserIssue

        # Get the issue
        issue = (
            db.query(UserIssue)
            .filter(
                UserIssue.user_id == current_user.id,
                UserIssue.issue_id == issue_id,
                UserIssue.session_id == session_id,
            )
            .first()
        )

        if not issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
            )

        return {
            "id": issue.id,
            "issue_id": issue.issue_id,
            "user_id": issue.user_id,
            "title": issue.title,
            "description": issue.description,
            "issue_text_raw": issue.issue_text_raw,
            "issue_steps": issue.issue_steps,
            "session_id": issue.session_id,
            "context_card_id": issue.context_card_id,
            "context_cards": issue.context_cards,
            "ideas": issue.ideas,
            "repo_owner": issue.repo_owner,
            "repo_name": issue.repo_name,
            "priority": issue.priority,
            "status": issue.status,
            "agent_response": issue.agent_response,
            "processing_time": issue.processing_time,
            "tokens_used": issue.tokens_used,
            "github_issue_url": issue.github_issue_url,
            "github_issue_number": issue.github_issue_number,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "processed_at": issue.processed_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get issue: {str(e)}",
        )


@router.put(
    "/sessions/{session_id}/issues/{issue_id}/status", response_model=UserIssueResponse
)
async def update_issue_status_for_session(
    session_id: str,
    issue_id: str,
    status: str,
    agent_response: Optional[str] = None,
    processing_time: Optional[float] = None,
    tokens_used: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update issue status for a session - Consolidated from issue_service.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Import issue service functionality
        from daifuUserAgent.IssueOps import IssueService

        # Update issue status
        issue_service = IssueService(db)
        updated_issue = issue_service.update_issue_status(
            current_user.id,
            issue_id,
            status,
            agent_response,
            processing_time,
            tokens_used,
        )

        if not updated_issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
            )

        return {
            "id": updated_issue.id,
            "issue_id": updated_issue.issue_id,
            "user_id": updated_issue.user_id,
            "title": updated_issue.title,
            "description": updated_issue.description,
            "issue_text_raw": updated_issue.issue_text_raw,
            "issue_steps": updated_issue.issue_steps,
            "session_id": updated_issue.session_id,
            "context_card_id": updated_issue.context_card_id,
            "context_cards": updated_issue.context_cards,
            "ideas": updated_issue.ideas,
            "repo_owner": updated_issue.repo_owner,
            "repo_name": updated_issue.repo_name,
            "priority": updated_issue.priority,
            "status": updated_issue.status,
            "agent_response": updated_issue.agent_response,
            "processing_time": updated_issue.processing_time,
            "tokens_used": updated_issue.tokens_used,
            "github_issue_url": updated_issue.github_issue_url,
            "github_issue_number": updated_issue.github_issue_number,
            "created_at": updated_issue.created_at,
            "updated_at": updated_issue.updated_at,
            "processed_at": updated_issue.processed_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update issue status: {str(e)}",
        )


@router.post(
    "/sessions/{session_id}/issues/{issue_id}/create-github-issue", response_model=dict
)
async def create_github_issue_from_user_issue_for_session(
    session_id: str,
    issue_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create GitHub issue from user issue for a session - Consolidated from issue_service.py
    """
    try:
        # Use the consolidated IssueOps service directly to avoid wrapper arg mismatch
        from .IssueOps import IssueService as IssueOpsService
        from .session_service import SessionService

        # Ensure session exists and belongs to user
        SessionService.ensure_owned_session(db, current_user.id, session_id)

        # Create GitHub issue using consolidated IssueOps
        issue_service = IssueOpsService(db)
        result = await issue_service.create_github_issue_from_user_issue(
            current_user.id, issue_id
        )

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Issue not found or missing repository information",
            )

        return {
            "success": True,
            "issue": {
                "id": result.id,
                "issue_id": result.issue_id,
                "title": result.title,
                "description": result.description,
                "issue_text_raw": result.issue_text_raw,
                "issue_steps": result.issue_steps,
                "session_id": result.session_id,
                "context_card_id": result.context_card_id,
                "context_cards": result.context_cards,
                "ideas": result.ideas,
                "repo_owner": result.repo_owner,
                "repo_name": result.repo_name,
                "priority": result.priority,
                "status": result.status,
                "agent_response": result.agent_response,
                "processing_time": result.processing_time,
                "tokens_used": result.tokens_used,
                "github_issue_url": result.github_issue_url,
                "github_issue_number": result.github_issue_number,
                "created_at": result.created_at,
                "updated_at": result.updated_at,
                "processed_at": result.processed_at,
            },
            "github_url": result.github_issue_url,
            "message": f"GitHub issue created successfully: {result.github_issue_url}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create GitHub issue: {str(e)}",
        )
