#!/usr/bin/env python3
"""
GitHub OAuth Authentication Module

This module handles GitHub OAuth authentication flow, token management,
and user authentication using the ghapi library.
"""

import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from db.database import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from ghapi.all import GhApi
from models import AuthToken, User
from sqlalchemy.orm import Session

# Security scheme for JWT-like token authentication
security = HTTPBearer()

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv(
    "GITHUB_REDIRECT_URI", "https://yudai.app/auth/callback"
)
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API_URL = "https://api.github.com/user"

# Fallback redirect URIs for different environments
FALLBACK_REDIRECT_URIS = [
    "https://yudai.app/auth/callback",
    "http://localhost:3000/auth/callback",
    "http://localhost:8080/auth/callback",
    "https://dev.yudai.app/auth/callback",
    "https://api.yudai.app/auth/callback",
]

# Session storage for state parameter (in production, use Redis or database)
oauth_states = {}


class GitHubOAuthError(Exception):
    """Custom exception for GitHub OAuth errors"""

    pass


def generate_oauth_state() -> str:
    """Generate a random state parameter for OAuth security"""
    return secrets.token_urlsafe(32)


def get_github_oauth_url(state: str) -> str:
    """
    Generate GitHub OAuth authorization URL

    Args:
        state: Random state parameter for security

    Returns:
        GitHub OAuth authorization URL
    """
    if not GITHUB_CLIENT_ID:
        raise GitHubOAuthError("GitHub Client ID not configured")

    # Use the configured redirect URI, with fallback to first in list
    redirect_uri = GITHUB_REDIRECT_URI or FALLBACK_REDIRECT_URIS[0]

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "repo user email",  # Request repository, user info, and email access
        "state": state,
        "response_type": "code",
    }

    auth_url = f"{GITHUB_AUTH_URL}?{urlencode(params)}"

    # Log the generated URL for debugging (remove in production)
    print(f"Generated GitHub OAuth URL: {auth_url}")
    print(f"Client ID: {GITHUB_CLIENT_ID}")
    print(f"Redirect URI: {redirect_uri}")

    return auth_url


async def exchange_code_for_token(code: str, state: str) -> Dict[str, Any]:
    """
    Exchange authorization code for access token

    Args:
        code: Authorization code from GitHub
        state: State parameter for verification

    Returns:
        Token response from GitHub
    """
    if not GITHUB_CLIENT_SECRET:
        raise GitHubOAuthError("GitHub Client Secret not configured")

    # Verify state parameter
    if state not in oauth_states:
        raise GitHubOAuthError("Invalid state parameter")

    # Remove used state
    oauth_states.pop(state, None)

    # Exchange code for token
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    # Try with the configured redirect URI first
    redirect_uri = GITHUB_REDIRECT_URI or FALLBACK_REDIRECT_URIS[0]

    data = {
        "client_id": GITHUB_CLIENT_ID,
        "client_secret": GITHUB_CLIENT_SECRET,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(GITHUB_TOKEN_URL, headers=headers, json=data)

    # If the first attempt fails, try with fallback URIs
    if response.status_code != 200:
        print(f"First attempt failed with redirect_uri: {redirect_uri}")
        print(f"Response: {response.text}")

        # Try fallback URIs
        for fallback_uri in FALLBACK_REDIRECT_URIS[1:]:
            if fallback_uri != redirect_uri:
                data["redirect_uri"] = fallback_uri
                print(f"Trying fallback redirect_uri: {fallback_uri}")

                response = await client.post(
                    GITHUB_TOKEN_URL, headers=headers, json=data
                )
                if response.status_code == 200:
                    break

    if response.status_code != 200:
        raise GitHubOAuthError(f"Failed to exchange code for token: {response.text}")

    token_data = response.json()

    if "error" in token_data:
        raise GitHubOAuthError(
            f"GitHub OAuth error: {token_data.get('error_description', token_data['error'])}"
        )

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
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(GITHUB_USER_API_URL, headers=headers)

    if response.status_code != 200:
        raise GitHubOAuthError(f"Failed to get user info: {response.text}")

    return response.json()


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
        raise GitHubOAuthError(f"Failed to create or update user: {str(e)}")


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


def validate_github_config():
    """Validate that GitHub OAuth configuration is complete"""
    missing_vars = []

    if not GITHUB_CLIENT_ID:
        missing_vars.append("GITHUB_CLIENT_ID")

    if not GITHUB_CLIENT_SECRET:
        missing_vars.append("GITHUB_CLIENT_SECRET")

    if missing_vars:
        raise GitHubOAuthError(
            f"Missing required GitHub OAuth configuration: {', '.join(missing_vars)}"
        )
