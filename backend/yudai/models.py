"""
Unified models for YudaiV3 - SQLAlchemy and Pydantic models in one place

BACKEND MODIFICATION PLAN FOR UNIFIED STATE MANAGEMENT:
====================================================================

✅ COMPLETED:
1. Session management models (ChatSession, ChatMessage, ContextCard)
2. Authentication models (User, AuthToken, SessionToken)
3. Repository models (Repository, Issue, PullRequest, Commit)
4. AI Solver models (AIModel, Solve, SolveRun)

🔄 IN PROGRESS:
1. API endpoint unification (all operations through session context)
2. Error response standardization

📋 NEXT STEPS:
1. Add session update endpoints (PUT /daifu/sessions/{session_id})
2. Add bulk message operations (POST /daifu/sessions/{session_id}/messages/bulk)
3. Standardize error responses across all endpoints
4. Add session statistics endpoint (GET /daifu/sessions/{session_id}/stats)
5. Add session export/import functionality

🔧 IMMEDIATE TODO:
- Update session_routes.py to add missing CRUD endpoints
- Ensure all API responses match frontend expectations
- Add proper error handling with consistent error codes
- Test all endpoints with the new unified frontend state management
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

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
    CONTEXT = "context"
    IDEAS = "ideas"


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


class SandboxStatus(str, Enum):
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    TERMINATED = "terminated"


class SessionRuntimeStatus(str, Enum):
    PROVISIONING = "provisioning"
    RUNNING = "running"
    STOPPED = "stopped"
    TERMINATED = "terminated"


class SessionAuditEventName(str, Enum):
    SANDBOX_START = "sandbox_start"
    SOLVE_START = "solve_start"
    GITHUB_ISSUE_CREATE = "github_issue_create"
    PR_CREATE = "pr_create"
    SANDBOX_TERMINATE = "sandbox_terminate"


class SessionMode(str, Enum):
    PENDING = "pending"
    ARCHITECT = "architect"
    TESTER = "tester"
    CODER = "coder"
    COMPLETE = "complete"
    FAILED = "failed"


class SessionModeStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class UserQuestionStatus(str, Enum):
    PENDING = "pending"
    ANSWERED = "answered"


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
    sandboxes: Mapped[List["Sandbox"]] = relationship(
        back_populates="created_by",
        foreign_keys="Sandbox.created_by_user_id",
    )
    session_audit_events: Mapped[List["SessionAuditEvent"]] = relationship(
        back_populates="user",
        foreign_keys="SessionAuditEvent.user_id",
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
    repo_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    repo_context: Mapped[Optional[str]] = mapped_column(
        JSON, nullable=True
    )  # Repository metadata
    runtime_workspace_path: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )

    # Status and statistics
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    current_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SessionMode.PENDING.value, index=True
    )
    mode_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SessionModeStatus.IDLE.value
    )
    mode_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    architect_issue_url: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True
    )
    architect_issue_number: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    architect_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tester_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    tester_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    coder_pr_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    coder_pr_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    coder_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    workflow_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    mode_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )

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
    user_questions: Mapped[List["UserQuestion"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    solves: Mapped[List["Solve"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    runtime_records: Mapped[List["SessionRuntime"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    artifacts: Mapped[List["SessionArtifact"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["SessionAuditEvent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    executions: Mapped[List["AgentExecution"]] = relationship(
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
    context_cards: Mapped[Optional[List[str]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    referenced_files: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actions: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSON, nullable=True)

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
    """Curated user/session context cards for chat and issue generation."""

    __tablename__ = "context_cards"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    user: Mapped["User"] = relationship()
    session: Mapped["ChatSession"] = relationship(back_populates="context_cards")


class UserQuestion(Base):
    """Persisted agent follow-up questions and user answers for a chat session."""

    __tablename__ = "user_questions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    question_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[Optional[List[Dict[str, str]]]] = mapped_column(JSON_TYPE, nullable=True)
    multi_select: Mapped[bool] = mapped_column(Boolean, default=False)
    selected_option_ids: Mapped[Optional[List[str]]] = mapped_column(JSON_TYPE, nullable=True)
    answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=UserQuestionStatus.PENDING.value, index=True
    )
    question_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    asked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    answered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    session: Mapped["ChatSession"] = relationship(back_populates="user_questions")
    user: Mapped["User"] = relationship()


class UserIssue(Base):
    """User-generated issues for agent processing (distinct from GitHub Issues)"""

    __tablename__ = "user_issues"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Core issue data (as requested by user)
    issue_id: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
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
    canonical_slug: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True
    )
    hugging_face_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_timestamp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    context_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    architecture: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    pricing: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON_TYPE, nullable=True)
    top_provider: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    per_request_limits: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    supported_parameters: Mapped[Optional[List[str]]] = mapped_column(
        JSON_TYPE, nullable=True, default=list
    )
    default_parameters: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
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
    """Individual experiment run executed inside a Modal sandbox."""

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
# REAL-TIME SESSION LIFECYCLE MODELS (Phase 0 contract freeze targets)
# ============================================================================


class Sandbox(Base):
    """Persistent sandbox lifecycle metadata tracked by the controller."""

    __tablename__ = "sandboxes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    identity_key: Mapped[str] = mapped_column(
        String(512), nullable=False, unique=True, index=True
    )
    org_slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repo_owner: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repo_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    repo_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SandboxStatus.PROVISIONING.value, index=True
    )
    tunnel_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    tunnel_auth_mode: Mapped[str] = mapped_column(
        String(64), nullable=False, default="session_jwt_passthrough"
    )
    tunnel_token_ttl_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    terminated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    active_session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=True, index=True
    )
    lifecycle_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    created_by: Mapped[Optional["User"]] = relationship(
        back_populates="sandboxes", foreign_keys=[created_by_user_id]
    )
    active_session: Mapped[Optional["ChatSession"]] = relationship(
        foreign_keys=[active_session_id]
    )
    runtimes: Mapped[List["SessionRuntime"]] = relationship(
        back_populates="sandbox", cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["SessionAuditEvent"]] = relationship(
        back_populates="sandbox", cascade="all, delete-orphan"
    )


class SessionRuntime(Base):
    """Runtime state that links a session to its active sandbox."""

    __tablename__ = "session_runtime"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    runtime_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sandbox_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("sandboxes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SessionRuntimeStatus.PROVISIONING.value,
        index=True,
    )
    completion_issue_created: Mapped[bool] = mapped_column(Boolean, default=False)
    completion_pr_created: Mapped[bool] = mapped_column(Boolean, default=False)
    completion_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    completion_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tunnel_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    tunnel_resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    tunnel_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    runtime_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    session: Mapped["ChatSession"] = relationship(back_populates="runtime_records")
    sandbox: Mapped[Optional["Sandbox"]] = relationship(back_populates="runtimes")
    artifacts: Mapped[List["SessionArtifact"]] = relationship(
        back_populates="runtime", cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["SessionAuditEvent"]] = relationship(
        back_populates="runtime", cascade="all, delete-orphan"
    )


class SessionArtifact(Base):
    """Exported bundle metadata produced when a session reaches completion criteria."""

    __tablename__ = "session_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    runtime_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("session_runtime.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    artifact_key: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="bundle_metadata"
    )
    cache_manifest_path: Mapped[Optional[str]] = mapped_column(
        String(1000), nullable=True
    )
    bundle_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    checksum_sha256: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    object_etag: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    byte_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    artifact_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    exported_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    session: Mapped["ChatSession"] = relationship(back_populates="artifacts")
    runtime: Mapped[Optional["SessionRuntime"]] = relationship(back_populates="artifacts")


class SessionAuditEvent(Base):
    """Audit rows for runtime lifecycle and external side-effects."""

    __tablename__ = "session_audit_events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    event_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("chat_sessions.id"), nullable=True, index=True
    )
    sandbox_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("sandboxes.id"), nullable=True, index=True
    )
    runtime_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("session_runtime.id"), nullable=True, index=True
    )
    event_payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    user: Mapped[Optional["User"]] = relationship(
        back_populates="session_audit_events", foreign_keys=[user_id]
    )
    session: Mapped[Optional["ChatSession"]] = relationship(back_populates="audit_events")
    sandbox: Mapped[Optional["Sandbox"]] = relationship(back_populates="audit_events")
    runtime: Mapped[Optional["SessionRuntime"]] = relationship(
        back_populates="audit_events"
    )


class AgentExecution(Base):
    """Execution attempts for fixed Architect -> Tester -> Coder workflow."""

    __tablename__ = "agent_executions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SessionModeStatus.RUNNING.value, index=True
    )
    execution_plan: Mapped[Optional[List[str]]] = mapped_column(JSON_TYPE, nullable=True)
    output_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON_TYPE, nullable=True
    )
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

    session: Mapped["ChatSession"] = relationship(back_populates="executions")


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
    small_change: bool = False
    best_effort: bool = False
    max_iterations: int = 50
    max_cost: float = 10.0

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
    metadata: Optional[Dict[str, Any]] = None


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
    repo_url: Optional[str] = None
    runtime_workspace_path: Optional[str] = None
    is_active: bool
    total_messages: int
    total_tokens: int
    current_mode: str = SessionMode.PENDING.value
    mode_status: str = SessionModeStatus.IDLE.value
    mode_updated_at: Optional[datetime] = None
    architect_issue_url: Optional[str] = None
    architect_issue_number: Optional[int] = None
    architect_completed_at: Optional[datetime] = None
    tester_status: Optional[str] = None
    tester_completed_at: Optional[datetime] = None
    coder_pr_url: Optional[str] = None
    coder_pr_number: Optional[int] = None
    coder_completed_at: Optional[datetime] = None
    workflow_completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ChatAction(BaseModel):
    action_type: str = Field(..., max_length=50)
    label: str = Field(..., max_length=100)
    issue_title: Optional[str] = Field(None, max_length=200)
    issue_description: Optional[str] = Field(None, max_length=2000)
    labels: Optional[List[str]] = Field(default_factory=list)

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
    referenced_files: Optional[List[str]] = None
    error_message: Optional[str] = None
    actions: Optional[List[ChatAction]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CreateContextCardRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    content: str = Field(..., min_length=1)
    source: Literal["chat", "upload"] = Field(default="chat")
    tokens: int = Field(default=0, ge=0)


class UpdateContextCardRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    content: Optional[str] = Field(None, min_length=1)
    source: Optional[Literal["chat", "upload"]] = None
    tokens: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class ContextCardResponse(BaseModel):
    id: int
    session_id: int
    title: str
    description: Optional[str] = None
    content: str
    source: Literal["chat", "upload"]
    tokens: int
    is_active: bool
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
    repo_url: Optional[str] = None
    repo_context: Optional[Dict[str, Any]] = None
    runtime_workspace_path: Optional[str] = None
    is_active: bool
    total_messages: int
    total_tokens: int
    current_mode: str = SessionMode.PENDING.value
    mode_status: str = SessionModeStatus.IDLE.value
    mode_updated_at: Optional[datetime] = None
    architect_issue_url: Optional[str] = None
    architect_issue_number: Optional[int] = None
    architect_completed_at: Optional[datetime] = None
    tester_status: Optional[str] = None
    tester_completed_at: Optional[datetime] = None
    coder_pr_url: Optional[str] = None
    coder_pr_number: Optional[int] = None
    coder_completed_at: Optional[datetime] = None
    workflow_completed_at: Optional[datetime] = None
    mode_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    runtime_id: Optional[str] = None
    sandbox_id: Optional[str] = None
    tunnel_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SessionContextResponse(BaseModel):
    """Complete session context including messages and unified state"""

    session: SessionResponse
    messages: List[ChatMessageResponse]
    context_cards: Optional[List[ContextCardResponse]] = Field(default_factory=list)
    repository_info: Optional[Dict[str, Any]] = None
    statistics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    user_issues: Optional[List["UserIssueResponse"]] = Field(default_factory=list)
    pending_questions: Optional[List["UserQuestionResponse"]] = Field(default_factory=list)


# User Issue Models
class CreateUserIssueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    issue_text_raw: str = Field(..., min_length=1)
    description: Optional[str] = Field(None)
    session_id: Optional[str] = Field(None, max_length=255)
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


class CreateGitHubIssueResponse(BaseModel):
    """Response model for GitHub issue creation endpoint"""

    success: bool
    github_url: str
    message: str
    github_issue_number: Optional[int] = None
    execution_started: bool = False
    execution_id: Optional[str] = None
    execution_status: Optional[str] = None
    execution_error: Optional[str] = None
    requires_confirmation: bool = False
    confirmation_question_id: Optional[str] = None
    pending_tool: Optional[str] = None


class ChatRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=255)
    message: ChatMessageInput
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


class ConversationOption(BaseModel):
    id: str = Field(..., min_length=1, max_length=128)
    label: str = Field(..., min_length=1, max_length=255)


class ConversationQuestion(BaseModel):
    question_id: str = Field(..., min_length=1, max_length=64)
    prompt: str = Field(..., min_length=1)
    multi_select: bool = False
    options: List[ConversationOption] = Field(default_factory=list)


class ConversationRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    selected_option_ids: Optional[List[str]] = Field(default_factory=list)


class ConversationResponse(BaseModel):
    session_id: str
    reply: str
    current_mode: str
    mode_status: str
    follow_up_question: Optional[ConversationQuestion] = None


class UserQuestionOption(BaseModel):
    id: str = Field(..., min_length=1, max_length=128)
    label: str = Field(..., min_length=1, max_length=255)


class AskQuestionRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    options: List[UserQuestionOption] = Field(default_factory=list)
    multi_select: bool = False
    mode: Optional[Literal["architect", "tester", "coder"]] = None
    objective: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    metadata: Optional[Dict[str, Any]] = None


class AnswerQuestionRequest(BaseModel):
    selected_option_ids: List[str] = Field(default_factory=list)
    answer_text: Optional[str] = Field(default=None, max_length=10000)
    resume_execution: bool = True


class UserQuestionResponse(BaseModel):
    question_id: str
    session_id: str
    mode: Optional[str] = None
    prompt: str
    options: List[UserQuestionOption] = Field(default_factory=list)
    multi_select: bool = False
    selected_option_ids: List[str] = Field(default_factory=list)
    answer_text: Optional[str] = None
    status: str
    asked_at: datetime
    answered_at: Optional[datetime] = None


class AskQuestionResponse(BaseModel):
    question: UserQuestionResponse
    mode_status: str


class AnswerQuestionResponse(BaseModel):
    question: UserQuestionResponse
    resumed: bool = False
    resumed_mode: Optional[str] = None
    mode_status: str


class ExecutionRequest(BaseModel):
    objective: str = Field(..., min_length=1, max_length=10000)
    force_mode: Optional[Literal["architect", "tester", "coder"]] = None


class StageToolRequest(BaseModel):
    tool_name: Literal["run_architect_mode", "run_tester_mode", "run_coder_mode"]
    objective: str = Field(..., min_length=1, max_length=10000)


class CreateGitHubIssueToolRequest(BaseModel):
    issue_id: str = Field(..., min_length=1, max_length=255)


class ExecutionArtifactResponse(BaseModel):
    bundle_path: Optional[str] = None
    metadata_path: Optional[str] = None
    checksum_sha256: Optional[str] = None
    byte_size: Optional[int] = None


class ExecutionStatusResponse(BaseModel):
    execution_id: Optional[str] = None
    session_id: str
    mode: str
    status: str
    plan: List[str] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancel_requested: bool = False
    waiting_for_input: bool = False
    current_mode_execution_id: Optional[str] = None
    artifact: Optional[ExecutionArtifactResponse] = None
    detail: Optional[str] = None


class ExecutionResponse(ExecutionStatusResponse):
    execution_id: str
    started_at: datetime


class CancelExecutionResponse(BaseModel):
    execution_id: Optional[str] = None
    session_id: str
    status: str
    message: str


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
