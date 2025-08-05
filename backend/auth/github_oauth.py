#!/usr/bin/env python3
"""
GitHub OAuth Authentication Module
Simplified to match Ruby reference implementation
"""

import os
from datetime import datetime, timedelta
from typing import Any, Dict
from urllib.parse import urlencode

import httpx
from models import AuthToken, User
from sqlalchemy.orm import Session

# GitHub OAuth Configuration - matching Ruby implementation
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# GitHub OAuth URLs
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API_URL = "https://api.github.com/user"


def parse_response(response) -> Dict[str, Any]:
    """
    Parse HTTP response exactly like Ruby implementation
    
    Args:
        response: httpx.Response object
        
    Returns:
        Parsed JSON response or empty dict on error
    """
    if response.status_code == 200:
        return response.json()
    else:
        print(response)
        print(response.text)
        return {}


class GitHubOAuthError(Exception):
    """Custom exception for GitHub OAuth errors"""
    pass


def get_github_oauth_url() -> str:
    """
    Generate GitHub OAuth authorization URL
    Simplified version without state parameter like Ruby
    
    Returns:
        GitHub OAuth authorization URL
    """
    if not CLIENT_ID:
        raise GitHubOAuthError("GitHub Client ID not configured")
    
    # Use production redirect URI
    redirect_uri = os.getenv("GITHUB_REDIRECT_URI", "https://yudai.app/auth/callback")
    
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
    }
    
    return f"{GITHUB_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access token
    Matches Ruby implementation exactly
    
    Args:
        code: Authorization code from GitHub
        
    Returns:
        Token response from GitHub
    """
    if not CLIENT_SECRET:
        raise GitHubOAuthError("GitHub Client Secret not configured")
    
    # Match Ruby implementation exactly
    headers = {"Accept": "application/json"}
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(GITHUB_TOKEN_URL, headers=headers, data=data)
    
    return parse_response(response)


async def user_info(token: str) -> Dict[str, Any]:
    """
    Get GitHub user information using access token
    Matches Ruby implementation exactly
    
    Args:
        token: GitHub access token
        
    Returns:
        GitHub user information
    """
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(GITHUB_USER_API_URL, headers=headers)
    
    return parse_response(response)


async def create_or_update_user(
    db: Session, github_user: Dict[str, Any], access_token: str
) -> User:
    """
    Create or update user in database from GitHub user info
    Simplified version
    
    Args:
        db: Database session
        github_user: GitHub user information
        access_token: GitHub access token
        
    Returns:
        User object
    """
    if not github_user or "id" not in github_user or "login" not in github_user:
        raise GitHubOAuthError("Invalid GitHub user information received")
    
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
        
        db.flush()
        
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
        
        db.commit()
        db.refresh(user)
        
        return user
        
    except Exception as e:
        db.rollback()
        raise GitHubOAuthError(f"Failed to create or update user: {str(e)}")


def validate_github_config():
    """Validate that GitHub OAuth configuration is complete"""
    missing_vars = []
    
    if not CLIENT_ID:
        missing_vars.append("CLIENT_ID")
    
    if not CLIENT_SECRET:
        missing_vars.append("CLIENT_SECRET")
    
    if missing_vars:
        raise GitHubOAuthError(
            f"Missing required GitHub OAuth configuration: {', '.join(missing_vars)}"
        )
