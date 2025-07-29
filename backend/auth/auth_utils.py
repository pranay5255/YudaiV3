"""
Shared authentication utilities for YudaiV3 backend
"""
from fastapi import HTTPException, status
from models import User


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
            detail="Authentication required. Please log in."
        )
    
    if not user.id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user session. Please re-authenticate."
        ) 