"""
Centralized Session Validator Service for DAifu Agent
Eliminates duplication in session validation logic
"""

from fastapi import HTTPException, status
from issueChatServices.session_service import SessionService
from sqlalchemy.orm import Session


class SessionValidator:
    """Centralized service for session validation"""
    
    @staticmethod
    def validate_session_id(session_id: str) -> str:
        """
        Validate that session_id is provided and not empty
        
        Args:
            session_id: Session ID to validate
            
        Returns:
            Validated session_id
            
        Raises:
            HTTPException: If session_id is missing or empty
        """
        if not session_id or not session_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id is required and cannot be empty"
            )
        return session_id.strip()
    
    @staticmethod
    def validate_session_exists(
        db: Session,
        user_id: int,
        session_id: str,
        touch_session: bool = True
    ):
        """
        Validate that session exists and belongs to user
        
        Args:
            db: Database session
            user_id: User ID
            session_id: Session ID to validate
            touch_session: Whether to update session activity timestamp
            
        Returns:
            Session object if valid
            
        Raises:
            HTTPException: If session doesn't exist or doesn't belong to user
        """
        # Validate session_id format
        session_id = SessionValidator.validate_session_id(session_id)
        
        # Check if session exists and belongs to user
        if touch_session:
            session = SessionService.touch_session(db, user_id, session_id)
        else:
            session = SessionService.get_session_by_id(db, user_id, session_id)
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} not found or access denied"
            )
        
        return session
    
    @staticmethod
    def validate_session_active(
        db: Session,
        user_id: int,
        session_id: str,
        touch_session: bool = True
    ):
        """
        Validate that session exists, belongs to user, and is active
        
        Args:
            db: Database session
            user_id: User ID
            session_id: Session ID to validate
            touch_session: Whether to update session activity timestamp
            
        Returns:
            Session object if valid and active
            
        Raises:
            HTTPException: If session doesn't exist, doesn't belong to user, or is inactive
        """
        session = SessionValidator.validate_session_exists(db, user_id, session_id, touch_session)
        
        if not session.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session {session_id} is not active"
            )
        
        return session
    
    @staticmethod
    def validate_conversation_id(conversation_id: str) -> str:
        """
        Validate conversation_id (alias for session_id for backward compatibility)
        
        Args:
            conversation_id: Conversation ID to validate
            
        Returns:
            Validated conversation_id
            
        Raises:
            HTTPException: If conversation_id is missing or empty
        """
        if not conversation_id or not conversation_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="conversation_id (session_id) is required and cannot be empty"
            )
        return conversation_id.strip()
    
    @staticmethod
    def validate_conversation_exists(
        db: Session,
        user_id: int,
        conversation_id: str,
        touch_session: bool = True
    ):
        """
        Validate conversation_id exists (alias for session validation)
        
        Args:
            db: Database session
            user_id: User ID
            conversation_id: Conversation ID to validate
            touch_session: Whether to update session activity timestamp
            
        Returns:
            Session object if valid
            
        Raises:
            HTTPException: If conversation doesn't exist or doesn't belong to user
        """
        # conversation_id is just an alias for session_id
        return SessionValidator.validate_session_exists(db, user_id, conversation_id, touch_session) 