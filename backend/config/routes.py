# backend/config/routes.py - Simplified Contract One routes


class APIRoutes:
    """Simplified API route definitions for Contract One"""

    # Base prefixes (nginx strips /api/ prefix)
    AUTH_PREFIX = "/auth"
    GITHUB_PREFIX = "/github"
    DAIFU_PREFIX = "/daifu"

    # Auth routes
    AUTH_LOGIN = f"{AUTH_PREFIX}/api/login"
    AUTH_CALLBACK = f"{AUTH_PREFIX}/callback"
    AUTH_USER = f"{AUTH_PREFIX}/api/user"
    AUTH_LOGOUT = f"{AUTH_PREFIX}/api/logout"

    # GitHub routes
    GITHUB_REPOS = f"{GITHUB_PREFIX}/repositories"
    GITHUB_REPO_BRANCHES = f"{GITHUB_PREFIX}/repositories/{{owner}}/{{repo}}/branches"

    # Session routes
    SESSIONS_BASE = f"{DAIFU_PREFIX}/sessions"
    SESSIONS_DETAIL = f"{DAIFU_PREFIX}/sessions/{{sessionId}}"
    SESSIONS_MESSAGES = f"{DAIFU_PREFIX}/sessions/{{sessionId}}/messages"
    SESSIONS_CHAT = f"{DAIFU_PREFIX}/sessions/{{sessionId}}/chat"

    # Session Context Cards routes
    SESSIONS_CONTEXT_CARDS = f"{DAIFU_PREFIX}/sessions/{{sessionId}}/context-cards"
    SESSIONS_CONTEXT_CARD_DETAIL = (
        f"{DAIFU_PREFIX}/sessions/{{sessionId}}/context-cards/{{cardId}}"
    )

    # Session File Dependencies routes
    SESSIONS_FILE_DEPS_SESSION = (
        f"{DAIFU_PREFIX}/sessions/{{sessionId}}/file-deps/session"
    )
    SESSIONS_EXTRACT = f"{DAIFU_PREFIX}/sessions/{{sessionId}}/extract"

    # Session Issues routes
    SESSIONS_ISSUES_CREATE = (
        f"{DAIFU_PREFIX}/sessions/{{sessionId}}/issues/create-with-context"
    )
    SESSIONS_ISSUES_LIST = f"{DAIFU_PREFIX}/sessions/{{sessionId}}/issues"
    SESSIONS_ISSUES_DETAIL = f"{DAIFU_PREFIX}/sessions/{{sessionId}}/issues/{{issueId}}"

    # Session Solver routes
    SESSIONS_SOLVER_START = f"{DAIFU_PREFIX}/sessions/{{sessionId}}/solve/start"
    SESSIONS_SOLVER_STATUS = (
        f"{DAIFU_PREFIX}/sessions/{{sessionId}}/solve/sessions/{{solveSessionId}}"
    )
    SESSIONS_SOLVER_CANCEL = f"{DAIFU_PREFIX}/sessions/{{sessionId}}/solve/sessions/{{solveSessionId}}/cancel"

    # System routes
    HEALTH = "/health"
    ROOT = "/"

    @classmethod
    def get_router_prefixes(cls):
        """Get router prefixes for FastAPI mounting"""
        return {
            "auth": cls.AUTH_PREFIX,
            "github": cls.GITHUB_PREFIX,
            "sessions": cls.DAIFU_PREFIX,
        }


# Export simplified constants
API_ROUTES = APIRoutes()
