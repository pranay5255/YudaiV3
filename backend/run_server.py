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
from daifuUserAgent.chat_api import router as daifu_router
from daifuUserAgent.session_routes import router as session_router

# Import database initialization
from db.database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from github import github_router
from issueChatServices import issue_router
from repo_processorGitIngest.filedeps import router as filedeps_router
from routers.solve_router import router as solve_router

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
# - auth_router: Login/logout operations only
# - session_router: All session CRUD, messages, context cards, file dependencies
# - github_router: Repository operations (used by unified repository state)
#
# 🔄 ROUTERS TO CONSOLIDATE:
# - daifu_router: Move chat operations to session_router for unified session context
# - filedeps_router: Move file operations to session_router for unified file state
# - issue_router: Keep separate but ensure it integrates with session context
# - solve_router: Keep separate for AI solver operations
#
# 📋 MIGRATION PLAN:
# 1. Move all chat operations from daifu_router to session_router
# 2. Move file dependency operations from filedeps_router to session_router
# 3. Ensure all operations require session context
# 4. Standardize error responses across all routers
# ============================================================================

app.include_router(auth_router, prefix=APIRoutes.AUTH_PREFIX, tags=["authentication"])
app.include_router(github_router, prefix=APIRoutes.GITHUB_PREFIX, tags=["github"])
app.include_router(session_router, prefix=APIRoutes.DAIFU_PREFIX, tags=["sessions"])
app.include_router(daifu_router, prefix=APIRoutes.DAIFU_PREFIX, tags=["chat"])
app.include_router(issue_router, prefix=APIRoutes.ISSUES_PREFIX, tags=["issues"])
app.include_router(
    filedeps_router, prefix=APIRoutes.FILEDEPS_PREFIX, tags=["file-dependencies"]
)
app.include_router(solve_router, prefix=APIRoutes.API_V1_PREFIX, tags=["ai-solver"])


# Add a unified root endpoint
@app.get(APIRoutes.ROOT)
async def api_root():
    """Root endpoint with API information."""
    return {
        "message": "YudaiV3 Backend API",
        "version": "1.0.0",
        "services": {
            "authentication": APIRoutes.AUTH_PREFIX,
            "github": APIRoutes.GITHUB_PREFIX,
            "chat": APIRoutes.DAIFU_PREFIX,
            "issues": APIRoutes.ISSUES_PREFIX,
            "file-dependencies": APIRoutes.FILEDEPS_PREFIX,
            "ai-solver": APIRoutes.API_V1_PREFIX,
        },
        "documentation": {"swagger": "/docs", "redoc": "/redoc"},
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
