"""
Shared authentication utilities for YudaiV3 backend
"""
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, status
from models import SessionToken, User
from sqlalchemy.orm import Session


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
    """Create a new session token for a user"""
    # Deactivate any existing active session tokens for this user
    db.query(SessionToken).filter(
        SessionToken.user_id == user_id,
        SessionToken.is_active == True
    ).update({"is_active": False})
    
    # Generate new session token
    session_token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
    
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
    
    return db_session_token


def validate_session_token(db: Session, session_token: str) -> Optional[User]:
    """Validate a session token and return the associated user"""
    if not session_token:
        return None
    
    # Find active session token
    db_session_token = db.query(SessionToken).filter(
        SessionToken.session_token == session_token,
        SessionToken.is_active == True
    ).first()
    
    if not db_session_token:
        return None
    
    # Check if token is expired
    if db_session_token.expires_at < datetime.utcnow():
        # Deactivate expired token
        db_session_token.is_active = False
        db.commit()
        return None
    
    # Get user
    user = db.query(User).filter(User.id == db_session_token.user_id).first()
    
    if not user:
        return None
    
    return user


def deactivate_session_token(db: Session, session_token: str) -> bool:
    """Deactivate a session token"""
    db_session_token = db.query(SessionToken).filter(
        SessionToken.session_token == session_token,
        SessionToken.is_active == True
    ).first()
    
    if db_session_token:
        db_session_token.is_active = False
        db.commit()
        return True
    
    return False 