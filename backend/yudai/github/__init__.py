#!/usr/bin/env python3
"""
backend/github/__init__.py

Expose the GitHub API router for inclusion in the main FastAPI app.
"""

from .routes import router as github_router  # noqa: F401


