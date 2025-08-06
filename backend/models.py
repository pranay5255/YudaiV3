"""
Unified models for YudaiV3 - SQLAlchemy and Pydantic models in one place
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, validator
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

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
    session_tokens: Mapped[List["SessionToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")

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

class SessionToken(Base):
    """Session tokens for frontend authentication"""
    __tablename__ = "session_tokens"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Session token (for frontend)
    session_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    
    # Session metadata
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="session_tokens")

class Repository(Base):
    """Repository data from GitHub"""
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    github_repo_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Core GitHub metadata
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    repo_url: Mapped[Optional[str]] = mapped_column(
        String(500), unique=True, index=True, nullable=True
    )  # Original repository URL
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    private: Mapped[bool] = mapped_column(Boolean, default=False)
    html_url: Mapped[str] = mapped_column(String(500), nullable=False)
    clone_url: Mapped[str] = mapped_column(String(500), nullable=False)
    language: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Stats
    stargazers_count: Mapped[int] = mapped_column(Integer, default=0)
    forks_count: Mapped[int] = mapped_column(Integer, default=0)
    open_issues_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps from GitHub
    github_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    github_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    pushed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Timestamps of our record
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="repositories")
    issues: Mapped[List["Issue"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    pull_requests: Mapped[List["PullRequest"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    commits: Mapped[List["Commit"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    file_items: Mapped[List["FileItem"]] = relationship(back_populates="repository", cascade="all, delete-orphan")
    file_analyses: Mapped[List["FileAnalysis"]] = relationship(back_populates="repository", cascade="all, delete-orphan")

class Issue(Base):
    """Issues from a repository"""
    __tablename__ = "issues"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    github_issue_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), nullable=False)
    
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    html_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    author_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    github_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    github_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    github_closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    repository: Mapped["Repository"] = relationship(back_populates="issues")

class PullRequest(Base):
    """Pull Requests from a repository"""
    __tablename__ = "pull_requests"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    github_pr_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), nullable=False)
    
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    html_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    author_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    github_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    github_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    github_closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    merged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    repository: Mapped["Repository"] = relationship(back_populates="pull_requests")

class Commit(Base):
    """Commits from a repository"""
    __tablename__ = "commits"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sha: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), nullable=False)
    
    message: Mapped[str] = mapped_column(Text, nullable=False)
    html_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    repository: Mapped["Repository"] = relationship(back_populates="commits")

class FileItem(Base):
    """Individual file items from repository analysis used by @FileDependencies.tsx"""
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

class FileAnalysis(Base):
    """File analysis results from repository processing"""
    __tablename__ = "file_analyses"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    repository_id: Mapped[int] = mapped_column(ForeignKey("repositories.id"), nullable=False)
    
    # Analysis data
    raw_data: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    processed_data: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    max_file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Status and metadata
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, processing, completed, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    repository: Mapped["Repository"] = relationship(back_populates="file_analyses")

class ContextCard(Base):
    """Context cards created by users"""
    # TODO: MAke this compatible to display for @ContextCard.tsx
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
    # TODO: Make this compatible to display for @IdeasToImplement.tsx
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

class ChatSession(Base):
    """Chat sessions for user conversations"""
    __tablename__ = "chat_sessions"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Session data
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Repository context (session backbone)
    repo_owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    repo_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    repo_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default="main")
    repo_context: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Repository metadata
    
    # Status and statistics
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship()
    messages: Mapped[List["ChatMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    file_embeddings: Mapped[List["FileEmbedding"]] = relationship(back_populates="session", cascade="all, delete-orphan")

class ChatMessage(Base):
    """Individual chat messages within sessions"""
    __tablename__ = "chat_messages"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    
    # Message data
    message_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    sender_type: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # user, assistant, system
    is_code: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Metadata
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    processing_time: Mapped[Optional[float]] = mapped_column(nullable=True)  # milliseconds
    context_cards: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    referenced_files: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    session: Mapped["ChatSession"] = relationship(back_populates="messages")

class UserIssue(Base):
    """User-generated issues for agent processing (distinct from GitHub Issues)"""
    __tablename__ = "user_issues"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    # Core issue data (as requested by user)
    issue_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    context_card_id: Mapped[Optional[int]] = mapped_column(ForeignKey("context_cards.id"), nullable=True)
    issue_text_raw: Mapped[str] = mapped_column(Text, nullable=False)
    issue_steps: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Store as JSON array
    
    # Additional data from chat API
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    chat_session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chat_sessions.id"), nullable=True)
    
    # Context and metadata
    context_cards: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Array of context card IDs
    ideas: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Array of idea IDs
    repo_owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    repo_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Processing metadata
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low, medium, high
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, processing, completed, failed
    agent_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_time: Mapped[Optional[float]] = mapped_column(nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    
    # GitHub integration
    github_issue_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    github_issue_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    user: Mapped["User"] = relationship()
    context_card: Mapped[Optional["ContextCard"]] = relationship()
    chat_session: Mapped[Optional["ChatSession"]] = relationship()

class FileEmbedding(Base):
    """File embeddings for semantic search using pgvector"""
    __tablename__ = "file_embeddings"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), nullable=False)
    repository_id: Mapped[Optional[int]] = mapped_column(ForeignKey("repositories.id"), nullable=True)
    
    # File information
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Embedding data
    embedding: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Store as JSON for now
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    # Metadata (renamed to avoid SQLAlchemy conflict)
    file_metadata: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    session: Mapped["ChatSession"] = relationship(back_populates="file_embeddings")
    repository: Mapped[Optional["Repository"]] = relationship()

class OAuthState(Base):
    """OAuth state parameters for GitHub authentication"""
    __tablename__ = "oauth_states"
    
    state: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)
    
    def __repr__(self):
        return f"<OAuthState(state={self.state}, expires_at={self.expires_at})>"

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

# Chat Models
class CreateChatSessionRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None)

class CreateChatMessageRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=255)
    message_id: str = Field(..., min_length=1, max_length=255)
    message_text: str = Field(..., min_length=1)
    sender_type: str = Field(..., pattern="^(user|assistant|system)$")
    role: str = Field(..., pattern="^(user|assistant|system)$")
    is_code: bool = Field(default=False)
    tokens: int = Field(default=0, ge=0)
    model_used: Optional[str] = Field(None, max_length=100)
    processing_time: Optional[float] = Field(None, ge=0)
    context_cards: Optional[List[str]] = Field(default_factory=list)
    referenced_files: Optional[List[str]] = Field(default_factory=list)
    error_message: Optional[str] = Field(None)

class ChatSessionResponse(BaseModel):
    id: int
    session_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    total_messages: int
    total_tokens: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class ChatMessageResponse(BaseModel):
    id: int
    message_id: str
    message_text: str
    sender_type: str
    role: str
    is_code: bool
    tokens: int
    model_used: Optional[str] = None
    processing_time: Optional[float] = None
    context_cards: Optional[List[str]] = None
    referenced_files: Optional[List[str]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

# Session Management Models
class CreateSessionRequest(BaseModel):
    repo_owner: str = Field(..., min_length=1, max_length=255)
    repo_name: str = Field(..., min_length=1, max_length=255)
    repo_branch: Optional[str] = Field("main", max_length=255)
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None)

class SessionResponse(BaseModel):
    id: int
    session_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    repo_owner: Optional[str] = None
    repo_name: Optional[str] = None
    repo_branch: Optional[str] = None
    repo_context: Optional[Dict[str, Any]] = None
    is_active: bool
    total_messages: int
    total_tokens: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class SessionContextResponse(BaseModel):
    """Complete session context including messages, context cards, and unified state"""
    session: SessionResponse
    messages: List[ChatMessageResponse]
    context_cards: List[str] = Field(default_factory=list)
    repository_info: Optional[Dict[str, Any]] = None
    file_embeddings_count: int = 0
    statistics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    user_issues: Optional[List["UserIssueResponse"]] = Field(default_factory=list)
    file_embeddings: Optional[List["FileEmbeddingResponse"]] = Field(default_factory=list)

# File Embedding Models
class CreateFileEmbeddingRequest(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=1000)
    file_name: str = Field(..., min_length=1, max_length=500)
    file_type: str = Field(..., min_length=1, max_length=100)
    file_content: Optional[str] = Field(None)
    chunk_text: str = Field(..., min_length=1)
    chunk_index: int = Field(default=0, ge=0)
    tokens: int = Field(default=0, ge=0)
    file_metadata: Optional[Dict[str, Any]] = Field(None)

class FileEmbeddingResponse(BaseModel):
    id: int
    session_id: int
    repository_id: Optional[int] = None
    file_path: str
    file_name: str
    file_type: str
    chunk_index: int
    tokens: int
    file_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# User Issue Models
class CreateUserIssueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    issue_text_raw: str = Field(..., min_length=1)
    description: Optional[str] = Field(None)
    session_id: Optional[str] = Field(None, max_length=255)
    context_card_id: Optional[int] = Field(None)
    context_cards: Optional[List[str]] = Field(default_factory=list)
    ideas: Optional[List[str]] = Field(default_factory=list)
    repo_owner: Optional[str] = Field(None, max_length=255)
    repo_name: Optional[str] = Field(None, max_length=255)
    priority: Literal["low", "medium", "high"] = Field(default="medium")
    issue_steps: Optional[List[str]] = Field(default_factory=list)

class UserIssueResponse(BaseModel):
    id: int
    issue_id: str
    user_id: int
    title: str
    description: Optional[str] = None
    issue_text_raw: str
    issue_steps: Optional[List[str]] = None
    session_id: Optional[str] = None
    context_card_id: Optional[int] = None
    context_cards: Optional[List[str]] = None
    ideas: Optional[List[str]] = None
    repo_owner: Optional[str] = None
    repo_name: Optional[str] = None
    priority: str
    status: str
    agent_response: Optional[str] = None
    processing_time: Optional[float] = None
    tokens_used: int
    github_issue_url: Optional[str] = None
    github_issue_number: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
    
class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(
        default="default", alias="sessionId"
    )
    message: ChatMessageInput
    context_cards: Optional[List[str]] = Field(default_factory=list)
    repo_owner: Optional[str] = Field(None, alias="repoOwner")
    repo_name: Optional[str] = Field(None, alias="repoName")

    model_config = ConfigDict(populate_by_name=True)

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
    name: str = Field(...)
    owner: str = Field(...)
    created_at: datetime = Field(...)
    updated_at: Optional[datetime] = Field(None)

    model_config = ConfigDict(from_attributes=True)


class FileAnalysisResponse(BaseModel):
    id: int = Field(...)
    repository_id: int = Field(..., alias="repositoryId")
    total_files: int = Field(...)
    total_tokens: int = Field(...)
    max_file_size: Optional[int] = Field(None, alias="maxFileSize")
    status: str = Field(...)
    processed_at: datetime = Field(..., alias="processedAt")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

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

# ============================================================================
# AUTHENTICATION MODELS
# ============================================================================

class UserProfile(BaseModel):
    id: int
    github_username: str
    github_user_id: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: str
    last_login: Optional[str] = None

class AuthResponse(BaseModel):
    success: bool
    message: str
    user: Optional[UserProfile] = None
    access_token: Optional[str] = None
    error: Optional[str] = None

class SessionTokenResponse(BaseModel):
    session_token: str
    expires_at: datetime
    user: UserProfile

class SessionTokenRequest(BaseModel):
    session_token: str

class CreateSessionTokenRequest(BaseModel):
    user_id: int
    expires_in_hours: int = Field(default=24, ge=1, le=168)  # 1 hour to 1 week

class CreateSessionFromGitHubRequest(BaseModel):
    github_token: str = Field(..., min_length=1, description="GitHub access token from OAuth")

# ============================================================================
# GITHUB API MODELS
# ============================================================================

class GitHubUser(BaseModel):
    login: str
    id: int
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None

class GitHubLabel(BaseModel):
    id: int
    name: str
    color: str
    description: Optional[str] = None

class GitHubRepo(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool
    html_url: str
    description: Optional[str] = None
    clone_url: Optional[str] = None
    language: Optional[str] = None
    stargazers_count: Optional[int] = 0
    forks_count: Optional[int] = 0
    open_issues_count: Optional[int] = 0
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    pushed_at: Optional[datetime] = None
    topics: Optional[List[str]] = []
    license: Optional[Dict[str, Any]] = None

class GitHubIssue(BaseModel):
    id: int
    number: int
    html_url: str
    title: str
    body: Optional[str] = None
    state: str
    user: Optional[GitHubUser] = None
    labels: List[GitHubLabel] = []
    assignees: List[GitHubUser] = []
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None

class GitHubPullRequest(BaseModel):
    id: int
    number: int
    html_url: str
    title: str
    body: Optional[str] = None
    state: str
    user: Optional[GitHubUser] = None
    labels: List[GitHubLabel] = []
    assignees: List[GitHubUser] = []
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None
    head: Optional[Dict[str, Any]] = None
    base: Optional[Dict[str, Any]] = None

class GitHubCommitAuthor(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    date: Optional[datetime] = None

class GitHubCommit(BaseModel):
    sha: str
    html_url: str
    message: str
    author: Optional[GitHubCommitAuthor] = None
    committer: Optional[GitHubCommitAuthor] = None
    parents: Optional[List[Dict[str, Any]]] = []

class GitHubBranch(BaseModel):
    name: str
    commit: Dict[str, Any]
    protected: bool

class GitHubSearchResponse(BaseModel):
    total_count: int
    incomplete_results: bool
    items: List[GitHubRepo]