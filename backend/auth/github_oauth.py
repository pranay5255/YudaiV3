#!/usr/bin/env python3
"""
GitHub OAuth Authentication Module

This module handles GitHub OAuth authentication flow and user access token generation.
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from auth.state_manager import state_manager
from db.database import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from ghapi.all import GhApi
from models import AuthToken, User
from sqlalchemy.orm import Session

# Security scheme for JWT-like token authentication
security = HTTPBearer()

# GitHub OAuth Configuration
GITHUB_APP_CLIENT_ID = os.getenv("CLIENT_ID")  # For user authorization
GITHUB_APP_CLIENT_SECRET = os.getenv("CLIENT_SECRET")  # For user authorization

# GitHub App URLs
GITHUB_APP_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_APP_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API_URL = "https://api.github.com/user"

# Fallback redirect URIs for different environments
FALLBACK_REDIRECT_URIS = [
    "https://yudai.app/auth/callback",
    "http://localhost:3000/auth/callback",
    "http://localhost:8080/auth/callback",
    "https://dev.yudai.app/auth/callback",
    "https://api.yudai.app/auth/callback",
]

# Import centralized state manager


def parse_response(response) -> Dict[str, Any]:
    """
    Parse HTTP response similar to Ruby implementation
    
    Args:
        response: httpx.Response object
        
    Returns:
        Parsed JSON response or empty dict on error
    """
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        return {}


class GitHubAppError(Exception):
    """Custom exception for GitHub App errors"""
    pass


def generate_oauth_state() -> str:
    """Generate a random state parameter for OAuth security"""
    return state_manager.generate_state()





def get_github_app_oauth_url(state: str) -> str:
    """
    Generate GitHub App OAuth authorization URL for user access tokens
    
    Args:
        state: Random state parameter for security
        
    Returns:
        GitHub App OAuth authorization URL
    """
    if not GITHUB_APP_CLIENT_ID:
        raise GitHubAppError("GitHub App Client ID not configured")
    
    # Use the production redirect URI - standardize on GITHUB_REDIRECT_URI
    redirect_uri = os.getenv("GITHUB_REDIRECT_URI", "https://yudai.app/auth/callback")
    
    params = {
        "client_id": GITHUB_APP_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
    }
    
    auth_url = f"{GITHUB_APP_AUTH_URL}?{urlencode(params)}"
    
    return auth_url


async def exchange_code_for_user_token(code: str, state: str) -> Dict[str, Any]:
    """
    Exchange authorization code for user access token using GitHub App
    
    Args:
        code: Authorization code from GitHub
        state: State parameter for verification
        
    Returns:
        Token response from GitHub
    """
    if not GITHUB_APP_CLIENT_SECRET:
        raise GitHubAppError("GitHub App Client Secret not configured")
    
    # Verify state parameter using centralized manager
    db = next(get_db())
    if not state_manager.validate_state(db, state):
        raise GitHubAppError("Invalid state parameter")
    
    # Exchange code for token using OAuth App flow (for user authorization)
    headers = {"Accept": "application/json"}
    
    # Remove redirect_uri from the request as per the Ruby implementation
    data = {
        "client_id": GITHUB_APP_CLIENT_ID,
        "client_secret": GITHUB_APP_CLIENT_SECRET,
        "code": code,
    }
    
    async with httpx.AsyncClient() as client:
        # Use form-encoded data instead of JSON
        response = await client.post(GITHUB_APP_TOKEN_URL, headers=headers, data=data)
    
    token_data = parse_response(response)
    
    # Handle errors more gracefully like the Ruby implementation
    if "error" in token_data:
        error_msg = token_data.get('error_description', token_data['error'])
        print(f"GitHub OAuth error: {error_msg}")
    
    return token_data


async def get_github_user_info(access_token: str) -> Dict[str, Any]:
    """
    Get GitHub user information using access token
    
    Args:
        access_token: GitHub access token
        
    Returns:
        GitHub user information
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(GITHUB_USER_API_URL, headers=headers)
    
    return parse_response(response)


async def create_or_update_user(
    db: Session, github_user: Dict[str, Any], access_token: str
) -> User:
    """
    Create or update user in database from GitHub user info
    
    Args:
        db: Database session
        github_user: GitHub user information
        access_token: GitHub access token
        
    Returns:
        User object
    """
    # Handle case where github_user might be empty (like in Ruby implementation)
    if not github_user or "id" not in github_user or "login" not in github_user:
        raise GitHubAppError("Invalid GitHub user information received")
    
    github_id = str(github_user["id"])
    username = github_user["login"]
    
    try:
        # Check if user exists
        user = db.query(User).filter(User.github_user_id == github_id).first()
        
        if user:
            # Update existing user
            user.github_username = username
            user.email = github_user.get("email")
            user.display_name = github_user.get("name")
            user.avatar_url = github_user.get("avatar_url")
            user.last_login = datetime.utcnow()
            user.updated_at = datetime.utcnow()
        else:
            # Create new user
            user = User(
                github_username=username,
                github_user_id=github_id,
                email=github_user.get("email"),
                display_name=github_user.get("name"),
                avatar_url=github_user.get("avatar_url"),
                last_login=datetime.utcnow(),
            )
            db.add(user)
        
        # Flush to get the user ID without committing the transaction
        db.flush()
        
        # Now user.id is available for the auth token
        # Deactivate any existing active tokens for this user
        db.query(AuthToken).filter(
            AuthToken.user_id == user.id, AuthToken.is_active
        ).update({"is_active": False})
        
        # Create new token
        auth_token = AuthToken(
            user_id=user.id,
            access_token=access_token,
            token_type="bearer",
            scope="repo user email",
            expires_at=datetime.utcnow() + timedelta(hours=8),
            is_active=True,
        )
        db.add(auth_token)
        
        # Commit the entire transaction
        db.commit()
        db.refresh(user)
        
        return user
        
    except Exception as e:
        # Rollback on any error
        db.rollback()
        raise GitHubAppError(f"Failed to create or update user: {str(e)}")


def get_github_api(user_id: int, db: Session) -> GhApi:
    """
    Get GitHub API instance for authenticated user
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        GhApi instance with user's access token
    """
    # Get user's active auth token
    auth_token = (
        db.query(AuthToken)
        .filter(
            AuthToken.user_id == user_id,
            AuthToken.is_active,
            AuthToken.expires_at > datetime.utcnow(),
        )
        .first()
    )
    
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid GitHub token found. Please re-authenticate.",
        )
    
    # Create GhApi instance with user's token
    return GhApi(token=auth_token.access_token)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    """
    Get current authenticated user from token
    
    Args:
        credentials: HTTP Bearer token credentials
        db: Database session
        
    Returns:
        User object
    """
    token = credentials.credentials
    
    # Find user by token
    auth_token = (
        db.query(AuthToken)
        .filter(
            AuthToken.access_token == token,
            AuthToken.is_active,
            AuthToken.expires_at > datetime.utcnow(),
        )
        .first()
    )
    
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    
    user = db.query(User).filter(User.id == auth_token.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise
    
    Args:
        credentials: Optional HTTP Bearer token credentials
        db: Database session
        
    Returns:
        User object or None
    """
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None


def validate_github_app_config():
    """Validate that GitHub OAuth configuration is complete"""
    missing_vars = []
    
    if not GITHUB_APP_CLIENT_ID:
        missing_vars.append("GITHUB_APP_CLIENT_ID")
    
    if not GITHUB_APP_CLIENT_SECRET:
        missing_vars.append("GITHUB_APP_CLIENT_SECRET")
    
    if missing_vars:
        raise GitHubAppError(
            f"Missing required GitHub OAuth configuration: {', '.join(missing_vars)}"
        )


# Backward compatibility aliases
GitHubOAuthError = GitHubAppError
get_github_oauth_url = get_github_app_oauth_url
exchange_code_for_token = exchange_code_for_user_token
validate_github_config = validate_github_app_config
