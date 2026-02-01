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

from pydantic import BaseModel, ConfigDict, Field, model_validator, validator

# Note: SQLAlchemy ORM models have been removed as part of migration to vanilla SQL
# All database operations now use psycopg3 with raw SQL queries
# Pydantic models below are kept for API request/response validation

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
    context_cards: Optional[List[str]] = None
    referenced_files: Optional[List[str]] = None
    error_message: Optional[str] = None
    actions: Optional[List[ChatAction]] = None
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


class CreateGitHubIssueResponse(BaseModel):
    """Response model for GitHub issue creation endpoint"""

    success: bool
    github_url: str
    message: str


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
