"""Controller-side execution orchestration for the fixed 3-mode pipeline."""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import re
import uuid
from typing import Any, Dict, List, Optional

from db.database import SessionLocal
from models import (
    AgentExecution,
    AuthToken,
    ChatMessage,
    ChatSession,
    SessionArtifact,
    SessionMode,
    SessionModeStatus,
    UserIssue,
    UserQuestion,
    UserQuestionStatus,
)
from sqlalchemy.orm import Session

from utils import utc_now

from .lifecycle import (
    RealtimeLifecycleService,
    SandboxExecBroker,
    get_realtime_lifecycle_service,
    get_sandbox_exec_broker,
)
from .modal_preflight import wait_for_sandbox_healthcheck
from .modal_sandbox import SANDBOX_MSWEA_CONFIG_ROOT, SANDBOX_WORKSPACE_PATH
from .ws_protocol import SessionWebSocketHub, WSMessageType, get_ws_hub

MODE_ORDER: tuple[str, str, str] = (
    SessionMode.ARCHITECT.value,
    SessionMode.TESTER.value,
    SessionMode.CODER.value,
)

SANDBOX_EXECUTION_ROOT = ".yudai/executions"

MSWEA_CONFIG_ROOT = SANDBOX_MSWEA_CONFIG_ROOT
MSWEA_CONFIG_PATHS = {
    SessionMode.ARCHITECT.value: f"{MSWEA_CONFIG_ROOT}/architect/config.yaml",
    SessionMode.TESTER.value: f"{MSWEA_CONFIG_ROOT}/tester/config.yaml",
    SessionMode.CODER.value: f"{MSWEA_CONFIG_ROOT}/coder/config.yaml",
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
        self._session_locks: Dict[str, asyncio.Lock] = {}

    async def start_execution(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
        objective: str,
        force_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        next_mode = self._next_mode_for_session(session)
        if next_mode == SessionMode.COMPLETE.value:
            raise ExecutionConflictError("Session workflow already complete")
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
        execution_id = f"execp_{uuid.uuid4().hex[:24]}"
        started_at = utc_now()

        self._set_active_execution(
            session,
            {
                "execution_id": execution_id,
                "objective": objective,
                "objective_with_context": contextual_objective,
                "status": SessionModeStatus.RUNNING.value,
                "mode": next_mode,
                "plan": self._build_mode_plan(next_mode, contextual_objective),
                "started_at": started_at.isoformat(),
                "completed_at": None,
                "cancel_requested": False,
                "current_mode_execution_id": None,
                "artifact": None,
                "detail": "Pipeline queued",
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
                "detail": "Pipeline queued",
            },
        )
        return self.get_execution_status(db, session=session)

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

    def _schedule_execution_task(
        self,
        *,
        session_public_id: str,
        user_id: int,
        execution_id: str,
        objective: str,
    ) -> None:
        task = asyncio.create_task(
            self.run_full_pipeline(
                session_public_id=session_public_id,
                user_id=user_id,
                execution_id=execution_id,
                objective=objective,
            ),
            name=f"session-execution-{session_public_id}",
        )
        self._session_tasks[session_public_id] = task

        def _cleanup(done_task: asyncio.Task[None]) -> None:
            current = self._session_tasks.get(session_public_id)
            if current is done_task:
                self._session_tasks.pop(session_public_id, None)

        task.add_done_callback(_cleanup)

    def _has_active_task(self, session_public_id: str) -> bool:
        task = self._session_tasks.get(session_public_id)
        return bool(task and not task.done())

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
                "Run MSWEA architect mode inside sandbox.",
                f"Objective: {objective}",
                "Persist issue metadata and stream sandbox events.",
            ]
        if mode == SessionMode.TESTER.value:
            return [
                "Run MSWEA tester mode with the architect issue number.",
                "Stream sandbox stdout/stderr/exit events to unified websocket clients.",
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

        if not tunnel_url:
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
            tunnel_url = envelope.sandbox.tunnel_url
            db.commit()

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
            'repo_branch="${REPO_BRANCH:-main}"',
            'repo_url="${REPO_URL:-}"',
            'pipeline_execution_id="${PIPELINE_EXECUTION_ID:-manual}"',
            f'mode_name="{mode}"',
            f"execution_dir={execution_dir_expr}",
            'mkdir -p "$execution_dir"',
            'printf "%s\\n" "$mode_name" > "$execution_dir/mode.txt"',
            'printf "%s\\n" "$repo_branch" > "$execution_dir/repo_branch.txt"',
            'printf "%s\\n" "${MSWEA_OBJECTIVE:-}" > "$execution_dir/objective.txt"',
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
            'help_text="$(python -m mswea.solve --help 2>&1 || true)"',
            f'config_path="{config_path}"',
            'cmd=(python -m mswea.solve --config "$config_path" --yolo-mode)',
            'if printf "%s" "$help_text" | grep -q -- "--workspace"; then',
            '  cmd+=(--workspace "$workspace")',
            'fi',
            'if [ -n "${MSWEA_OBJECTIVE:-}" ]; then',
            '  if printf "%s" "$help_text" | grep -q -- "--task"; then',
            '    cmd+=(--task "$MSWEA_OBJECTIVE")',
            '  elif printf "%s" "$help_text" | grep -q -- "--prompt"; then',
            '    cmd+=(--prompt "$MSWEA_OBJECTIVE")',
            '  elif printf "%s" "$help_text" | grep -q -- "--objective"; then',
            '    cmd+=(--objective "$MSWEA_OBJECTIVE")',
            '  fi',
            'fi',
        ]

        if include_issue_number:
            command_lines.extend(
                [
                    'if [ -n "${MSWEA_ISSUE_NUMBER:-}" ] && printf "%s" "$help_text" | grep -q -- "--issue-number"; then',
                    '  cmd+=(--issue-number "$MSWEA_ISSUE_NUMBER")',
                    'fi',
                ]
            )

        if include_test_branch:
            command_lines.extend(
                [
                    'if [ -n "${MSWEA_TEST_BRANCH:-}" ] && printf "%s" "$help_text" | grep -q -- "--test-branch"; then',
                    '  cmd+=(--test-branch "$MSWEA_TEST_BRANCH")',
                    'fi',
                ]
            )

        command_lines.extend(
            [
                'printf "%q " "${cmd[@]}" > "$execution_dir/command.txt"',
                f"printf '[{mode}] running:'",
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
            ]
        )

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
                "python - <<'PY'",
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
            timeout_seconds=120,
            env={"WORKSPACE_PATH": session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH},
        )
        if result.get("exit_code", 1) != 0:
            raise RuntimeError(f"Failed to write sandbox summary for {mode} mode")

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
        }
        if issue_number is not None:
            env["MSWEA_ISSUE_NUMBER"] = str(issue_number)
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
        parsed = self.parse_mswea_output(output_text)
        result.update(parsed)
        result["config_path"] = MSWEA_CONFIG_PATHS[mode]

        await self._write_mode_summary(
            db,
            session=session,
            mode=mode,
            pipeline_execution_id=pipeline_execution_id,
            summary=result,
        )
        return result

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
                "text": "Architect mode is running MSWEA to create a GitHub issue...",
                "final": False,
            },
        )

        result = await self._execute_mswea_mode(
            db,
            session=session,
            execution=execution,
            mode=SessionMode.ARCHITECT.value,
            objective=objective,
            timeout_seconds=1200,
            pipeline_execution_id=pipeline_execution_id,
        )

        issue_number = self._to_int(result.get("issue_number"))
        issue_url = result.get("issue_url") if isinstance(result.get("issue_url"), str) else None

        if issue_number is None and issue_url:
            match = ISSUE_URL_PATTERN.search(issue_url)
            if match:
                issue_number = self._to_int(match.group(1))

        if issue_url is None and issue_number is not None:
            issue_url = self._infer_issue_url(session, issue_number)

        if issue_number is None or not issue_url:
            raise RuntimeError("Architect mode completed without parsable issue metadata from MSWEA output")

        title = objective.strip().split("\n")[0][:180] or "Implementation task"
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
        issue.github_issue_number = issue_number
        issue.github_issue_url = issue_url
        db.add(issue)
        db.flush()

        session.architect_issue_number = issue_number
        session.architect_issue_url = issue_url
        session.architect_completed_at = utc_now()

        self._merge_mode_metadata(
            session,
            {
                "architect_execution_id": execution.id,
                "issue_id": issue.issue_id,
                "issue_number": issue_number,
                "architect_config_path": result.get("config_path"),
            },
        )

        self.lifecycle.mark_issue_created(
            db,
            session_public_id=session.session_id,
            user_id=user_id,
            issue_url=issue_url,
            issue_number=issue_number,
        )

        await self.ws_hub.send_to_session(
            session.session_id,
            WSMessageType.LLM_STREAM,
            {
                "stream": "llm",
                "text": f"Architect mode created issue #{issue_number}.",
                "final": True,
            },
        )

        result.update(
            {
                "issue_id": issue.issue_id,
                "issue_number": issue_number,
                "issue_url": issue_url,
            }
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
            timeout_seconds=1200,
            pipeline_execution_id=pipeline_execution_id,
        )

        session.tester_status = "complete"
        session.tester_completed_at = utc_now()
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
            test_branch=test_branch,
            timeout_seconds=1800,
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
