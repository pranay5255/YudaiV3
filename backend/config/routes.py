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
    # GITHUB_PREFIX = "/github"  # Removed as deprecated
    DAIFU_PREFIX = "/daifu"  # Unified: sessions, chat, file dependencies
    ISSUES_PREFIX = "/issues"
    # FILEDEPS_PREFIX = "/filedeps"  # DEPRECATED: moved to DAIFU_PREFIX
    API_V1_PREFIX = "/api/v1"

    # Authentication routes
    AUTH_LOGIN = f"{AUTH_PREFIX}/api/login"
    AUTH_CALLBACK = f"{AUTH_PREFIX}/callback"
    AUTH_USER = f"{AUTH_PREFIX}/api/user"
    AUTH_LOGOUT = f"{AUTH_PREFIX}/api/logout"

    # GitHub integration routes - DEPRECATED and removed
    # GITHUB_REPOS = f"{GITHUB_PREFIX}/repositories"
    # GITHUB_REPO_BRANCHES = f"{GITHUB_PREFIX}/repositories/{{owner}}/{{repo}}/branches"
    # GITHUB_USER_REPOS = f"{GITHUB_PREFIX}/repositories"

    # DAIFU (Chat) routes - UNIFIED SESSION ROUTES
    DAIFU_CHAT = f"{DAIFU_PREFIX}/chat"
    DAIFU_SESSIONS = DAIFU_PREFIX

    # Session-based Issue management routes - CONSOLIDATED
    SESSIONS_ISSUES_CREATE_WITH_CONTEXT = f"{DAIFU_PREFIX}/{{session_id}}/issues/create-with-context"
    SESSIONS_ISSUES_LIST = f"{DAIFU_PREFIX}/{{session_id}}/issues"
    SESSIONS_ISSUES_DETAIL = f"{DAIFU_PREFIX}/{{session_id}}/issues/{{issue_id}}"
    SESSIONS_ISSUES_UPDATE_STATUS = f"{DAIFU_PREFIX}/{{session_id}}/issues/{{issue_id}}/status"
    SESSIONS_ISSUES_CREATE_GITHUB_ISSUE = f"{DAIFU_PREFIX}/{{session_id}}/issues/{{issue_id}}/create-github-issue"

    # Session-based AI Solver routes - CONSOLIDATED
    SESSIONS_SOLVER_START = f"{DAIFU_PREFIX}/{{session_id}}/solve/start"
    SESSIONS_SOLVER_SESSION_DETAIL = f"{DAIFU_PREFIX}/{{session_id}}/solve/sessions/{{solve_session_id}}"
    SESSIONS_SOLVER_SESSION_STATS = f"{DAIFU_PREFIX}/{{session_id}}/solve/sessions/{{solve_session_id}}/stats"
    SESSIONS_SOLVER_CANCEL = f"{DAIFU_PREFIX}/{{session_id}}/solve/sessions/{{solve_session_id}}/cancel"
    SESSIONS_SOLVER_LIST = f"{DAIFU_PREFIX}/{{session_id}}/solve/sessions"
    SESSIONS_SOLVER_HEALTH = f"{DAIFU_PREFIX}/{{session_id}}/solve/health"

    # DEPRECATED: Old separate routes (kept for backward compatibility reference)
    # ISSUES_CREATE_WITH_CONTEXT = f"{ISSUES_PREFIX}/from-session-enhanced"
    # ISSUES_LIST = ISSUES_PREFIX
    # ISSUES_CREATE_GITHUB_ISSUE = f"{ISSUES_PREFIX}/{{issue_id}}/create-github-issue"
    # SOLVER_SOLVE = f"{API_V1_PREFIX}/solve"

    # Health and utility routes
    HEALTH = "/health"
    ROOT = "/"

    @classmethod
    def get_router_prefixes(cls) -> Dict[str, str]:
        """Get all router prefixes for mounting in FastAPI"""
        return {
            "auth": cls.AUTH_PREFIX,
            # "github": cls.GITHUB_PREFIX,  # Removed as deprecated
            "sessions": cls.DAIFU_PREFIX,  # UNIFIED: sessions, chat, file dependencies, issues, solver
            # DEPRECATED: Separate routers consolidated into sessions
            # "issues": cls.ISSUES_PREFIX,
            # "solver": cls.API_V1_PREFIX,
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
            # Removed deprecated GitHub checks
            # (cls.GITHUB_REPOS, cls.GITHUB_PREFIX, "GITHUB_REPOS"),
            # (cls.GITHUB_REPO_BRANCHES, cls.GITHUB_PREFIX, "GITHUB_REPO_BRANCHES"),
            # (cls.GITHUB_USER_REPOS, cls.GITHUB_PREFIX, "GITHUB_USER_REPOS"),
            (cls.DAIFU_CHAT, cls.DAIFU_PREFIX, "DAIFU_CHAT"),
            (cls.DAIFU_SESSIONS, cls.DAIFU_PREFIX, "DAIFU_SESSIONS"),
            # Session-based consolidated routes
            (
                cls.SESSIONS_ISSUES_CREATE_WITH_CONTEXT,
                cls.DAIFU_PREFIX,
                "SESSIONS_ISSUES_CREATE_WITH_CONTEXT",
            ),
            (cls.SESSIONS_ISSUES_LIST, cls.DAIFU_PREFIX, "SESSIONS_ISSUES_LIST"),
            (
                cls.SESSIONS_ISSUES_CREATE_GITHUB_ISSUE,
                cls.DAIFU_PREFIX,
                "SESSIONS_ISSUES_CREATE_GITHUB_ISSUE",
            ),
            (cls.SESSIONS_SOLVER_START, cls.DAIFU_PREFIX, "SESSIONS_SOLVER_START"),
            (cls.SESSIONS_SOLVER_LIST, cls.DAIFU_PREFIX, "SESSIONS_SOLVER_LIST"),
            # DEPRECATED routes (commented out)
            # (cls.ISSUES_CREATE_WITH_CONTEXT, cls.ISSUES_PREFIX, "ISSUES_CREATE_WITH_CONTEXT"),
            # (cls.ISSUES_LIST, cls.ISSUES_PREFIX, "ISSUES_LIST"),
            # (cls.ISSUES_CREATE_GITHUB_ISSUE, cls.ISSUES_PREFIX, "ISSUES_CREATE_GITHUB_ISSUE"),
            # (cls.SOLVER_SOLVE, cls.API_V1_PREFIX, "SOLVER_SOLVE"),
        ]

        for route, expected_prefix, route_name in route_checks:
            if not route.startswith(expected_prefix):
                issues.append(
                    f"{route_name}: '{route}' does not start with '{expected_prefix}'"
                )

        return issues

    @classmethod
    def validate_routes_on_startup(cls) -> None:
        """Validate route consistency on application startup and exit if issues found"""
        import sys

        print("🔍 Validating API route consistency...")

        issues = cls.validate_route_consistency()

        if issues:
            print("❌ Route validation failed:")
            for issue in issues:
                print(f"   - {issue}")
            print("\n🚨 Critical: Route inconsistencies detected. Application cannot start safely.")
            sys.exit(1)
        else:
            print("✅ All API routes are consistent")

    @classmethod
    def print_route_summary(cls) -> None:
        """Print a summary of all configured routes for debugging"""
        print("\n📋 API Route Summary:")
        print("=" * 50)

        all_routes = cls.get_all_routes()
        for route_name, route_path in all_routes.items():
            print(f"  {route_name:<30} → {route_path}")

        print("=" * 50)


# Convenience constants for import
AUTH_ROUTES = {
    "login": APIRoutes.AUTH_LOGIN,
    "callback": APIRoutes.AUTH_CALLBACK,
    "user": APIRoutes.AUTH_USER,
    "logout": APIRoutes.AUTH_LOGOUT,
}

# Removed deprecated GITHUB_ROUTES
# GITHUB_ROUTES = {  # DEPRECATED and removed
#     "repos": APIRoutes.GITHUB_REPOS,
#     "repo_branches": APIRoutes.GITHUB_REPO_BRANCHES,
#     "user_repos": APIRoutes.GITHUB_USER_REPOS,
# }

DAIFU_ROUTES = {
    "chat": APIRoutes.DAIFU_CHAT,
    "sessions": APIRoutes.DAIFU_SESSIONS,
}

SESSIONS_ROUTES = {
    "base": APIRoutes.DAIFU_SESSIONS,
    "chat": APIRoutes.DAIFU_CHAT,
    # Consolidated Issues routes
    "issues_create_with_context": APIRoutes.SESSIONS_ISSUES_CREATE_WITH_CONTEXT,
    "issues_list": APIRoutes.SESSIONS_ISSUES_LIST,
    "issues_detail": APIRoutes.SESSIONS_ISSUES_DETAIL,
    "issues_update_status": APIRoutes.SESSIONS_ISSUES_UPDATE_STATUS,
    "issues_create_github_issue": APIRoutes.SESSIONS_ISSUES_CREATE_GITHUB_ISSUE,
    # Consolidated Solver routes
    "solver_start": APIRoutes.SESSIONS_SOLVER_START,
    "solver_session_detail": APIRoutes.SESSIONS_SOLVER_SESSION_DETAIL,
    "solver_session_stats": APIRoutes.SESSIONS_SOLVER_SESSION_STATS,
    "solver_cancel": APIRoutes.SESSIONS_SOLVER_CANCEL,
    "solver_list": APIRoutes.SESSIONS_SOLVER_LIST,
    "solver_health": APIRoutes.SESSIONS_SOLVER_HEALTH,
}

# DEPRECATED: Old separate route constants (kept for reference)
# ISSUES_ROUTES = {
#     "create_with_context": APIRoutes.ISSUES_CREATE_WITH_CONTEXT,
#     "list": APIRoutes.ISSUES_LIST,
#     "create_github_issue": APIRoutes.ISSUES_CREATE_GITHUB_ISSUE,
# }

# SOLVER_ROUTES = {
#     "solve": APIRoutes.SOLVER_SOLVE,
# }
