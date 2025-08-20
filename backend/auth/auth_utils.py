"""
Simplified authentication utilities - only create and validate tokens
"""
import logging
import secrets
import string
from datetime import timedelta
from typing import Optional

from fastapi import HTTPException, status
from models import SessionToken, User
from sqlalchemy.orm import Session

from utils import utc_now

logger = logging.getLogger(__name__)

def generate_session_token(length: int = 32) -> str:
    """Generate a secure random session token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_session_token(db: Session, user_id: int, expires_in_hours: int = 24) -> SessionToken:
    """Create a new session token for a user - simplified version"""
    try:
        logger.info(f"Creating session token for user_id: {user_id}")
        
        # Generate new session token
        session_token = generate_session_token()
        expires_at = utc_now() + timedelta(hours=expires_in_hours)
        
        # Create new session token
        db_session_token = SessionToken(
            user_id=user_id,
            session_token=session_token,
            expires_at=expires_at,
            is_active=True
        )
        
        db.add(db_session_token)
        db.commit()
        db.refresh(db_session_token)
        
        logger.info(f"Successfully created session token with ID: {db_session_token.id}")
        return db_session_token
        
    except Exception as e:
        logger.error(f"Error creating session token for user {user_id}: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session token"
        )

def validate_session_token(db: Session, session_token: str) -> Optional[User]:
    """Validate a session token and return the associated user"""
    try:
        if not session_token:
            logger.debug("No session token provided for validation")
            return None
        
        logger.debug(f"Validating session token: {session_token[:10]}...")
        
        # Find active session token
        
        db_session_token = db.query(SessionToken).filter(
            SessionToken.session_token == session_token,
            SessionToken.is_active
        ).first()
        
        if not db_session_token:
            logger.debug(f"No active session token found: {session_token[:10]}...")
            return None
        
        # Check if token is expired
        if db_session_token.expires_at < utc_now():
            logger.info(f"Session token expired: {session_token[:10]}...")
            return None
        
        # Get user
        user = db.query(User).filter(User.id == db_session_token.user_id).first()
        
        if not user:
            logger.warning(f"User not found for valid session token: {session_token[:10]}...")
            return None
        
        logger.debug(f"Successfully validated session token for user: {user.github_username}")
        return user
        
    except Exception as e:
        logger.error(f"Error validating session token: {str(e)}", exc_info=True)
        return None
