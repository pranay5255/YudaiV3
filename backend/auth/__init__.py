"""
Authentication module for YudaiV3

This module provides GitHub OAuth authentication functionality using ghapi.
"""

from .github_oauth import (
    get_current_user,
    get_current_user_optional,
    get_github_api,
    validate_github_config,
    GitHubOAuthError
)
from .auth_routes import router as auth_router

__all__ = [
    "get_current_user",
    "get_current_user_optional", 
    "get_github_api",
    "validate_github_config",
    "GitHubOAuthError",
    "auth_router"
] 