"""
Unified models for YudaiV3 - SQLAlchemy and Pydantic models in one place

BACKEND MODIFICATION PLAN FOR UNIFIED STATE MANAGEMENT:
====================================================================

✅ COMPLETED:
1. Session management models (ChatSession, ChatMessage, ContextCard, FileEmbedding)
2. Authentication models (User, AuthToken, SessionToken)
3. Repository models (Repository, Issue, PullRequest, Commit)
4. AI Solver models (AIModel, SWEAgentConfig, AISolveSession, AISolveEdit)

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
from pydantic import BaseModel, ConfigDict, Field, validator
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
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
    ai_solve_sessions: Mapped[List["AISolveSession"]] = relationship(
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
    permissions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)  # GitHub App permissions

    # Token metadata
    scope: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # OAuth scopes
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # GitHub App installation context
    repositories_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # API URL for accessible repos

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
    ai_solve_sessions: Mapped[List["AISolveSession"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )


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
    issue_steps: Mapped[Optional[str]] = mapped_column(
        JSON, nullable=True
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

    # File information
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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


class GitHubAppInstallation(Base):
    """GitHub App installations tracking"""

    __tablename__ = "github_app_installations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    github_installation_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    github_app_id: Mapped[str] = mapped_column(String(50), nullable=False)

    # Installation details
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "User" or "Organization"
    account_login: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Installation permissions and events
    permissions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    events: Mapped[Optional[List[str]]] = mapped_column(JSON_TYPE, nullable=True)

    # Repository access
    repository_selection: Mapped[str] = mapped_column(String(20), default="all")  # "all" or "selected"
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
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

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
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    solve_sessions: Mapped[List["AISolveSession"]] = relationship(
        back_populates="ai_model", cascade="all, delete-orphan"
    )


class SWEAgentConfig(Base):
    """SWE-agent configuration settings"""

    __tablename__ = "swe_agent_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    config_path: Mapped[str] = mapped_column(String(500), nullable=False)
    parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    solve_sessions: Mapped[List["AISolveSession"]] = relationship(
        back_populates="swe_config", cascade="all, delete-orphan"
    )


class AISolveSession(Base):
    """AI solve sessions tracking solver progress"""

    __tablename__ = "ai_solve_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), nullable=False)
    ai_model_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ai_models.id"), nullable=True
    )
    swe_config_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("swe_agent_configs.id"), nullable=True
    )

    # Session status and metadata
    status: Mapped[str] = mapped_column(
        String(50), default="pending", index=True
    )  # SolveStatus enum values
    repo_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    branch_name: Mapped[str] = mapped_column(String(255), default="main")
    trajectory_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
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
    user: Mapped["User"] = relationship()
    issue: Mapped["Issue"] = relationship()
    ai_model: Mapped[Optional["AIModel"]] = relationship(
        back_populates="solve_sessions"
    )
    swe_config: Mapped[Optional["SWEAgentConfig"]] = relationship(
        back_populates="solve_sessions"
    )
    edits: Mapped[List["AISolveEdit"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class AISolveEdit(Base):
    """Individual edits made by the AI solver"""

    __tablename__ = "ai_solve_edits"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("ai_solve_sessions.id"), nullable=False
    )

    # Edit details
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    edit_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # EditType enum values
    original_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    line_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    edit_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    session: Mapped["AISolveSession"] = relationship(back_populates="edits")


# ============================================================================
# ERROR MODELS & VALIDATION
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


class StandardizedErrorCodes:
    """Standardized error codes for consistent error handling"""

    # Authentication errors
    AUTH_INVALID_TOKEN = "AUTH_INVALID_TOKEN"
    AUTH_EXPIRED_TOKEN = "AUTH_EXPIRED_TOKEN"
    AUTH_MISSING_TOKEN = "AUTH_MISSING_TOKEN"
    AUTH_INSUFFICIENT_PERMISSIONS = "AUTH_INSUFFICIENT_PERMISSIONS"

    # Session errors
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_ACCESS_DENIED = "SESSION_ACCESS_DENIED"
    SESSION_INVALID_DATA = "SESSION_INVALID_DATA"
    SESSION_ALREADY_EXISTS = "SESSION_ALREADY_EXISTS"

    # Message errors
    MESSAGE_NOT_FOUND = "MESSAGE_NOT_FOUND"
    MESSAGE_INVALID_DATA = "MESSAGE_INVALID_DATA"
    MESSAGE_TOO_LONG = "MESSAGE_TOO_LONG"

    # File errors
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_ACCESS_DENIED = "FILE_ACCESS_DENIED"
    FILE_INVALID_FORMAT = "FILE_INVALID_FORMAT"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"

    # Repository errors
    REPO_NOT_FOUND = "REPO_NOT_FOUND"
    REPO_ACCESS_DENIED = "REPO_ACCESS_DENIED"
    REPO_INVALID_URL = "REPO_INVALID_URL"

    # AI/Model errors
    AI_MODEL_ERROR = "AI_MODEL_ERROR"
    AI_PROCESSING_FAILED = "AI_PROCESSING_FAILED"
    AI_RATE_LIMIT_EXCEEDED = "AI_RATE_LIMIT_EXCEEDED"

    # Database errors
    DB_CONNECTION_ERROR = "DB_CONNECTION_ERROR"
    DB_INTEGRITY_ERROR = "DB_INTEGRITY_ERROR"
    DB_TIMEOUT_ERROR = "DB_TIMEOUT_ERROR"

    # General errors
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    BAD_REQUEST = "BAD_REQUEST"


class APIResponse(BaseModel):
    """Standardized API response wrapper"""

    success: bool
    data: Optional[Any] = None
    error: Optional[APIError] = None
    message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


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
    message_text: str = Field(
        ..., min_length=1, max_length=10000
    )  # Match frontend field name
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


class IdeaItemInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=1000)
    complexity: ComplexityLevel = Field(default=ComplexityLevel.M)

    @validator("title")
    def validate_title(cls, v):
        if not v.strip():
            raise ValueError("Idea title cannot be empty")
        return v.strip()


class CLICommandInput(BaseModel):
    command: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1, max_length=500)
    arguments: Optional[List[str]] = Field(default_factory=list)

    @validator("command")
    def validate_command(cls, v):
        if not v.strip():
            raise ValueError("CLI command cannot be empty")
        return v.strip()



class RepositoryRequest(BaseModel):
    repo_url: str = Field(..., min_length=1)
    max_file_size: Optional[int] = Field(None, ge=1)

    @validator("repo_url")
    def validate_repo_url(cls, v):
        if not v.strip():
            raise ValueError("Repository URL cannot be empty")
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


class UpdateChatMessageRequest(BaseModel):
    message_text: Optional[str] = Field(None, min_length=1)
    is_code: Optional[bool] = Field(None)
    tokens: Optional[int] = Field(None, ge=0)
    model_used: Optional[str] = Field(None, max_length=100)
    processing_time: Optional[float] = Field(None, ge=0)
    context_cards: Optional[List[str]] = Field(None)
    referenced_files: Optional[List[str]] = Field(None)
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


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None)
    repo_branch: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = Field(None)


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


class UpdateContextCardRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    content: Optional[str] = Field(None, min_length=1)
    source: Optional[str] = Field(None, pattern="^(chat|file-deps|upload)$")
    tokens: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = Field(None)


# File Embedding Models
class CreateFileEmbeddingResponse(BaseModel):
    id: int
    session_id: int
    file_path: str
    file_name: str 
    file_type: str
    file_content: Optional[str] = None
    chunk_text: str
    chunk_index: int
    tokens: int
    file_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdateFileEmbeddingResponse(BaseModel):
    id: int
    session_id: int
    file_path: str
    file_name: str
    file_type: str
    file_content: Optional[str] = None
    chunk_text: str
    chunk_index: int
    tokens: int
    file_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FileEmbeddingResponse(BaseModel):
    """API response model for file embedding operations - excludes raw vector data for API efficiency"""
    id: int
    session_id: int
    repository_id: Optional[int] = None
    file_path: str
    file_name: str
    file_type: str
    file_content: Optional[str] = None
    # Note: embedding vector data excluded from API response for efficiency and Pydantic compatibility
    chunk_index: int
    chunk_text: str  # Raw chunk text for backend processing
    tokens: int
    session_tokens_used: int
    file_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# Frontend UI Response Models
class FileItemResponse(BaseModel):
    """Response model for frontend UI display in FileDependencies component - simplified for UI interactions"""
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


class FileTreeResponse(BaseModel):
    """Response model for file tree structure in repository analysis - matches frontend FileTreeResponse interface"""
    id: str
    name: str
    type: str
    Category: str  # Matches TypeScript interface with capital C
    tokens: int
    isDirectory: bool
    children: Optional[List["FileTreeResponse"]] = None
    path: Optional[str] = None
    expanded: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class SessionFileDependencyResponse(BaseModel):
    """Response model for session file dependencies"""
    id: int
    file_name: str
    file_path: str
    file_type: str
    tokens: int
    category: Optional[str] = None
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
    session_id: str = Field(
        ..., min_length=1, max_length=255
    )  # Remove alias to match frontend
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
    github_token: str = Field(
        ..., min_length=1, description="GitHub access token from OAuth"
    )


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
    default_branch: Optional[str] = None
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


# ============================================================================
# GITHUB APP OAUTH MODELS
# ============================================================================

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


class GitHubAppOAuthTokenResponse(BaseModel):
    """Response model for GitHub App OAuth token information"""
    id: int
    user_id: int
    token_type: str
    github_app_id: Optional[str] = None
    installation_id: Optional[int] = None
    permissions: Optional[Dict[str, Any]] = None
    scope: Optional[str] = None
    expires_at: Optional[datetime] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class GitHubAppInstallationRequest(BaseModel):
    """Request model for creating GitHub App installation"""
    installation_id: int
    setup_action: Optional[str] = None  # "install" or "update"


class GitHubAppOAuthCallbackRequest(BaseModel):
    """Request model for GitHub App OAuth callback"""
    code: str
    state: Optional[str] = None
    installation_id: Optional[int] = None
    setup_action: Optional[str] = None
