#!/usr/bin/env python3
"""
Authentication Routes for GitHub OAuth

This module provides the authentication endpoints for GitHub OAuth flow.
"""

import os
from datetime import datetime
from urllib.parse import quote

from auth.github_oauth import (
    GitHubAppError,
    create_or_update_user,
    exchange_code_for_user_token,
    get_current_user,
    get_github_app_oauth_url,
    get_github_user_info,
    validate_github_app_config,
)
from auth.state_manager import state_manager
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from models import User
from sqlalchemy.orm import Session

router = APIRouter()
security = HTTPBearer()


@router.get("/login")
async def login(db: Session = Depends(get_db)):
    """
    Initiate GitHub OAuth login flow
    
    Returns:
        Redirect to GitHub authorization page
    """
    try:
        # Validate configuration
        validate_github_app_config()
        
        # Clean up expired states periodically
        state_manager.cleanup_expired_states(db)
        
        # Generate state parameter using centralized manager
        state = state_manager.generate_state(db)
        
        # Generate authorization URL
        auth_url = get_github_app_oauth_url(state)
        
        # Redirect to GitHub
        return RedirectResponse(url=auth_url)
        
    except GitHubAppError as e:
        print(f"GitHub OAuth configuration error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication configuration error: {str(e)}"
        )
    except Exception as e:
        print(f"Login initiation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login initiation failed: {str(e)}"
        )


@router.get("/callback")
async def auth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """
    Handle GitHub OAuth callback
    
    Args:
        code: Authorization code from GitHub
        state: State parameter for verification
        db: Database session
        
    Returns:
        Redirect to frontend with success/error
    """
    try:
        # Validate required parameters
        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing authorization code"
            )
        
        if not state:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing state parameter"
            )
        
        # Validate state parameter using centralized manager
        if not state_manager.validate_state(db, state):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid state parameter"
            )
        
        # Exchange code for access token
        token_data = await exchange_code_for_user_token(code, state)
        
        if "access_token" not in token_data:
            error_msg = token_data.get("error_description", "Failed to obtain access token")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        access_token = token_data["access_token"]
        
        # Get user information from GitHub
        github_user = await get_github_user_info(access_token)
        
        if not github_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to retrieve user information from GitHub"
            )
        
        # Create or update user in database
        user = await create_or_update_user(db, github_user, access_token)
        
        # Get the auth token that was created
        from models import AuthToken
        auth_token = db.query(AuthToken).filter(
            AuthToken.user_id == user.id,
            AuthToken.is_active,
            AuthToken.access_token == access_token
        ).first()
        
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create auth token"
            )
        
        # Redirect to frontend with success and token
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        success_url = f"{frontend_url}/auth/success?user_id={user.id}&token={auth_token.access_token}"
        
        return RedirectResponse(url=success_url)
        
    except HTTPException:
        raise
    except GitHubAppError as e:
        # Log the specific error for debugging
        print(f"GitHub OAuth Error: {str(e)}")
        # Redirect to frontend with error
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        error_url = f"{frontend_url}/auth/error?message={quote(str(e))}"
        return RedirectResponse(url=error_url)
    except Exception as e:
        # Log the generic error for debugging
        print(f"Generic Error: {str(e)}")
        # Redirect to frontend with generic error
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
        error_url = f"{frontend_url}/auth/error?message={quote('Authentication failed')}"
        return RedirectResponse(url=error_url)


@router.get("/profile")
async def get_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Get current user profile
    
    Returns:
        User profile information
    """
    try:
        user = await get_current_user(credentials, db)
        
        return {
            "success": True,
            "user": {
                "id": user.id,
                "github_username": user.github_username,
                "display_name": user.display_name,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "github_user_id": user.github_user_id,
                "created_at": user.created_at.isoformat() if user.created_at else None,
                "last_login": user.last_login.isoformat() if user.last_login else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Failed to get profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Failed to get profile: {str(e)}"
        )


@router.get("/status")
async def auth_status(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Check authentication status
    
    Returns:
        Authentication status and user info if authenticated
    """
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return {
                "authenticated": False,
                "message": "No valid authorization header"
            }
        
        token = auth_header.split(" ")[1]
        
        # Find user by token
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(credentials, db)
        
        return {
            "authenticated": True,
            "user": {
                "id": user.id,
                "github_username": user.github_username,
                "display_name": user.display_name,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "github_user_id": user.github_user_id
            }
        }
        
    except Exception as e:
        return {
            "authenticated": False,
            "message": str(e)
        }


@router.post("/logout")
async def logout(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Logout user by invalidating their token
    
    Returns:
        Success message
    """
    try:
        # Get authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No valid authorization header"
            )
        
        token = auth_header.split(" ")[1]
        
        # Find and deactivate token
        from models import AuthToken
        
        auth_token = db.query(AuthToken).filter(
            AuthToken.access_token == token,
            AuthToken.is_active
        ).first()
        
        if auth_token:
            auth_token.is_active = False
            auth_token.updated_at = datetime.utcnow()
            db.commit()
            print(f"User {auth_token.user_id} logged out successfully")
        else:
            print("Attempted logout with invalid token")
        
        return {
            "success": True,
            "message": "Successfully logged out"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Logout failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )


@router.get("/config")
async def auth_config():
    """
    Get authentication configuration (public info only)
    
    Returns:
        Public authentication configuration
    """
    try:
        # Validate configuration
        validate_github_app_config()
        
        return {
            "auth_type": "github_oauth",
            "client_id": os.getenv("CLIENT_ID"),
            "redirect_uri": os.getenv("GITHUB_REDIRECT_URI"),
            "frontend_url": os.getenv("FRONTEND_URL", "http://localhost:3000")
        }
        
    except GitHubAppError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get configuration: {str(e)}"
        )


@router.get("/debug/state")
async def debug_state(db: Session = Depends(get_db)):
    """
    Debug endpoint to check state manager status (development only)
    
    Returns:
        State manager debug information
    """
    if os.getenv("NODE_ENV") == "production":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Debug endpoint not available in production"
        )
    
    # Clean up expired states
    expired_count = state_manager.cleanup_expired_states(db)
    
    return {
        "expired_states_cleaned": expired_count,
        "state_manager_working": True
    }


@router.get("/success")
async def auth_success(
    user_id: int,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Handle successful authentication
    
    Args:
        user_id: User ID from URL parameter
        token: Access token from URL parameter
        db: Database session
        
    Returns:
        Success response with user info
    """
    try:
        # Verify the token is valid
        from models import AuthToken
        auth_token = db.query(AuthToken).filter(
            AuthToken.user_id == user_id,
            AuthToken.access_token == token,
            AuthToken.is_active
        ).first()
        
        if not auth_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        # Get user info
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return {
            "success": True,
            "message": "Authentication successful",
            "user": {
                "id": user.id,
                "github_username": user.github_username,
                "display_name": user.display_name,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "github_user_id": user.github_user_id
            },
            "access_token": token
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process success: {str(e)}"
        )


@router.get("/error")
async def auth_error(message: str = "Authentication failed"):
    """
    Handle authentication errors
    
    Args:
        message: Error message from URL parameter
        
    Returns:
        Error response
    """
    return {
        "success": False,
        "error": True,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }
