"""
Authentication module for YudaiV3

Simplified GitHub OAuth authentication functionality.
"""

from .auth_routes import router as auth_router
from .github_oauth import (
    GitHubOAuthError,
    create_or_update_user,
    exchange_code,
    get_github_oauth_url,
    user_info,
    validate_github_config,
)

__all__ = [
    "validate_github_config",
    "GitHubOAuthError", 
    "get_github_oauth_url",
    "exchange_code",
    "user_info",
    "create_or_update_user",
    "auth_router"
]