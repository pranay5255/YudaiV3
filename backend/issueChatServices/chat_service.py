"""
Chat service for managing chat sessions and messages in the database
"""
import uuid
import random
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from models import (
    ChatSession, ChatMessage, User,
    CreateChatSessionRequest, CreateChatMessageRequest,
    ChatSessionResponse, ChatMessageResponse
)
from utils.langfuse_utils import chat_service_trace


class ChatService:
    """Service class for managing chat operations"""
    
    @staticmethod
    def count_tokens(text: str) -> int:
        """Simple token counting using word split - V1 implementation"""
        if not text or not text.strip():
            return 0
        return len(text.split())
    
    @staticmethod
    def generate_session_title() -> str:
        """Generate a random session title"""
        adjectives = [
            "Smart", "Bright", "Creative", "Insightful", "Productive", "Focused",
            "Efficient", "Innovative", "Dynamic", "Strategic", "Analytical", "Quick"
        ]
        nouns = [
            "Session", "Chat", "Discussion", "Conversation", "Meeting", "Brainstorm",
            "Exploration", "Analysis", "Review", "Planning", "Development", "Work"
        ]
        
        adjective = random.choice(adjectives)
        noun = random.choice(nouns)
        number = random.randint(1, 999)
        
        return f"{adjective} {noun} #{number}"
    
    @staticmethod
    @chat_service_trace
    def create_chat_session(
        db: Session, 
        user_id: int, 
        request: CreateChatSessionRequest
    ) -> ChatSessionResponse:
        """Create a new chat session"""
        # Generate title if not provided
        title = request.title
        if not title:
            title = ChatService.generate_session_title()
        
        session = ChatSession(
            user_id=user_id,
            session_id=request.session_id,
            title=title,
            description=request.description,
            is_active=True,
            total_messages=0,
            total_tokens=0,
            last_activity=datetime.utcnow()
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return ChatSessionResponse.model_validate(session)
    
    @staticmethod
    def get_chat_session(
        db: Session, 
        user_id: int, 
        session_id: str
    ) -> Optional[ChatSessionResponse]:
        """Get a chat session by session_id"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
            
        return ChatSessionResponse.model_validate(session)
    
    @staticmethod
    def get_user_chat_sessions(
        db: Session, 
        user_id: int, 
        limit: int = 50
    ) -> List[ChatSessionResponse]:
        """Get all chat sessions for a user"""
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(desc(ChatSession.last_activity)).limit(limit).all()
        
        return [ChatSessionResponse.model_validate(session) for session in sessions]
    
    @staticmethod
    @chat_service_trace
    def create_chat_message(
        db: Session,
        user_id: int,
        request: CreateChatMessageRequest
    ) -> ChatMessageResponse:
        """Create a new chat message"""
        # First, get or create the session
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == request.session_id
            )
        ).first()
        
        if not session:
            # Create a new session if it doesn't exist
            session = ChatSession(
                user_id=user_id,
                session_id=request.session_id,
                title=ChatService.generate_session_title(),
                is_active=True,
                total_messages=0,
                total_tokens=0,
                last_activity=datetime.utcnow()
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        
        # Count tokens if not provided in request
        tokens = request.tokens
        if tokens == 0:
            tokens = ChatService.count_tokens(request.message_text)
        
        # Create the message
        message = ChatMessage(
            session_id=session.id,
            message_id=request.message_id,
            message_text=request.message_text,
            sender_type=request.sender_type,
            role=request.role,
            is_code=request.is_code,
            tokens=tokens,
            model_used=request.model_used,
            context_cards=request.context_cards,
            referenced_files=request.referenced_files
        )
        
        db.add(message)
        
        # Update session statistics
        session.total_messages += 1
        session.total_tokens += tokens
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
        # First verify the session belongs to the user
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
    def update_session_title(
        db: Session,
        user_id: int,
        session_id: str,
        title: str
    ) -> Optional[ChatSessionResponse]:
        """Update the title of a chat session"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
        
        session.title = title
        session.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(session)
        
        return ChatSessionResponse.model_validate(session)
    
    @staticmethod
    def deactivate_session(
        db: Session,
        user_id: int,
        session_id: str
    ) -> bool:
        """Deactivate a chat session"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return False
        
        session.is_active = False
        session.updated_at = datetime.utcnow()
        
        db.commit()
        return True
    
    @staticmethod
    def get_session_statistics(
        db: Session,
        user_id: int,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get statistics for a chat session"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
        
        # Get message count by sender type
        user_messages = db.query(ChatMessage).filter(
            and_(
                ChatMessage.session_id == session.id,
                ChatMessage.sender_type == "user"
            )
        ).count()
        
        assistant_messages = db.query(ChatMessage).filter(
            and_(
                ChatMessage.session_id == session.id,
                ChatMessage.sender_type == "assistant"
            )
        ).count()
        
        return {
            "session_id": session.session_id,
            "total_messages": session.total_messages,
            "total_tokens": session.total_tokens,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "created_at": session.created_at,
            "last_activity": session.last_activity
        } 