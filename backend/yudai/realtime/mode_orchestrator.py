"""Controller-side execution orchestration for the fixed 3-mode pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import re
import uuid
from typing import Any, Dict, List, Optional

from yudai.config import get_agent_config, get_model_config, get_sandbox_config
from yudai.config.realtime_flags import get_realtime_feature_flags
from yudai.db.database import SessionLocal
from yudai.models import (
    AgentExecution,
    AuthToken,
    ChatMessage,
    ChatSession,
    ContextCard,
    SandboxStatus,
    SessionArtifact,
    SessionMode,
    SessionModeStatus,
    UserIssue,
    UserQuestion,
    UserQuestionStatus,
)
from sqlalchemy.orm import Session

from yudai.utils import utc_now

from .lifecycle import (
    RealtimeLifecycleService,
    SandboxExecBroker,
    get_realtime_lifecycle_service,
    get_sandbox_exec_broker,
)
from .modal_preflight import wait_for_sandbox_healthcheck
from .modal_sandbox import (
    SANDBOX_MSWEA_CONFIG_ROOT,
    SANDBOX_WORKSPACE_PATH,
)
from .mode_contracts import (
    CHANGED_FILES_END,
    CHANGED_FILES_START,
    CONTRACT_VERSION,
    ModeContractError,
    extract_changed_files_from_output,
    normalize_changed_files,
    parse_mode_contract,
    validate_mode_changed_files,
)
from .ws_protocol import SessionWebSocketHub, WSMessageType, get_ws_hub

MODE_ORDER: tuple[str, str, str] = (
    SessionMode.ARCHITECT.value,
    SessionMode.TESTER.value,
    SessionMode.CODER.value,
)

SANDBOX_EXECUTION_ROOT = ".yudai/executions"
BROWSER_CHECK_TOOL_NAME = "run_frontend_browser_check"
BROWSER_CHECK_MODE = SessionMode.BROWSER_CHECK.value
BROWSER_CHECK_SUMMARY_START = "__YUDAI_BROWSER_CHECK_SUMMARY_START__"
BROWSER_CHECK_SUMMARY_END = "__YUDAI_BROWSER_CHECK_SUMMARY_END__"
BROWSER_CHECK_REPORT_START = "__YUDAI_BROWSER_CHECK_REPORT_START__"
BROWSER_CHECK_REPORT_END = "__YUDAI_BROWSER_CHECK_REPORT_END__"

MSWEA_CONFIG_ROOT = SANDBOX_MSWEA_CONFIG_ROOT
MSWEA_CONFIG_PATHS = {
    SessionMode.ARCHITECT.value: f"{MSWEA_CONFIG_ROOT}/architect/config.yaml",
    SessionMode.TESTER.value: f"{MSWEA_CONFIG_ROOT}/tester/config.yaml",
    SessionMode.CODER.value: f"{MSWEA_CONFIG_ROOT}/coder/config.yaml",
    BROWSER_CHECK_MODE: f"{MSWEA_CONFIG_ROOT}/browser/config.yaml",
}

ISSUE_URL_PATTERN = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+/issues/(\d+)")
PR_URL_PATTERN = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+/pull/(\d+)")
ISSUE_NUMBER_PATTERN = re.compile(r"(?im)\b(?:issue[_ -]?number|issue number)\b\s*[:=]\s*(\d+)")
PR_NUMBER_PATTERN = re.compile(r"(?im)\b(?:pr[_ -]?number|pull[_ -]?number|pr number)\b\s*[:=]\s*(\d+)")
TEST_BRANCH_PATTERN = re.compile(r"(?im)\b(?:test[_ -]?branch|test branch)\b\s*[:=]\s*([^\s\"']+)")


class ExecutionConflictError(RuntimeError):
    """Raised when a second execution is attempted for the same session."""


class ExecutionNotFoundError(RuntimeError):
    """Raised when the requested execution state is missing."""


class SessionExecutionOrchestrator:
    """Single facade for session execution lifecycle and 3-mode orchestration."""

    def __init__(
        self,
        *,
        broker: Optional[SandboxExecBroker] = None,
        lifecycle: Optional[RealtimeLifecycleService] = None,
        ws_hub: Optional[SessionWebSocketHub] = None,
    ) -> None:
        self.broker = broker or get_sandbox_exec_broker()
        self.lifecycle = lifecycle or get_realtime_lifecycle_service()
        self.ws_hub = ws_hub or get_ws_hub()
        self._session_tasks: Dict[str, asyncio.Task[None]] = {}
        self._browser_check_tasks: Dict[str, asyncio.Task[None]] = {}
        self._session_locks: Dict[str, asyncio.Lock] = {}

    async def start_execution(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
        objective: str,
        force_mode: Optional[str] = None,
        max_modes: Optional[int] = None,
        trigger: str = "execution_api",
    ) -> Dict[str, Any]:
        next_mode = self._next_mode_for_session(session)
        if next_mode == SessionMode.COMPLETE.value:
            raise ExecutionConflictError("Session workflow already complete")
        if max_modes is not None and max_modes < 1:
            raise ValueError("max_modes must be at least 1 when provided")
        if force_mode and force_mode != next_mode:
            raise ValueError(
                f"Mode switching is server-controlled. Expected '{next_mode}', got '{force_mode}'."
            )
        if self._has_active_task(session.session_id):
            raise ExecutionConflictError("An execution is already running for this session")

        contextual_objective = self._build_objective_with_context(
            db,
            session=session,
            objective=objective,
        )
        execution_id = f"exec_{uuid.uuid4().hex[:24]}"
        execution_plan = self._build_mode_plan(next_mode, contextual_objective)
        execution_started_at = utc_now()
        session_public_id = session.session_id

        execution = AgentExecution(
            id=execution_id,
            session_id=session.id,
            mode=next_mode,
            status=SessionModeStatus.RUNNING.value,
            execution_plan=execution_plan,
            execution_metadata={
                "trigger": trigger,
                "objective": objective,
                "objective_with_context": contextual_objective,
                "max_modes": max_modes,
            },
            started_at=execution_started_at,
        )
        db.add(execution)
        queued_detail = "Stage queued" if max_modes == 1 else "Pipeline queued"

        self._set_active_execution(
            session,
            {
                "execution_id": execution_id,
                "objective": objective,
                "objective_with_context": contextual_objective,
                "status": SessionModeStatus.RUNNING.value,
                "mode": next_mode,
                "plan": execution_plan,
                "started_at": execution_started_at.isoformat(),
                "completed_at": None,
                "cancel_requested": False,
                "waiting_for_input": False,
                "current_mode_execution_id": None,
                "artifact": None,
                "detail": queued_detail,
                "trigger": trigger,
                "max_modes": max_modes,
            },
        )
        session.current_mode = next_mode
        session.mode_status = SessionModeStatus.RUNNING.value
        session.mode_updated_at = utc_now()
        session.last_activity = utc_now()
        db.commit()

        self._schedule_execution_task(
            session_public_id=session_public_id,
            user_id=user_id,
            execution_id=execution_id,
            objective=contextual_objective,
            max_modes=max_modes,
        )

        await self.ws_hub.send_to_session(
            session_public_id,
            WSMessageType.MODE_EVENT,
            {
                "mode": next_mode,
                "state": SessionModeStatus.RUNNING.value,
                "execution_id": execution_id,
                "detail": queued_detail,
            },
        )
        return {
            "execution_id": execution_id,
            "session_id": session_public_id,
            "mode": next_mode,
            "status": SessionModeStatus.RUNNING.value,
            "plan": execution_plan,
            "started_at": execution_started_at,
            "completed_at": None,
            "cancel_requested": False,
            "waiting_for_input": False,
            "current_mode_execution_id": None,
            "artifact": None,
            "detail": queued_detail,
        }

    async def start_stage_execution(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
        objective: str,
        mode: str,
        trigger: str = "daifu_stage_tool",
    ) -> Dict[str, Any]:
        return await self.start_execution(
            db,
            session=session,
            user_id=user_id,
            objective=objective,
            force_mode=mode,
            max_modes=1,
            trigger=trigger,
        )

    async def start_browser_check(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
        objective: str,
        trigger: str = f"daifu_tool:{BROWSER_CHECK_TOOL_NAME}",
    ) -> Dict[str, Any]:
        """Start the manual browser verifier sidecar without advancing mode state."""
        if self._has_active_task(session.session_id):
            raise ExecutionConflictError("An execution is already running for this session")

        execution_id = f"exec_{uuid.uuid4().hex[:24]}"
        started_at = utc_now()
        execution_plan = self._build_mode_plan(BROWSER_CHECK_MODE, objective)
        execution = AgentExecution(
            id=execution_id,
            session_id=session.id,
            mode=BROWSER_CHECK_MODE,
            status=SessionModeStatus.RUNNING.value,
            execution_plan=execution_plan,
            execution_metadata={
                "trigger": trigger,
                "objective": objective,
                "tool_name": BROWSER_CHECK_TOOL_NAME,
                "sidecar": True,
            },
            started_at=started_at,
        )
        db.add(execution)

        metadata = dict(session.mode_metadata or {})
        metadata["browser_check"] = {
            "execution_id": execution_id,
            "status": SessionModeStatus.RUNNING.value,
            "objective": objective,
            "started_at": started_at.isoformat(),
            "completed_at": None,
        }
        session.mode_metadata = metadata
        session.last_activity = utc_now()
        db.commit()

        self._schedule_browser_check_task(
            session_public_id=session.session_id,
            user_id=user_id,
            execution_id=execution_id,
            objective=objective,
        )

        await self.ws_hub.send_to_session(
            session.session_id,
            WSMessageType.TOOL_CALL,
            {
                "tool_name": BROWSER_CHECK_TOOL_NAME,
                "tool_input": {
                    "session_id": session.session_id,
                    "objective": objective,
                },
                "call_id": execution_id,
            },
        )
        await self.ws_hub.send_to_session(
            session.session_id,
            WSMessageType.MODE_EVENT,
            {
                "mode": BROWSER_CHECK_MODE,
                "state": SessionModeStatus.RUNNING.value,
                "execution_id": execution_id,
                "detail": "Browser check queued",
            },
        )

        return {
            "execution_id": execution_id,
            "session_id": session.session_id,
            "mode": BROWSER_CHECK_MODE,
            "status": SessionModeStatus.RUNNING.value,
            "plan": execution_plan,
            "started_at": started_at,
            "completed_at": None,
            "cancel_requested": False,
            "waiting_for_input": False,
            "current_mode_execution_id": execution_id,
            "artifact": None,
            "detail": "Browser check queued",
        }

    async def resume_execution(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
        objective: str,
    ) -> Dict[str, Any]:
        active_execution = self._get_active_execution(session)
        if not active_execution:
            raise ExecutionNotFoundError("No execution is available to resume")
        if self._has_active_task(session.session_id):
            raise ExecutionConflictError("An execution is already running for this session")

        next_mode = self._next_mode_for_session(session)
        if next_mode == SessionMode.COMPLETE.value:
            raise ExecutionConflictError("Session workflow already complete")

        contextual_objective = self._build_objective_with_context(
            db,
            session=session,
            objective=objective,
        )
        execution_id = str(active_execution.get("execution_id") or f"execp_{uuid.uuid4().hex[:24]}")
        started_at = str(active_execution.get("started_at") or utc_now().isoformat())

        self._set_active_execution(
            session,
            {
                **active_execution,
                "execution_id": execution_id,
                "objective": objective,
                "objective_with_context": contextual_objective,
                "status": SessionModeStatus.RUNNING.value,
                "mode": next_mode,
                "plan": self._build_mode_plan(next_mode, contextual_objective),
                "started_at": started_at,
                "completed_at": None,
                "cancel_requested": False,
                "waiting_for_input": False,
                "detail": "Pipeline resumed after question answer",
            },
        )
        session.current_mode = next_mode
        session.mode_status = SessionModeStatus.RUNNING.value
        session.mode_updated_at = utc_now()
        session.last_activity = utc_now()
        db.commit()

        self._schedule_execution_task(
            session_public_id=session.session_id,
            user_id=user_id,
            execution_id=execution_id,
            objective=contextual_objective,
        )

        await self.ws_hub.send_to_session(
            session.session_id,
            WSMessageType.MODE_EVENT,
            {
                "mode": next_mode,
                "state": SessionModeStatus.RUNNING.value,
                "execution_id": execution_id,
                "detail": "Pipeline resumed after question answer",
            },
        )
        return self.get_execution_status(db, session=session)

    async def cancel_execution(
        self,
        db: Session,
        *,
        session: ChatSession,
    ) -> Dict[str, Any]:
        active_execution = self._get_active_execution(session)
        task = self._session_tasks.get(session.session_id)
        if not active_execution and task is None:
            raise ExecutionNotFoundError("No active execution was found for this session")

        execution_id = str((active_execution or {}).get("execution_id") or "")
        self._set_active_execution(
            session,
            {
                **(active_execution or {}),
                "execution_id": execution_id or None,
                "status": SessionModeStatus.CANCELLED.value,
                "completed_at": utc_now().isoformat(),
                "cancel_requested": True,
                "detail": "Execution cancellation requested",
            },
        )
        session.mode_status = SessionModeStatus.CANCELLED.value
        session.mode_updated_at = utc_now()
        session.last_activity = utc_now()
        db.commit()

        if task and not task.done():
            task.cancel()
        else:
            artifact = await self._finalize_runtime(
                db,
                session=session,
                execution_id=execution_id or None,
                execution_status=SessionModeStatus.CANCELLED.value,
                reason="execution_cancelled",
            )
            if artifact:
                self._update_active_execution(session, artifact=artifact)
                db.commit()

        await self.ws_hub.send_to_session(
            session.session_id,
            WSMessageType.MODE_EVENT,
            {
                "mode": session.current_mode or self._next_mode_for_session(session),
                "state": SessionModeStatus.CANCELLED.value,
                "execution_id": execution_id or None,
                "detail": "Execution cancelled",
            },
        )
        return self.get_execution_status(db, session=session)

    def get_execution_status(
        self,
        db: Session,
        *,
        session: ChatSession,
    ) -> Dict[str, Any]:
        active_execution = self._get_active_execution(session)
        latest_artifact = (
            db.query(SessionArtifact)
            .filter(SessionArtifact.session_id == session.id)
            .order_by(SessionArtifact.id.desc())
            .first()
        )

        artifact_payload = active_execution.get("artifact") if active_execution else None
        if artifact_payload is None and latest_artifact:
            artifact_payload = self._artifact_payload_from_row(latest_artifact)

        next_mode = self._next_mode_for_session(session)
        objective_for_plan = str((active_execution or {}).get("objective_with_context") or "")

        return {
            "execution_id": (active_execution or {}).get("execution_id"),
            "session_id": session.session_id,
            "mode": str((active_execution or {}).get("mode") or session.current_mode or next_mode),
            "status": str((active_execution or {}).get("status") or session.mode_status or SessionModeStatus.IDLE.value),
            "plan": list((active_execution or {}).get("plan") or self._build_mode_plan(next_mode, objective_for_plan)),
            "started_at": self._parse_datetime((active_execution or {}).get("started_at")),
            "completed_at": self._parse_datetime((active_execution or {}).get("completed_at")),
            "cancel_requested": bool((active_execution or {}).get("cancel_requested")),
            "waiting_for_input": session.mode_status == SessionModeStatus.WAITING_FOR_INPUT.value,
            "current_mode_execution_id": (active_execution or {}).get("current_mode_execution_id"),
            "artifact": artifact_payload,
            "detail": (active_execution or {}).get("detail"),
        }

    async def run_full_pipeline(
        self,
        *,
        session_public_id: str,
        user_id: int,
        execution_id: str,
        objective: str,
        max_modes: Optional[int] = None,
    ) -> None:
        lock = self._session_locks.setdefault(session_public_id, asyncio.Lock())
        async with lock:
            db = SessionLocal()
            session: Optional[ChatSession] = None
            current_mode_execution: Optional[AgentExecution] = None
            try:
                session = (
                    db.query(ChatSession)
                    .filter(
                        ChatSession.session_id == session_public_id,
                        ChatSession.user_id == user_id,
                    )
                    .first()
                )
                if not session:
                    return

                await self._ensure_runtime_ready(db, session=session, user_id=user_id)
                modes_to_run = self._remaining_modes(session)
                if max_modes is not None:
                    modes_to_run = modes_to_run[:max_modes]
                if not modes_to_run:
                    self._set_mode_state(
                        session,
                        mode=SessionMode.COMPLETE.value,
                        mode_status=SessionModeStatus.COMPLETE.value,
                    )
                    self._update_active_execution(
                        session,
                        execution_id=execution_id,
                        mode=SessionMode.COMPLETE.value,
                        status=SessionModeStatus.COMPLETE.value,
                        completed_at=utc_now().isoformat(),
                        current_mode_execution_id=None,
                        detail="Workflow already complete.",
                    )
                    db.commit()
                    return

                for mode in modes_to_run:
                    self._raise_if_cancel_requested(session)
                    current_mode_execution = self._create_execution_row(
                        db,
                        session=session,
                        mode=mode,
                        objective=objective,
                        pipeline_execution_id=execution_id,
                    )
                    self._set_mode_state(
                        session,
                        mode=mode,
                        mode_status=SessionModeStatus.RUNNING.value,
                    )
                    self._update_active_execution(
                        session,
                        execution_id=execution_id,
                        mode=mode,
                        status=SessionModeStatus.RUNNING.value,
                        plan=current_mode_execution.execution_plan or [],
                        current_mode_execution_id=current_mode_execution.id,
                        detail=f"{mode.capitalize()} mode running",
                    )
                    db.commit()

                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.TOOL_CALL,
                        {
                            "tool_name": f"run_{mode}_mode",
                            "tool_input": {
                                "session_id": session_public_id,
                                "mode": mode,
                                "issue_number": session.architect_issue_number,
                                "issue_url": session.architect_issue_url,
                            },
                            "call_id": current_mode_execution.id,
                        },
                    )

                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.MODE_EVENT,
                        {
                            "mode": mode,
                            "state": SessionModeStatus.RUNNING.value,
                            "execution_id": execution_id,
                            "mode_execution_id": current_mode_execution.id,
                        },
                    )

                    if mode == SessionMode.ARCHITECT.value:
                        result = await self._run_architect(
                            db,
                            session=session,
                            execution=current_mode_execution,
                            user_id=user_id,
                            objective=objective,
                            pipeline_execution_id=execution_id,
                        )
                    elif mode == SessionMode.TESTER.value:
                        result = await self._run_tester(
                            db,
                            session=session,
                            execution=current_mode_execution,
                            objective=objective,
                            pipeline_execution_id=execution_id,
                        )
                    else:
                        result = await self._run_coder(
                            db,
                            session=session,
                            execution=current_mode_execution,
                            user_id=user_id,
                            objective=objective,
                            pipeline_execution_id=execution_id,
                        )

                    if result.get("waiting_for_input"):
                        current_mode_execution.status = SessionModeStatus.WAITING_FOR_INPUT.value
                        current_mode_execution.completed_at = utc_now()
                        current_mode_execution.output_summary = result
                        self._set_mode_state(
                            session,
                            mode=mode,
                            mode_status=SessionModeStatus.WAITING_FOR_INPUT.value,
                        )
                        self._update_active_execution(
                            session,
                            execution_id=execution_id,
                            mode=mode,
                            status=SessionModeStatus.WAITING_FOR_INPUT.value,
                            waiting_for_input=True,
                            current_mode_execution_id=None,
                            detail=result.get("detail") or f"{mode.capitalize()} mode is waiting for input",
                        )
                        db.commit()

                        await self.ws_hub.send_to_session(
                            session_public_id,
                            WSMessageType.MODE_EVENT,
                            {
                                "mode": mode,
                                "state": SessionModeStatus.WAITING_FOR_INPUT.value,
                                "execution_id": execution_id,
                                "mode_execution_id": current_mode_execution.id,
                                "detail": result.get("detail"),
                            },
                        )
                        return

                    current_mode_execution.status = SessionModeStatus.COMPLETE.value
                    current_mode_execution.completed_at = utc_now()
                    current_mode_execution.output_summary = result
                    self._set_mode_state(
                        session,
                        mode=mode,
                        mode_status=SessionModeStatus.COMPLETE.value,
                    )
                    self._update_active_execution(
                        session,
                        execution_id=execution_id,
                        mode=mode,
                        status=SessionModeStatus.RUNNING.value,
                        current_mode_execution_id=None,
                        detail=f"{mode.capitalize()} mode complete",
                    )
                    db.commit()

                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.MODE_EVENT,
                        {
                            "mode": mode,
                            "state": SessionModeStatus.COMPLETE.value,
                            "execution_id": execution_id,
                            "mode_execution_id": current_mode_execution.id,
                        },
                    )

                remaining_after_run = self._remaining_modes(session)
                if remaining_after_run:
                    next_mode = remaining_after_run[0]
                    self._set_mode_state(
                        session,
                        mode=next_mode,
                        mode_status=SessionModeStatus.IDLE.value,
                    )
                    self._update_active_execution(
                        session,
                        execution_id=execution_id,
                        mode=next_mode,
                        status=SessionModeStatus.COMPLETE.value,
                        completed_at=utc_now().isoformat(),
                        current_mode_execution_id=None,
                        detail=f"{modes_to_run[-1].capitalize()} mode complete; {next_mode.capitalize()} mode is next.",
                    )
                    db.commit()

                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.STATE_EVENT,
                        {
                            "state": "stage_complete",
                            "session_id": session_public_id,
                            "current_mode": next_mode,
                            "execution_id": execution_id,
                        },
                    )
                    return

                self._set_mode_state(
                    session,
                    mode=SessionMode.COMPLETE.value,
                    mode_status=SessionModeStatus.COMPLETE.value,
                )
                session.workflow_completed_at = utc_now()
                self._update_active_execution(
                    session,
                    execution_id=execution_id,
                    mode=SessionMode.COMPLETE.value,
                    status=SessionModeStatus.COMPLETE.value,
                    completed_at=utc_now().isoformat(),
                    current_mode_execution_id=None,
                    detail="Workflow complete",
                )

                artifact = await self._finalize_runtime(
                    db,
                    session=session,
                    execution_id=execution_id,
                    execution_status=SessionModeStatus.COMPLETE.value,
                    reason="workflow_complete",
                )
                if artifact:
                    self._update_active_execution(session, artifact=artifact)
                db.commit()

                await self.ws_hub.send_to_session(
                    session_public_id,
                    WSMessageType.STATE_EVENT,
                    {
                        "state": "workflow_complete",
                        "session_id": session_public_id,
                        "current_mode": SessionMode.COMPLETE.value,
                        "execution_id": execution_id,
                    },
                )
            except asyncio.CancelledError:
                if session is not None:
                    if current_mode_execution is not None:
                        current_mode_execution.status = SessionModeStatus.CANCELLED.value
                        current_mode_execution.completed_at = utc_now()
                    self._set_mode_state(
                        session,
                        mode=session.current_mode or self._next_mode_for_session(session),
                        mode_status=SessionModeStatus.CANCELLED.value,
                    )
                    self._update_active_execution(
                        session,
                        execution_id=execution_id,
                        status=SessionModeStatus.CANCELLED.value,
                        completed_at=utc_now().isoformat(),
                        current_mode_execution_id=None,
                        detail="Execution cancelled",
                    )
                    artifact = await self._finalize_runtime(
                        db,
                        session=session,
                        execution_id=execution_id,
                        execution_status=SessionModeStatus.CANCELLED.value,
                        reason="execution_cancelled",
                    )
                    if artifact:
                        self._update_active_execution(session, artifact=artifact)
                    db.commit()

                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.MODE_EVENT,
                        {
                            "mode": session.current_mode or self._next_mode_for_session(session),
                            "state": SessionModeStatus.CANCELLED.value,
                            "execution_id": execution_id,
                            "mode_execution_id": current_mode_execution.id if current_mode_execution else None,
                        },
                    )
                raise
            except Exception as exc:
                if session is not None:
                    if current_mode_execution is not None:
                        current_mode_execution.status = SessionModeStatus.FAILED.value
                        current_mode_execution.completed_at = utc_now()
                        current_mode_execution.error_message = str(exc)
                    self._set_mode_state(
                        session,
                        mode=SessionMode.FAILED.value,
                        mode_status=SessionModeStatus.FAILED.value,
                    )
                    self._update_active_execution(
                        session,
                        execution_id=execution_id,
                        mode=session.current_mode or self._next_mode_for_session(session),
                        status=SessionModeStatus.FAILED.value,
                        completed_at=utc_now().isoformat(),
                        current_mode_execution_id=None,
                        detail=str(exc),
                    )
                    artifact = await self._finalize_runtime(
                        db,
                        session=session,
                        execution_id=execution_id,
                        execution_status=SessionModeStatus.FAILED.value,
                        reason="execution_failed",
                    )
                    if artifact:
                        self._update_active_execution(session, artifact=artifact)
                    db.commit()

                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.ERROR,
                        {
                            "message": str(exc),
                            "execution_id": execution_id,
                            "mode": session.current_mode,
                        },
                    )
                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.MODE_EVENT,
                        {
                            "mode": session.current_mode or self._next_mode_for_session(session),
                            "state": SessionModeStatus.FAILED.value,
                            "execution_id": execution_id,
                            "mode_execution_id": current_mode_execution.id if current_mode_execution else None,
                        },
                    )
            finally:
                db.close()

    async def run_browser_check(
        self,
        *,
        session_public_id: str,
        user_id: int,
        execution_id: str,
        objective: str,
    ) -> None:
        lock = self._session_locks.setdefault(session_public_id, asyncio.Lock())
        async with lock:
            db = SessionLocal()
            session: Optional[ChatSession] = None
            execution: Optional[AgentExecution] = None
            result: Dict[str, Any] = {}
            try:
                session = (
                    db.query(ChatSession)
                    .filter(
                        ChatSession.session_id == session_public_id,
                        ChatSession.user_id == user_id,
                    )
                    .first()
                )
                if not session:
                    return

                execution = (
                    db.query(AgentExecution)
                    .filter(
                        AgentExecution.id == execution_id,
                        AgentExecution.session_id == session.id,
                        AgentExecution.mode == BROWSER_CHECK_MODE,
                    )
                    .first()
                )
                if not execution:
                    return

                await self._ensure_runtime_ready(db, session=session, user_id=user_id)
                result = await self._execute_browser_check(
                    db,
                    session=session,
                    execution=execution,
                    objective=objective,
                )
                if result.get("exit_code", 1) != 0:
                    raise RuntimeError(
                        "Browser check failed with "
                        f"exit_code={result.get('exit_code')}"
                    )

                artifact = await self._export_browser_check_artifact(
                    db,
                    session=session,
                    execution_id=execution_id,
                    result=result,
                )
                if artifact:
                    result["artifact"] = artifact

                execution.status = SessionModeStatus.COMPLETE.value
                execution.completed_at = utc_now()
                execution.output_summary = result
                self._record_browser_check_metadata(
                    session,
                    execution_id=execution_id,
                    status=SessionModeStatus.COMPLETE.value,
                    objective=objective,
                    result=result,
                    artifact=artifact,
                )
                self._create_browser_check_context_card(
                    db,
                    session=session,
                    result=result,
                    artifact=artifact,
                )
                session.last_activity = utc_now()
                db.commit()

                await self.ws_hub.send_to_session(
                    session_public_id,
                    WSMessageType.MODE_EVENT,
                    {
                        "mode": BROWSER_CHECK_MODE,
                        "state": SessionModeStatus.COMPLETE.value,
                        "execution_id": execution_id,
                        "detail": "Browser check complete",
                    },
                )
            except asyncio.CancelledError:
                if session is not None and execution is not None:
                    execution.status = SessionModeStatus.CANCELLED.value
                    execution.completed_at = utc_now()
                    execution.output_summary = result or None
                    self._record_browser_check_metadata(
                        session,
                        execution_id=execution_id,
                        status=SessionModeStatus.CANCELLED.value,
                        objective=objective,
                        result=result,
                        artifact=None,
                    )
                    db.commit()
                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.MODE_EVENT,
                        {
                            "mode": BROWSER_CHECK_MODE,
                            "state": SessionModeStatus.CANCELLED.value,
                            "execution_id": execution_id,
                            "detail": "Browser check cancelled",
                        },
                    )
                raise
            except Exception as exc:
                if session is not None and execution is not None:
                    result = dict(result or {})
                    result["error"] = str(exc)
                    execution.status = SessionModeStatus.FAILED.value
                    execution.completed_at = utc_now()
                    execution.error_message = str(exc)
                    execution.output_summary = result
                    self._record_browser_check_metadata(
                        session,
                        execution_id=execution_id,
                        status=SessionModeStatus.FAILED.value,
                        objective=objective,
                        result=result,
                        artifact=None,
                    )
                    session.last_activity = utc_now()
                    db.commit()
                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.ERROR,
                        {
                            "message": str(exc),
                            "execution_id": execution_id,
                            "mode": BROWSER_CHECK_MODE,
                        },
                    )
                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.MODE_EVENT,
                        {
                            "mode": BROWSER_CHECK_MODE,
                            "state": SessionModeStatus.FAILED.value,
                            "execution_id": execution_id,
                            "detail": str(exc),
                        },
                    )
            finally:
                db.close()

    def _schedule_execution_task(
        self,
        *,
        session_public_id: str,
        user_id: int,
        execution_id: str,
        objective: str,
        max_modes: Optional[int] = None,
    ) -> None:
        task = asyncio.create_task(
            self.run_full_pipeline(
                session_public_id=session_public_id,
                user_id=user_id,
                execution_id=execution_id,
                objective=objective,
                max_modes=max_modes,
            ),
            name=f"session-execution-{session_public_id}",
        )
        self._session_tasks[session_public_id] = task

        def _cleanup(done_task: asyncio.Task[None]) -> None:
            current = self._session_tasks.get(session_public_id)
            if current is done_task:
                self._session_tasks.pop(session_public_id, None)

        task.add_done_callback(_cleanup)

    def _schedule_browser_check_task(
        self,
        *,
        session_public_id: str,
        user_id: int,
        execution_id: str,
        objective: str,
    ) -> None:
        task = asyncio.create_task(
            self.run_browser_check(
                session_public_id=session_public_id,
                user_id=user_id,
                execution_id=execution_id,
                objective=objective,
            ),
            name=f"browser-check-{session_public_id}",
        )
        self._browser_check_tasks[session_public_id] = task

        def _cleanup(done_task: asyncio.Task[None]) -> None:
            current = self._browser_check_tasks.get(session_public_id)
            if current is done_task:
                self._browser_check_tasks.pop(session_public_id, None)

        task.add_done_callback(_cleanup)

    def _has_active_task(self, session_public_id: str) -> bool:
        task = self._session_tasks.get(session_public_id)
        sidecar_task = self._browser_check_tasks.get(session_public_id)
        return bool(task and not task.done()) or bool(sidecar_task and not sidecar_task.done())

    def _remaining_modes(self, session: ChatSession) -> List[str]:
        pending: List[str] = []
        if not session.architect_completed_at:
            pending.append(SessionMode.ARCHITECT.value)
        if not session.tester_completed_at:
            pending.append(SessionMode.TESTER.value)
        if not session.coder_completed_at:
            pending.append(SessionMode.CODER.value)
        return pending

    def _next_mode_for_session(self, session: ChatSession) -> str:
        remaining = self._remaining_modes(session)
        return remaining[0] if remaining else SessionMode.COMPLETE.value

    @staticmethod
    def _parse_datetime(raw: Any) -> Optional[datetime]:
        if raw is None:
            return None
        if isinstance(raw, datetime):
            return raw
        text = str(raw).strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def _artifact_payload_from_row(artifact: SessionArtifact) -> Dict[str, Any]:
        return {
            "bundle_path": artifact.bundle_path,
            "metadata_path": (
                artifact.artifact_metadata or {}
            ).get("sandbox_bundle", {}).get("metadata_path")
            if isinstance(artifact.artifact_metadata, dict)
            else None,
            "checksum_sha256": artifact.checksum_sha256,
            "byte_size": artifact.byte_size,
        }

    @staticmethod
    def _get_active_execution(session: ChatSession) -> Dict[str, Any]:
        metadata = session.mode_metadata or {}
        active_execution = metadata.get("active_execution")
        return active_execution if isinstance(active_execution, dict) else {}

    @staticmethod
    def _set_active_execution(session: ChatSession, execution_state: Dict[str, Any]) -> None:
        metadata = session.mode_metadata or {}
        metadata["active_execution"] = execution_state
        session.mode_metadata = metadata

    def _update_active_execution(self, session: ChatSession, **updates: Any) -> None:
        execution_state = dict(self._get_active_execution(session))
        execution_state.update({key: value for key, value in updates.items() if value is not None})
        self._set_active_execution(session, execution_state)

    @staticmethod
    def _truncate_for_context(value: str, limit: int = 400) -> str:
        compact = " ".join((value or "").split())
        if len(compact) <= limit:
            return compact
        return compact[:limit] + "..."

    def _build_objective_with_context(
        self,
        db: Session,
        *,
        session: ChatSession,
        objective: str,
    ) -> str:
        objective_sections = [f"Primary Objective:\n{objective.strip()}"]

        recent_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(12)
            .all()
        )
        if recent_messages:
            lines = []
            for message in reversed(recent_messages):
                role = (message.role or message.sender_type or "user").strip().lower()
                lines.append(f"- [{role}] {self._truncate_for_context(message.message_text, 300)}")
            objective_sections.append(
                "Relevant Chat Context (most recent messages):\n" + "\n".join(lines)
            )

        answered_questions = (
            db.query(UserQuestion)
            .filter(
                UserQuestion.session_id == session.id,
                UserQuestion.status == UserQuestionStatus.ANSWERED.value,
            )
            .order_by(UserQuestion.answered_at.desc(), UserQuestion.created_at.desc())
            .limit(10)
            .all()
        )
        if answered_questions:
            qa_lines = []
            for question in reversed(answered_questions):
                options = {
                    str(item.get("id")): str(item.get("label"))
                    for item in (question.options or [])
                    if isinstance(item, dict) and item.get("id") and item.get("label")
                }
                selected = []
                for option_id in question.selected_option_ids or []:
                    option_id_str = str(option_id)
                    selected.append(options.get(option_id_str, option_id_str))

                answer_parts: List[str] = []
                if selected:
                    answer_parts.append("selected: " + ", ".join(selected))
                if question.answer_text:
                    answer_parts.append("text: " + self._truncate_for_context(question.answer_text, 250))
                if not answer_parts:
                    answer_parts.append("answered")

                qa_lines.append(
                    f"- Q: {self._truncate_for_context(question.question_text, 280)}\n"
                    f"  A: {'; '.join(answer_parts)}"
                )
            objective_sections.append("Clarifications from Q&A:\n" + "\n".join(qa_lines))

        return "\n\n".join(section for section in objective_sections if section.strip())

    def _build_mode_plan(self, mode: str, objective: str) -> List[str]:
        if mode == SessionMode.ARCHITECT.value:
            return [
                "Run MSWEA architect mode inside sandbox against the existing GitHub issue.",
                f"Objective: {objective}",
                "Append repo-grounded handoff context and stream sandbox events.",
            ]
        if mode == SessionMode.TESTER.value:
            return [
                "Run MSWEA tester mode with the architect issue number.",
                "Stream sandbox stdout/stderr/exit events to unified websocket clients.",
            ]
        if mode == SessionMode.CODER.value:
            return [
                "Run MSWEA coder mode with issue number and tester branch.",
                "Parse PR metadata and export sandbox artifacts before termination.",
            ]
        if mode == BROWSER_CHECK_MODE:
            return [
                "Run MSWEA browser-check mode inside the existing sandbox workspace.",
                "Start the frontend, inspect it with Playwright Chromium, and capture a screenshot.",
                "Persist the visual report and screenshot artifact without terminating the sandbox.",
            ]
        return [
            "Run MSWEA coder mode with issue number and tester branch.",
            "Parse PR metadata and export sandbox artifacts before termination.",
        ]

    def _create_execution_row(
        self,
        db: Session,
        *,
        session: ChatSession,
        mode: str,
        objective: str,
        pipeline_execution_id: str,
    ) -> AgentExecution:
        execution = AgentExecution(
            id=f"exec_{uuid.uuid4().hex[:24]}",
            session_id=session.id,
            mode=mode,
            status=SessionModeStatus.RUNNING.value,
            execution_plan=self._build_mode_plan(mode, objective),
            execution_metadata={
                "objective": objective,
                "pipeline_execution_id": pipeline_execution_id,
            },
            started_at=utc_now(),
        )
        db.add(execution)
        db.flush()
        return execution

    def _set_mode_state(self, session: ChatSession, *, mode: str, mode_status: str) -> None:
        session.current_mode = mode
        session.mode_status = mode_status
        session.mode_updated_at = utc_now()

    def _raise_if_cancel_requested(self, session: ChatSession) -> None:
        if bool(self._get_active_execution(session).get("cancel_requested")):
            raise asyncio.CancelledError()

    @staticmethod
    def _to_int(value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _merge_mode_metadata(session: ChatSession, updates: Dict[str, Any]) -> None:
        metadata = session.mode_metadata or {}
        metadata.update(updates)
        session.mode_metadata = metadata

    @staticmethod
    def _record_mode_contract(session: ChatSession, mode: str, result: Dict[str, Any]) -> None:
        metadata = dict(session.mode_metadata or {})
        workflow_contracts = metadata.get("workflow_contracts")
        if not isinstance(workflow_contracts, dict):
            workflow_contracts = {}

        compact_keys = {
            "mode",
            "contract_version",
            "issue_number",
            "issue_url",
            "context_file",
            "questions",
            "ready_for_tester",
            "test_branch",
            "tests_changed",
            "expected_failures",
            "pr_url",
            "pr_number",
            "tests_run",
            "changed_files",
            "config_path",
            "exit_code",
            "duration_ms",
        }
        workflow_contracts["contract_version"] = CONTRACT_VERSION
        workflow_contracts[mode] = {
            key: value
            for key, value in result.items()
            if key in compact_keys and value is not None
        }
        metadata["workflow_contracts"] = workflow_contracts
        session.mode_metadata = metadata

    async def _pause_for_architect_questions(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        user_id: int,
        objective: str,
        result: Dict[str, Any],
    ) -> Dict[str, Any]:
        question_ids: List[str] = []
        for question_payload in result.get("questions") or []:
            if not isinstance(question_payload, dict):
                continue
            prompt = str(question_payload.get("prompt") or "").strip()
            if not prompt:
                continue
            options = [
                {"id": str(option.get("id")), "label": str(option.get("label"))}
                for option in (question_payload.get("options") or [])
                if isinstance(option, dict) and option.get("id") and option.get("label")
            ]
            question = UserQuestion(
                question_id=f"q_{uuid.uuid4().hex[:10]}",
                session_id=session.id,
                user_id=user_id,
                mode=SessionMode.ARCHITECT.value,
                question_text=prompt,
                options=options,
                multi_select=bool(question_payload.get("multi_select")),
                status=UserQuestionStatus.PENDING.value,
                question_metadata={
                    "origin": "mswea_architect_contract",
                    "mode_execution_id": execution.id,
                    "contract_version": CONTRACT_VERSION,
                },
            )
            db.add(question)
            db.flush()
            question_ids.append(question.question_id)

            await self.ws_hub.send_to_session(
                session.session_id,
                WSMessageType.AGENT_QUESTION,
                {
                    "question_id": question.question_id,
                    "question_text": question.question_text,
                    "multi_select": bool(question.multi_select),
                    "options": options,
                },
            )

        if not question_ids:
            raise RuntimeError("Architect mode requested user input but produced no valid questions")

        metadata = dict(session.mode_metadata or {})
        pending_ids = [
            str(item)
            for item in (metadata.get("pending_question_ids") or [])
            if str(item).strip()
        ]
        pending_ids.extend(question_id for question_id in question_ids if question_id not in pending_ids)
        metadata["pending_question_ids"] = pending_ids
        metadata["pending_resume_objective"] = objective
        metadata["last_question_id"] = question_ids[-1]
        metadata["architect_waiting_contract_execution_id"] = execution.id
        session.mode_metadata = metadata
        session.mode_status = SessionModeStatus.WAITING_FOR_INPUT.value
        session.mode_updated_at = utc_now()
        session.last_activity = utc_now()

        paused_result = dict(result)
        paused_result.update(
            {
                "waiting_for_input": True,
                "question_ids": question_ids,
                "detail": "Architect mode needs user input before Tester mode.",
            }
        )
        return paused_result

    @staticmethod
    def _infer_issue_url(session: ChatSession, issue_number: int) -> Optional[str]:
        if not session.repo_owner or not session.repo_name:
            return None
        return f"https://github.com/{session.repo_owner}/{session.repo_name}/issues/{issue_number}"

    @staticmethod
    def _infer_pr_url(session: ChatSession, pr_number: int) -> Optional[str]:
        if not session.repo_owner or not session.repo_name:
            return None
        return f"https://github.com/{session.repo_owner}/{session.repo_name}/pull/{pr_number}"

    def parse_mswea_output(self, output_text: str) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {}

        issue_match = ISSUE_URL_PATTERN.search(output_text)
        if issue_match:
            parsed["issue_url"] = issue_match.group(0)
            parsed["issue_number"] = self._to_int(issue_match.group(1))

        pr_match = PR_URL_PATTERN.search(output_text)
        if pr_match:
            parsed["pr_url"] = pr_match.group(0)
            parsed["pr_number"] = self._to_int(pr_match.group(1))

        issue_number_match = ISSUE_NUMBER_PATTERN.search(output_text)
        if issue_number_match:
            parsed["issue_number"] = self._to_int(issue_number_match.group(1))

        pr_number_match = PR_NUMBER_PATTERN.search(output_text)
        if pr_number_match:
            parsed["pr_number"] = self._to_int(pr_number_match.group(1))

        branch_match = TEST_BRANCH_PATTERN.search(output_text)
        if branch_match:
            parsed["test_branch"] = branch_match.group(1).strip().strip("'\"")

        for line in reversed(output_text.splitlines()):
            raw = line.strip()
            if not raw or not raw.startswith("{"):
                continue
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue

            if "issue_url" in payload and isinstance(payload["issue_url"], str):
                parsed["issue_url"] = payload["issue_url"].strip()
            if "issue_number" in payload:
                parsed["issue_number"] = self._to_int(payload.get("issue_number"))
            if "pr_url" in payload and isinstance(payload["pr_url"], str):
                parsed["pr_url"] = payload["pr_url"].strip()
            if "pr_number" in payload:
                parsed["pr_number"] = self._to_int(payload.get("pr_number"))
            if "test_branch" in payload and isinstance(payload["test_branch"], str):
                parsed["test_branch"] = payload["test_branch"].strip()
            break

        return parsed

    async def _ensure_runtime_ready(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
    ) -> None:
        runtime = self.lifecycle._get_latest_runtime(db, session_id=session.id)
        sandbox = (
            self.lifecycle.get_sandbox_or_404(db, runtime.sandbox_id)
            if runtime and runtime.sandbox_id
            else None
        )
        tunnel_url = sandbox.tunnel_url if sandbox and sandbox.tunnel_url else None

        async def provision_runtime() -> str:
            repo_owner = session.repo_owner or self._repo_owner_from_url(session.repo_url)
            repo_name = session.repo_name or self._repo_name_from_url(session.repo_url)
            if not repo_owner or not repo_name:
                raise RuntimeError("Session repository information is incomplete for sandbox provisioning")

            github_token = self._get_user_github_token(db, user_id)
            envelope = await self.lifecycle.create_runtime_for_session(
                db,
                session=session,
                user_id=user_id,
                org=None,
                repo_owner=repo_owner,
                repo_name=repo_name,
                environment=session.repo_branch or "main",
                repo_branch=session.repo_branch or "main",
                repo_url=session.repo_url or f"https://github.com/{repo_owner}/{repo_name}.git",
                github_token=github_token,
                env_inputs={
                    "SESSION_PUBLIC_ID": session.session_id,
                    "WORKSPACE_PATH": session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH,
                },
            )
            db.commit()
            return envelope.sandbox.tunnel_url

        if not tunnel_url:
            tunnel_url = await provision_runtime()

        try:
            await wait_for_sandbox_healthcheck(tunnel_url, timeout_seconds=60.0)
        except Exception:
            if not get_realtime_feature_flags().modal_provisioning_enabled or not sandbox:
                raise

            lifecycle_metadata = sandbox.lifecycle_metadata or {}
            lifecycle_metadata.pop("modal_sandbox_id", None)
            sandbox.lifecycle_metadata = lifecycle_metadata
            sandbox.tunnel_url = None
            sandbox.status = "terminated"
            sandbox.terminated_at = utc_now()
            db.commit()

            tunnel_url = await provision_runtime()
            await wait_for_sandbox_healthcheck(tunnel_url, timeout_seconds=60.0)

    @staticmethod
    def _get_user_github_token(db: Session, user_id: int) -> Optional[str]:
        auth_token = (
            db.query(AuthToken)
            .filter(
                AuthToken.user_id == user_id,
                AuthToken.is_active.is_(True),
            )
            .order_by(AuthToken.created_at.desc())
            .first()
        )
        return auth_token.access_token if auth_token else None

    @staticmethod
    def _repo_owner_from_url(repo_url: Optional[str]) -> Optional[str]:
        if not repo_url:
            return None
        parts = [part for part in str(repo_url).rstrip("/").split("/") if part]
        if len(parts) < 2:
            return None
        return parts[-2]

    @staticmethod
    def _repo_name_from_url(repo_url: Optional[str]) -> Optional[str]:
        if not repo_url:
            return None
        last = str(repo_url).rstrip("/").split("/")[-1]
        return last[:-4] if last.endswith(".git") else last

    def _build_mswea_command(
        self,
        *,
        mode: str,
        include_issue_number: bool,
        include_test_branch: bool,
    ) -> str:
        config_path = MSWEA_CONFIG_PATHS[mode]
        execution_dir_expr = f'"$workspace/{SANDBOX_EXECUTION_ROOT}/$pipeline_execution_id/$mode_name"'
        command_lines = [
            "set -euo pipefail",
            f'workspace="${{WORKSPACE_PATH:-{SANDBOX_WORKSPACE_PATH}}}"',
            'HOME="${HOME:-/root}"',
            'repo_branch="${REPO_BRANCH:-main}"',
            'repo_url="${REPO_URL:-}"',
            'pipeline_execution_id="${PIPELINE_EXECUTION_ID:-manual}"',
            f'mode_name="{mode}"',
            f"execution_dir={execution_dir_expr}",
            'context_file="${YUDAI_CONTEXT_FILE:-$workspace/.yudai/context.md}"',
            'case "$context_file" in /*) ;; *) context_file="$workspace/$context_file" ;; esac',
            'if [ -n "${GITHUB_TOKEN:-}" ]; then',
            '  mkdir -p "$HOME"',
            '  umask 077',
            '  printf "machine github.com\\nlogin x-access-token\\npassword %s\\n" "$GITHUB_TOKEN" > "$HOME/.netrc"',
            'fi',
            'if [ "${repo_url#git@github.com:}" != "$repo_url" ]; then',
            '  repo_url="https://github.com/${repo_url#git@github.com:}"',
            'fi',
            'preserved_context=""',
            'if [ -f "$context_file" ]; then',
            '  preserved_context="$(mktemp "${TMPDIR:-/tmp}/yudai-context.XXXXXX")"',
            '  cp "$context_file" "$preserved_context"',
            'fi',
            'if [ -d "$workspace/.git" ]; then',
            '  cd "$workspace"',
            '  git fetch --all --prune 2>/dev/null || true',
            '  git checkout -f "$repo_branch" 2>/dev/null || true',
            '  git reset --hard "origin/$repo_branch" 2>/dev/null || true',
            '  git clean -fdx 2>/dev/null || true',
            'elif [ -n "$repo_url" ]; then',
            '  mkdir -p "$(dirname "$workspace")"',
            '  git clone --depth 1 -b "$repo_branch" "$repo_url" "$workspace"',
            '  cd "$workspace"',
            'else',
            '  mkdir -p "$workspace"',
            '  cd "$workspace"',
            'fi',
            'mkdir -p "$execution_dir" "$(dirname "$context_file")"',
            'if [ -n "$preserved_context" ] && [ -f "$preserved_context" ]; then',
            '  cp "$preserved_context" "$context_file"',
            'fi',
            'if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then',
            '  git rev-parse HEAD > "$execution_dir/base_commit.txt" 2>/dev/null || true',
            '  git status --porcelain=v1 --untracked-files=all > "$execution_dir/git_status_before.txt" 2>/dev/null || true',
            'fi',
            'export YUDAI_CONTEXT_FILE="$context_file"',
            'if [ ! -f "$context_file" ]; then',
            '  {',
            '    printf "# Yudai Mode Context\\n\\n"',
            '    printf -- "- Pipeline execution: %s\\n" "$pipeline_execution_id"',
            '    printf -- "- Repository: %s\\n" "${repo_url:-unknown}"',
            '    printf -- "- Branch: %s\\n" "$repo_branch"',
            '    printf "\\n"',
            '  } > "$context_file"',
            'fi',
            'printf "%s\\n" "$mode_name" > "$execution_dir/mode.txt"',
            'printf "%s\\n" "$repo_branch" > "$execution_dir/repo_branch.txt"',
            'printf "%s\\n" "${MSWEA_OBJECTIVE:-}" > "$execution_dir/objective.txt"',
            'printf "%s\\n" "$context_file" > "$execution_dir/context_file.txt"',
            '{',
            '  printf "\\n## Mode Input: %s\\n\\n" "$mode_name"',
            '  printf -- "- Pipeline execution: %s\\n" "$pipeline_execution_id"',
            '  printf -- "- Repository branch: %s\\n" "$repo_branch"',
            '  if [ -n "${MSWEA_ISSUE_NUMBER:-}" ]; then printf -- "- GitHub issue number: #%s\\n" "$MSWEA_ISSUE_NUMBER"; fi',
            '  if [ -n "${MSWEA_ISSUE_URL:-}" ]; then printf -- "- GitHub issue URL: %s\\n" "$MSWEA_ISSUE_URL"; fi',
            '  if [ -n "${MSWEA_TEST_BRANCH:-}" ]; then printf -- "- Tester branch: %s\\n" "$MSWEA_TEST_BRANCH"; fi',
            '  printf "\\n"',
            '} >> "$context_file"',
            f'config_path="{config_path}"',
            'if ! command -v mini >/dev/null 2>&1; then',
            '  echo "mini-swe-agent CLI not found: expected executable named mini" >&2',
            '  exit 127',
            'fi',
            'python_bin="${PYTHON:-}"',
            'if [ -z "$python_bin" ]; then',
            '  if command -v python3 >/dev/null 2>&1; then',
            '    python_bin="python3"',
            '  elif command -v python >/dev/null 2>&1; then',
            '    python_bin="python"',
            '  else',
            '    echo "python interpreter not found: expected python3 or python" >&2',
            '    exit 127',
            '  fi',
            'fi',
            f'model_name="${{MSWEA_MODEL_NAME:-{get_model_config().agent_model_name}}}"',
            'task_text="${MSWEA_OBJECTIVE:-}"',
            'task_text="$(printf "%s\\n\\nShared context file: %s" "$task_text" "$context_file")"',
            'if [ -n "${MSWEA_ISSUE_NUMBER:-}" ]; then',
            '  task_text="$(printf "%s\\n\\nGitHub issue number: #%s" "$task_text" "$MSWEA_ISSUE_NUMBER")"',
            'fi',
            'if [ -n "${MSWEA_ISSUE_URL:-}" ]; then',
            '  task_text="$(printf "%s\\nGitHub issue URL: %s" "$task_text" "$MSWEA_ISSUE_URL")"',
            'fi',
            'if [ -n "${MSWEA_TEST_BRANCH:-}" ]; then',
            '  task_text="$(printf "%s\\n\\nUse or compare against test branch: %s" "$task_text" "$MSWEA_TEST_BRANCH")"',
            'fi',
            'printf "%s\\n" "$model_name" > "$execution_dir/model.txt"',
            'cmd=(mini -c "$config_path" -y -m "$model_name" -t "$task_text")',
        ]

        command_lines.extend(
            [
                'printf "%q " "${cmd[@]}" > "$execution_dir/command.txt"',
                'if [ "${YUDAI_MSWEA_COMMAND_PROBE:-0}" = "1" ]; then',
                '  export mode_name config_path model_name',
                '  "$python_bin" - "$execution_dir/command_probe.json" "${cmd[@]}" <<\'PY\'',
                'import json',
                'import os',
                'import sys',
                'payload = {',
                '    "mode": os.environ.get("mode_name", ""),',
                '    "workspace": os.environ.get("WORKSPACE_PATH", ""),',
                '    "repo_url": os.environ.get("REPO_URL", ""),',
                '    "repo_branch": os.environ.get("REPO_BRANCH", "main"),',
                '    "config_path": os.environ.get("config_path", ""),',
                '    "model_name": os.environ.get("model_name", ""),',
                '    "objective": os.environ.get("MSWEA_OBJECTIVE", ""),',
                '    "issue_number": os.environ.get("MSWEA_ISSUE_NUMBER", ""),',
                '    "issue_url": os.environ.get("MSWEA_ISSUE_URL", ""),',
                '    "test_branch": os.environ.get("MSWEA_TEST_BRANCH", ""),',
                '    "context_file": os.environ.get("YUDAI_CONTEXT_FILE", ""),',
                '    "argv": sys.argv[2:],',
                '}',
                'path = sys.argv[1]',
                'with open(path, "w", encoding="utf-8") as fh:',
                '    json.dump(payload, fh, ensure_ascii=True, indent=2)',
                '    fh.write("\\n")',
                'print(json.dumps(payload, ensure_ascii=True))',
                'PY',
                '  exit 0',
                'fi',
                f"printf '[{mode}] running:'",
                'printf " %q" "${cmd[@]}"',
                'printf "\\n"',
                'set +e',
                '"${cmd[@]}" > >(tee "$execution_dir/stdout.log") 2> >(tee "$execution_dir/stderr.log" >&2)',
                'exit_code=$?',
                'set -e',
                'printf "%s" "$exit_code" > "$execution_dir/exit_code.txt"',
                'if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then',
                '  "$python_bin" - "$execution_dir/changed_files.json" "$execution_dir/base_commit.txt" <<\'PY\'',
                'import json',
                'import subprocess',
                'import sys',
                'from pathlib import Path',
                '',
                'out_path = Path(sys.argv[1])',
                'base_path = Path(sys.argv[2])',
                '',
                'def run(args):',
                '    completed = subprocess.run(args, capture_output=True, text=True)',
                '    return completed.stdout if completed.returncode == 0 else ""',
                '',
                'files = []',
                'base_commit = base_path.read_text(encoding="utf-8").strip() if base_path.exists() else ""',
                'head_commit = run(["git", "rev-parse", "HEAD"]).strip()',
                'if base_commit and head_commit:',
                '    for line in run(["git", "diff", "--name-only", base_commit, head_commit]).splitlines():',
                '        if line.strip():',
                '            files.append(line.strip())',
                '',
                'for line in run(["git", "status", "--porcelain=v1", "--untracked-files=all"]).splitlines():',
                '    if len(line) < 4:',
                '        continue',
                '    path = line[3:].strip()',
                '    if " -> " in path:',
                '        old_path, new_path = path.split(" -> ", 1)',
                '        files.extend([old_path.strip(), new_path.strip()])',
                '    elif path:',
                '        files.append(path)',
                '',
                'deduped = []',
                'seen = set()',
                'for path in files:',
                '    normalized = path.replace("\\\\", "/")',
                '    while normalized.startswith("./"):',
                '        normalized = normalized[2:]',
                '    normalized = normalized.lstrip("/")',
                '    if normalized and normalized not in seen:',
                '        seen.add(normalized)',
                '        deduped.append(normalized)',
                'out_path.write_text(json.dumps(deduped, ensure_ascii=True) + "\\n", encoding="utf-8")',
                'PY',
                f'  printf "{CHANGED_FILES_START}\\n"',
                '  cat "$execution_dir/changed_files.json"',
                f'  printf "\\n{CHANGED_FILES_END}\\n"',
                'fi',
                'if [ "$exit_code" -ne 0 ]; then',
                '  exit "$exit_code"',
                'fi',
            ]
        )

        return "\n".join(command_lines)

    def _build_browser_check_command(self) -> str:
        config_path = MSWEA_CONFIG_PATHS[BROWSER_CHECK_MODE]
        execution_dir_expr = f'"$workspace/{SANDBOX_EXECUTION_ROOT}/$pipeline_execution_id/{BROWSER_CHECK_MODE}"'
        command_lines = [
            "set -euo pipefail",
            f'workspace="${{WORKSPACE_PATH:-{SANDBOX_WORKSPACE_PATH}}}"',
            'HOME="${HOME:-/root}"',
            'repo_branch="${REPO_BRANCH:-main}"',
            'repo_url="${REPO_URL:-}"',
            'pipeline_execution_id="${PIPELINE_EXECUTION_ID:-manual}"',
            f'mode_name="{BROWSER_CHECK_MODE}"',
            f"execution_dir={execution_dir_expr}",
            'screenshot_path="${BROWSER_CHECK_SCREENSHOT_PATH:-$execution_dir/screenshot.png}"',
            'report_path="${BROWSER_CHECK_REPORT_PATH:-$execution_dir/visual_report.md}"',
            'summary_path="${BROWSER_CHECK_SUMMARY_PATH:-$execution_dir/summary.json}"',
            'if [ -n "${GITHUB_TOKEN:-}" ]; then',
            '  mkdir -p "$HOME"',
            '  umask 077',
            '  printf "machine github.com\\nlogin x-access-token\\npassword %s\\n" "$GITHUB_TOKEN" > "$HOME/.netrc"',
            'fi',
            'if [ "${repo_url#git@github.com:}" != "$repo_url" ]; then',
            '  repo_url="https://github.com/${repo_url#git@github.com:}"',
            'fi',
            'if [ -d "$workspace/.git" ]; then',
            '  cd "$workspace"',
            'elif [ -e "$workspace" ] && [ "$(find "$workspace" -mindepth 1 -maxdepth 1 2>/dev/null | head -n 1)" ]; then',
            '  cd "$workspace"',
            'elif [ ! -e "$workspace" ] && [ -n "$repo_url" ]; then',
            '  mkdir -p "$(dirname "$workspace")"',
            '  git clone --depth 1 -b "$repo_branch" "$repo_url" "$workspace"',
            '  cd "$workspace"',
            'else',
            '  mkdir -p "$workspace"',
            '  cd "$workspace"',
            'fi',
            'mkdir -p "$execution_dir" "$(dirname "$screenshot_path")" "$(dirname "$report_path")" "$(dirname "$summary_path")"',
            'export WORKSPACE_PATH="$workspace"',
            'export BROWSER_CHECK_SCREENSHOT_PATH="$screenshot_path"',
            'export BROWSER_CHECK_REPORT_PATH="$report_path"',
            'export BROWSER_CHECK_SUMMARY_PATH="$summary_path"',
            'printf "%s\\n" "$mode_name" > "$execution_dir/mode.txt"',
            'printf "%s\\n" "$repo_branch" > "$execution_dir/repo_branch.txt"',
            'printf "%s\\n" "${BROWSER_CHECK_OBJECTIVE:-}" > "$execution_dir/objective.txt"',
            'if [ -d .git ]; then',
            '  git status --porcelain=v1 > "$execution_dir/before_status.txt" 2>/dev/null || true',
            'else',
            '  : > "$execution_dir/before_status.txt"',
            'fi',
            f'config_path="{config_path}"',
            'if ! command -v mini >/dev/null 2>&1; then',
            '  echo "mini-swe-agent CLI not found: expected executable named mini" >&2',
            '  exit 127',
            'fi',
            'python_bin="${PYTHON:-}"',
            'if [ -z "$python_bin" ]; then',
            '  if command -v python3 >/dev/null 2>&1; then',
            '    python_bin="python3"',
            '  elif command -v python >/dev/null 2>&1; then',
            '    python_bin="python"',
            '  else',
            '    echo "python interpreter not found: expected python3 or python" >&2',
            '    exit 127',
            '  fi',
            'fi',
            f'model_name="${{MSWEA_MODEL_NAME:-{get_model_config().agent_model_name}}}"',
            'task_text="${BROWSER_CHECK_OBJECTIVE:-}"',
            'task_text="$(printf "%s\\n\\nWorkspace: %s" "$task_text" "$workspace")"',
            'task_text="$(printf "%s\\nScreenshot path: %s" "$task_text" "$screenshot_path")"',
            'task_text="$(printf "%s\\nReport path: %s" "$task_text" "$report_path")"',
            'task_text="$(printf "%s\\nSummary JSON path: %s" "$task_text" "$summary_path")"',
            'task_text="$(printf "%s\\n\\nDo not edit implementation files. You may write generated artifacts and helpers under .yudai/." "$task_text")"',
            'cmd=(mini -c "$config_path" -y -m "$model_name" -t "$task_text")',
            'printf "%q " "${cmd[@]}" > "$execution_dir/command.txt"',
            'if [ "${YUDAI_BROWSER_CHECK_COMMAND_PROBE:-0}" = "1" ]; then',
            '  export mode_name config_path model_name',
            '  "$python_bin" - "$execution_dir/command_probe.json" "${cmd[@]}" <<\'PY\'',
            'import json',
            'import os',
            'import sys',
            'payload = {',
            '    "mode": os.environ.get("mode_name", ""),',
            '    "workspace": os.environ.get("WORKSPACE_PATH", ""),',
            '    "repo_url": os.environ.get("REPO_URL", ""),',
            '    "repo_branch": os.environ.get("REPO_BRANCH", "main"),',
            '    "config_path": os.environ.get("config_path", ""),',
            '    "model_name": os.environ.get("model_name", ""),',
            '    "objective": os.environ.get("BROWSER_CHECK_OBJECTIVE", ""),',
            '    "screenshot_path": os.environ.get("BROWSER_CHECK_SCREENSHOT_PATH", ""),',
            '    "report_path": os.environ.get("BROWSER_CHECK_REPORT_PATH", ""),',
            '    "summary_path": os.environ.get("BROWSER_CHECK_SUMMARY_PATH", ""),',
            '    "argv": sys.argv[2:],',
            '}',
            'path = sys.argv[1]',
            'with open(path, "w", encoding="utf-8") as fh:',
            '    json.dump(payload, fh, ensure_ascii=True, indent=2)',
            '    fh.write("\\n")',
            'print(json.dumps(payload, ensure_ascii=True))',
            'PY',
            '  exit 0',
            'fi',
            f"printf '[{BROWSER_CHECK_MODE}] running:'",
            'printf " %q" "${cmd[@]}"',
            'printf "\\n"',
            'set +e',
            '"${cmd[@]}" > >(tee "$execution_dir/stdout.log") 2> >(tee "$execution_dir/stderr.log" >&2)',
            'exit_code=$?',
            'set -e',
            'printf "%s" "$exit_code" > "$execution_dir/exit_code.txt"',
            'if [ "$exit_code" -ne 0 ]; then',
            '  exit "$exit_code"',
            'fi',
            'if [ -d .git ]; then',
            '  git status --porcelain=v1 > "$execution_dir/after_status.txt" 2>/dev/null || true',
            'else',
            '  : > "$execution_dir/after_status.txt"',
            'fi',
            '"$python_bin" - <<\'PY\'',
            'import json',
            'import os',
            'import pathlib',
            'import re',
            'import struct',
            'import subprocess',
            'import sys',
            'import zlib',
            '',
            'workspace = pathlib.Path(os.environ["WORKSPACE_PATH"]).resolve()',
            'screenshot_path = pathlib.Path(os.environ["BROWSER_CHECK_SCREENSHOT_PATH"])',
            'report_path = pathlib.Path(os.environ["BROWSER_CHECK_REPORT_PATH"])',
            'summary_path = pathlib.Path(os.environ["BROWSER_CHECK_SUMMARY_PATH"])',
            'execution_dir = summary_path.parent',
            'critical = []',
            '',
            'def load_status_paths(path):',
            '    if not path.exists():',
            '        return []',
            '    paths = []',
            '    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():',
            '        if not line.strip():',
            '            continue',
            '        raw_path = line[3:] if len(line) > 3 else line',
            '        if " -> " in raw_path:',
            '            raw_path = raw_path.split(" -> ", 1)[1]',
            '        paths.append(raw_path.strip())',
            '    return paths',
            '',
            'def allowed_setup_path(path):',
            '    normalized = path.replace("\\\\", "/")',
            '    name = pathlib.PurePosixPath(normalized).name',
            '    if normalized.startswith(".yudai/"):',
            '        return True',
            '    if name in {',
            '        "package.json", "package-lock.json", "npm-shrinkwrap.json",',
            '        "pnpm-lock.yaml", "yarn.lock", "bun.lock", "bun.lockb",',
            '        ".npmrc", ".yarnrc", ".yarnrc.yml",',
            '    }:',
            '        return True',
            '    return False',
            '',
            'def png_unique_pixel_count(path):',
            '    data = path.read_bytes()',
            '    if len(data) < 33 or data[:8] != b"\\x89PNG\\r\\n\\x1a\\n":',
            '        raise ValueError("not a PNG file")',
            '    pos = 8',
            '    width = height = bit_depth = color_type = None',
            '    idat = bytearray()',
            '    palette = None',
            '    while pos + 8 <= len(data):',
            '        length = struct.unpack(">I", data[pos:pos+4])[0]',
            '        chunk_type = data[pos+4:pos+8]',
            '        chunk = data[pos+8:pos+8+length]',
            '        pos += 12 + length',
            '        if chunk_type == b"IHDR":',
            '            width, height, bit_depth, color_type, _, _, _ = struct.unpack(">IIBBBBB", chunk)',
            '        elif chunk_type == b"PLTE":',
            '            palette = chunk',
            '        elif chunk_type == b"IDAT":',
            '            idat.extend(chunk)',
            '        elif chunk_type == b"IEND":',
            '            break',
            '    if not width or not height or not idat:',
            '        raise ValueError("missing PNG image data")',
            '    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}',
            '    channels = channels_by_type.get(color_type)',
            '    if channels is None or bit_depth != 8:',
            '        raw = zlib.decompress(bytes(idat))',
            '        return len(set(raw))',
            '    bpp = channels',
            '    row_len = width * channels',
            '    raw = zlib.decompress(bytes(idat))',
            '    rows = []',
            '    prev = bytearray(row_len)',
            '    offset = 0',
            '    for _ in range(height):',
            '        filter_type = raw[offset]',
            '        offset += 1',
            '        row = bytearray(raw[offset:offset + row_len])',
            '        offset += row_len',
            '        for i in range(row_len):',
            '            left = row[i - bpp] if i >= bpp else 0',
            '            up = prev[i]',
            '            up_left = prev[i - bpp] if i >= bpp else 0',
            '            if filter_type == 1:',
            '                row[i] = (row[i] + left) & 0xff',
            '            elif filter_type == 2:',
            '                row[i] = (row[i] + up) & 0xff',
            '            elif filter_type == 3:',
            '                row[i] = (row[i] + ((left + up) // 2)) & 0xff',
            '            elif filter_type == 4:',
            '                p = left + up - up_left',
            '                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)',
            '                predictor = left if pa <= pb and pa <= pc else up if pb <= pc else up_left',
            '                row[i] = (row[i] + predictor) & 0xff',
            '            elif filter_type != 0:',
            '                raise ValueError(f"unsupported PNG filter {filter_type}")',
            '        rows.append(bytes(row))',
            '        prev = row',
            '    pixels = set()',
            '    sample_stride = max(1, (width * height) // 250000)',
            '    index = 0',
            '    for row in rows:',
            '        for i in range(0, len(row), bpp):',
            '            if index % sample_stride == 0:',
            '                pixels.add(row[i:i+bpp])',
            '                if len(pixels) > 1:',
            '                    return len(pixels)',
            '            index += 1',
            '    return len(pixels)',
            '',
            'if not report_path.is_file() or report_path.stat().st_size == 0:',
            '    critical.append("visual report is missing or empty")',
            'if not summary_path.is_file() or summary_path.stat().st_size == 0:',
            '    critical.append("summary JSON is missing or empty")',
            'if not screenshot_path.is_file() or screenshot_path.stat().st_size == 0:',
            '    critical.append("screenshot is missing or empty")',
            '',
            'summary = {}',
            'if summary_path.is_file() and summary_path.stat().st_size > 0:',
            '    try:',
            '        summary = json.loads(summary_path.read_text(encoding="utf-8"))',
            '        if not isinstance(summary, dict):',
            '            critical.append("summary JSON is not an object")',
            '            summary = {}',
            '    except Exception as exc:',
            '        critical.append(f"summary JSON is invalid: {exc}")',
            '',
            'if screenshot_path.is_file() and screenshot_path.stat().st_size > 0:',
            '    try:',
            '        if png_unique_pixel_count(screenshot_path) < 2:',
            '            critical.append("screenshot appears visually blank")',
            '    except Exception as exc:',
            '        critical.append(f"screenshot is corrupt or unreadable: {exc}")',
            '',
            'before_paths = load_status_paths(execution_dir / "before_status.txt")',
            'after_paths = load_status_paths(execution_dir / "after_status.txt")',
            'newly_changed = sorted(set(after_paths) - set(before_paths))',
            'disallowed = [path for path in newly_changed if not allowed_setup_path(path)]',
            'if disallowed:',
            '    critical.append("browser check changed implementation files: " + ", ".join(disallowed[:20]))',
            '',
            'existing_critical = summary.get("critical_failures")',
            'if isinstance(existing_critical, list):',
            '    critical.extend(str(item) for item in existing_critical if str(item).strip())',
            'elif existing_critical:',
            '    critical.append(str(existing_critical))',
            '',
            'changed_file_summary = {',
            '    "before": before_paths,',
            '    "after": after_paths,',
            '    "newly_changed": newly_changed,',
            '    "disallowed": disallowed,',
            '}',
            'summary.update({',
            '    "mode": "browser_check",',
            '    "status": "failed" if critical else summary.get("status", "complete"),',
            '    "screenshot_path": str(screenshot_path),',
            '    "report_path": str(report_path),',
            '    "changed_file_summary": changed_file_summary,',
            '    "critical_failures": critical,',
            '})',
            'summary.setdefault("console_warning_count", 0)',
            'summary.setdefault("failed_request_count", 0)',
            'summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + "\\n", encoding="utf-8")',
            'if critical:',
            '    print(json.dumps(summary, ensure_ascii=True))',
            '    sys.exit(4)',
            'print(json.dumps(summary, ensure_ascii=True))',
            'PY',
            f'printf "{BROWSER_CHECK_SUMMARY_START}\\n"',
            'cat "$summary_path"',
            f'printf "\\n{BROWSER_CHECK_SUMMARY_END}\\n"',
            f'printf "{BROWSER_CHECK_REPORT_START}\\n"',
            'cat "$report_path"',
            f'printf "\\n{BROWSER_CHECK_REPORT_END}\\n"',
        ]
        return "\n".join(command_lines)

    def _build_summary_write_command(
        self,
        *,
        mode: str,
        pipeline_execution_id: str,
        summary: Dict[str, Any],
    ) -> str:
        summary_json = json.dumps(summary, ensure_ascii=True)
        return "\n".join(
            [
                "set -euo pipefail",
                'python_bin="${PYTHON:-}"',
                'if [ -z "$python_bin" ]; then',
                '  if command -v python3 >/dev/null 2>&1; then',
                '    python_bin="python3"',
                '  elif command -v python >/dev/null 2>&1; then',
                '    python_bin="python"',
                '  else',
                '    echo "python interpreter not found: expected python3 or python" >&2',
                '    exit 127',
                '  fi',
                'fi',
                '"$python_bin" - <<\'PY\'',
                "import json",
                "import os",
                "from pathlib import Path",
                f"summary = json.loads({json.dumps(summary_json, ensure_ascii=True)})",
                f"workspace = Path(os.environ.get('WORKSPACE_PATH', {json.dumps(SANDBOX_WORKSPACE_PATH)}))",
                f"summary_path = workspace / {json.dumps(SANDBOX_EXECUTION_ROOT)} / {json.dumps(pipeline_execution_id)} / {json.dumps(mode)} / 'summary.json'",
                "summary_path.parent.mkdir(parents=True, exist_ok=True)",
                "summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2) + '\\n', encoding='utf-8')",
                "print(summary_path)",
                "PY",
            ]
        )

    async def _write_mode_summary(
        self,
        db: Session,
        *,
        session: ChatSession,
        mode: str,
        pipeline_execution_id: str,
        summary: Dict[str, Any],
    ) -> None:
        result = await self.broker.run_command(
            db,
            session=session,
            command=self._build_summary_write_command(
                mode=mode,
                pipeline_execution_id=pipeline_execution_id,
                summary=summary,
            ),
            cwd=session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH,
            timeout_seconds=get_agent_config().summary_write_timeout_seconds,
            env={"WORKSPACE_PATH": session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH},
        )
        if result.get("exit_code", 1) != 0:
            raise RuntimeError(f"Failed to write sandbox summary for {mode} mode")

    @staticmethod
    def _extract_between_markers(text: str, start: str, end: str) -> Optional[str]:
        start_index = text.rfind(start)
        if start_index < 0:
            return None
        start_index += len(start)
        end_index = text.find(end, start_index)
        if end_index < 0:
            return None
        return text[start_index:end_index].strip()

    def _parse_browser_check_output(self, output_text: str) -> Dict[str, Any]:
        parsed: Dict[str, Any] = {}

        summary_text = self._extract_between_markers(
            output_text,
            BROWSER_CHECK_SUMMARY_START,
            BROWSER_CHECK_SUMMARY_END,
        )
        if summary_text:
            try:
                summary = json.loads(summary_text)
                if isinstance(summary, dict):
                    parsed["summary"] = summary
            except Exception as exc:
                parsed["summary_parse_error"] = str(exc)

        report_text = self._extract_between_markers(
            output_text,
            BROWSER_CHECK_REPORT_START,
            BROWSER_CHECK_REPORT_END,
        )
        if report_text:
            parsed["visual_report"] = report_text

        if "summary" not in parsed:
            for line in reversed(output_text.splitlines()):
                raw = line.strip()
                if not raw.startswith("{"):
                    continue
                try:
                    payload = json.loads(raw)
                except Exception:
                    continue
                if isinstance(payload, dict) and payload.get("mode") == BROWSER_CHECK_MODE:
                    parsed["summary"] = payload
                    break

        summary = parsed.get("summary")
        if isinstance(summary, dict):
            if isinstance(summary.get("screenshot_path"), str):
                parsed["screenshot_path"] = summary["screenshot_path"]
            if isinstance(summary.get("report_path"), str):
                parsed["report_path"] = summary["report_path"]
            parsed["console_warning_count"] = self._to_int(summary.get("console_warning_count")) or 0
            parsed["failed_request_count"] = self._to_int(summary.get("failed_request_count")) or 0
            parsed["changed_file_summary"] = summary.get("changed_file_summary")

        return parsed

    async def _execute_browser_check(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        objective: str,
    ) -> Dict[str, Any]:
        async def _relay_event(event: Dict[str, Any]) -> None:
            if event.get("type") != WSMessageType.SANDBOX_STREAM.value:
                return
            payload = event.get("payload", {}) or {}
            payload["mode"] = BROWSER_CHECK_MODE
            payload["execution_id"] = execution.id
            await self.ws_hub.send_to_session(
                session.session_id,
                WSMessageType.SANDBOX_STREAM,
                payload,
            )

        workspace = session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH
        execution_root = f"{workspace}/{SANDBOX_EXECUTION_ROOT}/{execution.id}/{BROWSER_CHECK_MODE}"
        env: Dict[str, str] = {
            "MSWEA_CONFIG_ROOT": MSWEA_CONFIG_ROOT,
            "PIPELINE_EXECUTION_ID": execution.id,
            "WORKSPACE_PATH": workspace,
            "REPO_BRANCH": session.repo_branch or "main",
            "BROWSER_CHECK_OBJECTIVE": objective,
            "BROWSER_CHECK_SCREENSHOT_PATH": f"{execution_root}/screenshot.png",
            "BROWSER_CHECK_REPORT_PATH": f"{execution_root}/visual_report.md",
            "BROWSER_CHECK_SUMMARY_PATH": f"{execution_root}/summary.json",
        }
        repo_url = session.repo_url
        if not repo_url and session.repo_owner and session.repo_name:
            repo_url = f"https://github.com/{session.repo_owner}/{session.repo_name}.git"
        if repo_url:
            env["REPO_URL"] = repo_url

        github_token = self._get_user_github_token(db, session.user_id)
        if github_token:
            env["GITHUB_TOKEN"] = github_token

        env.update(dict(get_sandbox_config().env_passthrough_values))

        result = await self.broker.run_command(
            db,
            session=session,
            command=self._build_browser_check_command(),
            cwd=workspace,
            env=env,
            timeout_seconds=get_sandbox_config().command_timeout_seconds,
            on_event=_relay_event,
        )
        output_text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}"
        parsed = self._parse_browser_check_output(output_text)
        result.update(parsed)
        result["config_path"] = MSWEA_CONFIG_PATHS[BROWSER_CHECK_MODE]
        result["execution_dir"] = execution_root
        return result

    async def _export_browser_check_artifact(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution_id: str,
        result: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        runtime = self.lifecycle._get_latest_runtime(db, session_id=session.id)
        if not runtime or not runtime.sandbox_id:
            return None

        sandbox = self.lifecycle.get_sandbox_or_404(db, runtime.sandbox_id)
        if sandbox.status == SandboxStatus.TERMINATED.value or not sandbox.tunnel_url:
            return None

        source_path = f"{SANDBOX_EXECUTION_ROOT}/{execution_id}/{BROWSER_CHECK_MODE}"
        workflow_name = f"{execution_id}-{BROWSER_CHECK_MODE}"
        runtime_summary = {
            "status": SessionModeStatus.COMPLETE.value,
            "execution_id": execution_id,
            "mode": BROWSER_CHECK_MODE,
            "screenshot_path": result.get("screenshot_path"),
            "report_path": result.get("report_path"),
            "console_warning_count": result.get("console_warning_count"),
            "failed_request_count": result.get("failed_request_count"),
        }
        export_info = await self.lifecycle.cache_store.download_and_export_bundle(
            tunnel_url=sandbox.tunnel_url,
            session_public_id=session.session_id,
            runtime_id=runtime.runtime_id,
            sandbox_id=sandbox.id,
            identity_key=sandbox.identity_key,
            workflow_name=workflow_name,
            archive_name="browser-check.tar.gz",
            source_paths=[source_path],
            runtime_summary=runtime_summary,
            cwd=session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH,
            env={"WORKSPACE_PATH": session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH},
            object_store={
                "provider": "s3",
                "key": self._browser_check_artifact_key(
                    session=session,
                    sandbox=sandbox,
                    execution_id=execution_id,
                ),
                "etag": None,
            },
        )

        artifact = SessionArtifact(
            session_id=session.id,
            runtime_id=runtime.id,
            artifact_key=self._browser_check_artifact_key(
                session=session,
                sandbox=sandbox,
                execution_id=execution_id,
            ),
            artifact_type="browser_check",
            cache_manifest_path=export_info["metadata"]["cache_manifest_path"],
            bundle_path=export_info["bundle_path"],
            checksum_sha256=export_info["bundle_sha256"],
            object_etag=None,
            byte_size=export_info["bundle_size"],
            artifact_metadata=export_info["metadata"],
            exported_at=utc_now(),
        )
        db.add(artifact)
        db.flush()
        return {
            "bundle_path": export_info["bundle_path"],
            "metadata_path": export_info["metadata_path"],
            "checksum_sha256": export_info["bundle_sha256"],
            "byte_size": export_info["bundle_size"],
            "artifact_type": "browser_check",
            "artifact_id": artifact.id,
        }

    def _record_browser_check_metadata(
        self,
        session: ChatSession,
        *,
        execution_id: str,
        status: str,
        objective: str,
        result: Dict[str, Any],
        artifact: Optional[Dict[str, Any]],
    ) -> None:
        metadata = dict(session.mode_metadata or {})
        metadata["browser_check"] = {
            "execution_id": execution_id,
            "status": status,
            "objective": objective,
            "completed_at": utc_now().isoformat(),
            "screenshot_path": result.get("screenshot_path"),
            "report_path": result.get("report_path"),
            "visual_report": result.get("visual_report"),
            "artifact": artifact,
            "console_warning_count": result.get("console_warning_count"),
            "failed_request_count": result.get("failed_request_count"),
            "changed_file_summary": result.get("changed_file_summary"),
            "error": result.get("error"),
        }
        session.mode_metadata = metadata

    def _create_browser_check_context_card(
        self,
        db: Session,
        *,
        session: ChatSession,
        result: Dict[str, Any],
        artifact: Optional[Dict[str, Any]],
    ) -> None:
        report = str(result.get("visual_report") or "").strip()
        summary = result.get("summary") if isinstance(result.get("summary"), dict) else {}
        artifact_ref = json.dumps(artifact or {}, ensure_ascii=True, indent=2)
        content_parts = [
            "Browser check visual report:",
            report or "No textual report was captured.",
            "",
            "Screenshot artifact reference:",
            artifact_ref,
            "",
            "Summary:",
            json.dumps(summary, ensure_ascii=True, indent=2),
        ]
        content = "\n".join(content_parts).strip()
        db.add(
            ContextCard(
                user_id=session.user_id,
                session_id=session.id,
                title="Frontend Browser Check",
                description="Visual verification report and screenshot artifact reference.",
                content=content,
                source="chat",
                tokens=max(1, len(content) // 4),
                is_active=True,
            )
        )

    async def _execute_mswea_mode(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        mode: str,
        objective: str,
        timeout_seconds: int,
        pipeline_execution_id: str,
        issue_number: Optional[int] = None,
        issue_url: Optional[str] = None,
        test_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        async def _relay_event(event: Dict[str, Any]) -> None:
            if event.get("type") != WSMessageType.SANDBOX_STREAM.value:
                return
            payload = event.get("payload", {}) or {}
            payload["mode"] = mode
            payload["execution_id"] = execution.id
            payload["pipeline_execution_id"] = pipeline_execution_id
            await self.ws_hub.send_to_session(
                session.session_id,
                WSMessageType.SANDBOX_STREAM,
                payload,
            )

        env: Dict[str, str] = {
            "MSWEA_OBJECTIVE": objective,
            "MSWEA_CONFIG_ROOT": MSWEA_CONFIG_ROOT,
            "PIPELINE_EXECUTION_ID": pipeline_execution_id,
            "WORKSPACE_PATH": session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH,
            "REPO_BRANCH": session.repo_branch or "main",
        }
        repo_url = session.repo_url
        if not repo_url and session.repo_owner and session.repo_name:
            repo_url = f"https://github.com/{session.repo_owner}/{session.repo_name}.git"
        if repo_url:
            env["REPO_URL"] = repo_url

        github_token = self._get_user_github_token(db, session.user_id)
        if github_token:
            env["GITHUB_TOKEN"] = github_token

        env.update(dict(get_sandbox_config().env_passthrough_values))

        if issue_number is not None:
            env["MSWEA_ISSUE_NUMBER"] = str(issue_number)
        if issue_url:
            env["MSWEA_ISSUE_URL"] = issue_url
        if test_branch:
            env["MSWEA_TEST_BRANCH"] = test_branch

        command = self._build_mswea_command(
            mode=mode,
            include_issue_number=issue_number is not None,
            include_test_branch=bool(test_branch),
        )

        result = await self.broker.run_command(
            db,
            session=session,
            command=command,
            cwd=session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH,
            env=env,
            timeout_seconds=timeout_seconds,
            on_event=_relay_event,
        )

        if result.get("exit_code", 1) != 0:
            raise RuntimeError(f"MSWEA {mode} mode failed with exit_code={result.get('exit_code')}")

        output_text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}"
        try:
            contract = parse_mode_contract(mode, output_text)
        except ModeContractError as exc:
            raise RuntimeError(str(exc)) from exc

        changed_files = result.get("changed_files")
        if not isinstance(changed_files, list):
            changed_files = extract_changed_files_from_output(output_text)
        try:
            changed_files = validate_mode_changed_files(mode, changed_files)
        except ModeContractError as exc:
            raise RuntimeError(str(exc)) from exc

        normalized_result: Dict[str, Any] = {
            "mode": mode,
            "status": "complete",
            "exit_code": result.get("exit_code"),
            "duration_ms": result.get("duration_ms"),
            "sandbox_id": result.get("sandbox_id"),
            "config_path": MSWEA_CONFIG_PATHS[mode],
            "context_file": contract.get("context_file")
            or f"{session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH}/.yudai/context.md",
            "changed_files": normalize_changed_files(changed_files),
            "contract_version": CONTRACT_VERSION,
        }
        normalized_result.update(contract)

        await self._write_mode_summary(
            db,
            session=session,
            mode=mode,
            pipeline_execution_id=pipeline_execution_id,
            summary=normalized_result,
        )
        return normalized_result

    async def _run_architect(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        user_id: int,
        objective: str,
        pipeline_execution_id: str,
    ) -> Dict[str, Any]:
        await self.ws_hub.send_to_session(
            session.session_id,
            WSMessageType.LLM_STREAM,
            {
                "stream": "llm",
                "text": "Architect mode is running MSWEA to enrich the existing GitHub issue context...",
                "final": False,
            },
        )

        result = await self._execute_mswea_mode(
            db,
            session=session,
            execution=execution,
            mode=SessionMode.ARCHITECT.value,
            objective=objective,
            issue_number=session.architect_issue_number,
            issue_url=session.architect_issue_url,
            timeout_seconds=get_agent_config().architect.timeout_seconds,
            pipeline_execution_id=pipeline_execution_id,
        )

        issue_number = self._to_int(result.get("issue_number")) or session.architect_issue_number
        issue_url = (
            result.get("issue_url")
            if isinstance(result.get("issue_url"), str) and result.get("issue_url")
            else session.architect_issue_url
        )

        if issue_number is None and issue_url:
            match = ISSUE_URL_PATTERN.search(issue_url)
            if match:
                issue_number = self._to_int(match.group(1))

        if issue_url is None and issue_number is not None:
            issue_url = self._infer_issue_url(session, issue_number)

        if issue_number is None or not issue_url:
            raise RuntimeError("Architect mode requires existing GitHub issue metadata before execution")

        title = objective.strip().split("\n")[0][:180] or "Implementation task"
        issue = (
            db.query(UserIssue)
            .filter(
                UserIssue.user_id == user_id,
                UserIssue.session_id == session.session_id,
                UserIssue.github_issue_number == issue_number,
            )
            .first()
        )
        if issue is None:
            issue = UserIssue(
                user_id=user_id,
                issue_id=f"issue_{uuid.uuid4().hex[:12]}",
                title=title,
                description=objective,
                issue_text_raw=objective,
                issue_steps=[
                    "Analyze the existing implementation",
                    "Add or update tests",
                    "Implement changes",
                    "Validate all tests pass",
                ],
                session_id=session.session_id,
                repo_owner=session.repo_owner,
                repo_name=session.repo_name,
                priority="medium",
                status="completed",
                tokens_used=max(1, len(objective) // 4),
                processed_at=utc_now(),
            )
            db.add(issue)
        issue.github_issue_number = issue_number
        issue.github_issue_url = issue_url
        ready_for_tester = bool(result.get("ready_for_tester"))
        issue.status = "completed" if ready_for_tester else "needs_input"
        db.flush()

        session.architect_issue_number = issue_number
        session.architect_issue_url = issue_url
        result.update(
            {
                "issue_id": issue.issue_id,
                "issue_number": issue_number,
                "issue_url": issue_url,
            }
        )
        self._record_mode_contract(session, SessionMode.ARCHITECT.value, result)

        self._merge_mode_metadata(
            session,
            {
                "architect_execution_id": execution.id,
                "issue_id": issue.issue_id,
                "issue_number": issue_number,
                "issue_url": issue_url,
                "architect_context_file": result.get("context_file"),
                "architect_config_path": result.get("config_path"),
            },
        )

        from yudai.daifuUserAgent.session_service import MemoryService

        MemoryService.save_session_snapshot(
            db,
            session,
            trigger="architect_context_enriched",
        )

        self.lifecycle.mark_issue_created(
            db,
            session_public_id=session.session_id,
            user_id=user_id,
            issue_url=issue_url,
            issue_number=issue_number,
        )

        if not ready_for_tester:
            MemoryService.save_session_snapshot(
                db,
                session,
                trigger="architect_waiting_for_input",
            )
            await self.ws_hub.send_to_session(
                session.session_id,
                WSMessageType.LLM_STREAM,
                {
                    "stream": "llm",
                    "text": f"Architect mode needs user input before Tester mode for issue #{issue_number}.",
                    "final": True,
                },
            )
            return await self._pause_for_architect_questions(
                db,
                session=session,
                execution=execution,
                user_id=user_id,
                objective=objective,
                result=result,
            )

        session.architect_completed_at = utc_now()

        await self.ws_hub.send_to_session(
            session.session_id,
            WSMessageType.LLM_STREAM,
            {
                "stream": "llm",
                "text": f"Architect mode enriched issue #{issue_number} and handed context to Tester mode.",
                "final": True,
            },
        )

        return result

    async def _run_tester(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        objective: str,
        pipeline_execution_id: str,
    ) -> Dict[str, Any]:
        issue_number = session.architect_issue_number
        if issue_number is None:
            raise RuntimeError("Tester mode requires architect_issue_number before execution")

        result = await self._execute_mswea_mode(
            db,
            session=session,
            execution=execution,
            mode=SessionMode.TESTER.value,
            objective=objective,
            issue_number=issue_number,
            issue_url=session.architect_issue_url,
            timeout_seconds=get_agent_config().tester.timeout_seconds,
            pipeline_execution_id=pipeline_execution_id,
        )

        session.tester_status = "complete"
        session.tester_completed_at = utc_now()
        self._record_mode_contract(session, SessionMode.TESTER.value, result)
        self._merge_mode_metadata(
            session,
            {
                "tester_execution_id": execution.id,
                "tester_exit_code": result.get("exit_code"),
                "tester_test_branch": result.get("test_branch"),
                "tester_config_path": result.get("config_path"),
            },
        )
        return result

    async def _run_coder(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        user_id: int,
        objective: str,
        pipeline_execution_id: str,
    ) -> Dict[str, Any]:
        issue_number = session.architect_issue_number
        if issue_number is None:
            raise RuntimeError("Coder mode requires architect_issue_number before execution")

        mode_metadata = session.mode_metadata or {}
        test_branch = mode_metadata.get("tester_test_branch")
        if not isinstance(test_branch, str) or not test_branch.strip():
            test_branch = f"yudai/issue-{issue_number}-tests"

        result = await self._execute_mswea_mode(
            db,
            session=session,
            execution=execution,
            mode=SessionMode.CODER.value,
            objective=objective,
            issue_number=issue_number,
            issue_url=session.architect_issue_url,
            test_branch=test_branch,
            timeout_seconds=get_agent_config().coder.timeout_seconds,
            pipeline_execution_id=pipeline_execution_id,
        )

        pr_number = self._to_int(result.get("pr_number"))
        pr_url = result.get("pr_url") if isinstance(result.get("pr_url"), str) else None

        if pr_number is None and pr_url:
            match = PR_URL_PATTERN.search(pr_url)
            if match:
                pr_number = self._to_int(match.group(1))

        if pr_url is None and pr_number is not None:
            pr_url = self._infer_pr_url(session, pr_number)

        if pr_number is None or not pr_url:
            raise RuntimeError("Coder mode completed without parsable PR metadata from MSWEA output")

        session.coder_pr_number = pr_number
        session.coder_pr_url = pr_url
        session.coder_completed_at = utc_now()
        self._merge_mode_metadata(
            session,
            {
                "coder_execution_id": execution.id,
                "coder_exit_code": result.get("exit_code"),
                "coder_test_branch": test_branch,
                "coder_config_path": result.get("config_path"),
            },
        )

        from yudai.daifuUserAgent.session_service import MemoryService

        MemoryService.save_session_snapshot(
            db,
            session,
            trigger="pull_request_created",
        )

        self.lifecycle.mark_pr_created(
            db,
            session_db_id=session.id,
            session_public_id=session.session_id,
            user_id=user_id,
            pr_url=pr_url,
            pr_number=pr_number,
        )
        result["pr_url"] = pr_url
        result["pr_number"] = pr_number
        result["test_branch"] = test_branch
        self._record_mode_contract(session, SessionMode.CODER.value, result)
        return result

    async def _finalize_runtime(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution_id: Optional[str],
        execution_status: str,
        reason: str,
    ) -> Optional[Dict[str, Any]]:
        if not execution_id:
            return None
        return await self.lifecycle.finalize_session_execution(
            db,
            session=session,
            reason=reason,
            execution_status=execution_status,
            execution_id=execution_id,
            artifact_source_paths=[f"{SANDBOX_EXECUTION_ROOT}/{execution_id}"],
        )

    @staticmethod
    def _browser_check_artifact_key(
        *,
        session: ChatSession,
        sandbox: Any,
        execution_id: str,
    ) -> str:
        return (
            "session-artifacts/"
            f"{sandbox.org_slug}/{sandbox.repo_owner}/{sandbox.repo_name}/"
            f"{sandbox.environment}/{session.session_id}/{execution_id}-browser-check.tar.gz"
        )


_execution_orchestrator_singleton: Optional[SessionExecutionOrchestrator] = None


def get_session_execution_orchestrator() -> SessionExecutionOrchestrator:
    global _execution_orchestrator_singleton
    if _execution_orchestrator_singleton is None:
        _execution_orchestrator_singleton = SessionExecutionOrchestrator()
    return _execution_orchestrator_singleton


ModeOrchestrator = SessionExecutionOrchestrator


def get_mode_orchestrator() -> SessionExecutionOrchestrator:
    return get_session_execution_orchestrator()


async def run_mode_pipeline_background(
    *,
    session_public_id: str,
    user_id: int,
    objective: str,
) -> None:
    db = SessionLocal()
    try:
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_public_id,
                ChatSession.user_id == user_id,
            )
            .first()
        )
        if not session:
            return
        active_execution = get_session_execution_orchestrator()._get_active_execution(session)
        execution_id = str(active_execution.get("execution_id") or f"execp_{uuid.uuid4().hex[:24]}")
    finally:
        db.close()

    await get_session_execution_orchestrator().run_full_pipeline(
        session_public_id=session_public_id,
        user_id=user_id,
        execution_id=execution_id,
        objective=objective,
    )
