#!/usr/bin/env python3
"""
Authentication Routes for GitHub OAuth
Enhanced with proper logging and error handling
"""
import logging
import os
from urllib.parse import urlencode

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
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPBearer
from models import (
    CreateSessionTokenRequest,
    SessionTokenRequest,
    SessionTokenResponse,
)
from sqlalchemy.orm import Session

# utc_now not used directly in this module after cleanup

# Configure logger for this module
logger = logging.getLogger(__name__)

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
        logger.info("Processing GitHub OAuth callback")
        
        if not code:
            error_msg = "Authorized, but no code provided."
            logger.warning("OAuth callback received without authorization code")
            return RedirectResponse(
                url=f"{os.getenv('FRONTEND_BASE_URL','http://localhost:3000')}/auth/callback?error={error_msg}",
                status_code=302
            )
        
        logger.debug(f"Exchanging authorization code: {code[:10]}...")
        
        # Exchange code for token
        token_data = await exchange_code(code)
        
        if "access_token" not in token_data:
            error_msg = "Unable to exchange code for token."
            logger.error(f"Token exchange failed: {token_data}")
            return RedirectResponse(
                url=f"{os.getenv('FRONTEND_BASE_URL','http://localhost:3000')}/auth/callback?error={error_msg}",
                status_code=302
            )
        
        access_token = token_data["access_token"]
        logger.debug("Successfully obtained GitHub access token")
        
        # Get user info
        github_user = await user_info(access_token)
        
        if not github_user:
            error_msg = "Unable to get user information."
            logger.error("Failed to retrieve GitHub user information")
            return RedirectResponse(
                url=f"{os.getenv('FRONTEND_BASE_URL','http://localhost:3000')}/auth/callback?error={error_msg}",
                status_code=302
            )
        
        username = github_user.get("login", "unknown")
        logger.info(f"Retrieved GitHub user info for: {username}")
        
        # Create or update user
        user = await create_or_update_user(db, github_user, access_token)
        logger.info(f"Created/updated user record for: {user.github_username} (ID: {user.id})")
        
        # Create session token for frontend (this ALWAYS creates a fresh token)
        session_token = create_session_token(db, user.id, expires_in_hours=24)
        logger.info(f"Created fresh session token for user: {user.github_username}")
        
        # Build success redirect URL with auth data (NO GitHub token for security)
        auth_params = {
            "session_token": session_token.session_token,
            "user_id": str(user.id),
            "username": user.github_username,
            "name": user.display_name or user.github_username,
            "email": user.email or "",
            "avatar": user.avatar_url or "",
            "github_id": user.github_user_id
        }
        
        redirect_url = f"{os.getenv('FRONTEND_BASE_URL','https://yudai.app')}/auth/callback?{urlencode(auth_params)}"
        logger.info(f"Redirecting user {user.github_username} to frontend with session token")
        
        return RedirectResponse(url=redirect_url, status_code=302)
        
    except GitHubOAuthError as e:
        error_msg = f"GitHub OAuth error: {str(e)}"
        logger.error(f"GitHub OAuth error during callback: {str(e)}")
        return RedirectResponse(
            url=f"{os.getenv('FRONTEND_BASE_URL','https://yudai.app')}/auth/callback?error={error_msg}",
            status_code=302
        )
        
    except Exception as e:
        error_msg = "Authentication failed due to internal error"
        logger.error(f"Unexpected error in auth callback: {str(e)}", exc_info=True)
        return RedirectResponse(
            url=f"{os.getenv('FRONTEND_BASE_URL','https://yudai.app')}/auth/callback?error={error_msg}",
            status_code=302
        )


# Removed: /api/create-session (avoids exposing GitHub token to frontend)


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
async def api_get_user(db: Session = Depends(get_db), credentials=Depends(HTTPBearer())):
    """Get user by Bearer session token in Authorization header."""
    try:
        token = credentials.credentials if credentials else None
        user = validate_session_token(db, token) if token else None
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session token")
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
        logger.error(f"Error in api_get_user: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/api/logout")
async def api_logout(request: SessionTokenRequest, db: Session = Depends(get_db)):
    """Logout user by deactivating session token"""
    try:
        logger.info(f"Processing logout for session token: {request.session_token[:10]}...")
        
        # Deactivate the session token
        success = deactivate_session_token(db, request.session_token)
        
        if success:
            logger.info("User logged out successfully")
            return {"success": True, "message": "Logged out successfully"}
        else:
            logger.warning("Logout attempted with inactive or non-existent session token")
            return {"success": False, "message": "Session token not found or already inactive"}
            
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.post("/api/refresh-session")
async def api_refresh_session(
    request: CreateSessionTokenRequest,
    db: Session = Depends(get_db)
):
    """Create a new session token for a user. Guard with env flag ADMIN_SESSION_REFRESH=true."""
    if os.getenv("ADMIN_SESSION_REFRESH", "false").lower() != "true":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enabled")
    try:
        from models import User
        user = db.query(User).filter(User.id == request.user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
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
        logger.error(f"Error refreshing session token: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
