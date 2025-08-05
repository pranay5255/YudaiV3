#!/usr/bin/env python3
"""
Authentication Routes for GitHub OAuth
Simplified to match Ruby reference implementation
"""


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
        
        # Build success redirect URL with auth data
        from urllib.parse import urlencode
        auth_params = {
            "token": access_token,
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
async def api_get_user_by_token(token: str, db: Session = Depends(get_db)):
    """Get user by access token - for frontend to verify authentication"""
    try:
        from models import AuthToken
        
        auth_token = db.query(AuthToken).filter(
            AuthToken.access_token == token,
            AuthToken.is_active
        ).first()
        
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        from models import User
        user = db.query(User).filter(User.id == auth_token.user_id).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "id": user.id,
            "github_username": user.github_username,
            "github_id": user.github_user_id,  # Fix: use github_id as expected by frontend
            "display_name": user.display_name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "access_token": token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
