#!/usr/bin/env python3
"""Enhanced database and API integration checks.

This script verifies database initialization and ensures that core API routes
are registered with the FastAPI application defined in ``run_server.py``.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.routing import APIRoute
from sqlalchemy import create_engine, inspect, text

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from run_server import app  # noqa: E402


def get_database_url() -> str:
    """Resolve the database URL from environment variables or defaults."""
    if os.getenv("DATABASE_URL"):
        return os.getenv("DATABASE_URL")
    if os.getenv("DOCKER_COMPOSE"):
        return "postgresql://yudai_user:yudai_password@db:5432/yudai_db"
    return "postgresql://yudai_user:yudai_password@localhost:5432/yudai_db"


def test_database() -> bool:
    """Test database connection and verify core tables exist."""
    database_url = get_database_url()
    print("🔍 Testing database connection...")
    print(f"   URL: {database_url}")
    try:
        engine = create_engine(database_url, pool_pre_ping=True, echo=False)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            print("✓ Database connection successful")
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            expected = [
                "users",
                "auth_tokens",
                "repositories",
                "chat_sessions",
                "chat_messages",
            ]
            missing = [t for t in expected if t not in tables]
            if missing:
                print(f"⚠ Missing tables: {missing}")
                return False
            print("✓ Required tables present")
            return True
    except Exception as e:  # pragma: no cover - debug output
        print(f"❌ Database test failed: {e}")
        return False


def check_api_routes() -> bool:
    """Ensure that all expected API prefixes and critical routes exist."""
    route_paths = {route.path for route in app.routes if isinstance(route, APIRoute)}
    prefixes = ["/auth", "/github", "/daifu", "/issues", "/filedeps"]
    for prefix in prefixes:
        if not any(path.startswith(prefix) for path in route_paths):
            print(f"⚠ Missing routes for prefix {prefix}")
            return False
    if "/daifu/chat/daifu" not in route_paths:
        print("⚠ Missing /daifu/chat/daifu endpoint")
        return False
    print("✓ All expected API routes are registered")
    return True


if __name__ == "__main__":
    db_ok = test_database()
    routes_ok = check_api_routes()
    sys.exit(0 if db_ok and routes_ok else 1)
