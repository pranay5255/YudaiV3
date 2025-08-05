#!/usr/bin/env python3
"""
Authentication Routes for GitHub OAuth
Simplified to match Ruby reference implementation
"""

from auth.auth_utils import (
    create_session_token,
    deactivate_session_token,
    validate_session_token,
)
from auth.github_oauth import (
    GitHubOAuthError,
    create_or_update_user,
    exchange_code,
    get_github_oauth_url,
    user_info,
    validate_github_config,
)
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models import CreateSessionTokenRequest, SessionTokenResponse
from sqlalchemy.orm import Session

router = APIRouter()


# Removed simple HTML login endpoint - frontend handles login UI


@router.get("/callback")
async def auth_callback(
    code: str,
    db: Session = Depends(get_db)
):
    """
    Handle GitHub OAuth callback - redirect to frontend with auth data
    
    Args:
        code: Authorization code from GitHub
        db: Database session
        
    Returns:
        Redirect response to frontend with auth data
    """
    try:
        if not code:
            error_msg = "Authorized, but no code provided."
            from fastapi.responses import RedirectResponse
            return RedirectResponse(
                url=f"https://yudai.app/auth/callback?error={error_msg}",
                status_code=302
            )
        
        # Exchange code for token
        token_data = await exchange_code(code)
        
        if "access_token" not in token_data:
            error_msg = "Unable to exchange code for token."
            from fastapi.responses import RedirectResponse
            return RedirectResponse(
                url=f"https://yudai.app/auth/callback?error={error_msg}",
                status_code=302
            )
        
        access_token = token_data["access_token"]
        
        # Get user info
        github_user = await user_info(access_token)
        
        if not github_user:
            error_msg = "Unable to get user information."
            from fastapi.responses import RedirectResponse
            return RedirectResponse(
                url=f"https://yudai.app/auth/callback?error={error_msg}",
                status_code=302
            )
        
        # Create or update user
        user = await create_or_update_user(db, github_user, access_token)
        
        # Create session token for frontend
        session_token = create_session_token(db, user.id, expires_in_hours=24)
        
        # Build success redirect URL with auth data (NO GitHub token)
        from urllib.parse import urlencode
        auth_params = {
            "session_token": session_token.session_token,
            "user_id": str(user.id),
            "username": user.github_username,
            "name": user.display_name or user.github_username,
            "email": user.email or "",
            "avatar": user.avatar_url or "",
            "github_id": user.github_user_id
        }
        
        from fastapi.responses import RedirectResponse
        redirect_url = f"https://yudai.app/auth/callback?{urlencode(auth_params)}"
        
        return RedirectResponse(url=redirect_url, status_code=302)
        
    except GitHubOAuthError as e:
        error_msg = f"Authentication failed: {str(e)}"
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"https://yudai.app/auth/callback?error={error_msg}",
            status_code=302
        )
        
    except Exception as e:
        error_msg = f"Authentication failed: {str(e)}"
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"https://yudai.app/auth/callback?error={error_msg}",
            status_code=302
        )


# Simple API endpoints for frontend integration (minimal)
@router.get("/api/login")
async def api_login():
    """API endpoint to get login URL"""
    try:
        validate_github_config()
        auth_url = get_github_oauth_url()
        return {"login_url": auth_url}
    except GitHubOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/api/user")
async def api_get_user_by_session_token(session_token: str, db: Session = Depends(get_db)):
    """Get user by session token - for frontend to verify authentication"""
    try:
        user = validate_session_token(db, session_token)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired session token"
            )
        
        return {
            "id": user.id,
            "github_username": user.github_username,
            "github_id": user.github_user_id,
            "display_name": user.display_name,
            "email": user.email,
            "avatar_url": user.avatar_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/api/logout")
async def api_logout(session_token: str, db: Session = Depends(get_db)):
    """Logout user by deactivating session token"""
    try:
        success = deactivate_session_token(db, session_token)
        
        if success:
            return {"success": True, "message": "Logged out successfully"}
        else:
            return {"success": False, "message": "Session token not found or already inactive"}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/api/refresh-session")
async def api_refresh_session(
    request: CreateSessionTokenRequest,
    db: Session = Depends(get_db)
):
    """Create a new session token for a user (for testing/admin purposes)"""
    try:
        from models import User
        
        # Verify user exists
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Create new session token
        session_token = create_session_token(db, user.id, request.expires_in_hours)
        
        return SessionTokenResponse(
            session_token=session_token.session_token,
            expires_at=session_token.expires_at,
            user={
                "id": user.id,
                "github_username": user.github_username,
                "github_user_id": user.github_user_id,
                "email": user.email,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
                "created_at": user.created_at.isoformat(),
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
