#!/usr/bin/env python3
"""
Session Management Routes for DAifu Agent

This module provides FastAPI routes for session management,
including session creation, context management, messages, and file dependencies.

TODO: Complete Implementation Tasks
========================================

CRITICAL ISSUES:
1. LLM Service Integration
   - The chat endpoint calls LLMService.generate_response_with_history() which doesn't exist
   - Need to implement or import proper LLM service integration
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
import json

# Import chat functionality from chat_api
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from auth.github_oauth import get_current_user
from daifuUserAgent.llm_service import LLMService
from db.database import get_db
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

# Import from filedeps.py
from models import (
    AISolveSession,
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
    FileEmbeddingResponse,
    FileItemResponse,
    Repository,
    RepositoryRequest,
    SessionContextResponse,
    SessionFileDependencyResponse,
    SessionResponse,
    User,
)
from pgvector.sqlalchemy import Vector
from repo_processorGitIngest.scraper_script import (
    categorize_file,
    extract_repository_data,
)
from sqlalchemy.orm import Session

router = APIRouter(tags=["sessions"])

# CRITICAL PRIORITY ENDPOINTS


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
            last_activity=datetime.utcnow(),
        )

        db.add(db_session)
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
            detail=f"Failed to create session: {str(e)}",
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
        # Get session from database with user verification
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
                    (datetime.utcnow() - db_session.created_at).total_seconds()
                )
                if db_session.created_at
                else 0,
            },
            user_issues=[],
            file_embeddings=file_embedding_responses,
        )

        return context_response

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
        db_session.last_activity = datetime.utcnow()

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

        # Get messages for this session
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == db_session.id)
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


@router.delete("/sessions/{session_id}/context-cards/{card_id}")
async def delete_context_card(
    session_id: str,
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a context card from a session.
    This is a MEDIUM priority endpoint for context cleanup.
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

        # Find and verify context card belongs to this session and user
        context_card = (
            db.query(ContextCard)
            .filter(
                ContextCard.id == card_id,
                ContextCard.session_id == db_session.id,
                ContextCard.user_id == current_user.id,
            )
            .first()
        )

        if not context_card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Context card not found"
            )

        # Soft delete by setting is_active to False
        context_card.is_active = False
        db.commit()

        return {"success": True, "message": "Context card deleted successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete context card: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/file-deps/session",
    response_model=List[SessionFileDependencyResponse],
)
async def get_file_dependencies_for_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get file dependencies for a session (file metadata only, no embeddings).
    This is a MEDIUM priority endpoint for file context display.
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

        # Get file embeddings for this session and aggregate by file
        file_embeddings = (
            db.query(FileEmbedding)
            .filter(FileEmbedding.session_id == db_session.id)
            .order_by(FileEmbedding.created_at.desc())
            .all()
        )

        # Aggregate file data by file_path to avoid duplicates
        file_data = {}
        for fe in file_embeddings:
            if fe.file_path not in file_data:
                file_data[fe.file_path] = {
                    "id": fe.id,
                    "file_name": fe.file_name,
                    "file_path": fe.file_path,
                    "file_type": fe.file_type,
                    "tokens": fe.tokens,
                    "category": fe.file_metadata.get("category")
                    if fe.file_metadata
                    else None,
                    "created_at": fe.created_at,
                }
            else:
                # Sum tokens for chunks of the same file
                file_data[fe.file_path]["tokens"] += fe.tokens

        # Convert to response format
        return [
            SessionFileDependencyResponse(**file_info)
            for file_info in file_data.values()
        ]

    except Exception as e:
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
    Chat Endpoint within Session Context - Consolidated from chat_api.py

    This endpoint processes chat messages within a specific session context.
    It validates the session exists and belongs to the user before processing.
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
        # Get GitHub context if repository info is provided
        github_context = ""
        repo_owner = db_session.repo_owner
        repo_name = db_session.repo_name

        # Check for repository object in request first (preferred format)
        if (
            request.repository
            and request.repository.get("owner")
            and request.repository.get("name")
        ):
            repo_owner = request.repository["owner"]
            repo_name = request.repository["name"]

        # Get GitHub context if we have repository information
        github_context = ""
        github_data = None
        if repo_owner and repo_name:
            # Import GitHub operations
            from daifuUserAgent.githubOps import GitHubOps

            github_ops = GitHubOps(db)

            # Get repository info
            repo_data = await github_ops.fetch_repository_info(
                repo_owner, repo_name, current_user.id
            )

            # Get recent issues and commits for context
            issues_data = await github_ops.fetch_repository_issues(
                repo_owner, repo_name, current_user.id, limit=5
            )
            commits_data = await github_ops.fetch_repository_commits(
                repo_owner, repo_name, current_user.id, limit=5
            )

            # Build context string (similar to ChatOps._build_context_string)
            context_parts = []
            if repo_data.get("name"):
                context_parts.append(f"Repository: {repo_data['name']}")
                if repo_data.get("description"):
                    context_parts.append(f"Description: {repo_data['description']}")
                if repo_data.get("language"):
                    context_parts.append(f"Primary Language: {repo_data['language']}")
                if repo_data.get("topics"):
                    context_parts.append(
                        f"Topics: {', '.join(repo_data['topics'][:5])}"
                    )

            if issues_data:
                context_parts.append(f"\nRecent Issues ({len(issues_data)}):")
                for issue in issues_data[:3]:
                    context_parts.append(f"- #{issue['number']}: {issue['title']}")

            if commits_data:
                context_parts.append(f"\nRecent Commits ({len(commits_data)}):")
                for commit in commits_data[:3]:
                    context_parts.append(f"- {commit['sha']}: {commit['message']}")

            github_context = (
                "\n".join(context_parts)
                if context_parts
                else "Repository context not available"
            )

            # Get detailed GitHub data for structured response
            github_data = await github_ops.fetch_repository_info_detailed(
                repo_owner, repo_name, current_user.id
            )

        # Add user message to conversation history
        user_message = request.message.message_text
        _add_to_conversation_history(session_id, "User", user_message, db, current_user)

        # Get conversation history for context
        history = _get_conversation_history(session_id, 50, db)

        # Get relevant file contexts for the user message
        file_contexts = await LLMService.get_relevant_file_contexts(
            db=db, session_id=db_session.id, query_text=user_message
        )

        # Generate AI response with file contexts
        reply = await LLMService.generate_response_with_history(
            repo_context=github_context,
            conversation_history=history,
            github_data=github_data,
            file_contexts=file_contexts,
        )

        # Add assistant response to conversation history
        _add_to_conversation_history(session_id, "DAifu", reply, db, current_user)

        # Update session statistics
        db_session.last_activity = datetime.utcnow()
        db.commit()

        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000

        # Generate a unique message ID
        message_id = str(uuid.uuid4())

        return ChatResponse(
            reply=reply,
            conversation=history + [("User", user_message), ("DAifu", reply)],
            message_id=message_id,
            processing_time=processing_time,
            session_id=session_id,
        )

    except HTTPException:
        raise
    except Exception as e:
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
        db_session.last_activity = datetime.utcnow()

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
    db: Session, repo_url: str, repo_name: str, repo_owner: str, user_id: int
) -> Repository:
    """Retrieve existing repository metadata or create a new record."""
    # First try to find existing repository by URL and user
    repository = (
        db.query(Repository)
        .filter(Repository.repo_url == repo_url, Repository.user_id == user_id)
        .first()
    )

    if repository:
        return repository

    # Create new repository record
    repository = Repository(
        user_id=user_id,
        name=repo_name,
        owner=repo_owner,
        full_name=f"{repo_owner}/{repo_name}",
        repo_url=repo_url,
    )
    db.add(repository)
    db.flush()
    return repository


@router.post("/sessions/{session_id}/extract", response_model=FileItemResponse)
async def extract_file_dependencies_for_session(
    session_id: str,
    request: RepositoryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Extract file dependencies for a specific session and create embeddings.

    This endpoint integrates with the session system and creates file embeddings
    that can be used for semantic search and context management.
    """
    try:
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

        # Create root FileItem node
        root_file_item = FileItemResponse(
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
            # Ensure repository metadata exists
            repository = _get_or_create_repository(
                db=db,
                repo_url=request.repo_url,
                repo_name=repo_name,
                repo_owner=repo_owner,
                user_id=current_user.id,
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
            saved_embeddings = _save_file_embeddings_to_db_with_session(
                db, repository.id, file_tree, db_session.id
            )
            print(f"Saved {len(saved_embeddings)} file embeddings")

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
    """Save file analysis results to database."""
    analysis = Repository(
        repository_id=repository_id,
        raw_data=json.dumps(raw_data),
        processed_data=json.dumps(processed_data),
        total_files=total_files,
        total_tokens=total_tokens,
        max_file_size=max_file_size,
        status="completed",
    )
    db.add(analysis)
    db.flush()
    return analysis


def _save_file_embeddings_to_db_with_session(
    db: Session, repository_id: int, file_tree: List[Dict[str, Any]], session_id: int
) -> List[FileEmbedding]:
    """Create file embeddings in database linked to session, skipping deprecated FileItem."""
    saved_embeddings = []

    def save_recursive(items: List[Dict[str, Any]]):
        for item_data in items:
            # If it's a file (not directory), create embeddings linked to session
            if not item_data["isDirectory"] and item_data.get("content"):
                embeddings = _create_file_embeddings_for_session(
                    db, session_id, repository_id, item_data, item_data["content"]
                )
                saved_embeddings.extend(embeddings)

            # Recursively process children if it's a directory
            if item_data["isDirectory"] and "children" in item_data:
                save_recursive(item_data["children"])

    save_recursive(file_tree)
    return saved_embeddings


def _create_file_embeddings_for_session(
    db: Session,
    session_id: int,
    repository_id: int,
    item_data: Dict[str, Any],
    content: str,
) -> List[FileEmbedding]:
    """
    Store file embeddings linked to session for semantic search.
    """
    from utils.chunking import create_file_chunker

    saved_embeddings: List[FileEmbedding] = []
    file_path = item_data.get("path")
    file_name = item_data.get("name")
    file_type = item_data.get("type")
    file_category = item_data.get("Category")

    try:
        chunker = create_file_chunker()
        chunks = chunker.chunk_text(content, file_path)

        for i, chunk in enumerate(chunks):
            embedding_vector = LLMService.embed_text(chunk)
            if hasattr(embedding_vector, "__await__"):
                # If embed_text is async, run it synchronously
                import asyncio

                embedding_vector = asyncio.run(embedding_vector)

            embedding = FileEmbedding(
                session_id=session_id,
                repository_id=repository_id,
                file_path=file_path,
                file_name=file_name,
                file_type=file_type,
                chunk_index=i,
                chunk_text=chunk,
                embedding=Vector(embedding_vector),
                tokens=_estimate_tokens_for_file(file_path, len(chunk)),
                file_metadata=json.dumps(
                    {
                        "category": file_category,
                        "content_size": len(content),
                    }
                ),
            )
            db.add(embedding)
            saved_embeddings.append(embedding)

        db.flush()
        return saved_embeddings

    except Exception as e:
        print(f"Error storing embeddings for {file_path}: {e}")
        return []


# ============================================================================
# SOLVER ENDPOINTS - Consolidated under sessions context
# ============================================================================


@router.post("/{session_id}/solve/start", response_model=dict)
async def start_solve_session_for_session(
    session_id: str,
    request: Optional[dict] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start AI solver for a session - Consolidated from solve_router.py

    This endpoint validates the session exists and belongs to the user,
    then starts a background AI solve session.
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

        # Get repository details from session
        if not db_session.repo_owner or not db_session.repo_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session has no associated repository",
            )

        # Prepare solve parameters
        repo_url = f"https://github.com/{db_session.repo_owner}/{db_session.repo_name}"
        branch = db_session.repo_branch or "main"
        ai_model_id = request.get("ai_model_id") if request else None
        swe_config_id = request.get("swe_config_id") if request else None

        # Import solver adapter
        from solver.ai_solver import AISolverAdapter

        # Create solver adapter
        solver = AISolverAdapter(db)

        # Create a new session record first to get the session_id
        solve_session = AISolveSession(
            user_id=current_user.id,
            issue_id=0,  # Will be set when issue is created
            status="PENDING",
            repo_url=repo_url,
            branch_name=branch,
            ai_model_id=ai_model_id,
            swe_config_id=swe_config_id,
        )
        db.add(solve_session)
        db.commit()
        db.refresh(solve_session)

        # Start solver in background task
        background_tasks.add_task(
            solver.run_solver,
            issue_id=0,  # Placeholder - will be updated when issue is created
            user_id=current_user.id,
            repo_url=repo_url,
            branch=branch,
            ai_model_id=ai_model_id,
            swe_config_id=swe_config_id,
        )

        return {
            "message": "AI Solver started successfully",
            "session_id": solve_session.id,
            "solve_session_id": solve_session.id,
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


@router.get("/{session_id}/solve/sessions/{solve_session_id}", response_model=dict)
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
    "/{session_id}/solve/sessions/{solve_session_id}/stats", response_model=dict
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
    "/{session_id}/solve/sessions/{solve_session_id}/cancel", response_model=dict
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


@router.get("/{session_id}/solve/sessions", response_model=list)
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


@router.get("/{session_id}/solve/health", response_model=dict)
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
            "timestamp": datetime.utcnow().isoformat(),
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
# ISSUES ENDPOINTS - Consolidated under sessions context
# ============================================================================


@router.post("/{session_id}/issues/create-with-context", response_model=dict)
async def create_issue_with_context_for_session(
    session_id: str,
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create an issue with context for a session using LLM-based generation
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

        # Create issue service instance
        issue_service = IssueService(db)

        # Generate issue using LLM with full context
        llm_generated_issue = await issue_service.generate_issue_from_context(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            title=request.get("title", ""),
            description=request.get("description", ""),
            chat_messages=request.get("chat_messages", []),
            file_context=request.get("file_context", []),
            repo_owner=db_session.repo_owner,
            repo_name=db_session.repo_name,
            priority=request.get("priority", "medium"),
        )

        # Update the _fetch_github_repo_context call in generate_issue_from_context to use user_id
        # This is already handled in the IssueOps._fetch_github_repo_context method

        # Create user issue in database with LLM-generated content
        from models import CreateUserIssueRequest

        issue_request = CreateUserIssueRequest(
            title=llm_generated_issue["title"],
            issue_text_raw=llm_generated_issue["body"],
            description=request.get("description", ""),
            session_id=session_id,
            context_cards=request.get("context_cards", []),
            repo_owner=db_session.repo_owner,
            repo_name=db_session.repo_name,
            priority=request.get("priority", "medium"),
            issue_steps=[
                "Analyze chat conversation context",
                "Review file dependencies and implementation details",
                "Design implementation approach based on LLM analysis",
                "Implement functionality according to specifications",
                "Add comprehensive tests and documentation",
                "Validate implementation against acceptance criteria",
            ],
        )

        user_issue = issue_service.create_user_issue(db, current_user.id, issue_request)

        return {
            "success": True,
            "preview_only": False,
            "user_issue": {
                "id": user_issue.id,
                "issue_id": user_issue.issue_id,
                "title": user_issue.title,
                "description": user_issue.description,
                "issue_text_raw": user_issue.issue_text_raw,
            },
            "github_preview": {
                "title": llm_generated_issue["title"],
                "body": llm_generated_issue["body"],
                "labels": llm_generated_issue["labels"],
                "assignees": llm_generated_issue["assignees"],
                "repository_info": {
                    "owner": db_session.repo_owner,
                    "name": db_session.repo_name,
                    "branch": db_session.repo_branch,
                },
                "metadata": {
                    "generated_by_llm": True,
                    "processing_time": llm_generated_issue["processing_time"],
                    "tokens_used": llm_generated_issue["tokens_used"],
                    "llm_model": "deepseek/deepseek-r1-0528",
                    "generated_at": datetime.utcnow().isoformat(),
                },
            },
            "llm_response": llm_generated_issue["llm_response"],
            "message": f"Issue created successfully with ID: {user_issue.issue_id}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create issue with context: {str(e)}",
        )


@router.get("/{session_id}/issues", response_model=list)
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


@router.get("/{session_id}/issues/{issue_id}", response_model=dict)
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


@router.put("/{session_id}/issues/{issue_id}/status", response_model=dict)
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


@router.post("/{session_id}/issues/{issue_id}/create-github-issue", response_model=dict)
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

        # Create GitHub issue
        issue_service = IssueService(db)
        result = await issue_service.create_github_issue_from_user_issue(
            current_user.id, issue_id, current_user
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
