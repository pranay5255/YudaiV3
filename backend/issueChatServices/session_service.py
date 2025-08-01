"""
Comprehensive Session Service for managing chat sessions, repository context, and unified state
This service acts as the central hub for session-based state management between frontend and backend
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from models import (
    ChatMessage,
    ChatSession,
    ContextCard,
    FileEmbedding,
    SessionResponse,
    UserIssue,
)
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session
from unified_state import StateConverter, UnifiedSessionState


class SessionService:
    """Comprehensive service class for session-based state management"""
    
    @staticmethod
    def create_session(
        db: Session,
        user_id: int,
        repo_owner: str,
        repo_name: str,
        repo_branch: str = "main",
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> SessionResponse:
        """
        Create a new session for repository-based work
        Sessions are the primary key for all frontend-backend state sharing
        """
        # Generate session ID based on repo and timestamp
        timestamp = int(datetime.utcnow().timestamp())
        session_id = f"{repo_owner}_{repo_name}_{repo_branch}_{timestamp}"
        
        # Create repository context metadata
        repo_context = {
            "owner": repo_owner,
            "name": repo_name,
            "branch": repo_branch,
            "full_name": f"{repo_owner}/{repo_name}",
            "html_url": f"https://github.com/{repo_owner}/{repo_name}",
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Create new session
        session = ChatSession(
            user_id=user_id,
            session_id=session_id,
            title=title or f"Session for {repo_owner}/{repo_name}",
            description=description or f"Working session for {repo_owner}/{repo_name} on {repo_branch} branch",
            repo_owner=repo_owner,
            repo_name=repo_name,
            repo_branch=repo_branch,
            repo_context=repo_context,
            is_active=True,
            total_messages=0,
            total_tokens=0,
            last_activity=datetime.utcnow()
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return SessionResponse.model_validate(session)
    
    @staticmethod
    def get_or_create_session(
        db: Session,
        user_id: int,
        repo_owner: str,
        repo_name: str,
        repo_branch: str = "main",
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> SessionResponse:
        """
        Get existing active session or create new one for repository
        Ensures one active session per repository-branch combination
        """
        # Try to find existing active session for this repo
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.repo_owner == repo_owner,
                ChatSession.repo_name == repo_name,
                ChatSession.repo_branch == repo_branch,
                ChatSession.is_active
            )
        ).first()
        
        if session:
            # Update last activity and return existing session
            session.last_activity = datetime.utcnow()
            db.commit()
            db.refresh(session)
            return SessionResponse.model_validate(session)
        
        # Create new session if none exists
        return SessionService.create_session(
            db, user_id, repo_owner, repo_name, repo_branch, title, description
        )
    
    @staticmethod
    def get_session_by_id(
        db: Session,
        user_id: int,
        session_id: str
    ) -> Optional[SessionResponse]:
        """Get a specific session by session_id"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
        
        return SessionResponse.model_validate(session)
    
    @staticmethod
    def get_user_sessions(
        db: Session,
        user_id: int,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        limit: int = 50
    ) -> List[SessionResponse]:
        """Get user sessions with optional repository filtering"""
        query = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.is_active
            )
        )
        
        if repo_owner:
            query = query.filter(ChatSession.repo_owner == repo_owner)
        if repo_name:
            query = query.filter(ChatSession.repo_name == repo_name)
        
        sessions = query.order_by(desc(ChatSession.last_activity)).limit(limit).all()
        
        return [SessionResponse.model_validate(session) for session in sessions]
    
    @staticmethod
    def touch_session(
        db: Session,
        user_id: int,
        session_id: str
    ) -> Optional[SessionResponse]:
        """Update last_activity timestamp for session keep-alive"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
        
        session.last_activity = datetime.utcnow()
        db.commit()
        db.refresh(session)
        
        return SessionResponse.model_validate(session)
    
    @staticmethod
    def get_comprehensive_session_context(
        db: Session,
        user_id: int,
        session_id: str
    ) -> Optional[UnifiedSessionState]:
        """
        Get complete session context and return it as a UnifiedSessionState object
        """
        # Get session
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
        
        # Get all related data
        messages = db.query(ChatMessage).filter(ChatMessage.session_id == session.id).order_by(ChatMessage.created_at).all()
        
        context_card_ids = set()
        for msg in messages:
            if msg.context_cards:
                context_card_ids.update(msg.context_cards)
        
        context_cards = db.query(ContextCard).filter(ContextCard.id.in_(list(context_card_ids))).all() if context_card_ids else []
        
        # Note: File embeddings are kept in database only for filedeps functionality
        # They are not included in real-time frontend state
        
        # Convert to unified state
        unified_state = StateConverter.chat_session_to_unified(
            chat_session=session,
            messages=messages,
            context_cards=context_cards
        )
        
        return unified_state
    
    @staticmethod
    def update_session_statistics(
        db: Session,
        session_id: int,
        message_tokens: int = 0,
        increment_messages: int = 0
    ) -> bool:
        """Update session statistics when messages are added"""
        session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
        
        if not session:
            return False
        
        session.total_messages += increment_messages
        session.total_tokens += message_tokens
        session.last_activity = datetime.utcnow()
        
        db.commit()
        return True
    
    @staticmethod
    def deactivate_session(
        db: Session,
        user_id: int,
        session_id: str
    ) -> bool:
        """Deactivate a session (soft delete)"""
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
    def update_session_title(
        db: Session,
        user_id: int,
        session_id: str,
        title: str
    ) -> Optional[SessionResponse]:
        """Update session title"""
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
        
        return SessionResponse.model_validate(session)
    
    @staticmethod
    def get_session_statistics(
        db: Session,
        user_id: int,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get detailed statistics for a session"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
        
        # Count messages by type
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
        
        # Count file embeddings
        file_embeddings_count = db.query(FileEmbedding).filter(
            FileEmbedding.session_id == session.id
        ).count()
        
        # Count user issues
        user_issues_count = db.query(UserIssue).filter(
            UserIssue.chat_session_id == session.id
        ).count()
        
        return {
            "session_id": session.session_id,
            "total_messages": session.total_messages,
            "total_tokens": session.total_tokens,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "file_embeddings_count": file_embeddings_count,
            "user_issues_count": user_issues_count,
            "created_at": session.created_at,
            "last_activity": session.last_activity,
            "repository_info": session.repo_context
        }
