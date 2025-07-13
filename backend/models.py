"""
Unified models for YudaiV3 - SQLAlchemy and Pydantic models in one place
"""
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List, Literal, Union, Dict, Any, ForwardRef
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

# ============================================================================
# ENUMS
# ============================================================================

class ContextSource(str, Enum):
    CHAT = "chat"
    FILE_DEPS = "file-deps"
    UPLOAD = "upload"

class ComplexityLevel(str, Enum):
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"

class ToastType(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    INFO = "info"

class ProgressStep(str, Enum):
    PM = "PM"
    ARCHITECT = "Architect"
    TEST_WRITER = "Test-Writer"
    CODER = "Coder"

class TabType(str, Enum):
    CHAT = "chat"
    FILE_DEPS = "file-deps"
    CONTEXT = "context"
    IDEAS = "ideas"

class FileType(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"

# ============================================================================
# SQLALCHEMY MODELS (Database Schema)
# ============================================================================

Base = declarative_base()

class User(Base):
    """User model for authentication and user management"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    github_username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    github_user_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    auth_tokens: Mapped[List["AuthToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    repositories: Mapped[List["Repository"]] = relationship(back_populates="user", cascade="all, delete-orphan")

class AuthToken(Base):
    """Authentication tokens for GitHub OAuth"""
    __tablename__ = "auth_tokens"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # GitHub OAuth tokens
    access_token: Mapped[str] = mapped_column(String(500), nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    token_type: Mapped[str] = mapped_column(String(50), default="bearer")
    
    # Token metadata
    scope: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="auth_tokens")

class Repository(Base):
    """Repository data extracted from filedeps.py API"""
    __tablename__ = "repositories"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Repository metadata
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False)
    repo_owner: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Processing metadata
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    max_file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Statistics
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    # Extraction data
    raw_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    processed_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="repositories")
    file_items: Mapped[List["FileItem"]] = relationship(back_populates="repository", cascade="all, delete-orphan")

class FileItem(Base):
    """Individual file items from repository analysis"""
    __tablename__ = "file_items"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), nullable=False)
    
    # File metadata
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)  # INTERNAL, EXTERNAL
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    # Tree structure
    is_directory: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("file_items.id"), nullable=True)
    
    # File content (optional)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_size: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    repository: Mapped["Repository"] = relationship(back_populates="file_items")
    children: Mapped[List["FileItem"]] = relationship(back_populates="parent", cascade="all, delete-orphan")
    parent: Mapped[Optional["FileItem"]] = relationship(remote_side=[id], back_populates="children")

class ContextCard(Base):
    """Context cards created by users"""
    __tablename__ = "context_cards"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Context data
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship()

class IdeaItem(Base):
    """Ideas to implement"""
    __tablename__ = "idea_items"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Idea data
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    complexity: Mapped[str] = mapped_column(String(10), nullable=False)
    
    # Status
    status: Mapped[str] = mapped_column(String(50), default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship()

# ============================================================================
# PYDANTIC MODELS (API Request/Response)
# ============================================================================

# Base Pydantic models with SQLAlchemy compatibility
class ProjectConfig(BaseModel):
    project_name: str = Field(..., alias="projectName")
    repo_path: str = Field(..., alias="repoPath") 
    cli_config: Optional[Dict[str, Any]] = Field(None, alias="cliConfig")
    
    model_config = ConfigDict(populate_by_name=True)

class PromptContext(BaseModel):
    prompt: str = Field(...)
    tokens: int = Field(..., ge=0)
    generated_code: Optional[str] = Field(None, alias="generatedCode")
    
    model_config = ConfigDict(populate_by_name=True)

# Core User Input Models
class ChatMessageInput(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    is_code: bool = Field(default=False)
    
    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError('Message content cannot be empty')
        return v

class ContextCardInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    source: ContextSource = Field(default=ContextSource.CHAT)
    
    @validator('title')
    def validate_title(cls, v):
        if len(v.strip()) < 1:
            raise ValueError('Title cannot be empty')
        return v.strip()

class FileItemInput(BaseModel):
    name: str = Field(..., min_length=1)
    file_type: FileType = Field(...)
    tokens: int = Field(..., ge=0)
    is_directory: bool = Field(default=False)
    path: Optional[str] = Field(None)
    content: Optional[str] = Field(None)
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('File name cannot be empty')
        return v.strip()

class IdeaItemInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=1000)
    complexity: ComplexityLevel = Field(default=ComplexityLevel.M)
    
    @validator('title')
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError('Idea title cannot be empty')
        return v.strip()

class CLICommandInput(BaseModel):
    command: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1, max_length=500)
    arguments: Optional[List[str]] = Field(default_factory=list)
    
    @validator('command')
    def validate_command(cls, v):
        if not v.strip():
            raise ValueError('CLI command cannot be empty')
        return v.strip()

# File Dependencies Models
class FileItemResponse(BaseModel):
    id: str = Field(...)
    name: str = Field(...)
    type: Literal["INTERNAL", "EXTERNAL"] = Field(...)
    tokens: int = Field(..., ge=0)
    Category: str = Field(...)
    isDirectory: Optional[bool] = Field(default=False)
    children: Optional[List['FileItemResponse']] = Field(default=None)
    expanded: Optional[bool] = Field(default=False)

# Allow recursive FileItem definition
FileItemResponse.model_rebuild()

class RepositoryRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)
    max_file_size: Optional[int] = Field(None, ge=1)
    
    @validator('repo_url')
    def validate_repo_url(cls, v):
        if not v.strip():
            raise ValueError('Repository URL cannot be empty')
        return v.strip()

# Request/Response Models
class CreateContextRequest(BaseModel):
    context_card: ContextCardInput
    
class CreateIdeaRequest(BaseModel):
    idea: IdeaItemInput
    
class ProcessFileRequest(BaseModel):
    file: FileItemInput
    
class ChatRequest(BaseModel):
    message: ChatMessageInput
    context_cards: Optional[List[str]] = Field(default_factory=list)

class CreateIssueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    context_cards: List[str] = Field(default_factory=list)
    ideas: List[str] = Field(default_factory=list)
    priority: Literal["low", "medium", "high"] = Field(default="medium")
    
class ProcessUploadRequest(BaseModel):
    file_name: str = Field(...)
    file_type: str = Field(...)
    content: str = Field(...)
    max_tokens: int = Field(default=10000, ge=1, le=100000)

# Response Models
class APIResponse(BaseModel):
    success: bool = Field(...)
    message: str = Field(...)
    data: Optional[Dict[str, Any]] = Field(None)
    error: Optional[str] = Field(None)

class ContextCardResponse(BaseModel):
    id: str = Field(...)
    title: str = Field(...)
    description: str = Field(...)
    tokens: int = Field(...)
    source: ContextSource = Field(...)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class IssueResponse(BaseModel):
    issue_id: str = Field(...)
    issue_url: str = Field(...)
    title: str = Field(...)
    status: str = Field(...)

# Database Response Models (for API responses from database)
class RepositoryResponse(BaseModel):
    id: int = Field(...)
    repo_url: str = Field(...)
    repo_name: str = Field(...)
    repo_owner: str = Field(...)
    total_files: int = Field(...)
    total_tokens: int = Field(...)
    status: str = Field(...)
    created_at: datetime = Field(...)
    
    model_config = ConfigDict(from_attributes=True)

class FileItemDBResponse(BaseModel):
    id: int = Field(...)
    name: str = Field(...)
    path: str = Field(...)
    file_type: str = Field(...)
    category: str = Field(...)
    tokens: int = Field(...)
    is_directory: bool = Field(...)
    content_size: int = Field(...)
    created_at: datetime = Field(...)
    
    model_config = ConfigDict(from_attributes=True)