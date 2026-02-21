#!/usr/bin/env python3
"""
YudaiV3 Backend API Server - Contract One Architecture

All API calls go through /api/* umbrella (nginx strips prefix)
"""

import os
from contextlib import asynccontextmanager

import uvicorn

# Import routers
from auth import auth_router
from config.realtime_flags import get_realtime_feature_flags
from daifuUserAgent.session_routes import router as session_router

# Import database
from db.database import init_db
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from github import github_router
from realtime.controller_routes import router as controller_router
from solver.solver import router as solver_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    print("🚀 Starting YudaiV3 Backend API server...")
    print("📊 Initializing database...")
    init_db()
    print("✅ Database initialized successfully")
    print("🔗 Contract One: All API calls through /api/* umbrella")

    yield

    print("🛑 Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="YudaiV3 Backend API",
    description="Contract One: All API calls through /api/* umbrella",
    version="2.0.0",
    docs_url="/docs",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "ALLOW_ORIGINS", "http://localhost:3000,https://yudai.app"
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers - Contract One compatible
app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(github_router, prefix="/github", tags=["github"])
app.include_router(session_router, prefix="/daifu", tags=["sessions"])
app.include_router(solver_router, prefix="/daifu", tags=["solver"])
app.include_router(controller_router, tags=["realtime-controller"])


# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "YudaiV3 Backend API",
        "version": "2.0.0",
        "architecture": "Contract One - /api/* umbrella",
        "docs": "/docs",
    }


# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "yudai-v3-backend"}


@app.get("/realtime/flags")
async def realtime_flags():
    """Expose phase rollout flags for frontend/controller coordination."""
    flags = get_realtime_feature_flags()
    return {"flags": flags.as_dict()}


if __name__ == "__main__":
    print("🚀 Starting YudaiV3 Backend API server...")
    print("📡 Server: http://localhost:8000")
    print("📚 Docs: http://localhost:8000/docs")
    print("💚 Health: http://localhost:8000/health")

    uvicorn.run(app, host="0.0.0.0", port=8000)
