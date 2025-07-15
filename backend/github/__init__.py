"""
GitHub API integration module for YudaiV3

This module provides GitHub API functionality using ghapi for authenticated users.
"""

from .github_api import (
    get_user_repositories,
    get_repository_details,
    create_issue,
    get_repository_issues,
    get_repository_pulls,
    get_repository_commits,
    search_repositories,
    GitHubAPIError
)
from .github_routes import router as github_router

__all__ = [
    "get_user_repositories",
    "get_repository_details", 
    "create_issue",
    "get_repository_issues",
    "get_repository_pulls",
    "get_repository_commits",
    "search_repositories",
    "GitHubAPIError",
    "github_router"
] 