"""
Database package for YudaiV3
"""

from models import (
    AuthToken,
    FileAnalysis,
    FileItem,
    Repository,
    SessionToken,
    User,
    UserIssue,
)

from .database import Base, SessionLocal, engine, get_db, init_db

# Import create_sample_data function
try:
    from .database import create_sample_data
except ImportError:
    # Fallback if function doesn't exist
    def create_sample_data():
        print("Sample data creation not available")
        return False

__all__ = [
    "Base", 
    "engine", 
    "SessionLocal", 
    "get_db", 
    "init_db",
    "create_sample_data",  # Add this
    "User",
    "AuthToken",
    "SessionToken",
    "Repository",
    "FileItem",
    "FileAnalysis",
    "UserIssue"
] 