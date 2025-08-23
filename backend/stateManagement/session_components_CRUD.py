"""
Component CRUD Routes for Session Management
Handles chat messages, file dependencies, and context cards within sessions
"""
import logging
from typing import List

from auth.github_oauth import get_current_user
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models import (
    ChatMessage,
    ChatMessageResponse,
    ChatSession,
    ContextCard,
    ContextCardResponse,
    CreateChatMessageRequest,
    CreateContextCardRequest,
    CreateFileEmbeddingRequest,
    FileEmbedding,
    FileEmbeddingResponse,
    UpdateChatMessageRequest,
    UpdateContextCardRequest,
    UpdateFileEmbeddingRequest,
    User,
)
from sqlalchemy import and_
from sqlalchemy.orm import Session

from utils import utc_now

logger = logging.getLogger(__name__)
router = APIRouter()

# ============================================================================
# CHAT MESSAGES CRUD
# ============================================================================

@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def add_chat_message(
    session_id: str,
    request: CreateChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new chat message to a session"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Create chat message
        message = ChatMessage(
            session_id=session.id,
            message_id=request.message_id,
            message_text=request.message_text,
            sender_type=request.sender_type,
            role=request.role,
            is_code=request.is_code,
            tokens=request.tokens,
            model_used=request.model_used,
            processing_time=request.processing_time,
            context_cards=request.context_cards,
            referenced_files=request.referenced_files,
            error_message=request.error_message
        )
        
        db.add(message)
        
        # Update session statistics
        session.total_messages += 1
        session.total_tokens += request.tokens
        session.last_activity = utc_now()
        
        db.commit()
        db.refresh(message)
        
        return ChatMessageResponse.model_validate(message)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding chat message: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add chat message"
        )

## (messages list endpoint defined below)

@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    session_id: str,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chat messages for a session"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at).limit(limit).all()
        
        return [ChatMessageResponse.model_validate(msg) for msg in messages]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting chat messages: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve chat messages"
        )

@router.delete("/sessions/{session_id}/messages/{message_id}")
async def delete_chat_message(
    session_id: str,
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a chat message from a session"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Find and delete message
        message = db.query(ChatMessage).filter(
            and_(
                ChatMessage.session_id == session.id,
                ChatMessage.message_id == message_id
            )
        ).first()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Update session statistics
        session.total_messages -= 1
        session.total_tokens -= message.tokens
        session.last_activity = utc_now()
        
        db.delete(message)
        db.commit()
        
        return {"success": True, "message": "Chat message deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting chat message: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete chat message"
        )

@router.put("/sessions/{session_id}/messages/{message_id}", response_model=ChatMessageResponse)
async def update_chat_message(
    session_id: str,
    message_id: str,
    updates: UpdateChatMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a chat message"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Find the message to update
        message = db.query(ChatMessage).filter(
            and_(
                ChatMessage.session_id == session.id,
                ChatMessage.message_id == message_id
            )
        ).first()
        
        if not message:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message not found"
            )
        
        # Apply updates only for non-None fields
        update_data = updates.model_dump(exclude_unset=True)
        old_tokens = message.tokens
        
        for field, value in update_data.items():
            setattr(message, field, value)
        
        message.updated_at = utc_now()
        
        # Update session statistics if tokens changed
        if 'tokens' in update_data:
            token_diff = message.tokens - old_tokens
            session.total_tokens += token_diff
            session.last_activity = utc_now()
        
        db.commit()
        db.refresh(message)
        
        return ChatMessageResponse.model_validate(message)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating chat message: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update chat message"
        )

@router.post("/sessions/{session_id}/messages/bulk", response_model=List[ChatMessageResponse])
async def bulk_add_messages(
    session_id: str,
    messages: List[CreateChatMessageRequest],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add multiple chat messages to a session in bulk"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        created_messages = []
        total_tokens = 0
        
        for request in messages:
            # Create chat message
            message = ChatMessage(
                session_id=session.id,
                message_id=request.message_id,
                message_text=request.message_text,
                sender_type=request.sender_type,
                role=request.role,
                is_code=request.is_code,
                tokens=request.tokens,
                model_used=request.model_used,
                processing_time=request.processing_time,
                context_cards=request.context_cards,
                referenced_files=request.referenced_files,
                error_message=request.error_message
            )
            
            db.add(message)
            created_messages.append(message)
            total_tokens += request.tokens
        
        # Update session statistics
        session.total_messages += len(messages)
        session.total_tokens += total_tokens
        session.last_activity = utc_now()
        
        db.commit()
        
        # Refresh all messages
        for message in created_messages:
            db.refresh(message)
        
        return [ChatMessageResponse.model_validate(msg) for msg in created_messages]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk adding chat messages: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk add chat messages"
        )

# ============================================================================
# CONTEXT CARDS CRUD
# ============================================================================

@router.post("/sessions/{session_id}/context-cards", response_model=ContextCardResponse)
async def add_context_card(
    session_id: str,
    request: CreateContextCardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new context card to a session"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Create context card
        context_card = ContextCard(
            user_id=current_user.id,
            session_id=session.id,
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
        
        return ContextCardResponse.model_validate(context_card)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding context card: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add context card"
        )

@router.get("/sessions/{session_id}/context-cards", response_model=List[ContextCardResponse])
async def get_context_cards(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get context cards for a session"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        context_cards = db.query(ContextCard).filter(
            and_(
                ContextCard.user_id == current_user.id,
                ContextCard.session_id == session.id,
                ContextCard.is_active
            )
        ).all()
        
        return [ContextCardResponse.model_validate(card) for card in context_cards]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting context cards: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve context cards"
        )

@router.delete("/sessions/{session_id}/context-cards/{card_id}")
async def delete_context_card(
    session_id: str,
    card_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a context card from a session"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Find and delete context card
        context_card = db.query(ContextCard).filter(
            and_(
                ContextCard.id == card_id,
                ContextCard.user_id == current_user.id,
                ContextCard.session_id == session.id
            )
        ).first()
        
        if not context_card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Context card not found"
            )
        
        context_card.is_active = False
        db.commit()
        
        return {"success": True, "message": "Context card deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting context card: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete context card"
        )

@router.put("/sessions/{session_id}/context-cards/{card_id}", response_model=ContextCardResponse)
async def update_context_card(
    session_id: str,
    card_id: int,
    updates: UpdateContextCardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a context card"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Find the context card to update
        context_card = db.query(ContextCard).filter(
            and_(
                ContextCard.id == card_id,
                ContextCard.user_id == current_user.id,
                ContextCard.session_id == session.id
            )
        ).first()
        
        if not context_card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Context card not found"
            )
        
        # Apply updates only for non-None fields
        update_data = updates.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(context_card, field, value)
        
        context_card.updated_at = utc_now()
        
        db.commit()
        db.refresh(context_card)
        
        return ContextCardResponse.model_validate(context_card)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating context card: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update context card"
        )

@router.post("/sessions/{session_id}/context-cards/bulk", response_model=List[ContextCardResponse])
async def bulk_add_context_cards(
    session_id: str,
    cards: List[CreateContextCardRequest],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add multiple context cards to a session in bulk"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        created_cards = []
        
        for request in cards:
            # Create context card
            context_card = ContextCard(
                user_id=current_user.id,
                session_id=session.id,
                title=request.title,
                description=request.description,
                content=request.content,
                source=request.source,
                tokens=request.tokens,
                is_active=True
            )
            
            db.add(context_card)
            created_cards.append(context_card)
        
        db.commit()
        
        # Refresh all cards
        for card in created_cards:
            db.refresh(card)
        
        return [ContextCardResponse.model_validate(card) for card in created_cards]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk adding context cards: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk add context cards"
        )

# ============================================================================
# FILE DEPENDENCIES CRUD
# ============================================================================

@router.post("/sessions/{session_id}/file-dependencies", response_model=FileEmbeddingResponse)
async def add_file_dependency(
    session_id: str,
    request: CreateFileEmbeddingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a new file dependency to a session"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Create file embedding
        file_embedding = FileEmbedding(
            session_id=session.id,
            file_path=request.file_path,
            file_name=request.file_name,
            file_type=request.file_type,
            file_content=request.file_content,
            chunk_text=request.chunk_text,
            chunk_index=request.chunk_index,
            tokens=request.tokens,
            file_metadata=request.file_metadata
        )
        
        db.add(file_embedding)
        db.commit()
        db.refresh(file_embedding)
        
        return FileEmbeddingResponse.model_validate(file_embedding)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding file dependency: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add file dependency"
        )

@router.get("/sessions/{session_id}/file-dependencies", response_model=List[FileEmbeddingResponse])
async def get_file_dependencies(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get file dependencies for a session"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        file_embeddings = db.query(FileEmbedding).filter(
            FileEmbedding.session_id == session.id
        ).all()
        
        return [FileEmbeddingResponse.model_validate(emb) for emb in file_embeddings]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file dependencies: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve file dependencies"
        )

@router.delete("/sessions/{session_id}/file-deps/{file_id}")
async def delete_file_dependency(
    session_id: str,
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a file dependency from a session"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Find and delete file embedding
        file_embedding = db.query(FileEmbedding).filter(
            and_(
                FileEmbedding.id == file_id,
                FileEmbedding.session_id == session.id
            )
        ).first()
        
        if not file_embedding:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File dependency not found"
            )
        
        db.delete(file_embedding)
        db.commit()
        
        return {"success": True, "message": "File dependency deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting file dependency: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete file dependency"
        )

@router.put("/sessions/{session_id}/file-deps/{file_id}", response_model=FileEmbeddingResponse)
async def update_file_dependency(
    session_id: str,
    file_id: int,
    updates: UpdateFileEmbeddingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a file dependency"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Find the file embedding to update
        file_embedding = db.query(FileEmbedding).filter(
            and_(
                FileEmbedding.id == file_id,
                FileEmbedding.session_id == session.id
            )
        ).first()
        
        if not file_embedding:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File dependency not found"
            )
        
        # Apply updates only for non-None fields
        update_data = updates.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(file_embedding, field, value)
        
        file_embedding.updated_at = utc_now()
        
        db.commit()
        db.refresh(file_embedding)
        
        return FileEmbeddingResponse.model_validate(file_embedding)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating file dependency: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update file dependency"
        )

@router.post("/sessions/{session_id}/file-deps/bulk", response_model=List[FileEmbeddingResponse])
async def bulk_add_file_dependencies(
    session_id: str,
    deps: List[CreateFileEmbeddingRequest],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add multiple file dependencies to a session in bulk"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        created_embeddings = []
        
        for request in deps:
            # Create file embedding
            file_embedding = FileEmbedding(
                session_id=session.id,
                file_path=request.file_path,
                file_name=request.file_name,
                file_type=request.file_type,
                file_content=request.file_content,
                chunk_text=request.chunk_text,
                chunk_index=request.chunk_index,
                tokens=request.tokens,
                file_metadata=request.file_metadata
            )
            
            db.add(file_embedding)
            created_embeddings.append(file_embedding)
        
        db.commit()
        
        # Refresh all embeddings
        for embedding in created_embeddings:
            db.refresh(embedding)
        
        return [FileEmbeddingResponse.model_validate(emb) for emb in created_embeddings]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk adding file dependencies: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bulk add file dependencies"
        )


@router.get("/sessions/{session_id}/file-deps/session", response_model=List[FileEmbeddingResponse])
async def get_file_dependencies_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get file dependencies for a session (compatible with FileDependencies.tsx)"""
    try:
        # Verify session ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Get file embeddings for this session
        file_embeddings = db.query(FileEmbedding).filter(
            FileEmbedding.session_id == session.id
        ).order_by(FileEmbedding.file_path, FileEmbedding.chunk_index).all()
        
        return [FileEmbeddingResponse.model_validate(emb) for emb in file_embeddings]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session file dependencies: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session file dependencies"
        )