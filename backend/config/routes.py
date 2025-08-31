#!/usr/bin/env python3
"""
backend/config/routes.py - Centralized route definitions for YudaiV3 backend

This file serves as the single source of truth for all API route definitions.
It ensures consistency between frontend, backend, and nginx configurations.
"""

from typing import Dict


class APIRoutes:
    """Centralized API route definitions for YudaiV3 backend"""

    # Base prefixes - These match nginx routing patterns
    AUTH_PREFIX = "/auth"
    GITHUB_PREFIX = "/github"
    DAIFU_PREFIX = "/daifu"
    ISSUES_PREFIX = "/issues"
    FILEDEPS_PREFIX = "/filedeps"
    API_V1_PREFIX = "/api/v1"

    # Authentication routes
    AUTH_LOGIN = f"{AUTH_PREFIX}/api/login"
    AUTH_CALLBACK = f"{AUTH_PREFIX}/callback"
    AUTH_USER = f"{AUTH_PREFIX}/api/user"
    AUTH_LOGOUT = f"{AUTH_PREFIX}/api/logout"

    # GitHub integration routes
    GITHUB_REPOS = f"{GITHUB_PREFIX}/repositories"
    GITHUB_REPO_BRANCHES = f"{GITHUB_PREFIX}/repositories/{{owner}}/{{repo}}/branches"
    GITHUB_USER_REPOS = f"{GITHUB_PREFIX}/repositories"

    # DAIFU (Chat) routes
    DAIFU_CHAT = f"{DAIFU_PREFIX}/chat"
    DAIFU_SESSIONS = DAIFU_PREFIX

    # Issue management routes
    ISSUES_CREATE_WITH_CONTEXT = f"{ISSUES_PREFIX}/from-session-enhanced"
    ISSUES_LIST = ISSUES_PREFIX
    ISSUES_CREATE_GITHUB_ISSUE = f"{ISSUES_PREFIX}/{{issue_id}}/create-github-issue"

    # File dependencies routes
    FILEDEPS_EXTRACT = f"{FILEDEPS_PREFIX}/extract"

    # AI Solver routes
    SOLVER_SOLVE = f"{API_V1_PREFIX}/solve"

    # Health and utility routes
    HEALTH = "/health"
    ROOT = "/"

    @classmethod
    def get_router_prefixes(cls) -> Dict[str, str]:
        """Get all router prefixes for mounting in FastAPI"""
        return {
            "auth": cls.AUTH_PREFIX,
            "github": cls.GITHUB_PREFIX,
            "daifu_sessions": cls.DAIFU_PREFIX,
            "daifu_chat": cls.DAIFU_PREFIX,
            "issues": cls.ISSUES_PREFIX,
            "filedeps": cls.FILEDEPS_PREFIX,
            "solver": cls.API_V1_PREFIX,
        }

    @classmethod
    def get_all_routes(cls) -> Dict[str, str]:
        """Get all route definitions for documentation and validation"""
        routes = {}
        for attr_name in dir(cls):
            if not attr_name.startswith("_") and not callable(getattr(cls, attr_name)):
                value = getattr(cls, attr_name)
                if isinstance(value, str):
                    routes[attr_name] = value
        return routes

    @classmethod
    def validate_route_consistency(cls) -> list[str]:
        """Validate that route definitions are consistent"""
        issues = []

        # Check that all routes start with their respective prefixes
        route_checks = [
            (cls.AUTH_LOGIN, cls.AUTH_PREFIX, "AUTH_LOGIN"),
            (cls.AUTH_CALLBACK, cls.AUTH_PREFIX, "AUTH_CALLBACK"),
            (cls.AUTH_USER, cls.AUTH_PREFIX, "AUTH_USER"),
            (cls.AUTH_LOGOUT, cls.AUTH_PREFIX, "AUTH_LOGOUT"),
            (cls.GITHUB_REPOS, cls.GITHUB_PREFIX, "GITHUB_REPOS"),
            (cls.GITHUB_REPO_BRANCHES, cls.GITHUB_PREFIX, "GITHUB_REPO_BRANCHES"),
            (cls.GITHUB_USER_REPOS, cls.GITHUB_PREFIX, "GITHUB_USER_REPOS"),
            (cls.DAIFU_CHAT, cls.DAIFU_PREFIX, "DAIFU_CHAT"),
            (cls.DAIFU_SESSIONS, cls.DAIFU_PREFIX, "DAIFU_SESSIONS"),
            (
                cls.ISSUES_CREATE_WITH_CONTEXT,
                cls.ISSUES_PREFIX,
                "ISSUES_CREATE_WITH_CONTEXT",
            ),
            (cls.ISSUES_LIST, cls.ISSUES_PREFIX, "ISSUES_LIST"),
            (
                cls.ISSUES_CREATE_GITHUB_ISSUE,
                cls.ISSUES_PREFIX,
                "ISSUES_CREATE_GITHUB_ISSUE",
            ),
            (cls.FILEDEPS_EXTRACT, cls.FILEDEPS_PREFIX, "FILEDEPS_EXTRACT"),
            (cls.SOLVER_SOLVE, cls.API_V1_PREFIX, "SOLVER_SOLVE"),
        ]

        for route, expected_prefix, route_name in route_checks:
            if not route.startswith(expected_prefix):
                issues.append(
                    f"{route_name}: '{route}' does not start with '{expected_prefix}'"
                )

        return issues


# Convenience constants for import
AUTH_ROUTES = {
    "login": APIRoutes.AUTH_LOGIN,
    "callback": APIRoutes.AUTH_CALLBACK,
    "user": APIRoutes.AUTH_USER,
    "logout": APIRoutes.AUTH_LOGOUT,
}

GITHUB_ROUTES = {
    "repos": APIRoutes.GITHUB_REPOS,
    "repo_branches": APIRoutes.GITHUB_REPO_BRANCHES,
    "user_repos": APIRoutes.GITHUB_USER_REPOS,
}

DAIFU_ROUTES = {
    "chat": APIRoutes.DAIFU_CHAT,
    "sessions": APIRoutes.DAIFU_SESSIONS,
}

ISSUES_ROUTES = {
    "create_with_context": APIRoutes.ISSUES_CREATE_WITH_CONTEXT,
    "list": APIRoutes.ISSUES_LIST,
    "create_github_issue": APIRoutes.ISSUES_CREATE_GITHUB_ISSUE,
}

FILEDEPS_ROUTES = {
    "extract": APIRoutes.FILEDEPS_EXTRACT,
}

SOLVER_ROUTES = {
    "solve": APIRoutes.SOLVER_SOLVE,
}
