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
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

router = APIRouter()


# Removed simple HTML login endpoint - frontend handles login UI


@router.get("/callback")
async def auth_callback(
    code: str,
    db: Session = Depends(get_db)
):
    """
    Handle GitHub OAuth callback - matches Ruby implementation exactly
    
    Args:
        code: Authorization code from GitHub
        db: Database session
        
    Returns:
        HTML response with success or error message
    """
    try:
        if not code:
            return HTMLResponse(
                content="Authorized, but no code provided.",
                status_code=400
            )
        
        # Exchange code for token - matches Ruby exchange_code function
        token_data = await exchange_code(code)
        
        if "access_token" not in token_data:
            error_msg = f"Authorized, but unable to exchange code {code} for token."
            return HTMLResponse(content=error_msg, status_code=400)
        
        access_token = token_data["access_token"]
        
        # Get user info - matches Ruby user_info function  
        github_user = await user_info(access_token)
        
        if not github_user:
            return HTMLResponse(
                content="Authorized, but unable to get user information.",
                status_code=400
            )
        
        # Create or update user
        user = await create_or_update_user(db, github_user, access_token)
        
        # Extract user info like Ruby implementation
        handle = github_user.get("login", "unknown")
        name = github_user.get("name", handle)
        
        # Success message matching Ruby format exactly
        success_message = f"Successfully authorized! Welcome, {name} ({handle})."
        
        return HTMLResponse(content=success_message)
        
    except GitHubOAuthError as e:
        error_msg = f"Authentication failed: {str(e)}"
        return HTMLResponse(content=error_msg, status_code=400)
        
    except Exception as e:
        error_msg = f"Authentication failed: {str(e)}"
        return HTMLResponse(content=error_msg, status_code=500)


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
