"""
Unified models for YudaiV3 - SQLAlchemy and Pydantic models in one place

BACKEND MODIFICATION PLAN FOR UNIFIED STATE MANAGEMENT:
====================================================================

✅ COMPLETED:
1. Session management models (ChatSession, ChatMessage, ContextCard, FileEmbedding)
2. Authentication models (User, AuthToken, SessionToken)
3. Repository models (Repository, Issue, PullRequest, Commit)
4. AI Solver models (AIModel, Solve, SolveRun)

🔄 IN PROGRESS:
1. Model consolidation (FileItem → FileEmbedding, FileAnalysis → Repository metadata)
2. API endpoint unification (all operations through session context)
3. Error response standardization

📋 NEXT STEPS:
1. Add session update endpoints (PUT /daifu/sessions/{session_id})
2. Add bulk message operations (POST /daifu/sessions/{session_id}/messages/bulk)
3. Add file dependency update endpoints (PUT /daifu/sessions/{session_id}/file-deps/{file_id})
4. Standardize error responses across all endpoints
5. Add session statistics endpoint (GET /daifu/sessions/{session_id}/stats)
6. Remove deprecated FileItem and FileAnalysis models after migration
7. Add session export/import functionality

🔧 IMMEDIATE TODO:
- Update session_routes.py to add missing CRUD endpoints
- Ensure all API responses match frontend expectations
- Add proper error handling with consistent error codes
- Test all endpoints with the new unified frontend state management
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, ConfigDict, Field, model_validator, validator
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

# Import JSON type for PostgreSQL
try:
    from sqlalchemy.dialects.postgresql import JSON as PG_JSON

    JSON_TYPE = PG_JSON
except ImportError:
    JSON_TYPE = JSON

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


# AI Solver Enums
class SolveStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EditType(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


# ============================================================================
# SQLALCHEMY MODELS (Database Schema)
# ============================================================================

Base = declarative_base()


class User(Base):
    """User model for authentication and user management"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    github_username: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    github_user_id: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    last_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    auth_tokens: Mapped[List["AuthToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    repositories: Mapped[List["Repository"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    session_tokens: Mapped[List["SessionToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    chat_sessions: Mapped[List["ChatSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    solves: Mapped[List["Solve"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AuthToken(Base):
    """Authentication tokens for GitHub App OAuth"""

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # GitHub App OAuth tokens
    access_token: Mapped[str] = mapped_column(String(500), nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    token_type: Mapped[str] = mapped_column(String(50), default="bearer")

    # GitHub App specific fields
    github_app_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    installation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("github_app_installations.github_installation_id"), nullable=True
    )
    permissions: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )  # GitHub App permissions

    # Token metadata
    scope: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # OAuth scopes
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # GitHub App installation context
    repositories_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True
    )  # API URL for accessible repos

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="auth_tokens")
    installation: Mapped[Optional["GitHubAppInstallation"]] = relationship(
        back_populates="auth_tokens"
    )


class SessionToken(Base):
    """Session tokens for frontend authentication"""

    __tablename__ = "session_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Session token (for frontend)
    session_token: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )

    # Session metadata
    # Store expiration as timezone-aware UTC timestamp
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="session_tokens")


class Repository(Base):
    """Repository data from GitHub"""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Optional GitHub numeric repository ID. Keep non-unique to allow multiple users/tests
    # to reference the same upstream repository without constraint conflicts.
    github_repo_id: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )

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
    default_branch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Timestamps from GitHub
    github_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    github_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pushed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps of our record
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Cached GitHub context data
    github_context: Mapped[Optional[str]] = mapped_column(
        JSON_TYPE, nullable=True
    )  # Stores comprehensive GitHub context from get_github_context
    github_context_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # When the GitHub context was last fetched

    # Relationships
    user: Mapped["User"] = relationship(back_populates="repositories")
    issues: Mapped[List["Issue"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    pull_requests: Mapped[List["PullRequest"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )
    commits: Mapped[List["Commit"]] = relationship(
        back_populates="repository", cascade="all, delete-orphan"
    )


class Issue(Base):
    """Issues from a repository"""

    __tablename__ = "issues"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    github_issue_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, index=True
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"), nullable=False
    )

    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    html_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    author_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    github_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    github_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    github_closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    repository: Mapped["Repository"] = relationship(back_populates="issues")


class PullRequest(Base):
    """Pull Requests from a repository"""

    __tablename__ = "pull_requests"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    github_pr_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, index=True
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"), nullable=False
    )

    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(1000), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    html_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    author_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    github_created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    github_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    github_closed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    merged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    repository: Mapped["Repository"] = relationship(back_populates="pull_requests")


class Commit(Base):
    """Commits from a repository"""

    __tablename__ = "commits"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sha: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False, index=True
    )
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id"), nullable=False
    )

    message: Mapped[str] = mapped_column(Text, nullable=False)
    html_url: Mapped[str] = mapped_column(String(1000), nullable=False)

    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    repository: Mapped["Repository"] = relationship(back_populates="commits")


class ChatSession(Base):
    """Chat sessions for user conversations"""

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Session data
    session_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Repository context (session backbone)
    repo_owner: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    repo_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    repo_branch: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default="main"
    )
    repo_context: Mapped[Optional[str]] = mapped_column(
        JSON, nullable=True
    )  # Repository metadata
    generate_embeddings: Mapped[bool] = mapped_column(Boolean, default=False)
    generate_facts_memories: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status and statistics
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    last_activity: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="chat_sessions")
    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    context_cards: Mapped[List["ContextCard"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    file_embeddings: Mapped[List["FileEmbedding"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    file_items: Mapped[List["FileItem"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    solves: Mapped[List["Solve"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class ChatMessage(Base):
    """Individual chat messages within sessions"""

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=False
    )

    # Message data
    message_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    sender_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # user, assistant, system
    role: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # user, assistant, system
    is_code: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadata
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    processing_time: Mapped[Optional[float]] = mapped_column(
        nullable=True
    )  # milliseconds
    context_cards: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    referenced_files: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class ContextCard(Base):
    """Context cards created by users"""

    __tablename__ = "context_cards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=True
    )

    # Context data
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship()
    session: Mapped[Optional["ChatSession"]] = relationship(
        back_populates="context_cards"
    )


class UserIssue(Base):
    """User-generated issues for agent processing (distinct from GitHub Issues)"""

    __tablename__ = "user_issues"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Core issue data (as requested by user)
    issue_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    context_card_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("context_cards.id"), nullable=True
    )
    issue_text_raw: Mapped[str] = mapped_column(Text, nullable=False)
    issue_steps: Mapped[Optional[List[str]]] = mapped_column(
        JSON_TYPE, nullable=True
    )  # Store as JSON array

    # Additional data from chat API
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    # chat_session_id: Mapped[Optional[int]] = mapped_column(ForeignKey("chat_sessions.id"), nullable=True)

    # Context and metadata
    # context_cards: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Array of context card IDs
    # ideas: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Array of idea IDs
    repo_owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    repo_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Processing metadata
    priority: Mapped[str] = mapped_column(
        String(20), default="medium"
    )  # low, medium, high
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending, processing, completed, failed
    agent_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_time: Mapped[Optional[float]] = mapped_column(nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)

    # GitHub integration
    github_issue_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    github_issue_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    user: Mapped["User"] = relationship()


class FileEmbedding(Base):
    """File embeddings for semantic search and file dependencies storage"""

    __tablename__ = "file_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=False
    )
    repository_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("repositories.id"), nullable=True
    )

    # File reference (foreign key to FileItem)
    file_item_id: Mapped[int] = mapped_column(
        ForeignKey("file_items.id"), nullable=False
    )

    # File information (minimal - most data in FileItem)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)

    # Embedding data - using pgvector for efficient similarity search
    embedding: Mapped[Optional[Vector]] = mapped_column(
        Vector(384), nullable=True
    )  # sentence-transformers/all-MiniLM-L6-v2 dimensions
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0)

    # Token tracking for quota management
    session_tokens_used: Mapped[int] = mapped_column(
        Integer, default=0
    )  # Track tokens used for this session

    # Metadata (renamed to avoid SQLAlchemy conflict)
    file_metadata: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(back_populates="file_embeddings")
    repository: Mapped[Optional["Repository"]] = relationship()
    file_item: Mapped["FileItem"] = relationship(back_populates="embeddings")


class FileItem(Base):
    """File metadata for frontend display - matches FileItem interface exactly"""

    __tablename__ = "file_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=False
    )
    repository_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("repositories.id"), nullable=True
    )

    # Core file information (matches frontend FileItem interface)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="INTERNAL")
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    # Optional fields
    is_directory: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    content_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    file_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    content_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    session: Mapped["ChatSession"] = relationship(back_populates="file_items")
    repository: Mapped[Optional["Repository"]] = relationship()
    embeddings: Mapped[List["FileEmbedding"]] = relationship(
        back_populates="file_item", cascade="all, delete-orphan"
    )


class GitHubAppInstallation(Base):
    """GitHub App installations tracking"""

    __tablename__ = "github_app_installations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    github_installation_id: Mapped[int] = mapped_column(
        Integer, unique=True, nullable=False, index=True
    )
    github_app_id: Mapped[str] = mapped_column(String(50), nullable=False)

    # Installation details
    account_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "User" or "Organization"
    account_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Installation permissions and events
    permissions: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    events: Mapped[Optional[List[str]]] = mapped_column(JSON_TYPE, nullable=True)

    # Repository access
    repository_selection: Mapped[str] = mapped_column(
        String(20), default="all"
    )  # "all" or "selected"
    single_file_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Installation status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    suspended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    auth_tokens: Mapped[List["AuthToken"]] = relationship(
        back_populates="installation", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<GitHubAppInstallation(id={self.id}, account={self.account_login}, active={self.is_active})>"


class OAuthState(Base):
    """OAuth state parameters for GitHub App authentication"""

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_used: Mapped[bool] = mapped_column(Boolean, default=False)

    # GitHub App OAuth specific fields
    github_app_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    def __repr__(self):
        return f"<OAuthState(state={self.state}, expires_at={self.expires_at})>"


# ============================================================================
# AI SOLVER MODELS
# ============================================================================


class AIModel(Base):
    """AI model configurations for the solver"""

    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    input_price_per_million_tokens: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    output_price_per_million_tokens: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    last_price_refresh_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class Solve(Base):
    """Top-level solve job tracking a fan-out of experiments."""

    __tablename__ = "solves"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=True, index=True
    )
    repo_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    issue_number: Mapped[int] = mapped_column(Integer, nullable=False)
    base_branch: Mapped[str] = mapped_column(String(255), default="main")
    status: Mapped[str] = mapped_column(
        String(50), default=SolveStatus.PENDING.value, index=True
    )
    matrix: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    limits: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    requested_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    champion_run_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("solve_runs.id"), nullable=True
    )
    max_parallel: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_budget_s: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="solves")
    session: Mapped[Optional["ChatSession"]] = relationship(back_populates="solves")
    runs: Mapped[List["SolveRun"]] = relationship(
        back_populates="solve",
        cascade="all, delete-orphan",
        foreign_keys="SolveRun.solve_id",
    )
    champion_run: Mapped[Optional["SolveRun"]] = relationship(
        "SolveRun",
        foreign_keys=[champion_run_id],
        post_update=True,
    )


class SolveRun(Base):
    """Individual experiment run executed inside an E2B sandbox."""

    __tablename__ = "solve_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    solve_id: Mapped[str] = mapped_column(
        ForeignKey("solves.id", ondelete="CASCADE"), nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    temperature: Mapped[float] = mapped_column(Float, nullable=False)
    max_edits: Mapped[int] = mapped_column(Integer, nullable=False)
    evolution: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default=SolveStatus.PENDING.value, index=True
    )
    sandbox_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    pr_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    tests_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    loc_changed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    files_changed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    logs_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    diagnostics: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    trajectory_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # Agent trajectory data
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    solve: Mapped["Solve"] = relationship(
        back_populates="runs",
        foreign_keys=[solve_id],
    )


# ============================================================================
# AI SOLVER PYDANTIC SCHEMAS (Simplified - Only Used Models)
# ============================================================================


# Core solver response schemas
class SolveRunOut(BaseModel):
    """Solve run response schema."""

    id: str
    solve_id: str
    model: str
    temperature: float
    max_edits: int
    evolution: str
    status: SolveStatus
    sandbox_id: Optional[str] = None
    pr_url: Optional[str] = None
    tests_passed: Optional[bool] = None
    loc_changed: Optional[int] = None
    files_changed: Optional[int] = None
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    logs_url: Optional[str] = None
    diagnostics: Optional[Dict[str, Any]] = None
    trajectory_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SolveOut(BaseModel):
    """Top-level solve response schema."""

    id: str
    user_id: int
    session_id: Optional[int] = None
    repo_url: str
    issue_number: int
    base_branch: str
    status: SolveStatus
    matrix: Dict[str, Any]
    limits: Optional[Dict[str, Any]] = None
    requested_by: Optional[str] = None
    champion_run_id: Optional[str] = None
    max_parallel: Optional[int] = None
    time_budget_s: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SolveDetailOut(SolveOut):
    """Solve detail response including experiment runs."""

    runs: List[SolveRunOut] = Field(default_factory=list)
    champion_run: Optional[SolveRunOut] = None


class SolveProgress(BaseModel):
    """Aggregate progress metrics for a solve session."""

    runs_total: int = 0
    runs_completed: int = 0
    runs_failed: int = 0
    runs_running: int = 0
    last_update: Optional[datetime] = None
    message: Optional[str] = None


class StartSolveRequest(BaseModel):
    """Request payload for launching a solver run."""

    issue_id: int
    repo_url: str
    branch_name: str = "main"
    ai_model_id: Optional[int] = None
    ai_model_ids: Optional[List[int]] = None

    @validator("repo_url")
    def validate_repo_url(cls, value: str) -> str:
        if not value or "github.com" not in value:
            raise ValueError("repo_url must be a valid GitHub repository URL")
        return value.strip()

    @model_validator(mode="after")
    def validate_model_selection(self):
        if self.ai_model_id and self.ai_model_ids:
            raise ValueError("Provide either ai_model_id or ai_model_ids, not both")
        if self.ai_model_ids:
            filtered_ids = [model_id for model_id in self.ai_model_ids if model_id]
            if not filtered_ids:
                raise ValueError("ai_model_ids cannot be empty")
            # Remove duplicates while preserving order
            seen: set[int] = set()
            deduped: List[int] = []
            for model_id in filtered_ids:
                if model_id not in seen:
                    seen.add(model_id)
                    deduped.append(model_id)
            self.ai_model_ids = deduped
        return self


class StartSolveResponse(BaseModel):
    """Response payload returned after launching a solve session."""

    solve_session_id: str
    status: SolveStatus


class SolveStatusResponse(BaseModel):
    """Status payload returned for solve session polling."""

    solve_session_id: str
    status: SolveStatus
    progress: SolveProgress = Field(default_factory=SolveProgress)
    runs: List[SolveRunOut] = Field(default_factory=list)
    champion_run: Optional[SolveRunOut] = None
    error_message: Optional[str] = None


class CancelSolveResponse(BaseModel):
    """Response payload for cancellation requests."""

    solve_session_id: str
    status: SolveStatus
    message: str


# ============================================================================
# ERROR MODELS & VALIDATION (Simplified)
# ============================================================================


class APIError(BaseModel):
    """Standardized API error response"""

    detail: Optional[str] = None
    message: Optional[str] = None
    status: Optional[int] = None
    error_code: Optional[str] = None
    timestamp: Optional[datetime] = None
    path: Optional[str] = None
    request_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# PYDANTIC MODELS (API Request/Response) - Essential Only
# ============================================================================


# Core input models
class ChatMessageInput(BaseModel):
    message_text: str = Field(..., min_length=1, max_length=10000)
    is_code: bool = Field(default=False)

    @validator("message_text")
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError("Message content cannot be empty")
        return v

    model_config = ConfigDict(populate_by_name=True)


class ContextCardInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    source: ContextSource = Field(default=ContextSource.CHAT)

    @validator("title")
    def validate_title(cls, v):
        if len(v.strip()) < 1:
            raise ValueError("Title cannot be empty")
        return v.strip()


class FileItemInput(BaseModel):
    name: str = Field(..., min_length=1)
    file_type: FileType = Field(...)
    tokens: int = Field(..., ge=0)
    is_directory: bool = Field(default=False)
    path: Optional[str] = Field(None)
    content: Optional[str] = Field(None)

    @validator("name")
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError("File name cannot be empty")
        return v.strip()


class RepositoryRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)
    max_file_size: Optional[int] = Field(None, ge=1)

    @validator("repo_url")
    def validate_repo_url(cls, v):
        if not v.strip():
            raise ValueError("Repository URL cannot be empty")
        return v.strip()


# Chat Models
class CreateChatMessageRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=255)
    message_id: str = Field(..., min_length=1, max_length=255)
    message_text: str = Field(..., min_length=1, max_length=10000)
    sender_type: str = Field(..., pattern="^(user|assistant|system)$")
    role: str = Field(..., pattern="^(user|assistant|system)$")
    is_code: bool = Field(default=False)
    tokens: int = Field(default=0, ge=0)
    model_used: Optional[str] = Field(None, max_length=100)
    processing_time: Optional[float] = Field(None, ge=0)
    context_cards: Optional[List[str]] = Field(default_factory=list)
    referenced_files: Optional[List[str]] = Field(default_factory=list)
    error_message: Optional[str] = Field(None)

    @validator("message_text")
    def validate_message_text(cls, v):
        if not v.strip():
            raise ValueError("Message text cannot be empty or whitespace only")
        return v.strip()

    @validator("session_id")
    def validate_session_id(cls, v):
        if not v.strip():
            raise ValueError("Session ID cannot be empty")
        return v.strip()


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
    generate_embeddings: bool = False
    generate_facts_memories: bool = False

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
    index_codebase: Optional[bool] = Field(default=True)
    index_max_file_size: Optional[int] = Field(default=None, ge=1)
    generate_embeddings: bool = Field(default=True)
    generate_facts_memories: bool = Field(default=False)


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None)
    repo_branch: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = Field(None)
    generate_embeddings: Optional[bool] = None
    generate_facts_memories: Optional[bool] = None


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
    generate_embeddings: bool = False
    generate_facts_memories: bool = False

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
    file_embeddings: Optional[List["FileEmbeddingResponse"]] = Field(
        default_factory=list
    )


# Context Card Models
class CreateContextCardRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    source: str = Field(..., pattern="^(chat|file-deps|upload)$")
    tokens: int = Field(default=0, ge=0)


# File Embedding Models
class FileEmbeddingResponse(BaseModel):
    """Response model for embedding operations - excludes vector data"""

    id: int
    session_id: int
    repository_id: Optional[int] = None
    file_item_id: int
    file_path: str
    file_name: str
    chunk_index: int
    chunk_text: str
    tokens: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Frontend UI Response Models
class FileItemResponse(BaseModel):
    """Response model for frontend UI display in FileDependencies component"""

    id: str
    name: str
    path: Optional[str] = None
    type: str
    tokens: int
    category: str
    isDirectory: Optional[bool] = None
    children: Optional[List["FileItemResponse"]] = None
    expanded: Optional[bool] = None
    content_size: Optional[int] = None
    created_at: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_type: Optional[str] = None
    content_summary: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# User Issue Models
class CreateUserIssueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    issue_text_raw: str = Field(..., min_length=1)
    description: Optional[str] = Field(None)
    session_id: Optional[str] = Field(None, max_length=255)
    context_card_id: Optional[int] = Field(None)
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
    session_id: str = Field(..., min_length=1, max_length=255)
    message: ChatMessageInput
    context_cards: Optional[List[str]] = Field(default_factory=list)
    repository: Optional[Dict[str, Any]] = None
    model_config = ConfigDict(populate_by_name=True)

    @validator("session_id")
    def validate_session_id(cls, v):
        if not v or not v.strip():
            raise ValueError("session_id is required and cannot be empty")
        return v.strip()


class ChatResponse(BaseModel):
    reply: str = Field(...)
    conversation: List[Tuple[str, str]] = Field(...)
    message_id: str = Field(...)
    processing_time: float = Field(...)
    session_id: str = Field(...)
    model_config = ConfigDict(populate_by_name=True)


class ContextCardResponse(BaseModel):
    id: int = Field(...)
    session_id: Optional[int] = Field(None)
    title: str = Field(...)
    description: str = Field(...)
    content: str = Field(...)
    source: str = Field(...)
    tokens: int = Field(...)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(...)
    updated_at: Optional[datetime] = Field(None)

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# AUTHENTICATION MODELS (Essential Only)
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


# ============================================================================
# GITHUB API MODELS (Essential Only)
# ============================================================================


class GitHubRepo(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool
    html_url: Optional[str] = None
    description: Optional[str] = None
    clone_url: Optional[str] = None
    language: Optional[str] = None
    stargazers_count: Optional[int] = 0
    forks_count: Optional[int] = 0
    open_issues_count: Optional[int] = 0
    default_branch: Optional[str] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    pushed_at: Optional[datetime] = None
    topics: Optional[List[str]] = []
    license: Optional[Dict[str, Any]] = None

    @validator("html_url", always=True)
    def set_html_url_from_clone_url(cls, v, values):
        """If html_url is not provided or is None, use clone_url as fallback."""
        if not v and values.get("clone_url"):
            return values["clone_url"]
        return v


class GitHubAppInstallationResponse(BaseModel):
    """Response model for GitHub App installation information"""

    id: int
    github_installation_id: int
    github_app_id: str
    account_type: str
    account_login: str
    account_id: int
    permissions: Optional[Dict[str, Any]] = None
    events: Optional[List[str]] = None
    repository_selection: str
    single_file_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
