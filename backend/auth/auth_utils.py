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
    try:
        print(f"create_session_token: Creating session token for user_id: {user_id}")
        
        # Deactivate any existing active session tokens for this user
        existing_tokens = db.query(SessionToken).filter(
            SessionToken.user_id == user_id,
            SessionToken.is_active == True
        ).all()
        
        if existing_tokens:
            print(f"create_session_token: Deactivating {len(existing_tokens)} existing tokens")
            for token in existing_tokens:
                token.is_active = False
        
        # Generate new session token
        session_token = generate_session_token()
        expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)
        
        print(f"create_session_token: Generated token: {session_token[:10]}...")
        print(f"create_session_token: Expires at: {expires_at}")
        
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
        
        print(f"create_session_token: Successfully created session token with ID: {db_session_token.id}")
        
        # Verify the token was saved
        saved_token = db.query(SessionToken).filter(
            SessionToken.session_token == session_token
        ).first()
        
        if saved_token:
            print("create_session_token: Verified token saved to database")
        else:
            print("create_session_token: ERROR - Token not found in database after save!")
        
        return db_session_token
        
    except Exception as e:
        print(f"create_session_token: Error creating session token: {str(e)}")
        db.rollback()
        raise


def validate_session_token(db: Session, session_token: str) -> Optional[User]:
    """Validate a session token and return the associated user"""
    try:
        if not session_token:
            print("validate_session_token: No session token provided")
            return None
        
        print(f"validate_session_token: Looking for token: {session_token[:10]}...")
        
        # First, let's check if the session_tokens table exists and has any data
        try:
            total_tokens = db.query(SessionToken).count()
            print(f"validate_session_token: Total session tokens in database: {total_tokens}")
        except Exception as e:
            print(f"validate_session_token: Error checking session_tokens table: {str(e)}")
            return None
        
        # Find active session token
        db_session_token = db.query(SessionToken).filter(
            SessionToken.session_token == session_token,
            SessionToken.is_active == True
        ).first()
        
        if not db_session_token:
            print(f"validate_session_token: No active session token found for token: {session_token[:10]}...")
            
            # Let's check if the token exists but is inactive
            inactive_token = db.query(SessionToken).filter(
                SessionToken.session_token == session_token
            ).first()
            
            if inactive_token:
                print(f"validate_session_token: Token exists but is inactive (is_active: {inactive_token.is_active})")
            else:
                print("validate_session_token: Token does not exist in database at all")
            
            return None
        
        # Check if token is expired
        if db_session_token.expires_at < datetime.utcnow():
            print(f"validate_session_token: Session token expired for token: {session_token[:10]}...")
            # Deactivate expired token
            db_session_token.is_active = False
            db.commit()
            return None
        
        # Get user
        user = db.query(User).filter(User.id == db_session_token.user_id).first()
        
        if not user:
            print(f"validate_session_token: User not found for session token: {session_token[:10]}...")
            return None
        
        print(f"validate_session_token: Successfully validated session token for user: {user.github_username}")
        return user
        
    except Exception as e:
        print(f"validate_session_token: Error validating session token: {str(e)}")
        return None


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