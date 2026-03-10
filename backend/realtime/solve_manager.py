"""
Solver manager orchestrating asynchronous mini-swe-agent solve sessions.

This module handles:
- Solve session orchestration and lifecycle management
- Database updates and state tracking
- Async task management and cleanup
- Integration with sandbox executor for agent execution
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from pathlib import Path
import re
import shlex
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from db.database import SessionLocal
from fastapi import HTTPException, status
from context.facts_and_memories import (
    FactsAndMemoriesService,
    RepositorySnapshotService,
)
from models import (
    AIModel,
    AuthToken,
    CancelSolveResponse,
    ChatSession,
    ChatMessage,
    Issue,
    Solve,
    SolveProgress,
    SolveRun,
    SolveRunOut,
    SolveStatus,
    SolveStatusResponse,
    StartSolveRequest,
    StartSolveResponse,
    User,
)
from realtime.agentScriptGen import AgentScriptParams, build_agent_script, build_pr_script
from realtime.lifecycle import get_realtime_lifecycle_service
from realtime.modal_sandbox import SANDBOX_WORKSPACE_PATH
from realtime.sandbox_exec_broker import get_sandbox_exec_broker
from realtime.solve_stream_protocol import SOLVE_RESULT_PREFIX, TRAJECTORY_UPDATE_PREFIX
from realtime.ws_hub import get_ws_hub
from realtime.ws_protocol import WSMessageType
from sqlalchemy.orm import Session, joinedload

from utils import utc_now

logger = logging.getLogger(__name__)
TRAJECTORY_STORAGE_DIR = Path(
    os.getenv("TRAJECTORY_STORAGE_DIR", "/tmp/yudai/trajectories")
)
TRAJECTORY_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================================
# SOLVER MANAGER - ORCHESTRATION & DATABASE MANAGEMENT
# ============================================================================


@dataclass
class TrajectoryMetadata:
    exit_status: Optional[str] = None
    submission: Optional[str] = None
    instance_cost: Optional[float] = None
    api_calls: Optional[int] = None
    mini_version: Optional[str] = None
    model_name: Optional[str] = None
    total_messages: Optional[int] = None


@dataclass
class SolveExecutionResult:
    sandbox_id: str
    exit_code: int
    stdout: str
    stderr: str
    command: str
    duration_ms: int
    completed_at: datetime
    trajectory_file: Optional[str] = None
    local_trajectory_path: Optional[str] = None
    trajectory_metadata: Optional[TrajectoryMetadata] = None
    pr_url: Optional[str] = None
    script_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class SolveExecutionRequest:
    session_public_id: str
    issue_url: str
    issue_text: Optional[str]
    repo_url: str
    branch_name: str
    model_name: str
    temperature: float
    small_change: bool
    best_effort: bool
    max_iterations: int
    max_cost: float
    max_tokens: int
    solve_id: str
    solve_run_id: str
    issue_title: Optional[str] = None
    issue_body: Optional[str] = None
    github_token: Optional[str] = None
    workspace_path: str = ""  # resolved from modal_sandbox.SANDBOX_WORKSPACE_PATH
    timeout: int = 1800
    verbose: bool = True


class SolveExecutionError(Exception):
    def __init__(self, message: str, logs: str = ""):
        super().__init__(message)
        self.logs = logs


class TrajectoryStreamAccumulator:
    def __init__(self, *, solve_id: str, run_id: str) -> None:
        self.solve_id = solve_id
        self.run_id = run_id
        self._buffer = ""
        self._trajectory: Dict[str, Any] = {"info": {}, "messages": []}
        self._solve_result: Dict[str, Any] = {}

    def ingest_stdout(self, chunk: str) -> List[Dict[str, Any]]:
        updates: List[Dict[str, Any]] = []
        self._buffer += chunk
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            payload = self._consume_line(line.rstrip("\r"))
            if payload is not None:
                updates.append(payload)
        return updates

    def finalize(self) -> List[Dict[str, Any]]:
        updates: List[Dict[str, Any]] = []
        if self._buffer:
            payload = self._consume_line(self._buffer.rstrip("\r"))
            if payload is not None:
                updates.append(payload)
            self._buffer = ""
        return updates

    @property
    def trajectory(self) -> Optional[Dict[str, Any]]:
        info = self._trajectory.get("info", {})
        messages = self._trajectory.get("messages", [])
        if not info and not messages:
            return None
        if self._solve_result:
            if self._solve_result.get("exit_status"):
                info["exit_status"] = self._solve_result["exit_status"]
            if self._solve_result.get("submission"):
                info["submission"] = self._solve_result["submission"]
        return {"info": info, "messages": messages}

    def _consume_line(self, line: str) -> Optional[Dict[str, Any]]:
        if not line:
            return None

        if line.startswith(TRAJECTORY_UPDATE_PREFIX):
            raw = line[len(TRAJECTORY_UPDATE_PREFIX) :]
            payload = json.loads(raw) if raw else {}
            if not isinstance(payload, dict):
                return None

            info = payload.get("info", {})
            messages = payload.get("messages", [])
            if not isinstance(info, dict):
                info = {}
            if not isinstance(messages, list):
                messages = []

            try:
                current_count = int(payload.get("message_count", len(messages)))
            except (TypeError, ValueError):
                current_count = len(messages)
            try:
                start_index = int(payload.get("new_message_start_index", 0))
            except (TypeError, ValueError):
                start_index = 0

            existing_messages = list(self._trajectory.get("messages", []))
            if start_index < 0 or start_index > len(existing_messages):
                start_index = max(min(start_index, len(existing_messages)), 0)
            if current_count < start_index:
                start_index = 0

            self._trajectory["info"] = info
            self._trajectory["messages"] = existing_messages[:start_index] + messages

            return {
                "solve_id": self.solve_id,
                "run_id": self.run_id,
                "messages": messages,
                "info": info,
                "message_count": current_count,
                "new_message_start_index": start_index,
            }

        if line.startswith(SOLVE_RESULT_PREFIX):
            raw = line[len(SOLVE_RESULT_PREFIX) :]
            payload = json.loads(raw) if raw else {}
            if isinstance(payload, dict):
                self._solve_result = payload

        return None


def _build_script_command(
    *,
    script_path: str,
    script_contents: str,
    runner: str,
) -> str:
    marker = "__YUDAI_SCRIPT__"
    script_dir = Path(script_path).parent
    return "\n".join(
        [
            "set -euo pipefail",
            f"mkdir -p {shlex.quote(str(script_dir))}",
            f"cat <<'{marker}' > {shlex.quote(script_path)}",
            script_contents,
            marker,
            f"chmod +x {shlex.quote(script_path)}",
            f"{runner} {shlex.quote(script_path)}",
        ]
    )


def _extract_trajectory_metadata(trajectory_data: Dict[str, Any]) -> TrajectoryMetadata:
    info = trajectory_data.get("info", {})
    if not isinstance(info, dict):
        info = {}
    model_stats = info.get("model_stats", {})
    if not isinstance(model_stats, dict):
        model_stats = {}
    config = info.get("config", {})
    if not isinstance(config, dict):
        config = {}
    model_config = config.get("model", {})
    if not isinstance(model_config, dict):
        model_config = {}
    messages = trajectory_data.get("messages", [])
    if not isinstance(messages, list):
        messages = []

    return TrajectoryMetadata(
        exit_status=info.get("exit_status"),
        submission=info.get("submission"),
        instance_cost=model_stats.get("instance_cost"),
        api_calls=model_stats.get("api_calls"),
        mini_version=info.get("mini_version"),
        model_name=model_config.get("model_name"),
        total_messages=len(messages),
    )


@dataclass
class SolveTaskState:
    """Tracks background task metadata for running solves."""

    solve_id: str
    run_ids: List[str]
    task: asyncio.Task


@dataclass
class ModelRunPlan:
    """Plan for executing a single model configuration inside a solve."""

    run_id: str
    ai_model_id: int
    model_identifier: str
    temperature: float


class SolverManager(ABC):
    """Base interface describing solver manager operations."""

    @abstractmethod
    async def start_solve(
        self, *, session_id: str, request: StartSolveRequest, user: User
    ) -> StartSolveResponse: ...

    @abstractmethod
    async def get_status(
        self, *, session_id: str, solve_id: str, user: User
    ) -> SolveStatusResponse: ...

    @abstractmethod
    async def cancel_solve(
        self, *, session_id: str, solve_id: str, user: User
    ) -> CancelSolveResponse: ...


class DefaultSolverManager(SolverManager):
    """Concrete solver manager that runs one experiment per solve session."""

    def __init__(
        self, session_factory=SessionLocal, *, max_parallel: Optional[int] = None
    ):
        self._session_factory = session_factory
        self._tasks: Dict[str, SolveTaskState] = {}
        self._lock = asyncio.Lock()
        self._max_parallel = max_parallel or int(os.getenv("SOLVER_MAX_PARALLEL", "3"))
        self._time_budget_s = int(os.getenv("SOLVER_TIME_BUDGET_SECONDS", "5400"))

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _extract_solve_options(self, solve: Solve) -> Dict[str, Any]:
        matrix = solve.matrix or {}
        return {
            "small_change": self._coerce_bool(matrix.get("small_change")),
            "best_effort": self._coerce_bool(matrix.get("best_effort")),
            "max_iterations": self._coerce_int(matrix.get("max_iterations"), 50),
            "max_cost": self._coerce_float(matrix.get("max_cost"), 10.0),
        }

    @staticmethod
    def _build_issue_text(
        *, issue_title: Optional[str], issue_body: Optional[str]
    ) -> Optional[str]:
        title = str(issue_title or "").strip()
        body = str(issue_body or "").strip()
        if not title and not body:
            return None
        if title and body:
            return f"GitHub Issue: {title}\n\n{body}"
        if title:
            return f"GitHub Issue: {title}"
        return body

    async def _build_solve_metadata(
        self,
        *,
        db: Session,
        chat_session: ChatSession,
        repo_url: str,
    ) -> Dict[str, Any]:
        conversation = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == chat_session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(10)
            .all()
        )
        conversation_payload = [
            {"author": message.sender_type, "text": message.message_text}
            for message in reversed(conversation)
        ]

        snapshot = await RepositorySnapshotService.fetch(repo_url=repo_url)
        facts_service = FactsAndMemoriesService()
        analysis = facts_service.build_yudai_grep_analysis(
            snapshot,
            conversation=conversation_payload,
        )
        return {
            "yudai_grep": analysis,
            "generated_at": utc_now().isoformat(),
        }

    async def start_solve(
        self, *, session_id: str, request: StartSolveRequest, user: User
    ) -> StartSolveResponse:
        await self._assert_capacity()

        solve_id = uuid.uuid4().hex
        model_run_plans: List[ModelRunPlan] = []
        issue_url: Optional[str] = None
        issue_title: Optional[str] = None
        issue_body: Optional[str] = None
        github_token: Optional[str] = None
        workspace_path = SANDBOX_WORKSPACE_PATH

        db = self._session_factory()
        try:
            chat_session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id, ChatSession.user_id == user.id
                )
                .first()
            )
            if not chat_session:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Session not found for user"
                )

            issue = (
                db.query(Issue)
                .options(joinedload(Issue.repository))
                .filter(Issue.id == request.issue_id)
                .first()
            )
            if not issue:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Issue not found")

            if issue.repository.user_id != user.id:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Issue not found")

            issue_url = issue.html_url
            issue_title = issue.title
            issue_body = issue.body

            auth_token = (
                db.query(AuthToken)
                .filter(AuthToken.user_id == user.id, AuthToken.is_active)
                .order_by(AuthToken.created_at.desc())
                .first()
            )
            github_token = auth_token.access_token if auth_token else None

            ai_models = self._select_models(
                db,
                ai_model_id=request.ai_model_id,
                ai_model_ids=request.ai_model_ids,
            )
            logger.info(
                "Starting solve %s with %d model(s): %s",
                solve_id,
                len(ai_models),
                ", ".join(model.model_id for model in ai_models),
            )

            repo_url = request.repo_url or getattr(issue.repository, "repo_url", None)
            if not repo_url:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Repository URL is required for solver execution",
                )
            runtime_branch = chat_session.repo_branch or "main"
            branch_name = request.branch_name or runtime_branch

            lifecycle = get_realtime_lifecycle_service()
            await lifecycle.create_runtime_for_session(
                db,
                session=chat_session,
                user_id=user.id,
                org=None,
                repo_owner=chat_session.repo_owner,
                repo_name=chat_session.repo_name,
                environment=runtime_branch,
                repo_branch=runtime_branch,
                repo_url=repo_url,
                env_inputs={
                    "SESSION_PUBLIC_ID": chat_session.session_id,
                    "WORKSPACE_PATH": chat_session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH,
                },
            )

            solve_metadata: Dict[str, Any] = {}
            try:
                solve_metadata = await self._build_solve_metadata(
                    db=db,
                    chat_session=chat_session,
                    repo_url=repo_url,
                )
            except Exception as metadata_error:
                logger.warning(
                    "Failed to build yudai-grep metadata for solve: %s",
                    metadata_error,
                )
                solve_metadata = {
                    "yudai_grep": {"error": str(metadata_error)},
                    "generated_at": utc_now().isoformat(),
                }

            experiments = []
            model_run_plans: List[ModelRunPlan] = []
            solve_runs: List[SolveRun] = []
            selected_models = ai_models[:1]

            for current_model in selected_models:
                run_id = uuid.uuid4().hex
                temperature = self._extract_temperature(current_model)
                experiments.append(
                    {
                        "run_id": run_id,
                        "model": current_model.model_id,
                        "temperature": temperature,
                        "mode": "yolo",
                        "ai_model_id": current_model.id,
                    }
                )
                solve_runs.append(
                    SolveRun(
                        id=run_id,
                        solve_id=solve_id,
                        model=current_model.model_id,
                        temperature=temperature,
                        max_edits=5,
                        evolution="baseline",
                        status=SolveStatus.PENDING.value,
                    )
                )
                model_run_plans.append(
                    ModelRunPlan(
                        run_id=run_id,
                        ai_model_id=current_model.id,
                        model_identifier=current_model.model_id,
                        temperature=temperature,
                    )
                )

            max_parallel = 1

            solve = Solve(
                id=solve_id,
                user_id=user.id,
                session_id=chat_session.id,
                repo_url=repo_url,
                issue_number=issue.number,
                base_branch=request.branch_name,
                status=SolveStatus.PENDING.value,
                matrix={
                    "experiments": experiments,
                    "small_change": request.small_change,
                    "best_effort": request.best_effort,
                    "max_iterations": request.max_iterations,
                    "max_cost": request.max_cost,
                    "metadata": solve_metadata,
                },
                limits={
                    "max_parallel": max_parallel,
                    "time_budget_s": self._time_budget_s,
                },
                requested_by=user.github_username or user.email or "unknown",
                max_parallel=max_parallel,
                time_budget_s=self._time_budget_s,
            )

            # Store user options as attributes for easy access
            solve.small_change = request.small_change
            solve.best_effort = request.best_effort
            solve.max_iterations = request.max_iterations
            solve.max_cost = request.max_cost

            db.add(solve)
            for solve_run in solve_runs:
                db.add(solve_run)

            lifecycle = get_realtime_lifecycle_service()
            lifecycle.record_solve_start(
                db,
                session_public_id=session_id,
                user_id=user.id,
                solve_id=solve_id,
                run_ids=[plan.run_id for plan in model_run_plans],
            )
            workspace_path = chat_session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH
            db.commit()
        finally:
            db.close()

        run_ids = [plan.run_id for plan in model_run_plans]

        task = asyncio.create_task(
            self._execute_runs(
                solve_id=solve_id,
                run_plans=model_run_plans,
                issue_url=issue_url or "",
                repo_url=repo_url,
                branch_name=branch_name,
                session_public_id=session_id,
                workspace_path=workspace_path,
                github_token=github_token,
                issue_title=issue_title,
                issue_body=issue_body,
                issue_text=self._build_issue_text(
                    issue_title=issue_title,
                    issue_body=issue_body,
                ),
            ),
            name=f"solve-{solve_id}",
        )

        task.add_done_callback(
            lambda t, sid=solve_id: asyncio.create_task(self._cleanup_task(sid))
        )

        async with self._lock:
            self._tasks[solve_id] = SolveTaskState(
                solve_id=solve_id,
                run_ids=run_ids,
                task=task,
            )

        return StartSolveResponse(
            solve_session_id=solve_id,
            status=SolveStatus.PENDING,
        )

    async def _execute_runs(
        self,
        *,
        solve_id: str,
        run_plans: List[ModelRunPlan],
        issue_url: str,
        repo_url: str,
        branch_name: str,
        session_public_id: str,
        workspace_path: str,
        github_token: Optional[str] = None,
        issue_title: Optional[str] = None,
        issue_body: Optional[str] = None,
        issue_text: Optional[str] = None,
    ):
        """Execute each requested run sequentially inside the session sandbox."""

        if not run_plans:
            logger.error("No run plans available for solve %s", solve_id)
            return

        try:
            for plan in run_plans:
                logger.info(
                    "Launching run %s for solve %s with model %s",
                    plan.run_id,
                    solve_id,
                    plan.model_identifier,
                )
                await self._execute_run(
                    solve_id=solve_id,
                    run_id=plan.run_id,
                    issue_url=issue_url,
                    repo_url=repo_url,
                    branch_name=branch_name,
                    model_name=plan.model_identifier,
                    session_public_id=session_public_id,
                    workspace_path=workspace_path,
                    github_token=github_token,
                    issue_title=issue_title,
                    issue_body=issue_body,
                    issue_text=issue_text,
                )
        except asyncio.CancelledError:
            logger.info("Solve %s execution loop cancelled", solve_id)
            raise

    async def get_status(
        self, *, session_id: str, solve_id: str, user: User
    ) -> SolveStatusResponse:
        db = self._session_factory()
        try:
            # Look up ChatSession by string session_id
            chat_session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id, ChatSession.user_id == user.id
                )
                .first()
            )
            if not chat_session:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Session not found for user"
                )

            # Query Solve using integer chat_session.id
            solve = (
                db.query(Solve)
                .filter(
                    Solve.id == solve_id,
                    Solve.session_id == chat_session.id,
                    Solve.user_id == user.id,
                )
                .first()
            )
            if not solve:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Solve session not found"
                )

            runs_out = [SolveRunOut.model_validate(run) for run in solve.runs]
            progress = self._build_progress(solve, runs_out)

            champion = (
                SolveRunOut.model_validate(solve.champion_run)
                if solve.champion_run
                else None
            )

            return SolveStatusResponse(
                solve_session_id=solve.id,
                status=SolveStatus(solve.status),
                progress=progress,
                runs=runs_out,
                champion_run=champion,
                error_message=solve.error_message,
                metadata=(solve.matrix or {}).get("metadata"),
            )
        finally:
            db.close()

    async def cancel_solve(
        self, *, session_id: str, solve_id: str, user: User
    ) -> CancelSolveResponse:
        state: Optional[SolveTaskState] = None
        async with self._lock:
            state = self._tasks.get(solve_id)

        if state:
            state.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.task

        db = self._session_factory()
        try:
            # Look up ChatSession by string session_id
            chat_session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id, ChatSession.user_id == user.id
                )
                .first()
            )
            if not chat_session:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Session not found for user"
                )

            # Query Solve using integer chat_session.id
            solve = (
                db.query(Solve)
                .filter(
                    Solve.id == solve_id,
                    Solve.session_id == chat_session.id,
                    Solve.user_id == user.id,
                )
                .first()
            )
            if not solve:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Solve session not found"
                )

            timestamp = utc_now()
            if solve.status not in {
                SolveStatus.COMPLETED.value,
                SolveStatus.CANCELLED.value,
                SolveStatus.FAILED.value,
            }:
                solve.status = SolveStatus.CANCELLED.value
                solve.error_message = "Solve cancelled by user"
                solve.completed_at = timestamp

            for run in solve.runs:
                if run.status not in {
                    SolveStatus.COMPLETED.value,
                    SolveStatus.CANCELLED.value,
                    SolveStatus.FAILED.value,
                }:
                    run.status = SolveStatus.CANCELLED.value
                    run.error_message = "Cancelled by user"
                    run.completed_at = timestamp

            db.commit()
        finally:
            db.close()

        await self._cleanup_task(solve_id)
        return CancelSolveResponse(
            solve_session_id=solve_id,
            status=SolveStatus.CANCELLED,
            message="Solve cancelled",
        )

    async def _execute_run(
        self,
        *,
        solve_id: str,
        run_id: str,
        session_public_id: str,
        issue_url: str,
        repo_url: str,
        branch_name: str,
        workspace_path: str,
        model_name: str,
        issue_text: Optional[str] = None,
        github_token: Optional[str] = None,
        issue_title: Optional[str] = None,
        issue_body: Optional[str] = None,
    ) -> None:
        db = self._session_factory()
        try:
            solve = db.query(Solve).filter(Solve.id == solve_id).first()
            run = db.query(SolveRun).filter(SolveRun.id == run_id).first()
            chat_session = (
                db.query(ChatSession).filter(ChatSession.session_id == session_public_id).first()
            )
            if not solve or not run or not chat_session:
                logger.warning("Solve or run record missing for %s", solve_id)
                return

            logger.info(
                "Preparing run %s for solve %s (model=%s, issue=%s)",
                run_id,
                solve_id,
                model_name,
                issue_url,
            )

            now = utc_now()
            solve.status = SolveStatus.RUNNING.value
            solve.started_at = solve.started_at or now
            run.status = SolveStatus.RUNNING.value
            run.started_at = now
            db.commit()
            await self._broadcast_run_status(
                session_public_id=session_public_id,
                solve_id=solve_id,
                run_id=run_id,
                status_value="running",
            )

            options = self._extract_solve_options(solve)

            request = self._build_execution_request(
                session_public_id=session_public_id,
                issue_url=issue_url,
                issue_text=issue_text,
                repo_url=repo_url,
                branch_name=branch_name,
                workspace_path=workspace_path,
                model_name=model_name,
                run=run,
                solve=solve,
                options=options,
                github_token=github_token,
                issue_title=issue_title,
                issue_body=issue_body,
            )

            try:
                result = await self._run_in_session_sandbox(
                    db=db,
                    session=chat_session,
                    request=request,
                )
                self._record_success(db, solve, run, result)
                if result.exit_code == 0:
                    await self._broadcast_run_status(
                        session_public_id=session_public_id,
                        solve_id=solve_id,
                        run_id=run_id,
                        status_value="completed",
                    )
                else:
                    await self._broadcast_run_status(
                        session_public_id=session_public_id,
                        solve_id=solve_id,
                        run_id=run_id,
                        status_value="failed",
                    )
                    await self._broadcast_run_error(
                        session_public_id=session_public_id,
                        solve_id=solve_id,
                        run_id=run_id,
                        message="Agent execution failed",
                    )
            except SolveExecutionError as exc:
                self._record_failure(
                    db,
                    solve,
                    run,
                    error_message=str(exc),
                    logs=exc.logs,
                )
                await self._broadcast_run_status(
                    session_public_id=session_public_id,
                    solve_id=solve_id,
                    run_id=run_id,
                    status_value="failed",
                )
                await self._broadcast_run_error(
                    session_public_id=session_public_id,
                    solve_id=solve_id,
                    run_id=run_id,
                    message=str(exc),
                )
            except asyncio.CancelledError:
                self._record_cancelled(db, solve, run)
                await self._broadcast_run_status(
                    session_public_id=session_public_id,
                    solve_id=solve_id,
                    run_id=run_id,
                    status_value="cancelled",
                )
                raise
            except Exception as exc:  # pragma: no cover - defensive programming
                logger.exception("Solver run failed: %s", exc)
                self._record_failure(
                    db,
                    solve,
                    run,
                    error_message=str(exc),
                    logs="",
                )
                await self._broadcast_run_error(
                    session_public_id=session_public_id,
                    solve_id=solve_id,
                    run_id=run_id,
                    message=str(exc),
                )
        finally:
            db.close()

    def _build_execution_request(
        self,
        *,
        session_public_id: str,
        issue_url: str,
        issue_text: Optional[str],
        repo_url: str,
        branch_name: str,
        workspace_path: str,
        model_name: str,
        run: SolveRun,
        solve: Solve,
        options: Dict[str, Any],
        github_token: Optional[str] = None,
        issue_title: Optional[str] = None,
        issue_body: Optional[str] = None,
    ) -> SolveExecutionRequest:
        """Create a controller-brokered solve execution request."""

        return SolveExecutionRequest(
            session_public_id=session_public_id,
            issue_url=issue_url,
            issue_text=issue_text,
            repo_url=repo_url,
            branch_name=branch_name,
            workspace_path=workspace_path,
            model_name=model_name,
            temperature=run.temperature,
            small_change=options["small_change"],
            best_effort=options["best_effort"],
            max_iterations=options["max_iterations"],
            max_cost=options["max_cost"],
            max_tokens=4000,
            solve_id=solve.id,
            solve_run_id=run.id,
            verbose=True,
            github_token=github_token,
            issue_title=issue_title,
            issue_body=issue_body,
        )

    def _record_success(
        self, db: Session, solve: Solve, run: SolveRun, result: SolveExecutionResult
    ):
        timestamp = result.completed_at
        succeeded = result.exit_code == 0
        run.status = (
            SolveStatus.COMPLETED.value if succeeded else SolveStatus.FAILED.value
        )
        run.completed_at = timestamp
        run.tests_passed = succeeded
        run.latency_ms = result.duration_ms
        run.sandbox_id = result.sandbox_id
        run.pr_url = result.pr_url
        run.error_message = None if succeeded else "Agent execution failed"

        # Store trajectory data with local path and metadata
        trajectory_data = {}
        if result.trajectory_file:
            trajectory_data["remote_path"] = result.trajectory_file
        if result.local_trajectory_path:
            trajectory_data["local_path"] = result.local_trajectory_path
        if result.trajectory_metadata:
            trajectory_data["metadata"] = {
                "exit_status": result.trajectory_metadata.exit_status,
                "submission": result.trajectory_metadata.submission,
                "instance_cost": result.trajectory_metadata.instance_cost,
                "api_calls": result.trajectory_metadata.api_calls,
                "mini_version": result.trajectory_metadata.mini_version,
                "model_name": result.trajectory_metadata.model_name,
                "total_messages": result.trajectory_metadata.total_messages,
            }
        if trajectory_data:
            run.trajectory_data = trajectory_data

        preview_length = 2000
        run.diagnostics = {
            "command": result.command,
            "stdout_tail": (result.stdout or "")[-preview_length:],
            "stderr_tail": (result.stderr or "")[-preview_length:],
            "script_path": result.script_path,
            "trajectory_file": result.trajectory_file,
            "local_trajectory_path": result.local_trajectory_path,
        }

        if succeeded and not solve.champion_run_id:
            solve.champion_run_id = run.id
            solve.error_message = None

        if run.pr_url:
            lifecycle = get_realtime_lifecycle_service()
            lifecycle.mark_pr_created(
                db,
                session_db_id=solve.session_id,
                session_public_id=None,
                user_id=solve.user_id,
                pr_url=run.pr_url,
                pr_number=self._extract_pr_number_from_url(run.pr_url),
            )

        logger.info(
            "Run %s for solve %s completed (exit_code=%s, success=%s)",
            run.id,
            solve.id,
            result.exit_code,
            succeeded,
        )

        self._finalize_solve_if_complete(db, solve, completed_at=timestamp)
        db.commit()

    def _record_failure(
        self,
        db: Session,
        solve: Solve,
        run: SolveRun,
        *,
        error_message: str,
        logs: str,
    ):
        timestamp = utc_now()
        run.status = SolveStatus.FAILED.value
        run.completed_at = timestamp
        run.error_message = error_message
        run.diagnostics = {"error_logs": logs[-4000:]}

        if not solve.error_message:
            solve.error_message = error_message

        logger.warning(
            "Run %s for solve %s failed: %s", run.id, solve.id, error_message
        )

        self._finalize_solve_if_complete(db, solve, completed_at=timestamp)
        db.commit()

    def _record_cancelled(self, db: Session, solve: Solve, run: SolveRun):
        timestamp = utc_now()
        run.status = SolveStatus.CANCELLED.value
        run.completed_at = timestamp
        run.error_message = "Cancelled by user"

        solve.status = SolveStatus.CANCELLED.value
        solve.error_message = "Cancelled by user"
        solve.completed_at = timestamp

        logger.info("Run %s for solve %s cancelled", run.id, solve.id)

        self._finalize_solve_if_complete(db, solve, completed_at=timestamp)
        db.commit()

    async def _run_in_session_sandbox(
        self,
        *,
        db: Session,
        session: ChatSession,
        request: SolveExecutionRequest,
    ) -> SolveExecutionResult:
        openrouter_api_key = str(os.getenv("OPENROUTER_API_KEY") or "").strip()
        if not openrouter_api_key:
            raise SolveExecutionError("OPENROUTER_API_KEY environment variable required")

        script_params = AgentScriptParams.from_payload(
            model_name=request.model_name,
            repo_url=request.repo_url,
            branch_name=request.branch_name,
            issue_url=request.issue_url,
            issue_text=request.issue_text,
            payload={
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "max_iterations": request.max_iterations,
                "max_cost": request.max_cost,
                "small_change": request.small_change,
                "best_effort": request.best_effort,
                "issue_title": request.issue_title,
                "issue_body": request.issue_body,
            },
            verbose=request.verbose,
        )

        remote_root = f"/tmp/yudai-solve/{request.solve_id}/{request.solve_run_id}"
        script_path = f"{remote_root}/run_agent.py"
        trajectory_path = f"{remote_root}/trajectory.json"
        command = _build_script_command(
            script_path=script_path,
            script_contents=build_agent_script(script_params),
            runner="python3",
        )

        broker = get_sandbox_exec_broker()
        accumulator = TrajectoryStreamAccumulator(
            solve_id=request.solve_id,
            run_id=request.solve_run_id,
        )
        base_env = {
            "OPENROUTER_API_KEY": openrouter_api_key,
            "WORKSPACE_PATH": request.workspace_path or SANDBOX_WORKSPACE_PATH,
            "REPO_URL": request.repo_url,
            "REPO_BRANCH": request.branch_name,
            "TRAJECTORY_PATH": trajectory_path,
            "PYTHONUNBUFFERED": "1",
        }
        if request.github_token:
            base_env["GITHUB_TOKEN"] = request.github_token

        async def on_event(event: Dict[str, Any]) -> None:
            if event.get("type") != WSMessageType.SANDBOX_STREAM.value:
                return
            payload = event.get("payload", {}) or {}
            if payload.get("event") != "stdout":
                return
            chunk = payload.get("data")
            if not isinstance(chunk, str):
                return
            for update in accumulator.ingest_stdout(chunk):
                await self._broadcast_trajectory(
                    session_public_id=session.session_id,
                    payload=update,
                )

        try:
            command_result = await broker.run_command(
                db,
                session=session,
                command=command,
                cwd=request.workspace_path or SANDBOX_WORKSPACE_PATH,
                env=base_env,
                timeout_seconds=request.timeout,
                on_event=on_event,
            )
        except Exception as exc:
            raise SolveExecutionError(str(exc)) from exc

        for update in accumulator.finalize():
            await self._broadcast_trajectory(
                session_public_id=session.session_id,
                payload=update,
            )

        trajectory = accumulator.trajectory
        local_trajectory_path, trajectory_metadata = self._persist_trajectory_snapshot(
            solve_id=request.solve_id,
            run_id=request.solve_run_id,
            repo_url=request.repo_url,
            trajectory=trajectory,
        )

        stdout = str(command_result.get("stdout") or "")
        stderr = str(command_result.get("stderr") or "")
        duration_ms = int(command_result.get("duration_ms") or 0)
        pr_url: Optional[str] = None

        if int(command_result.get("exit_code") or 0) == 0:
            pr_script_path = f"{remote_root}/create_pr.sh"
            pr_command = _build_script_command(
                script_path=pr_script_path,
                script_contents=build_pr_script(script_params),
                runner="bash",
            )
            try:
                pr_result = await broker.run_command(
                    db,
                    session=session,
                    command=pr_command,
                    cwd=request.workspace_path or SANDBOX_WORKSPACE_PATH,
                    env=base_env,
                    timeout_seconds=120,
                )
                stdout = "\n".join(
                    part for part in [stdout, str(pr_result.get("stdout") or "")] if part
                )
                stderr = "\n".join(
                    part for part in [stderr, str(pr_result.get("stderr") or "")] if part
                )
                duration_ms += int(pr_result.get("duration_ms") or 0)
                pr_url = self._extract_pr_url(stdout) or self._extract_pr_url(stderr)
                if pr_url:
                    from realtime.solve_video import kick_off_video_generation

                    asyncio.create_task(
                        kick_off_video_generation(
                            pr_url=pr_url,
                            repo_url=request.repo_url,
                            issue_url=request.issue_url,
                            branch_name=request.branch_name,
                            github_token=request.github_token or "",
                            solve_id=request.solve_id,
                            run_id=request.solve_run_id,
                        )
                    )
            except Exception as exc:  # pragma: no cover - best effort follow-up
                logger.warning(
                    "PR creation failed for solve %s run %s: %s",
                    request.solve_id,
                    request.solve_run_id,
                    exc,
                )

        return SolveExecutionResult(
            sandbox_id=str(command_result.get("sandbox_id") or ""),
            exit_code=int(command_result.get("exit_code") or 0),
            stdout=stdout,
            stderr=stderr,
            command=command,
            duration_ms=duration_ms,
            completed_at=utc_now(),
            trajectory_file=trajectory_path,
            local_trajectory_path=local_trajectory_path,
            trajectory_metadata=trajectory_metadata,
            pr_url=pr_url,
            script_path=script_path,
        )

    def _persist_trajectory_snapshot(
        self,
        *,
        solve_id: str,
        run_id: str,
        repo_url: str,
        trajectory: Optional[Dict[str, Any]],
    ) -> tuple[Optional[str], Optional[TrajectoryMetadata]]:
        if not trajectory:
            return None, None

        repo_slug = repo_url.replace("https://", "").replace("http://", "")
        repo_slug = repo_slug.replace("github.com/", "").replace("/", "_").replace(".", "_")
        local_path = TRAJECTORY_STORAGE_DIR / f"{repo_slug}_{solve_id}_{run_id}.traj.json"
        local_path.write_text(json.dumps(trajectory), encoding="utf-8")
        return str(local_path), _extract_trajectory_metadata(trajectory)

    async def _broadcast_trajectory(
        self,
        *,
        session_public_id: str,
        payload: Dict[str, Any],
    ) -> None:
        await get_ws_hub().send_to_session(
            session_public_id,
            WSMessageType.TRAJECTORY_UPDATE,
            payload,
        )

    async def _broadcast_run_status(
        self,
        *,
        session_public_id: str,
        solve_id: str,
        run_id: str,
        status_value: str,
    ) -> None:
        await get_ws_hub().send_to_session(
            session_public_id,
            WSMessageType.STATUS,
            {"status": status_value, "solve_id": solve_id, "run_id": run_id},
        )

    async def _broadcast_run_error(
        self,
        *,
        session_public_id: str,
        solve_id: str,
        run_id: str,
        message: str,
    ) -> None:
        await get_ws_hub().send_to_session(
            session_public_id,
            WSMessageType.ERROR,
            {"message": message, "solve_id": solve_id, "run_id": run_id},
        )

    async def _cleanup_task(self, solve_id: str):
        async with self._lock:
            self._tasks.pop(solve_id, None)

    async def _assert_capacity(self):
        async with self._lock:
            if len(self._tasks) >= self._max_parallel:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Maximum number of concurrent solves reached",
                )

    def _finalize_solve_if_complete(
        self, db: Session, solve: Solve, *, completed_at: Optional[datetime] = None
    ):
        """Mark the parent solve complete once all runs are resolved."""

        if solve.status == SolveStatus.CANCELLED.value:
            return

        pending_statuses = {
            SolveStatus.PENDING.value,
            SolveStatus.RUNNING.value,
        }
        pending_runs = (
            db.query(SolveRun)
            .filter(
                SolveRun.solve_id == solve.id,
                SolveRun.status.in_(pending_statuses),
            )
            .count()
        )

        if pending_runs > 0:
            solve.status = SolveStatus.RUNNING.value
            return

        finish_time = completed_at or utc_now()
        solve.completed_at = solve.completed_at or finish_time

        if solve.champion_run_id:
            solve.status = SolveStatus.COMPLETED.value
            solve.error_message = None
        else:
            solve.status = SolveStatus.FAILED.value
            solve.error_message = solve.error_message or "All runs failed"

    @staticmethod
    def _extract_pr_url(output_text: Optional[str]) -> Optional[str]:
        if not output_text:
            return None
        match = re.search(r"https://github\.com/[^\s/]+/[^\s/]+/pull/\d+", output_text)
        return match.group(0) if match else None

    @staticmethod
    def _extract_pr_number_from_url(pr_url: Optional[str]) -> Optional[int]:
        if not pr_url:
            return None
        try:
            pr_id = pr_url.rstrip("/").split("/")[-1]
            return int(pr_id)
        except (TypeError, ValueError):
            return None

    def _select_models(
        self,
        db: Session,
        *,
        ai_model_id: Optional[int],
        ai_model_ids: Optional[List[int]],
    ) -> List[AIModel]:
        """Resolve requested models, preserving caller ordering."""

        base_query = db.query(AIModel).filter(AIModel.is_active.is_(True))

        if ai_model_ids:
            models = base_query.filter(AIModel.id.in_(ai_model_ids)).all()
            found_by_id = {model.id: model for model in models}
            ordered_models: List[AIModel] = []
            missing_ids: List[int] = []
            for requested_id in ai_model_ids:
                model = found_by_id.get(requested_id)
                if model:
                    ordered_models.append(model)
                else:
                    missing_ids.append(requested_id)

            if missing_ids:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail=f"AI models not found: {', '.join(map(str, missing_ids))}",
                )

            if not ordered_models:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="No active AI models available for the requested IDs",
                )

            return ordered_models

        if ai_model_id:
            model = (
                base_query.filter(AIModel.id == ai_model_id)
                .order_by(AIModel.id.asc())
                .first()
            )
            if not model:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail="AI model not found or inactive",
                )
            return [model]

        default_model = base_query.order_by(AIModel.id.asc()).first()
        if not default_model:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="No active AI models configured",
            )
        return [default_model]

    @staticmethod
    def _extract_temperature(model: AIModel) -> float:
        try:
            return float((model.config or {}).get("temperature", 0.1))
        except (TypeError, ValueError):
            return 0.1

    @staticmethod
    def _build_progress(solve: Solve, runs: list[SolveRunOut]) -> SolveProgress:
        runs_total = len(runs)
        runs_completed = sum(1 for run in runs if run.status == SolveStatus.COMPLETED)
        runs_failed = sum(1 for run in runs if run.status == SolveStatus.FAILED)
        runs_running = sum(1 for run in runs if run.status == SolveStatus.RUNNING)

        return SolveProgress(
            runs_total=runs_total,
            runs_completed=runs_completed,
            runs_failed=runs_failed,
            runs_running=runs_running,
            last_update=solve.updated_at or utc_now(),
            message=solve.status,
        )
