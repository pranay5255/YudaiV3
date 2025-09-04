#!/usr/bin/env python3
"""
GitHub OAuth Authentication Module
Simplified to match Ruby reference implementation
"""

import os

# Import auth utilities
import secrets
import string
import time
from datetime import timedelta
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from cryptography.hazmat.primitives import serialization
from db.database import get_db
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import encode as jwt_encode
from models import AuthToken, SessionToken, User
from sqlalchemy.orm import Session

from utils import utc_now

# GitHub App OAuth Configuration - single source of truth
GITHUB_APP_CLIENT_ID = os.getenv("GITHUB_APP_CLIENT_ID")
GITHUB_APP_CLIENT_SECRET = os.getenv("GITHUB_APP_CLIENT_SECRET")
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_APP_PRIVATE_KEY_PATH = os.getenv("GITHUB_APP_PRIVATE_KEY_PATH")

# GitHub App OAuth URLs
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_API_URL = "https://api.github.com/user"
GITHUB_APP_API_URL = "https://api.github.com/app"
GITHUB_INSTALLATIONS_API_URL = "https://api.github.com/app/installations"

# GitHub App redirect URI - must match what's configured in GitHub App
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8001/auth/callback")

# Legacy support for old environment variables
GITHUB_CLIENT_ID = GITHUB_APP_CLIENT_ID or os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = GITHUB_APP_CLIENT_SECRET or os.getenv("GITHUB_CLIENT_SECRET")


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


def generate_github_app_jwt() -> str:
    """
    Generate a JWT token for GitHub App authentication
    Used to authenticate as the GitHub App itself

    Returns:
        JWT token for GitHub App authentication
    """
    if not GITHUB_APP_ID:
        raise GitHubOAuthError("GitHub App ID not configured")

    if not GITHUB_APP_PRIVATE_KEY_PATH:
        raise GitHubOAuthError("GitHub App private key path not configured")

    # Read the private key
    try:
        with open(GITHUB_APP_PRIVATE_KEY_PATH, 'rb') as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None
            )
    except Exception as e:
        raise GitHubOAuthError(f"Failed to load GitHub App private key: {e}")

    # Create JWT payload
    now = int(time.time())
    payload = {
        "iat": now - 60,  # Issued at (60 seconds ago to account for clock skew)
        "exp": now + (10 * 60),  # Expires in 10 minutes
        "iss": GITHUB_APP_ID,  # GitHub App ID as issuer
    }

    # Generate JWT
    jwt_token = jwt_encode(payload, private_key, algorithm="RS256")
    return jwt_token


async def get_installation_token(installation_id: int) -> Optional[str]:
    """
    Get an installation access token for a specific GitHub App installation
    Used for server-to-server API calls

    Args:
        installation_id: GitHub App installation ID

    Returns:
        Installation access token or None if failed
    """
    try:
        jwt_token = generate_github_app_jwt()

        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github.v3+json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GITHUB_INSTALLATIONS_API_URL}/{installation_id}/access_tokens",
                headers=headers
            )

        if response.status_code == 201:
            token_data = response.json()
            return token_data.get("token")
        else:
            print(f"[GitHub App] Failed to get installation token: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        print(f"[GitHub App] Error getting installation token: {e}")
        return None


def get_github_oauth_url() -> str:
    """
    Generate GitHub OAuth authorization URL for GitHub App
    This initiates the user-to-server OAuth flow

    Returns:
        GitHub OAuth authorization URL
    """
    if not GITHUB_APP_CLIENT_ID:
        raise GitHubOAuthError("GitHub App Client ID not configured")

    # Use the configured redirect URI
    redirect_uri = GITHUB_REDIRECT_URI

    # Log the redirect URI being used for debugging
    print(f"[GitHub App OAuth] Using redirect URI: {redirect_uri}")
    print(f"[GitHub App OAuth] Client ID: {GITHUB_APP_CLIENT_ID[:8]}...")

    params = {
        "client_id": GITHUB_APP_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "repo user:email read:org",  # Request permissions for repos, user info, and org access
    }

    auth_url = f"{GITHUB_AUTH_URL}?{urlencode(params)}"
    print(f"[GitHub App OAuth] Generated auth URL: {auth_url}")

    return auth_url


async def exchange_code(code: str) -> Dict[str, Any]:
    """
    Exchange authorization code for user access token
    Uses GitHub App's OAuth credentials

    Args:
        code: Authorization code from GitHub

    Returns:
        Token response from GitHub containing user access token
    """
    if not GITHUB_APP_CLIENT_SECRET:
        raise GitHubOAuthError("GitHub App Client Secret not configured")

    # Use GitHub App's OAuth credentials
    headers = {"Accept": "application/json"}
    data = {
        "client_id": GITHUB_APP_CLIENT_ID,
        "client_secret": GITHUB_APP_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_REDIRECT_URI,  # Must match the authorize step
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
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
    db: Session,
    github_user: Dict[str, Any],
    access_token: str,
    installation_id: Optional[int] = None,
    permissions: Optional[Dict[str, Any]] = None,
    repositories_url: Optional[str] = None
) -> User:
    """
    Create or update user in database from GitHub user info
    Enhanced for GitHub App OAuth support

    Args:
        db: Database session
        github_user: GitHub user information
        access_token: GitHub access token
        installation_id: Optional GitHub App installation ID
        permissions: Optional GitHub App permissions
        repositories_url: Optional URL for accessing installation repositories

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

        # Create new token with GitHub App OAuth support
        auth_token = AuthToken(
            user_id=user.id,
            access_token=access_token,
            token_type="bearer",
            scope="repo user:email read:org",  # GitHub App OAuth scopes
            expires_at=utc_now() + timedelta(hours=8),
            is_active=True,
            # GitHub App specific fields
            github_app_id=GITHUB_APP_ID,
            installation_id=installation_id,
            permissions=permissions,
            repositories_url=repositories_url,
        )
        db.add(auth_token)

        db.commit()
        db.refresh(user)

        return user

    except Exception as e:
        db.rollback()
        raise GitHubOAuthError(f"Failed to create or update user: {str(e)}")


def validate_github_app_config():
    """Validate that GitHub App OAuth configuration is complete"""
    missing_vars = []

    if not GITHUB_APP_CLIENT_ID:
        missing_vars.append("GITHUB_APP_CLIENT_ID")

    if not GITHUB_APP_CLIENT_SECRET:
        missing_vars.append("GITHUB_APP_CLIENT_SECRET")

    if not GITHUB_APP_ID:
        missing_vars.append("GITHUB_APP_ID")

    if not GITHUB_APP_PRIVATE_KEY_PATH:
        missing_vars.append("GITHUB_APP_PRIVATE_KEY_PATH")

    if missing_vars:
        raise GitHubOAuthError(
            f"Missing required GitHub App OAuth configuration: {', '.join(missing_vars)}"
        )

    # Check if private key file exists
    if not os.path.exists(GITHUB_APP_PRIVATE_KEY_PATH):
        raise GitHubOAuthError(
            f"GitHub App private key file not found: {GITHUB_APP_PRIVATE_KEY_PATH}"
        )


def validate_github_config():
    """Legacy validation function - redirects to new GitHub App validation"""
    return validate_github_app_config(        )


# ============================================================================
# SESSION TOKEN MANAGEMENT FUNCTIONS
# ============================================================================

def generate_session_token(length: int = 32) -> str:
    """Generate a secure random session token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def create_session_token(db: Session, user_id: int, expires_in_hours: int = 24) -> SessionToken:
    """Create a new session token for a user"""
    try:
        print(f"[Auth] Creating session token for user_id: {user_id}")

        # Generate new session token
        session_token = generate_session_token()
        expires_at = utc_now() + timedelta(hours=expires_in_hours)

        # Create new session token
        db_session_token = SessionToken(
            user_id=user_id,
            session_token=session_token,
            expires_at=expires_at,
            is_active=True
        )

        db.add(db_session_token)
        db.commit()
        db.refresh(db_session_token)

        print(f"[Auth] Successfully created session token with ID: {db_session_token.id}")
        return db_session_token

    except Exception as e:
        print(f"[Auth] Error creating session token for user {user_id}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session token"
        )


def validate_session_token(db: Session, session_token: str) -> Optional[User]:
    """Validate a session token and return the associated user"""
    try:
        if not session_token:
            print("[Auth] No session token provided for validation")
            return None

        print(f"[Auth] Validating session token: {session_token[:10]}...")

        # Find active session token
        db_session_token = db.query(SessionToken).filter(
            SessionToken.session_token == session_token,
            SessionToken.is_active
        ).first()

        if not db_session_token:
            print(f"[Auth] No active session token found: {session_token[:10]}...")
            return None

        # Check if token is expired
        if db_session_token.expires_at < utc_now():
            print(f"[Auth] Session token expired: {session_token[:10]}...")
            return None

        # Get user
        user = db.query(User).filter(User.id == db_session_token.user_id).first()

        if not user:
            print(f"[Auth] User not found for valid session token: {session_token[:10]}...")
            return None

        print(f"[Auth] Successfully validated session token for user: {user.github_username}")
        return user

    except Exception as e:
        print(f"[Auth] Error validating session token: {str(e)}")
        return None


def deactivate_session_token(db: Session, session_token: str) -> bool:
    """Deactivate a session token by setting is_active=False"""
    try:
        print(f"[Auth] Deactivating session token: {session_token[:10]}...")

        # Find the session token
        db_session_token = db.query(SessionToken).filter(
            SessionToken.session_token == session_token,
            SessionToken.is_active
        ).first()

        if not db_session_token:
            print(f"[Auth] Session token not found or already inactive: {session_token[:10]}...")
            return False

        # Deactivate the token
        db_session_token.is_active = False
        db_session_token.updated_at = utc_now()

        db.commit()

        print(f"[Auth] Successfully deactivated session token: {session_token[:10]}...")
        return True

    except Exception as e:
        print(f"[Auth] Error deactivating session token: {str(e)}")
        db.rollback()
        return False


# FastAPI security scheme for Bearer token authentication
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials

    # Always try session token first (frontend sends this)
    session_token = (
        db.query(SessionToken)
        .filter(
            SessionToken.session_token == token,
            SessionToken.is_active,
        )
        .first()
    )

    if session_token and session_token.expires_at > utc_now():
        user = db.query(User).filter(User.id == session_token.user_id).first()
        if user:
            return user

    # Fallback to GitHub token only if needed
    auth_token = (
        db.query(AuthToken)
        .filter(
            AuthToken.access_token == token,
            AuthToken.is_active,
        )
        .first()
    )

    if auth_token:
        # Check expiry for auth token
        if auth_token.expires_at and auth_token.expires_at < utc_now():
            # Deactivate expired token
            auth_token.is_active = False
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = db.query(User).filter(User.id == auth_token.user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    # Neither a valid session token nor a valid auth token
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_github_api(user_id: int, db: Session):
    """
    Get GitHub API client for authenticated user
    Uses user access token from GitHub App OAuth

    Args:
        user_id: User ID
        db: Database session

    Returns:
        GitHub API client instance

    Raises:
        HTTPException: If user not found or no valid token
    """
    # Get user's active token
    auth_token = (
        db.query(AuthToken)
        .filter(AuthToken.user_id == user_id, AuthToken.is_active)
        .first()
    )

    if not auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No valid authentication token found",
        )

    # Check if token is expired
    if auth_token.expires_at and auth_token.expires_at < utc_now():
        # Deactivate expired token
        auth_token.is_active = False
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
        )

    # Check if ghapi is available
    try:
        from ghapi.all import GhApi
    except ImportError as e:
        print(f"ImportError for ghapi: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub API library not available. Please install ghapi.",
        )

    try:
        return GhApi(token=auth_token.access_token)
    except Exception as e:
        print(f"Error initializing GhApi: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize GitHub API client: {str(e)}",
        )


def get_installation_github_api(installation_id: int):
    """
    Get GitHub API client for server-to-server operations using installation token
    Used for background operations and webhook processing

    Args:
        installation_id: GitHub App installation ID

    Returns:
        GitHub API client instance with installation token

    Raises:
        HTTPException: If installation token cannot be obtained
    """
    import asyncio

    # Get installation token
    installation_token = asyncio.run(get_installation_token(installation_id))

    if not installation_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not obtain installation access token",
        )

    # Check if ghapi is available
    try:
        from ghapi.all import GhApi
    except ImportError as e:
        print(f"ImportError for ghapi: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub API library not available. Please install ghapi.",
        )

    try:
        return GhApi(token=installation_token)
    except Exception as e:
        print(f"Error initializing GhApi with installation token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize GitHub API client: {str(e)}",
        )
