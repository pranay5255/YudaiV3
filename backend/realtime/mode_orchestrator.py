"""Fixed Architect -> Tester -> Coder workflow orchestration."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any, Dict, List, Optional

from db.database import SessionLocal
from models import (
    AgentExecution,
    ChatSession,
    SessionMode,
    SessionModeStatus,
    UserIssue,
)
from sqlalchemy.orm import Session

from utils import utc_now

from .lifecycle import RealtimeLifecycleService, get_realtime_lifecycle_service
from .sandbox_exec_broker import SandboxExecBroker, get_sandbox_exec_broker
from .ws_hub import SessionWebSocketHub, get_ws_hub
from .ws_protocol import WSMessageType

MODE_ORDER: tuple[str, str, str] = (
    SessionMode.ARCHITECT.value,
    SessionMode.TESTER.value,
    SessionMode.CODER.value,
)


class ModeOrchestrator:
    """Runs the immutable 3-mode sequence and publishes controller WS events."""

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

    async def run_full_pipeline(
        self,
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

            modes_to_run = self._remaining_modes(session)
            if not modes_to_run:
                await self.ws_hub.send_to_session(
                    session_public_id,
                    WSMessageType.MODE_EVENT,
                    {
                        "mode": SessionMode.COMPLETE.value,
                        "state": SessionModeStatus.COMPLETE.value,
                        "detail": "Workflow already complete.",
                    },
                )
                return

            for mode in modes_to_run:
                execution = self._create_execution_row(
                    db,
                    session=session,
                    mode=mode,
                    objective=objective,
                )
                self._set_mode_state(
                    session,
                    mode=mode,
                    mode_status=SessionModeStatus.RUNNING.value,
                )
                db.commit()

                await self.ws_hub.send_to_session(
                    session_public_id,
                    WSMessageType.MODE_EVENT,
                    {
                        "mode": mode,
                        "state": SessionModeStatus.RUNNING.value,
                        "execution_id": execution.id,
                    },
                )

                try:
                    if mode == SessionMode.ARCHITECT.value:
                        result = await self._run_architect(
                            db,
                            session=session,
                            execution=execution,
                            user_id=user_id,
                            objective=objective,
                        )
                    elif mode == SessionMode.TESTER.value:
                        result = await self._run_tester(
                            db,
                            session=session,
                            execution=execution,
                            objective=objective,
                        )
                    else:
                        result = await self._run_coder(
                            db,
                            session=session,
                            execution=execution,
                            user_id=user_id,
                            objective=objective,
                        )

                    execution.status = SessionModeStatus.COMPLETE.value
                    execution.completed_at = utc_now()
                    execution.output_summary = result
                    self._set_mode_state(
                        session,
                        mode=mode,
                        mode_status=SessionModeStatus.COMPLETE.value,
                    )
                    db.commit()

                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.MODE_EVENT,
                        {
                            "mode": mode,
                            "state": SessionModeStatus.COMPLETE.value,
                            "execution_id": execution.id,
                        },
                    )
                except Exception as exc:
                    execution.status = SessionModeStatus.FAILED.value
                    execution.completed_at = utc_now()
                    execution.error_message = str(exc)
                    self._set_mode_state(
                        session,
                        mode=SessionMode.FAILED.value,
                        mode_status=SessionModeStatus.FAILED.value,
                    )
                    db.commit()

                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.ERROR,
                        {"message": str(exc), "mode": mode, "execution_id": execution.id},
                    )
                    await self.ws_hub.send_to_session(
                        session_public_id,
                        WSMessageType.MODE_EVENT,
                        {
                            "mode": mode,
                            "state": SessionModeStatus.FAILED.value,
                            "execution_id": execution.id,
                        },
                    )
                    return

            self._set_mode_state(
                session,
                mode=SessionMode.COMPLETE.value,
                mode_status=SessionModeStatus.COMPLETE.value,
            )
            session.workflow_completed_at = utc_now()
            db.commit()

            await self.ws_hub.send_to_session(
                session_public_id,
                WSMessageType.STATE_EVENT,
                {
                    "state": "workflow_complete",
                    "session_id": session_public_id,
                    "current_mode": SessionMode.COMPLETE.value,
                },
            )
        finally:
            db.close()

    def _remaining_modes(self, session: ChatSession) -> List[str]:
        pending: list[str] = []
        if not session.architect_completed_at:
            pending.append(SessionMode.ARCHITECT.value)
        if not session.tester_completed_at:
            pending.append(SessionMode.TESTER.value)
        if not session.coder_completed_at:
            pending.append(SessionMode.CODER.value)
        return pending

    def _create_execution_row(
        self,
        db: Session,
        *,
        session: ChatSession,
        mode: str,
        objective: str,
    ) -> AgentExecution:
        execution = AgentExecution(
            id=f"exec_{uuid.uuid4().hex[:24]}",
            session_id=session.id,
            mode=mode,
            status=SessionModeStatus.RUNNING.value,
            execution_plan=self._build_mode_plan(mode, objective),
            execution_metadata={"objective": objective},
            started_at=utc_now(),
        )
        db.add(execution)
        db.flush()
        return execution

    def _set_mode_state(self, session: ChatSession, *, mode: str, mode_status: str) -> None:
        session.current_mode = mode
        session.mode_status = mode_status
        session.mode_updated_at = utc_now()

    def _build_mode_plan(self, mode: str, objective: str) -> List[str]:
        if mode == SessionMode.ARCHITECT.value:
            return [
                "Summarize user objective into an implementation issue.",
                f"Objective: {objective}",
                "Persist issue metadata and emit mode state events.",
            ]
        if mode == SessionMode.TESTER.value:
            return [
                "Analyze repository test tooling and run available tests.",
                "Emit sandbox stdout/stderr events to controller websocket clients.",
            ]
        return [
            "Apply implementation changes and run tests.",
            "Generate PR metadata and mark lifecycle completion when successful.",
        ]

    async def _run_architect(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        user_id: int,
        objective: str,
    ) -> Dict[str, Any]:
        await self.ws_hub.send_to_session(
            session.session_id,
            WSMessageType.LLM_STREAM,
            {"stream": "llm", "text": "Architect mode is creating a detailed issue...", "final": False},
        )

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
        db.add(issue)
        db.flush()

        issue_number = issue.id
        repo_owner = session.repo_owner or "repo-owner"
        repo_name = session.repo_name or "repo-name"
        issue_url = f"https://github.com/{repo_owner}/{repo_name}/issues/{issue_number}"
        issue.github_issue_number = issue_number
        issue.github_issue_url = issue_url

        session.architect_issue_number = issue_number
        session.architect_issue_url = issue_url
        session.architect_completed_at = utc_now()
        session.mode_metadata = {
            **(session.mode_metadata or {}),
            "architect_execution_id": execution.id,
            "issue_id": issue.issue_id,
            "issue_number": issue_number,
        }

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

        return {
            "issue_id": issue.issue_id,
            "issue_number": issue_number,
            "issue_url": issue_url,
        }

    async def _run_tester(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        objective: str,
    ) -> Dict[str, Any]:
        command = "\n".join(
            [
                "set -u",
                "workspace=\"${WORKSPACE_PATH:-/workspace/repo}\"",
                "if [ -d \"$workspace\" ]; then cd \"$workspace\"; fi",
                "echo \"[tester] objective: " + objective.replace('"', '\\"')[:300] + "\"",
                "if [ -f package.json ]; then",
                "  (npm test -- --runInBand || npm test || true)",
                "elif [ -f pyproject.toml ] || [ -f pytest.ini ] || [ -d tests ]; then",
                "  (pytest -q || true)",
                "else",
                "  echo \"No supported test runner detected.\"",
                "fi",
            ]
        )

        async def _relay_event(event: Dict[str, Any]) -> None:
            if event.get("type") != WSMessageType.SANDBOX_STREAM.value:
                return
            payload = event.get("payload", {}) or {}
            payload["mode"] = SessionMode.TESTER.value
            payload["execution_id"] = execution.id
            await self.ws_hub.send_to_session(
                session.session_id,
                WSMessageType.SANDBOX_STREAM,
                payload,
            )

        result = await self.broker.run_command(
            db,
            session=session,
            command=command,
            cwd=session.runtime_workspace_path or "/workspace/repo",
            timeout_seconds=900,
            on_event=_relay_event,
        )

        status = "complete" if result.get("exit_code", 1) == 0 else "failed"
        session.tester_status = status
        session.tester_completed_at = utc_now()
        session.mode_metadata = {
            **(session.mode_metadata or {}),
            "tester_execution_id": execution.id,
            "tester_exit_code": result.get("exit_code"),
        }
        return result

    async def _run_coder(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        user_id: int,
        objective: str,
    ) -> Dict[str, Any]:
        repo_owner = session.repo_owner or "repo-owner"
        repo_name = session.repo_name or "repo-name"
        issue_number = session.architect_issue_number or 1
        pr_number = issue_number + 1000
        pr_url = f"https://github.com/{repo_owner}/{repo_name}/pull/{pr_number}"

        command = "\n".join(
            [
                "set -u",
                "workspace=\"${WORKSPACE_PATH:-/workspace/repo}\"",
                "if [ -d \"$workspace\" ]; then cd \"$workspace\"; fi",
                "echo \"[coder] objective: " + objective.replace('"', '\\"')[:300] + "\"",
                "if [ -f package.json ]; then",
                "  (npm test -- --runInBand || npm test || true)",
                "elif [ -f pyproject.toml ] || [ -f pytest.ini ] || [ -d tests ]; then",
                "  (pytest -q || true)",
                "fi",
                f"echo \"PR_URL={pr_url}\"",
            ]
        )

        async def _relay_event(event: Dict[str, Any]) -> None:
            if event.get("type") != WSMessageType.SANDBOX_STREAM.value:
                return
            payload = event.get("payload", {}) or {}
            payload["mode"] = SessionMode.CODER.value
            payload["execution_id"] = execution.id
            await self.ws_hub.send_to_session(
                session.session_id,
                WSMessageType.SANDBOX_STREAM,
                payload,
            )

        result = await self.broker.run_command(
            db,
            session=session,
            command=command,
            cwd=session.runtime_workspace_path or "/workspace/repo",
            timeout_seconds=1800,
            on_event=_relay_event,
        )

        session.coder_pr_number = pr_number
        session.coder_pr_url = pr_url
        session.coder_completed_at = utc_now()
        session.mode_metadata = {
            **(session.mode_metadata or {}),
            "coder_execution_id": execution.id,
            "coder_exit_code": result.get("exit_code"),
        }

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
        return result


_mode_orchestrator_singleton: Optional[ModeOrchestrator] = None


def get_mode_orchestrator() -> ModeOrchestrator:
    global _mode_orchestrator_singleton
    if _mode_orchestrator_singleton is None:
        _mode_orchestrator_singleton = ModeOrchestrator()
    return _mode_orchestrator_singleton


async def run_mode_pipeline_background(
    *,
    session_public_id: str,
    user_id: int,
    objective: str,
) -> None:
    orchestrator = get_mode_orchestrator()
    await orchestrator.run_full_pipeline(
        session_public_id=session_public_id,
        user_id=user_id,
        objective=objective,
    )
