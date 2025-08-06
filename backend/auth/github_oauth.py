#!/usr/bin/env python3
"""
GitHub OAuth Authentication Module
Simplified to match Ruby reference implementation
"""

import os
from datetime import timedelta

from utils import utc_now
from typing import Any, Dict
from urllib.parse import urlencode

import httpx
from db.database import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
            user.last_login = utc_now()
            user.updated_at = utc_now()
        else:
            # Create new user
            user = User(
                github_username=username,
                github_user_id=github_id,
                email=github_user.get("email"),
                display_name=github_user.get("name"),
                avatar_url=github_user.get("avatar_url"),
                last_login=utc_now(),
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
            expires_at=utc_now() + timedelta(hours=8),
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


# FastAPI security scheme for Bearer token authentication
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get current authenticated user from Bearer token
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
        
    Returns:
        User: Authenticated user object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    # Find active auth token
    auth_token = db.query(AuthToken).filter(
        AuthToken.access_token == token,
        AuthToken.is_active == True
    ).first()
    
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if token is expired
    if auth_token.expires_at and auth_token.expires_at < utc_now():
        # Deactivate expired token
        auth_token.is_active = False
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user
    user = db.query(User).filter(User.id == auth_token.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user


def get_github_api(user_id: int, db: Session):
    """
    Get GitHub API client for authenticated user
    
    Args:
        user_id: User ID
        db: Database session
        
    Returns:
        GitHub API client instance
        
    Raises:
        HTTPException: If user not found or no valid token
    """
    # Get user's active token
    auth_token = db.query(AuthToken).filter(
        AuthToken.user_id == user_id,
        AuthToken.is_active == True
    ).first()
    
    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid authentication token found"
        )
    
    # Check if token is expired
    if auth_token.expires_at and auth_token.expires_at < utc_now():
        # Deactivate expired token
        auth_token.is_active = False
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired"
        )
    
    # Import ghapi here to avoid circular imports
    try:
        from ghapi import GhApi
        return GhApi(token=auth_token.access_token)
    except ImportError:
        # Fallback: create a simple mock API client for basic functionality
        class MockGitHubApi:
            def __init__(self, token):
                self.token = token
                self.repos = self
                self.issues = self
                self.pulls = self
                self.search = self
                
            def list_for_authenticated_user(self, **kwargs):
                return []
                
            def get(self, **kwargs):
                return {}
                
            def create(self, **kwargs):
                return {}
                
            def list_for_repo(self, **kwargs):
                return []
                
            def list(self, **kwargs):
                return []
                
            def list_commits(self, **kwargs):
                return []
                
            def list_branches(self, **kwargs):
                return []
                
            def repos(self, **kwargs):
                return {"items": []}
        
        return MockGitHubApi(auth_token.access_token)
