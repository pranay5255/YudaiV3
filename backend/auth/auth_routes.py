#!/usr/bin/env python3
"""
Authentication Routes for GitHub OAuth

This module provides FastAPI routes for GitHub OAuth authentication,
including login, callback, logout, and user profile endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from db.database import get_db
from models import User, AuthToken, UserProfile, AuthResponse  # Import types from models.py
from .github_oauth import (
    generate_oauth_state,
    get_github_oauth_url,
    exchange_code_for_token,
    get_github_user_info,
    create_or_update_user,
    get_current_user,
    get_current_user_optional,
    validate_github_config,
    oauth_states,
    GitHubOAuthError,
    GITHUB_CLIENT_ID,
    GITHUB_CLIENT_SECRET,
    GITHUB_REDIRECT_URI
)

# Create router for auth endpoints
router = APIRouter(tags=["authentication"])


@router.get("/login")
async def github_login():
    """
    Initiate GitHub OAuth login flow
    """
    try:
        validate_github_config()
        state = generate_oauth_state()
        oauth_states[state] = True
        auth_url = get_github_oauth_url(state)
        return RedirectResponse(url=auth_url)
    except GitHubOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/callback")
async def github_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """
    Handle GitHub OAuth callback
    """
    try:
        token_data = await exchange_code_for_token(code, state)
        access_token = token_data["access_token"]
        github_user = await get_github_user_info(access_token)
        user = await create_or_update_user(db, github_user, access_token)
        user_profile = UserProfile(
            id=user.id,
            github_username=user.github_username,
            github_user_id=user.github_user_id,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            created_at=user.created_at.isoformat(),
            last_login=user.last_login.isoformat() if user.last_login else None
        )
        return AuthResponse(
            success=True,
            message="Authentication successful",
            user=user_profile,
            access_token=access_token
        )
    except GitHubOAuthError as e:
        return AuthResponse(
            success=False,
            message="Authentication failed",
            error=str(e)
        )
    except Exception as e:
        return AuthResponse(
            success=False,
            message="Authentication failed",
            error=f"Unexpected error: {str(e)}"
        )

@router.get("/profile", response_model=UserProfile)
async def get_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's profile
    """
    return UserProfile(
        id=current_user.id,
        github_username=current_user.github_username,
        github_user_id=current_user.github_user_id,
        email=current_user.email,
        display_name=current_user.display_name,
        avatar_url=current_user.avatar_url,
        created_at=current_user.created_at.isoformat(),
        last_login=current_user.last_login.isoformat() if current_user.last_login else None
    )

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout current user (invalidate token)
    """
    db.query(AuthToken).filter(
        AuthToken.user_id == current_user.id,
        AuthToken.is_active == True
    ).update({"is_active": False})
    db.commit()
    return {"success": True, "message": "Logged out successfully"}

@router.get("/status")
async def auth_status(
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """
    Check authentication status
    """
    if current_user:
        user_profile = UserProfile(
            id=current_user.id,
            github_username=current_user.github_username,
            github_user_id=current_user.github_user_id,
            email=current_user.email,
            display_name=current_user.display_name,
            avatar_url=current_user.avatar_url,
            created_at=current_user.created_at.isoformat(),
            last_login=current_user.last_login.isoformat() if current_user.last_login else None
        )
        return {
            "authenticated": True,
            "user": user_profile
        }
    else:
        return {"authenticated": False}

@router.patch("/profile", response_model=UserProfile)
async def update_user_profile(
    profile_updates: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update current user's profile (e.g., active_repository)
    """
    try:
        # Update allowed fields
        if "active_repository" in profile_updates:
            current_user.active_repository = profile_updates["active_repository"]
        
        if "display_name" in profile_updates:
            current_user.display_name = profile_updates["display_name"]
        
        # Update timestamp
        current_user.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(current_user)
        
        return UserProfile(
            id=current_user.id,
            github_username=current_user.github_username,
            github_user_id=current_user.github_user_id,
            email=current_user.email,
            display_name=current_user.display_name,
            avatar_url=current_user.avatar_url,
            created_at=current_user.created_at.isoformat(),
            last_login=current_user.last_login.isoformat() if current_user.last_login else None
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update profile: {str(e)}"
        )

@router.get("/config")
async def get_auth_config():
    """
    Get authentication configuration status
    """
    try:
        validate_github_config()
        return {
            "github_oauth_configured": True,
            "client_id_configured": bool(GITHUB_CLIENT_ID),
            "client_secret_configured": bool(GITHUB_CLIENT_SECRET),
            "redirect_uri": GITHUB_REDIRECT_URI
        }
    except GitHubOAuthError as e:
        return {
            "github_oauth_configured": False,
            "error": str(e),
            "client_id_configured": bool(GITHUB_CLIENT_ID),
            "client_secret_configured": bool(GITHUB_CLIENT_SECRET),
            "redirect_uri": GITHUB_REDIRECT_URI
        }