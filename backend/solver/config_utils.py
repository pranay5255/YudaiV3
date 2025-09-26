"""Helper utilities to translate solver config into API schema instances."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import yaml

try:
    from backend.models import (
        AIModelOut,
        SWEAgentConfigOut,
        SolveSessionOut,
        SolveSessionStatsOut,
        SolveStatus,
        StartSolveRequest,
        StartSolveResponse,
        SolverTrajectoryOut,
        SolverTrajectoryStep,
    )
except ModuleNotFoundError:
    from enum import Enum

    class SolveStatus(str, Enum):
        PENDING = "pending"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"
        CANCELLED = "cancelled"

    class _DumpMixin:
        def model_dump(self) -> Dict[str, Any]:
            return asdict(self)

    @dataclass
    class AIModelOut(_DumpMixin):
        id: int
        name: str
        provider: str
        model_id: str
        config: Optional[Dict[str, Any]] = None
        is_active: bool = True
        created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
        updated_at: Optional[datetime] = None

    @dataclass
    class SWEAgentConfigOut(_DumpMixin):
        id: int
        name: str
        config_path: str
        parameters: Optional[Dict[str, Any]] = None
        is_default: bool = True
        created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
        updated_at: Optional[datetime] = None

    @dataclass
    class SolveSessionOut(_DumpMixin):
        id: int
        user_id: int
        issue_id: int
        ai_model_id: Optional[int]
        swe_config_id: Optional[int]
        status: SolveStatus
        repo_url: Optional[str]
        branch_name: str
        trajectory_data: Optional[Dict[str, Any]]
        error_message: Optional[str]
        started_at: Optional[datetime]
        completed_at: Optional[datetime]
        created_at: datetime
        updated_at: Optional[datetime]
        edits: list = field(default_factory=list)
        ai_model: Optional[AIModelOut] = None
        swe_config: Optional[SWEAgentConfigOut] = None

    @dataclass
    class SolveSessionStatsOut(_DumpMixin):
        session_id: int
        status: SolveStatus
        total_edits: int
        files_modified: int
        lines_added: int
        lines_removed: int
        duration_seconds: Optional[int]
        last_activity: Optional[datetime]
        trajectory_steps: int

    @dataclass
    class StartSolveRequest(_DumpMixin):
        repo_url: Optional[str]
        branch_name: str = "main"
        ai_model_id: Optional[int] = None
        swe_config_id: Optional[int] = None

    @dataclass
    class StartSolveResponse(_DumpMixin):
        message: str
        session_id: int
        issue_id: int
        status: str

    @dataclass
    class SolverTrajectoryStep(_DumpMixin):
        step_index: int
        timestamp: datetime
        action: str
        command: Optional[str]
        result: Optional[str]
        file_path: Optional[str]
        success: bool = True
        error_message: Optional[str] = None

    @dataclass
    class SolverTrajectoryOut(_DumpMixin):
        session_id: int
        total_steps: int
        steps: list
        final_status: SolveStatus
        summary: Optional[Dict[str, Any]] = None


def _utc_now() -> datetime:
    """Return timezone-aware UTC now."""

    return datetime.now(timezone.utc)


def load_solver_config(path: Optional[str] = None) -> Dict[str, Any]:
    """Load the SWE-agent YAML configuration."""

    if path:
        config_path = Path(path)
    else:
        config_path = Path(
            os.getenv("SWEAGENT_CONFIG_PATH", "backend/solver/config.yaml")
        )
    with config_path.expanduser().resolve().open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def _split_model_name(model_name: str) -> tuple[str, str]:
    parts = [segment for segment in model_name.split("/") if segment]
    if not parts:
        return ("unknown", "unknown-model")
    if len(parts) == 1:
        return (parts[0], parts[0])
    return (parts[0], "/".join(parts[1:]))


def build_ai_model_out(
    config: Dict[str, Any],
    *,
    ai_model_id: int = 0,
    name: Optional[str] = None,
    is_active: bool = True,
) -> AIModelOut:
    """Create an AIModelOut instance from config."""

    model_section = config.get("agent", {}).get("model", {})
    model_name = model_section.get("model_name", "openrouter/unknown-model")
    provider, provider_model_id = _split_model_name(model_name)
    dynamic_config = {k: v for k, v in model_section.items() if k != "model_name"}

    return AIModelOut(
        id=ai_model_id,
        name=name or provider_model_id,
        provider=provider,
        model_id=provider_model_id,
        config=dynamic_config or None,
        is_active=is_active,
        created_at=_utc_now(),
        updated_at=None,
    )


def build_swe_config_out(
    config: Dict[str, Any],
    config_path: str,
    *,
    swe_config_id: int = 0,
    name: Optional[str] = None,
    is_default: bool = True,
) -> SWEAgentConfigOut:
    """Create a SWEAgentConfigOut instance from config."""

    config_file = Path(config_path).expanduser().resolve()
    parameters = {k: v for k, v in config.items() if k != "agent"}

    return SWEAgentConfigOut(
        id=swe_config_id,
        name=name or config_file.stem,
        config_path=str(config_file),
        parameters=parameters or None,
        is_default=is_default,
        created_at=_utc_now(),
        updated_at=None,
    )


@dataclass
class SolverArtifacts:
    """Snapshot of config-driven solver objects."""

    config_path: Path
    ai_model: AIModelOut
    swe_config: SWEAgentConfigOut
    start_request: StartSolveRequest
    start_response: StartSolveResponse
    session: SolveSessionOut
    session_stats: SolveSessionStatsOut
    trajectory: SolverTrajectoryOut


def build_solver_artifacts(
    *,
    config: Dict[str, Any],
    config_path: str,
    issue_id: int,
    user_id: int,
    repo_url: str,
    branch_name: str = "main",
    session_id: int = 1,
    issue_title: Optional[str] = None,
) -> SolverArtifacts:
    """Assemble solver-facing schema objects from config and issue metadata."""

    resolved_path = Path(config_path).expanduser().resolve()
    ai_model = build_ai_model_out(config, ai_model_id=1)
    swe_config = build_swe_config_out(
        config, config_path=str(resolved_path), swe_config_id=1
    )

    start_request = StartSolveRequest(
        repo_url=repo_url,
        branch_name=branch_name,
        ai_model_id=ai_model.id,
        swe_config_id=swe_config.id,
    )

    start_response = StartSolveResponse(
        message=f"Initialized AI solver session {session_id}",
        session_id=session_id,
        issue_id=issue_id,
        status=SolveStatus.PENDING.value,
    )

    now = _utc_now()
    tools = config.get("agent", {}).get("tools", [])

    steps = [
        SolverTrajectoryStep(
            step_index=index,
            timestamp=now + timedelta(seconds=index),
            action=f"tool:{tool}",
            command=None,
            result=f"Tool '{tool}' available for use.",
            file_path=None,
            success=True,
            error_message=None,
        )
        for index, tool in enumerate(tools, start=1)
    ]

    trajectory = SolverTrajectoryOut(
        session_id=session_id,
        total_steps=len(steps),
        steps=steps,
        final_status=SolveStatus.PENDING,
        summary={
            "issue_title": issue_title,
            "config_path": str(resolved_path),
        },
    )

    session = SolveSessionOut(
        id=session_id,
        user_id=user_id,
        issue_id=issue_id,
        ai_model_id=ai_model.id,
        swe_config_id=swe_config.id,
        status=SolveStatus.PENDING,
        repo_url=repo_url,
        branch_name=branch_name,
        trajectory_data=trajectory.model_dump(),
        error_message=None,
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
        edits=[],
        ai_model=ai_model,
        swe_config=swe_config,
    )

    session_stats = SolveSessionStatsOut(
        session_id=session_id,
        status=SolveStatus.PENDING,
        total_edits=0,
        files_modified=0,
        lines_added=0,
        lines_removed=0,
        duration_seconds=None,
        last_activity=now,
        trajectory_steps=len(steps),
    )

    return SolverArtifacts(
        config_path=resolved_path,
        ai_model=ai_model,
        swe_config=swe_config,
        start_request=start_request,
        start_response=start_response,
        session=session,
        session_stats=session_stats,
        trajectory=trajectory,
    )
