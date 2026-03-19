"""Pydantic schemas for controller/sandbox realtime APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SandboxCreateRequest(BaseModel):
    org: str = Field(..., min_length=1, max_length=255)
    repo_owner: str = Field(..., min_length=1, max_length=255)
    repo_name: str = Field(..., min_length=1, max_length=255)
    environment: str = Field(..., min_length=1, max_length=255)
    repo_branch: Optional[str] = Field(default="main", max_length=255)
    session_id: Optional[str] = Field(default=None, max_length=255)


class SandboxResponse(BaseModel):
    sandbox_id: str
    identity_key: str
    status: str
    tunnel_url: Optional[str] = None
    tunnel_token_ttl_seconds: int = 3600
    last_heartbeat_at: Optional[datetime] = None
    terminated_at: Optional[datetime] = None
    modal_sandbox_id: Optional[str] = None


class TunnelResolveResponse(BaseModel):
    sandbox_id: str
    tunnel_url: str
    signed_tunnel_url: Optional[str] = None
    token_strategy: str = "session_jwt_passthrough"
    token_ttl_seconds: int = 3600
    signed_url_ttl_seconds: int = 300


class HeartbeatResponse(BaseModel):
    sandbox_id: str
    status: str
    last_heartbeat_at: datetime


class CleanupResponse(BaseModel):
    scanned: int
    terminated: int


class RuntimeEnsureRequest(BaseModel):
    org: str = Field(default="yudai", min_length=1, max_length=255)
    repo_owner: str = Field(..., min_length=1, max_length=255)
    repo_name: str = Field(..., min_length=1, max_length=255)
    environment: Optional[str] = Field(default=None, max_length=255)
    repo_branch: Optional[str] = Field(default="main", max_length=255)
    repo_url: Optional[str] = Field(default=None, max_length=1024)


class RuntimeResponse(BaseModel):
    runtime_id: Optional[str] = None
    sandbox_id: Optional[str] = None
    identity_key: Optional[str] = None
    status: str
    tunnel_url: Optional[str] = None
    token_ttl_seconds: Optional[int] = None
    tunnel_expires_at: Optional[datetime] = None
    completion_issue_created: bool = False
    completion_pr_created: bool = False
    completion_detected: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class HealthzResponse(BaseModel):
    status: str = "ok"
    service: str = "sandbox-session-server"
    controller_base_url: Optional[str] = None
    sandbox_id: Optional[str] = None
    heartbeat_enabled: bool = False
