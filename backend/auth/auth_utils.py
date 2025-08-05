"""
Shared authentication utilities for YudaiV3 backend
Enhanced with proper logging and atomic operations
"""
import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from models import SessionToken, User
from sqlalchemy.orm import Session

# Configure logger for this module
logger = logging.getLogger(__name__)


def handle_auth_error(e: Exception) -> HTTPException:
    """Handle authentication errors consistently across all endpoints"""
    if "Invalid or expired token" in str(e):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token. Please re-authenticate."
        )
    elif "User not found" in str(e):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found. Please re-authenticate."
        )
    else:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in."
        )


def validate_user_access(user: User, session_id: str = None) -> None:
    """Validate that user has access to the requested resource"""
    if not user or not user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid user authentication required"
        )
    
    # Additional validation can be added here
    # For example, check if user is active, has required permissions, etc.


def require_authentication(user: User) -> None:
    """Ensure user is authenticated, raise HTTPException if not"""
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )


def generate_session_token(length: int = 32) -> str:
    """Generate a secure random session token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def create_session_token(db: Session, user_id: int, expires_in_hours: int = 24) -> SessionToken:
    """
    Create a new session token for a user with atomic operations
    Always deactivates ALL existing tokens before creating a new one
    """
    try:
        logger.info(f"Creating session token for user_id: {user_id}")
        
        # Deactivate existing tokens using bulk update for efficiency
        existing_count = db.query(SessionToken).filter(
            SessionToken.user_id == user_id,
            SessionToken.is_active == True
        ).update({"is_active": False}, synchronize_session=False)
        
        if existing_count > 0:
            logger.info(f"Deactivated {existing_count} existing session tokens for user {user_id}")
        
        # Generate new session token
        session_token = generate_session_token()
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        logger.debug(f"Generated session token: {session_token[:10]}... (expires: {expires_at})")
        
        # Create new session token
        db_session_token = SessionToken(
            user_id=user_id,
            session_token=session_token,
            expires_at=expires_at,
            is_active=True
        )
        
        db.add(db_session_token)
        db.commit()  # Commit the transaction
        db.refresh(db_session_token)  # Refresh to get the ID
        
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
    """
    Validate a session token and return the associated user
    Automatically deactivates expired tokens
    """
    try:
        if not session_token:
            logger.debug("No session token provided for validation")
            return None
        
        logger.debug(f"Validating session token: {session_token[:10]}...")
        
        # Find active session token with user in a single query
        db_session_token = db.query(SessionToken).filter(
            SessionToken.session_token == session_token,
            SessionToken.is_active == True
        ).first()
        
        if not db_session_token:
            logger.debug(f"No active session token found: {session_token[:10]}...")
            return None
        
        # Check if token is expired
        if db_session_token.expires_at < datetime.utcnow():
            logger.info(f"Session token expired, deactivating: {session_token[:10]}...")
            db_session_token.is_active = False
            db.commit()
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


def deactivate_session_token(db: Session, session_token: str) -> bool:
    """Deactivate a specific session token"""
    try:
        db_session_token = db.query(SessionToken).filter(
            SessionToken.session_token == session_token,
            SessionToken.is_active == True
        ).first()
        
        if db_session_token:
            db_session_token.is_active = False
            db.commit()
            logger.info(f"Deactivated session token: {session_token[:10]}...")
            return True
        
        logger.debug(f"Session token not found or already inactive: {session_token[:10]}...")
        return False
        
    except Exception as e:
        logger.error(f"Error deactivating session token: {str(e)}", exc_info=True)
        db.rollback()
        return False


def cleanup_expired_tokens(db: Session) -> int:
    """
    Clean up expired session tokens
    Returns the number of tokens cleaned up
    """
    try:
        expired_count = db.query(SessionToken).filter(
            SessionToken.expires_at < datetime.utcnow(),
            SessionToken.is_active == True
        ).update({"is_active": False}, synchronize_session=False)
        
        db.commit()
        
        if expired_count > 0:
            logger.info(f"Cleaned up {expired_count} expired session tokens")
        
        return expired_count
        
    except Exception as e:
        logger.error(f"Error cleaning up expired tokens: {str(e)}", exc_info=True)
        db.rollback()
        return 0


def deactivate_all_user_tokens(db: Session, user_id: int) -> int:
    """
    Deactivate all session tokens for a specific user
    Useful for security purposes (e.g., password change, account suspension)
    Returns the number of tokens deactivated
    """
    try:
        deactivated_count = db.query(SessionToken).filter(
            SessionToken.user_id == user_id,
            SessionToken.is_active == True
        ).update({"is_active": False}, synchronize_session=False)
        
        db.commit()
        
        if deactivated_count > 0:
            logger.info(f"Deactivated {deactivated_count} session tokens for user {user_id}")
        
        return deactivated_count
        
    except Exception as e:
        logger.error(f"Error deactivating all tokens for user {user_id}: {str(e)}", exc_info=True)
        db.rollback()
        return 0