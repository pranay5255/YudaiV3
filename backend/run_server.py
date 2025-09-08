#!/usr/bin/env python3
"""
Unified FastAPI server for YudaiV3 backend services

This server implements a hybrid architecture combining:
- Authentication (GitHub OAuth)
- Standalone GitHub API integration
- Session-centric unified operations
- Chat services (DAifu agent)
- Issue management services
- AI Solver operations

Architecture:
- Standalone routes for direct frontend access
- Session-integrated routes for contextual operations
- Comprehensive usage tracking and monitoring
"""

import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

import uvicorn

# Import all service routers
from auth import auth_router
from daifuUserAgent.session_routes import router as session_router

# Import database initialization
from db.database import init_db
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from github import (
    github_router,  # Re-added: Standalone GitHub router for /github/* routes
)

# Import centralized route configuration
from config.routes import APIRoutes

# Global usage tracking
usage_stats = defaultdict(lambda: {"count": 0, "total_time": 0.0, "errors": 0})


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the FastAPI application."""
    # Startup
    print("🚀 Starting YudaiV3 Backend API server...")
    print("📊 Initializing database...")
    init_db()
    print("✅ Database initialized successfully")
    
    # Validate route consistency on startup
    print("🔍 Validating API route consistency...")
    APIRoutes.validate_routes_on_startup()
    APIRoutes.print_route_summary()
    
    yield
    # Shutdown
    print("📊 Final usage statistics:")
    print_usage_stats()
    print("🛑 Shutting down...")


def print_usage_stats():
    """Print current usage statistics."""
    if not usage_stats:
        print("No usage data available")
        return
    
    print("=" * 80)
    print("📊 API ENDPOINT USAGE STATISTICS")
    print("=" * 80)
    
    total_requests = sum(stats["count"] for stats in usage_stats.values())
    
    # Sort by usage count
    sorted_stats = sorted(usage_stats.items(), key=lambda x: x[1]["count"], reverse=True)
    
    for endpoint, stats in sorted_stats:
        usage_percentage = (stats["count"] / total_requests * 100) if total_requests > 0 else 0
        avg_time = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
        error_rate = (stats["errors"] / stats["count"] * 100) if stats["count"] > 0 else 0
        
        print(f"📍 {endpoint}")
        print(f"   📊 Usage: {stats['count']:>6} requests ({usage_percentage:>5.1f}%)")
        print(f"   ⏱️  Avg Time: {avg_time:>8.3f}s")
        print(f"   ❌ Error Rate: {error_rate:>6.1f}%")
        print()
    
    print("=" * 80)


# Usage tracking middleware
async def track_usage_middleware(request: Request, call_next):
    """Middleware to track API endpoint usage statistics."""
    start_time = time.time()
    endpoint = f"{request.method} {request.url.path}"
    
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Update usage stats
        usage_stats[endpoint]["count"] += 1
        usage_stats[endpoint]["total_time"] += process_time
        
        if response.status_code >= 400:
            usage_stats[endpoint]["errors"] += 1
        
        # Add processing time header
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
    except Exception:
        process_time = time.time() - start_time
        usage_stats[endpoint]["count"] += 1
        usage_stats[endpoint]["total_time"] += process_time
        usage_stats[endpoint]["errors"] += 1
        raise


# Create the main FastAPI application
app = FastAPI(
    title="YudaiV3 Backend API",
    description="""
    ## Unified Backend API for YudaiV3
    
    ### Architecture Overview
    This API implements a **hybrid architecture** combining:
    - **Standalone routes** for direct frontend access
    - **Session-integrated routes** for contextual operations
    - **Comprehensive usage tracking** and monitoring
    
    ### Service Categories
    
    #### 🔐 Authentication (`/auth/*`)
    - GitHub OAuth integration
    - User session management
    - Token validation and refresh
    
    #### 🐙 GitHub Integration (`/github/*`)
    - **Standalone GitHub API** for repository operations
    - Repository listing and branch fetching
    - Direct GitHub operations without session context
    - **Use case**: Repository selection, initial setup
    
    #### 🎯 Session Management (`/daifu/*`)
    - **Session-centric unified operations** including:
      - Session CRUD operations
      - Chat and conversation management
      - File dependencies and embeddings
      - Context cards management
      - Session-scoped GitHub operations (`/daifu/github/*`)
      - Session-scoped issue management (`/daifu/sessions/{id}/issues/*`)
      - Session-scoped AI solver operations (`/daifu/sessions/{id}/solve/*`)
    
    ### Route Duplication Strategy
    GitHub functionality intentionally exists in two contexts:
    1. **`/github/*`** - Standalone operations for setup/selection
    2. **`/daifu/github/*`** - Session-integrated operations for context
    
    This duplication is **architectural, not accidental**.
    
    ### Deprecated Services
    - **Issues** (`/issues/*`) → Migrated to `/daifu/sessions/{session_id}/issues/*`
    - **AI Solver** (`/api/v1/*`) → Migrated to `/daifu/sessions/{session_id}/solve/*`
    """,
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

# Add usage tracking middleware
app.middleware("http")(track_usage_middleware)

# ============================================================================
# ROUTER CONFIGURATION - HYBRID ARCHITECTURE WITH PROPER DEPRECATION
# ============================================================================
#
# 🏗️ ARCHITECTURE OVERVIEW:
# The YudaiV3 backend follows a hybrid architecture to support both:
# 1. Standalone API endpoints for direct frontend access
# 2. Session-integrated endpoints for contextual operations
#
# 📋 ACTIVE ROUTERS:
# 
# 1. auth_router (/auth/*):
#    - Authentication operations (login/logout/user management)
#    - GitHub OAuth integration
#    - User session management
#
# 2. github_router (/github/*):
#    - Standalone GitHub API integration
#    - Repository listing, branch fetching
#    - Direct GitHub operations without session context
#    - Required for: Repository selection, initial setup
#
# 3. session_router (/daifu/*):
#    - Session-centric unified operations including:
#      * Session CRUD (create, get, update, delete sessions)
#      * Chat messages and conversation history
#      * Context cards management
#      * File dependencies extraction and management
#      * File embeddings and semantic search
#      * Session-scoped GitHub operations (/daifu/github/*)
#      * Session-scoped issue management (/daifu/sessions/{id}/issues/*)
#      * Session-scoped AI solver operations (/daifu/sessions/{id}/solve/*)
#
# 🔄 DEPRECATION STATUS:
# ✅ COMPLETED CONSOLIDATIONS:
# - daifu_router: REMOVED - All chat operations → session_router
# - filedeps_router: REMOVED - All file operations → session_router  
# - issue_router: REMOVED - All issue operations → session_router (/daifu/sessions/{id}/issues/*)
# - solve_router: REMOVED - All solver operations → session_router (/daifu/sessions/{id}/solve/*)
#
# 🎯 CURRENT ARCHITECTURE BENEFITS:
# - Standalone GitHub routes: Direct access for repository selection
# - Session-integrated GitHub routes: Contextual operations within sessions
# - Unified session management: All operations tied to user sessions
# - Consistent authentication and authorization across all endpoints
# - Unified error handling, logging, and response formats
# - Single source of truth for session state management
#
# ⚠️ ROUTE DUPLICATION STRATEGY:
# GitHub functionality intentionally exists in two contexts:
# 1. /github/* - Standalone operations for setup/selection
# 2. /daifu/github/* - Session-integrated operations for context
# This duplication is architectural, not accidental.
# ============================================================================

# Mount routers in order of priority (most specific first)
app.include_router(auth_router, prefix=APIRoutes.AUTH_PREFIX, tags=["authentication"])
app.include_router(github_router, prefix=APIRoutes.GITHUB_PREFIX, tags=["github"])
app.include_router(session_router, prefix=APIRoutes.DAIFU_PREFIX, tags=["sessions"])

# DEPRECATED: issue_router and solve_router have been consolidated into session_router
# All issues and solver operations are now available under /daifu/sessions/{session_id}/...
# app.include_router(issue_router, prefix=APIRoutes.ISSUES_PREFIX, tags=["issues"])
# app.include_router(solve_router, prefix=APIRoutes.API_V1_PREFIX, tags=["ai-solver"])


# Add a unified root endpoint with comprehensive API information
@app.get(APIRoutes.ROOT)
async def api_root():
    """Root endpoint with comprehensive API information and usage statistics."""
    total_requests = sum(stats["count"] for stats in usage_stats.values())
    
    # Calculate router usage percentages
    router_stats = {
        "authentication": {"count": 0, "percentage": 0.0},
        "github": {"count": 0, "percentage": 0.0},
        "sessions": {"count": 0, "percentage": 0.0}
    }
    
    for endpoint, stats in usage_stats.items():
        if endpoint.startswith("GET /auth") or endpoint.startswith("POST /auth"):
            router_stats["authentication"]["count"] += stats["count"]
        elif endpoint.startswith("GET /github") or endpoint.startswith("POST /github"):
            router_stats["github"]["count"] += stats["count"]
        elif endpoint.startswith("GET /daifu") or endpoint.startswith("POST /daifu"):
            router_stats["sessions"]["count"] += stats["count"]
    
    # Calculate percentages
    for router in router_stats:
        if total_requests > 0:
            router_stats[router]["percentage"] = (router_stats[router]["count"] / total_requests) * 100
    
    return {
        "message": "YudaiV3 Backend API - Hybrid Architecture",
        "version": "1.0.0",
        "architecture": "Hybrid: Standalone + Session-centric unified state management",
        "usage_statistics": {
            "total_requests": total_requests,
            "router_usage": router_stats
        },
        "services": {
            "authentication": {
                "prefix": APIRoutes.AUTH_PREFIX,
                "description": "GitHub OAuth authentication and user management",
                "status": "active",
                "endpoints": [
                    "POST /auth/api/login - GitHub OAuth login",
                    "GET /auth/callback - OAuth callback handler",
                    "GET /auth/api/user - Get current user info",
                    "POST /auth/api/logout - Logout user"
                ]
            },
            "github": {
                "prefix": APIRoutes.GITHUB_PREFIX,
                "description": "Standalone GitHub API integration (repository operations)",
                "status": "active",
                "note": "For direct repository access and selection",
                "endpoints": [
                    "GET /github/repositories - List user repositories",
                    "GET /github/repositories/{owner}/{repo}/branches - List repository branches"
                ]
            },
            "sessions": {
                "prefix": APIRoutes.DAIFU_PREFIX,
                "description": "Unified session management (chat, file dependencies, context cards, issues, solver)",
                "status": "active",
                "features": [
                    "Session CRUD operations",
                    "Chat and conversation management", 
                    "File dependencies and embeddings",
                    "Context cards management",
                    "Session-scoped GitHub operations (/daifu/github/*)",
                    "Session-scoped issue management (/daifu/sessions/{id}/issues/*)",
                    "Session-scoped AI solver operations (/daifu/sessions/{id}/solve/*)"
                ],
                "key_endpoints": [
                    "POST /daifu/sessions - Create new session",
                    "GET /daifu/sessions/{session_id} - Get session context",
                    "POST /daifu/sessions/{session_id}/chat - Chat within session",
                    "GET /daifu/github/repositories - Session-scoped GitHub repos",
                    "POST /daifu/sessions/{session_id}/extract - Extract file dependencies",
                    "POST /daifu/sessions/{session_id}/issues/create-with-context - Create issue",
                    "POST /daifu/sessions/{session_id}/solve/start - Start AI solver"
                ]
            }
        },
        "deprecated_services": {
            "issues": {
                "prefix": APIRoutes.ISSUES_PREFIX,
                "status": "deprecated",
                "migration_path": f"{APIRoutes.DAIFU_PREFIX}/sessions/{{session_id}}/issues/*",
                "description": "Issue management migrated to session-scoped endpoints"
            },
            "ai-solver": {
                "prefix": APIRoutes.API_V1_PREFIX,
                "status": "deprecated", 
                "migration_path": f"{APIRoutes.DAIFU_PREFIX}/sessions/{{session_id}}/solve/*",
                "description": "SWE-agent AI solver migrated to session-scoped endpoints"
            }
        },
        "route_duplication_strategy": {
            "github_routes": {
                "standalone": f"{APIRoutes.GITHUB_PREFIX}/*",
                "session_integrated": f"{APIRoutes.DAIFU_PREFIX}/github/*",
                "rationale": "Standalone for setup/selection, session-integrated for contextual operations"
            }
        },
        "documentation": {
            "swagger": "/docs", 
            "redoc": "/redoc",
            "usage_stats": "/stats",
            "health": "/health"
        },
        "consolidation_status": "✅ Complete - Hybrid architecture implemented"
    }


# Add usage statistics endpoint
@app.get("/stats")
async def get_usage_statistics():
    """Get detailed API usage statistics."""
    total_requests = sum(stats["count"] for stats in usage_stats.values())
    
    if total_requests == 0:
        return {
            "message": "No usage data available yet",
            "total_requests": 0,
            "endpoints": []
        }
    
    # Sort by usage count
    sorted_stats = sorted(usage_stats.items(), key=lambda x: x[1]["count"], reverse=True)
    
    endpoint_stats = []
    for endpoint, stats in sorted_stats:
        usage_percentage = (stats["count"] / total_requests * 100)
        avg_time = stats["total_time"] / stats["count"] if stats["count"] > 0 else 0
        error_rate = (stats["errors"] / stats["count"] * 100) if stats["count"] > 0 else 0
        
        endpoint_stats.append({
            "endpoint": endpoint,
            "requests": stats["count"],
            "usage_percentage": round(usage_percentage, 2),
            "avg_response_time_seconds": round(avg_time, 3),
            "error_rate_percentage": round(error_rate, 2),
            "total_errors": stats["errors"]
        })
    
    return {
        "total_requests": total_requests,
        "endpoints": endpoint_stats,
        "timestamp": time.time()
    }


# Add health check endpoint
@app.get(APIRoutes.HEALTH)
async def health_check():
    """Health check endpoint with system status."""
    total_requests = sum(stats["count"] for stats in usage_stats.values())
    total_errors = sum(stats["errors"] for stats in usage_stats.values())
    error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
    
    return {
        "status": "healthy" if error_rate < 10 else "degraded",
        "service": "yudai-v3-backend",
        "version": "1.0.0",
        "architecture": "hybrid",
        "uptime_stats": {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate_percentage": round(error_rate, 2)
        },
        "active_routers": {
            "authentication": f"{APIRoutes.AUTH_PREFIX}/*",
            "github": f"{APIRoutes.GITHUB_PREFIX}/*", 
            "sessions": f"{APIRoutes.DAIFU_PREFIX}/*"
        },
        "timestamp": time.time()
    }


if __name__ == "__main__":
    print("🚀 Starting YudaiV3 Backend API server...")
    print("📡 Server will be available at: http://localhost:8000")
    print("📚 API documentation at: http://localhost:8000/docs")
    print("📖 ReDoc documentation at: http://localhost:8000/redoc")
    print("📊 Usage statistics at: http://localhost:8000/stats")
    print("💚 Health check at: http://localhost:8000/health")

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
