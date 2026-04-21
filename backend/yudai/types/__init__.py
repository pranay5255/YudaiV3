"""Pydantic API contract models exposed through FastAPI/OpenAPI."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, ConfigDict, Field

from yudai.models import (  # noqa: F401
    APIError,
    AnswerQuestionRequest,
    AnswerQuestionResponse,
    AskQuestionRequest,
    AskQuestionResponse,
    AuthResponse,
    CancelExecutionResponse,
    CancelSolveResponse,
    ChatAction,
    ChatMessageInput,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSessionResponse,
    ContextCardInput,
    ContextCardResponse,
    ConversationOption,
    ConversationQuestion,
    ConversationRequest,
    ConversationResponse,
    CreateChatMessageRequest,
    CreateContextCardRequest,
    CreateGitHubIssueResponse,
    CreateSessionRequest,
    CreateUserIssueRequest,
    ExecutionArtifactResponse,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatusResponse,
    FileEmbeddingResponse,
    FileItemInput,
    FileItemResponse,
    GitHubAppInstallationResponse,
    GitHubRepo,
    RepositoryRequest,
    SessionContextResponse,
    SessionResponse,
    SessionTokenRequest,
    SessionTokenResponse,
    SolveDetailOut,
    SolveOut,
    SolveProgress,
    SolveRunOut,
    SolveStatusResponse,
    StartSolveRequest,
    StartSolveResponse,
    UpdateSessionRequest,
    UserIssueResponse,
    UserProfile,
    UserQuestionOption,
    UserQuestionResponse,
)
from yudai.realtime.schemas import (  # noqa: F401
    CleanupResponse,
    HealthzResponse,
    HeartbeatResponse,
    RuntimeEnsureRequest,
    RuntimeResponse,
    SandboxCreateRequest,
    SandboxResponse,
    TunnelResolveResponse,
)
from yudai.realtime.ws_protocol import (  # noqa: F401
    AgentQuestionPayload,
    ChatMessagePayload,
    LLMStreamPayload,
    ModeEventPayload,
    SandboxStreamPayload,
    StatusPayload,
    ToolCallPayload,
    TrajectoryUpdatePayload,
    UserResponsePayload,
    WSEnvelope,
    WSMessageType,
)


class SandboxState(BaseModel):
    sandbox_id: str | None = None
    identity_key: str | None = None
    workspace_path: str | None = None


class ExecutionStatus(BaseModel):
    status: Literal["idle", "running", "complete", "failed"]
    mode: Literal["architect", "tester", "coder"] | None = None
    detail: str | None = None


class LoginUrlResponse(BaseModel):
    login_url: str


class LogoutResponse(BaseModel):
    success: bool
    message: str


class ValidateSessionResponse(BaseModel):
    id: int
    github_username: str
    github_id: str
    display_name: str | None = None
    email: str | None = None
    avatar_url: str | None = None


class AuthHealthResponse(BaseModel):
    status: str
    service: str
    oauth_configured: bool | None = None
    timestamp: str
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str


class RootResponse(BaseModel):
    service: str
    phase: str
    docs: str


class RealtimeFlagsResponse(BaseModel):
    flags: Dict[str, Any]


class GitHubRepositoryOwner(BaseModel):
    login: str
    id: int | None = None
    avatar_url: str | None = None
    html_url: str | None = None

    model_config = ConfigDict(extra="allow")


class GitHubRepositoryResponse(BaseModel):
    id: int
    name: str
    full_name: str
    private: bool = False
    html_url: str | None = None
    description: str | None = None
    clone_url: str | None = None
    language: str | None = None
    stargazers_count: int | None = None
    forks_count: int | None = None
    open_issues_count: int | None = None
    default_branch: str | None = None
    updated_at: datetime | str | None = None
    created_at: datetime | str | None = None
    pushed_at: datetime | str | None = None
    owner: GitHubRepositoryOwner | None = None

    model_config = ConfigDict(extra="allow")


class GitHubBranchCommit(BaseModel):
    sha: str | None = None
    url: str | None = None

    model_config = ConfigDict(extra="allow")


class GitHubBranchResponse(BaseModel):
    name: str
    protected: bool = False
    commit: GitHubBranchCommit

    model_config = ConfigDict(extra="allow")


class GitHubIssueResponse(BaseModel):
    number: int
    title: str
    state: str
    html_url: str | None = None
    body: str | None = None
    labels: List[Any] = Field(default_factory=list)
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None

    model_config = ConfigDict(extra="allow")


class AIModelResponse(BaseModel):
    id: int
    name: str
    provider: str
    model_id: str
    description: str | None = None


class IssueCreationResponse(BaseModel):
    success: bool
    preview_only: bool = False
    github_preview: Dict[str, Any]
    user_issue: Dict[str, Any] | None = None
    message: str

    model_config = ConfigDict(extra="allow")


class TrajectorySummaryResponse(BaseModel):
    id: str
    solve_id: str
    run_id: str
    model: str
    status: str
    local_path: str | None = None
    remote_path: str | None = None
    exit_status: str | None = None
    instance_cost: float | None = None
    api_calls: int | None = None
    mini_version: str | None = None
    model_name: str | None = None
    total_messages: int | None = None
    created_at: str | None = None
    completed_at: str | None = None

    model_config = ConfigDict(extra="allow")


class TrajectoryFileResponse(BaseModel):
    run_id: str
    solve_id: str
    model: str
    status: str
    local_path: str
    content: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="allow")


__all__ = [name for name in globals() if not name.startswith("_")]
