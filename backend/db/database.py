"""
Database configuration and session management for YudaiV3
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import Base from unified models
from models import Base

# Database URL from environment variables
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://yudai_user:yudai_password@db:5432/yudai_db"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=bool(os.getenv("DB_ECHO", "false").lower() == "true")
)

# Create session maker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency function to get database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Initialize database - create all tables
    """
    # Import all models here to ensure they are registered
    from models import (
        User, AuthToken, Repository, FileItem, ContextCard, IdeaItem,
        Issue, PullRequest, Commit
    )
    Base.metadata.create_all(bind=engine) 