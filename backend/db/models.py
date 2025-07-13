"""
SQLAlchemy models for YudaiV3 database
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    """
    User model for authentication and user management
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    github_username = Column(String(255), unique=True, index=True, nullable=False)
    github_user_id = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=True)
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    auth_tokens = relationship("AuthToken", back_populates="user", cascade="all, delete-orphan")
    repositories = relationship("Repository", back_populates="user", cascade="all, delete-orphan")

class AuthToken(Base):
    """
    Authentication tokens for GitHub OAuth
    """
    __tablename__ = "auth_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # GitHub OAuth tokens
    access_token = Column(String(500), nullable=False)
    refresh_token = Column(String(500), nullable=True)
    token_type = Column(String(50), default="bearer")
    
    # Token metadata
    scope = Column(String(500), nullable=True)  # GitHub scopes
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="auth_tokens")

class Repository(Base):
    """
    Repository data extracted from filedeps.py API
    """
    __tablename__ = "repositories"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Repository metadata
    repo_url = Column(String(500), nullable=False)
    repo_name = Column(String(255), nullable=False)
    repo_owner = Column(String(255), nullable=False)
    
    # Processing metadata
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
    max_file_size = Column(Integer, nullable=True)
    
    # Statistics
    total_files = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    
    # Extraction data
    raw_data = Column(JSON, nullable=True)  # Raw GitIngest data
    processed_data = Column(JSON, nullable=True)  # Processed file tree data
    
    # Status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="repositories")
    file_items = relationship("FileItem", back_populates="repository", cascade="all, delete-orphan")

class FileItem(Base):
    """
    Individual file items from repository analysis
    """
    __tablename__ = "file_items"
    
    id = Column(Integer, primary_key=True, index=True)
    repository_id = Column(Integer, ForeignKey("repositories.id"), nullable=False)
    
    # File metadata
    name = Column(String(500), nullable=False)
    path = Column(String(1000), nullable=False)
    file_type = Column(String(50), nullable=False)  # INTERNAL, EXTERNAL
    category = Column(String(100), nullable=False)
    tokens = Column(Integer, default=0)
    
    # Tree structure
    is_directory = Column(Boolean, default=False)
    parent_id = Column(Integer, ForeignKey("file_items.id"), nullable=True)
    
    # File content (optional)
    content = Column(Text, nullable=True)
    content_size = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    repository = relationship("Repository", back_populates="file_items")
    children = relationship("FileItem", back_populates="parent", cascade="all, delete-orphan")
    parent = relationship("FileItem", remote_side=[id], back_populates="children")

class ContextCard(Base):
    """
    Context cards created by users
    """
    __tablename__ = "context_cards"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Context data
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String(50), nullable=False)  # chat, file-deps, upload
    tokens = Column(Integer, default=0)
    
    # Metadata
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")

class IdeaItem(Base):
    """
    Ideas to implement
    """
    __tablename__ = "idea_items"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Idea data
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    complexity = Column(String(10), nullable=False)  # S, M, L, XL
    
    # Status
    status = Column(String(50), default="pending")  # pending, in-progress, completed
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User") 