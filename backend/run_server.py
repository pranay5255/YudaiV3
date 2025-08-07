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

from contextlib import asynccontextmanager

import uvicorn

# Import all service routers
from auth import auth_router
from daifuUserAgent.chat_api import router as daifu_router
from stateManagement.session_routes import router as session_router

# Import database initialization
from db.database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from github import github_router
from issueChatServices import issue_router
from repo_processorGitIngest.filedeps import router as filedeps_router


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
    lifespan=lifespan
)

# Add CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", 
        "http://localhost:5173",  # React dev servers
        "https://yudai.app",      # Production domain
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all service routers
app.include_router(auth_router, prefix="/auth", tags=["authentication"])
app.include_router(github_router, prefix="/github", tags=["github"])
app.include_router(session_router, prefix="/daifu", tags=["sessions"])
app.include_router(daifu_router, prefix="/daifu", tags=["chat"])
app.include_router(issue_router, prefix="/issues", tags=["issues"])
app.include_router(filedeps_router, prefix="/filedeps", tags=["file-dependencies"])

# Add a unified root endpoint
@app.get("/")
async def api_root():
    """Root endpoint with API information."""
    return {
        "message": "YudaiV3 Backend API",
        "version": "1.0.0",
        "services": {
            "authentication": "/auth",
            "github": "/github", 
            "chat": "/daifu",
            "issues": "/issues",
            "file-dependencies": "/filedeps"
        },
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }

# Add health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "yudai-v3-backend"}

if __name__ == "__main__":
    print("Starting YudaiV3 Backend API server...")
    print("Server will be available at: http://localhost:8000")
    print("API documentation at: http://localhost:8000/docs")
    print("ReDoc documentation at: http://localhost:8000/redoc")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
