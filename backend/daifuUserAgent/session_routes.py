#!/usr/bin/env python3
"""
Session Management Routes for DAifu Agent

This module provides FastAPI routes for session management,
including session creation, context management, messages, and file dependencies.
"""

import uuid
from datetime import datetime
from typing import List

from auth.github_oauth import get_current_user
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models import (
    ChatMessage,
    ChatMessageResponse,
    ChatSession,
    ContextCard,
    ContextCardResponse,
    CreateContextCardRequest,
    CreateSessionRequest,
    FileEmbedding,
    FileEmbeddingResponse,
    SessionContextResponse,
    SessionResponse,
    User,
)
from sqlalchemy.orm import Session

router = APIRouter(tags=["sessions"])

# CRITICAL PRIORITY ENDPOINTS

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
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
            last_activity=datetime.utcnow()
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
            last_activity=db_session.last_activity
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}"
        )

@router.get("/sessions/{session_id}", response_model=SessionContextResponse)
async def get_session_context(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get session context including messages, context cards, and repository info.
    This is a CRITICAL endpoint required for session loading.
    """
    try:
        # Get session from database with user verification
        db_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Get session messages
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == db_session.id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        # Get context cards for this session
        context_cards = db.query(ContextCard).filter(
            ContextCard.session_id == db_session.id,
            ContextCard.is_active
        ).all()
        
        # Get file embeddings for this session
        file_embeddings = db.query(FileEmbedding).filter(
            FileEmbedding.session_id == db_session.id
        ).all()
        
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
            last_activity=db_session.last_activity
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
                updated_at=msg.updated_at
            ) for msg in messages
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
                updated_at=card.updated_at
            ) for card in context_cards
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
                created_at=fe.created_at
            ) for fe in file_embeddings
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
                "html_url": f"https://github.com/{db_session.repo_owner}/{db_session.repo_name}"
            } if db_session.repo_owner and db_session.repo_name else None,
            file_embeddings_count=len(file_embeddings),
            statistics={
                "total_messages": db_session.total_messages,
                "total_tokens": db_session.total_tokens,
                "session_duration": int((datetime.utcnow() - db_session.created_at).total_seconds()) if db_session.created_at else 0
            },
            user_issues=[],
            file_embeddings=file_embedding_responses
        )
        
        return context_response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session context: {str(e)}"
        )

# HIGH PRIORITY ENDPOINTS

@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def add_chat_message(
    session_id: str,
    message_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a new chat message to a session.
    This endpoint is used by the chat system to store messages.
    """
    try:
        # Verify session exists and belongs to user
        db_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
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
            error_message=message_data.get("error_message")
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
            updated_at=message.updated_at
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add message: {str(e)}"
        )

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get chat messages for a session.
    This is a HIGH priority endpoint for chat history display.
    """
    try:
        # Verify session exists and belongs to user
        db_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Get messages for this session
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == db_session.id
        ).order_by(ChatMessage.created_at.asc()).limit(limit).all()
        
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
                updated_at=msg.updated_at
            ) for msg in messages
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat messages: {str(e)}"
        )

@router.post("/sessions/{session_id}/context-cards", response_model=ContextCardResponse)
async def add_context_card(
    session_id: str,
    request: CreateContextCardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add a context card to a session.
    This is a HIGH priority endpoint for context management.
    """
    try:
        # Verify session exists and belongs to user
        db_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
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
            is_active=True
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
            updated_at=context_card.updated_at
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add context card: {str(e)}"
        )

@router.get("/sessions/{session_id}/context-cards", response_model=List[ContextCardResponse])
async def get_context_cards(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get context cards for a session.
    This is a HIGH priority endpoint for context display.
    """
    try:
        # Verify session exists and belongs to user
        db_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Get active context cards for this session
        context_cards = db.query(ContextCard).filter(
            ContextCard.session_id == db_session.id,
            ContextCard.is_active
        ).order_by(ContextCard.created_at.desc()).all()
        
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
                updated_at=card.updated_at
            ) for card in context_cards
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context cards: {str(e)}"
        )

# MEDIUM PRIORITY ENDPOINTS

@router.delete("/sessions/{session_id}/context-cards/{card_id}")
async def delete_context_card(
    session_id: str,
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a context card from a session.
    This is a MEDIUM priority endpoint for context cleanup.
    """
    try:
        # Verify session exists and belongs to user
        db_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Find and verify context card belongs to this session and user
        context_card = db.query(ContextCard).filter(
            ContextCard.id == card_id,
            ContextCard.session_id == db_session.id,
            ContextCard.user_id == current_user.id
        ).first()
        
        if not context_card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Context card not found"
            )
        
        # Soft delete by setting is_active to False
        context_card.is_active = False
        db.commit()
        
        return {"success": True, "message": "Context card deleted successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete context card: {str(e)}"
        )

@router.get("/sessions/{session_id}/file-deps/session", response_model=List[FileEmbeddingResponse])
async def get_file_dependencies_for_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get file dependencies/embeddings for a session.
    This is a MEDIUM priority endpoint for file context display.
    """
    try:
        # Verify session exists and belongs to user
        db_session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id
        ).first()
        
        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Get file embeddings for this session
        file_embeddings = db.query(FileEmbedding).filter(
            FileEmbedding.session_id == db_session.id
        ).order_by(FileEmbedding.created_at.desc()).all()
        
        return [
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
                created_at=fe.created_at
            ) for fe in file_embeddings
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file dependencies: {str(e)}"
        )
