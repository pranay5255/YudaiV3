"""
Streamlined Chat Service for managing chat messages within sessions
Session management is handled by SessionService - this focuses on messages only
"""
from datetime import datetime
from typing import List

from models import (
    ChatMessage,
    ChatMessageResponse,
    ChatSession,
    ChatSessionResponse,
    CreateChatMessageRequest,
)
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session


class ChatService:
    """Streamlined service class for managing chat messages within sessions"""
    
    @staticmethod
    def create_chat_message(
        db: Session,
        user_id: int,
        request: CreateChatMessageRequest
    ) -> ChatMessageResponse:
        """
        Create a new chat message within an existing session
        Note: Session must exist - use SessionService to create sessions
        """
        # Get the session (must exist)
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == request.session_id
            )
        ).first()
        
        if not session:
            raise ValueError(f"Session {request.session_id} not found for user {user_id}")
        
        # Create the message
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
        session.last_activity = datetime.utcnow()
        
        db.commit()
        db.refresh(message)
        
        return ChatMessageResponse.model_validate(message)
    
    @staticmethod
    def get_chat_messages(
        db: Session,
        user_id: int,
        session_id: str,
        limit: int = 100
    ) -> List[ChatMessageResponse]:
        """Get messages for a specific chat session"""
        # Verify session belongs to user
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return []
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at).limit(limit).all()
        
        return [ChatMessageResponse.model_validate(message) for message in messages]
    
    @staticmethod
    def get_chat_sessions(
        db: Session, 
        user_id: int, 
        limit: int = 50
    ) -> List[ChatSessionResponse]:
        """Get all chat sessions for a user (legacy support)"""
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(desc(ChatSession.last_activity)).limit(limit).all()
        
        return [ChatSessionResponse.model_validate(session) for session in sessions]


# Legacy SessionService methods moved to dedicated session_service.py
# This service now focuses only on chat message management


# FileEmbeddingService moved to dedicated file_embedding_service.py if needed
# This service now focuses only on chat message management 