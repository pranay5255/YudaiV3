#!/usr/bin/env python3
"""
Unified FastAPI server for YudaiV3 backend services

This server combines all the backend services:
- Authentication (GitHub OAuth)
- GitHub API integration
- File dependencies extraction
- Chat services (DAifu agent)
- Issue management services
"""

import os
from contextlib import asynccontextmanager

import uvicorn

# Import all service routers
from auth import auth_router
from daifuUserAgent.session_routes import router as session_router

# Import database initialization
from db.database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
# from github import github_router  # Removed as deprecated

# DEPRECATED: issue_router and solve_router have been consolidated into session_router
# from issueChatServices import issue_router
# from routers.solve_router import router as solve_router
# ✅ CONSOLIDATION COMPLETED:
# - chat_api.py functionality has been consolidated into session_routes.py
# - filedeps.py functionality has been consolidated into session_routes.py
# - All chat and file dependency operations now happen within session context
# - Single unified router (session_router) handles all session-related operations
# Import centralized route configuration
from config.routes import APIRoutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the FastAPI application."""
    # Startup
    print("Initializing database...")
    init_db()
    print("Database initialized successfully")
    yield
    # Shutdown
    print("Shutting down...")


# Create the main FastAPI application
app = FastAPI(
    title="YudaiV3 Backend API",
    description="Unified backend API for YudaiV3 - File Dependencies, Chat, Issues, and GitHub Integration",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Add CORS middleware for frontend integration
allow_origins = os.getenv(
    "ALLOW_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://yudai.app,https://www.yudai.app",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# ROUTER CONFIGURATION FOR UNIFIED STATE MANAGEMENT
# ============================================================================
#
# ✅ ACTIVE ROUTERS (Unified State Management):
# - auth_router: Authentication operations (login/logout/user management)
# - github_router: GitHub API integration (repository operations)
# - session_router: ALL session-scoped operations including:
#   * Session CRUD (create, get, update, delete sessions)
#   * Chat messages and conversation history
#   * Context cards management
#   * File dependencies extraction and management
#   * File embeddings and semantic search
# - issue_router: Issue management (integrated with session context)
# - solve_router: AI solver operations (SWE-agent integration)
#
# ✅ CONSOLIDATION COMPLETED:
# - daifu_router: ✅ REMOVED - All chat operations consolidated into session_router
# - filedeps_router: ✅ REMOVED - All file operations consolidated into session_router
#
# 📋 UNIFIED ARCHITECTURE:
# - Session-centric design: All operations tied to user sessions
# - Consistent authentication and authorization across all endpoints
# - Unified error handling, logging, and response formats
# - Single source of truth for session state management
# ============================================================================

app.include_router(auth_router, prefix=APIRoutes.AUTH_PREFIX, tags=["authentication"])
# app.include_router(github_router, prefix=APIRoutes.GITHUB_PREFIX, tags=["github"])  # Deprecated and removed
app.include_router(session_router, prefix=APIRoutes.DAIFU_PREFIX, tags=["sessions"])

# DEPRECATED: issue_router and solve_router have been consolidated into session_router
# All issues and solver operations are now available under /daifu/sessions/{session_id}/...
# app.include_router(issue_router, prefix=APIRoutes.ISSUES_PREFIX, tags=["issues"])
# app.include_router(solve_router, prefix=APIRoutes.API_V1_PREFIX, tags=["ai-solver"])


# Add a unified root endpoint
@app.get(APIRoutes.ROOT)
async def api_root():
    """Root endpoint with API information."""
    return {
        "message": "YudaiV3 Backend API - Unified Session Architecture",
        "version": "1.0.0",
        "architecture": "Session-centric unified state management",
        "services": {
            "authentication": {
                "prefix": APIRoutes.AUTH_PREFIX,
                "description": "GitHub OAuth authentication and user management"
            },
            "sessions": {
                "prefix": APIRoutes.DAIFU_PREFIX,
                "description": "Unified session management (chat, file dependencies, context cards)"
            },
            "issues": {
                "prefix": APIRoutes.ISSUES_PREFIX,
                "description": "Issue management with session context integration"
            },
            "ai-solver": {
                "prefix": APIRoutes.API_V1_PREFIX,
                "description": "SWE-agent AI solver for automated code solutions"
            },
        },
        "documentation": {"swagger": "/docs", "redoc": "/redoc"},
        "consolidation_status": "✅ Complete - All deprecated routers removed"
    }


# Add health check endpoint
@app.get(APIRoutes.HEALTH)
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "yudai-v3-backend"}


if __name__ == "__main__":
    print("Starting YudaiV3 Backend API server...")
    print("Server will be available at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")
    print("ReDoc documentation at: http://localhost:8000/redoc")

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
