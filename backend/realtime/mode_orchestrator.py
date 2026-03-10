"""Architect -> Tester -> Coder workflow orchestration."""

from __future__ import annotations

import json
from pathlib import Path
import re
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
from .modal_sandbox import SANDBOX_MSWEA_CONFIG_ROOT, SANDBOX_WORKSPACE_PATH
from .sandbox_exec_broker import SandboxExecBroker, get_sandbox_exec_broker
from .ws_hub import SessionWebSocketHub, get_ws_hub
from .ws_protocol import WSMessageType

MODE_ORDER: tuple[str, str, str] = (
    SessionMode.ARCHITECT.value,
    SessionMode.TESTER.value,
    SessionMode.CODER.value,
)

# Paths as they exist inside the unified Modal sandbox image.
# Mode config yamls are baked into the image at build time.
MSWEA_CONFIG_ROOT = SANDBOX_MSWEA_CONFIG_ROOT
MSWEA_CONFIG_PATHS = {
    SessionMode.ARCHITECT.value: f"{MSWEA_CONFIG_ROOT}/architect/config.yaml",
    SessionMode.TESTER.value: f"{MSWEA_CONFIG_ROOT}/tester/config.yaml",
    SessionMode.CODER.value: f"{MSWEA_CONFIG_ROOT}/coder/config.yaml",
}

# Local template root (used only by _build_mode_configs to read + push to sandbox)
_MODE_CONFIG_TEMPLATE_ROOT = Path(__file__).resolve().parent / "mswea_mode_configs"
_MODE_CONFIG_TEMPLATE_PATHS = {
    SessionMode.ARCHITECT.value: _MODE_CONFIG_TEMPLATE_ROOT / "architect" / "config.yaml",
    SessionMode.TESTER.value: _MODE_CONFIG_TEMPLATE_ROOT / "tester" / "config.yaml",
    SessionMode.CODER.value: _MODE_CONFIG_TEMPLATE_ROOT / "coder" / "config.yaml",
}

ISSUE_URL_PATTERN = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+/issues/(\d+)")
PR_URL_PATTERN = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+/pull/(\d+)")
ISSUE_NUMBER_PATTERN = re.compile(r"(?im)\b(?:issue[_ -]?number|issue number)\b\s*[:=]\s*(\d+)")
PR_NUMBER_PATTERN = re.compile(r"(?im)\b(?:pr[_ -]?number|pull[_ -]?number|pr number)\b\s*[:=]\s*(\d+)")
TEST_BRANCH_PATTERN = re.compile(r"(?im)\b(?:test[_ -]?branch|test branch)\b\s*[:=]\s*([^\s\"']+)")


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
                "Run MSWEA architect mode inside sandbox.",
                f"Objective: {objective}",
                "Parse issue metadata from mode output and persist completion.",
            ]
        if mode == SessionMode.TESTER.value:
            return [
                "Run MSWEA tester mode with --issue-number in sandbox.",
                "Stream sandbox stdout/stderr/exit events to unified websocket clients.",
            ]
        return [
            "Run MSWEA coder mode with --issue-number and --test-branch in sandbox.",
            "Parse PR metadata and mark lifecycle completion when successful.",
        ]

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

    def _build_mode_configs(self) -> Dict[str, str]:
        configs: Dict[str, str] = {}
        for mode in MODE_ORDER:
            template_path = _MODE_CONFIG_TEMPLATE_PATHS[mode]
            if not template_path.exists():
                raise RuntimeError(f"Missing mode config template: {template_path}")
            configs[mode] = template_path.read_text(encoding="utf-8")
        return configs

    def _build_config_write_command(self) -> str:
        configs_json = json.dumps(self._build_mode_configs(), ensure_ascii=True)
        return "\n".join(
            [
                "set -eu",
                "python - <<'PY'",
                "import json",
                "import os",
                "from pathlib import Path",
                f"configs = json.loads({json.dumps(configs_json, ensure_ascii=True)})",
                f"config_root = Path(os.getenv('MSWEA_CONFIG_ROOT', {json.dumps(MSWEA_CONFIG_ROOT)}))",
                "for mode, content in configs.items():",
                "    path = config_root / mode / 'config.yaml'",
                "    path.parent.mkdir(parents=True, exist_ok=True)",
                "    path.write_text(content, encoding='utf-8')",
                "    print(f'WROTE_CONFIG={path}')",
                "PY",
            ]
        )

    def _build_mswea_command(
        self,
        *,
        mode: str,
        include_issue_number: bool,
        include_test_branch: bool,
    ) -> str:
        config_path = MSWEA_CONFIG_PATHS[mode]
        command_lines = [
            "set -eu",
            f"workspace=\"${{WORKSPACE_PATH:-{SANDBOX_WORKSPACE_PATH}}}\"",
            "if [ -d \"$workspace/.git\" ]; then",
            "  cd \"$workspace\"",
            "  git fetch --all --prune 2>/dev/null || true",
            "  git checkout -f \"${REPO_BRANCH:-main}\" 2>/dev/null || true",
            "  git reset --hard \"origin/${REPO_BRANCH:-main}\" 2>/dev/null || true",
            "  git clean -fdx 2>/dev/null || true",
            "elif [ -n \"${REPO_URL:-}\" ]; then",
            "  mkdir -p \"$(dirname \"$workspace\")\"",
            "  git clone --depth 1 -b \"${REPO_BRANCH:-main}\" \"$REPO_URL\" \"$workspace\"",
            "  cd \"$workspace\"",
            "else",
            "  if [ -d \"$workspace\" ]; then cd \"$workspace\"; fi",
            "fi",
            "help_text=\"$(python -m mswea.solve --help 2>&1 || true)\"",
            f"config_path=\"{config_path}\"",
            "cmd=(python -m mswea.solve --config \"$config_path\" --yolo-mode)",
            "if printf '%s' \"$help_text\" | grep -q -- '--workspace'; then",
            "  cmd+=(--workspace \"$workspace\")",
            "fi",
            "if [ -n \"${MSWEA_OBJECTIVE:-}\" ]; then",
            "  if printf '%s' \"$help_text\" | grep -q -- '--task'; then",
            "    cmd+=(--task \"$MSWEA_OBJECTIVE\")",
            "  elif printf '%s' \"$help_text\" | grep -q -- '--prompt'; then",
            "    cmd+=(--prompt \"$MSWEA_OBJECTIVE\")",
            "  elif printf '%s' \"$help_text\" | grep -q -- '--objective'; then",
            "    cmd+=(--objective \"$MSWEA_OBJECTIVE\")",
            "  fi",
            "fi",
        ]

        if include_issue_number:
            command_lines.extend(
                [
                    "if [ -n \"${MSWEA_ISSUE_NUMBER:-}\" ] && printf '%s' \"$help_text\" | grep -q -- '--issue-number'; then",
                    "  cmd+=(--issue-number \"$MSWEA_ISSUE_NUMBER\")",
                    "fi",
                ]
            )

        if include_test_branch:
            command_lines.extend(
                [
                    "if [ -n \"${MSWEA_TEST_BRANCH:-}\" ] && printf '%s' \"$help_text\" | grep -q -- '--test-branch'; then",
                    "  cmd+=(--test-branch \"$MSWEA_TEST_BRANCH\")",
                    "fi",
                ]
            )

        command_lines.extend(
            [
                f"printf '[{mode}] running:'",
                "printf ' %q' \"${cmd[@]}\"",
                "printf '\\n'",
                "\"${cmd[@]}\"",
            ]
        )

        return "\n".join(command_lines)

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

        # Best effort: parse JSON object lines and merge known keys.
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

    async def _ensure_mode_configs(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        mode: str,
    ) -> None:
        async def _relay_event(event: Dict[str, Any]) -> None:
            if event.get("type") != WSMessageType.SANDBOX_STREAM.value:
                return
            payload = event.get("payload", {}) or {}
            payload["mode"] = mode
            payload["execution_id"] = execution.id
            await self.ws_hub.send_to_session(
                session.session_id,
                WSMessageType.SANDBOX_STREAM,
                payload,
            )

        result = await self.broker.run_command(
            db,
            session=session,
            command=self._build_config_write_command(),
            cwd=session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH,
            timeout_seconds=180,
            on_event=_relay_event,
        )
        if result.get("exit_code", 1) != 0:
            raise RuntimeError(
                "Failed to create MSWEA mode config files in sandbox. "
                f"exit_code={result.get('exit_code')}"
            )

        self._merge_mode_metadata(
            session,
            {
                "mswea_mode_configs": {
                    "version": "v1",
                    "root": MSWEA_CONFIG_ROOT,
                    "paths": MSWEA_CONFIG_PATHS,
                    "created_at": utc_now().isoformat(),
                }
            },
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
        issue_number: Optional[int] = None,
        test_branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        await self._ensure_mode_configs(
            db,
            session=session,
            execution=execution,
            mode=mode,
        )

        async def _relay_event(event: Dict[str, Any]) -> None:
            if event.get("type") != WSMessageType.SANDBOX_STREAM.value:
                return
            payload = event.get("payload", {}) or {}
            payload["mode"] = mode
            payload["execution_id"] = execution.id
            await self.ws_hub.send_to_session(
                session.session_id,
                WSMessageType.SANDBOX_STREAM,
                payload,
            )

        env: Dict[str, str] = {
            "MSWEA_OBJECTIVE": objective,
            "MSWEA_CONFIG_ROOT": MSWEA_CONFIG_ROOT,
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
            raise RuntimeError(
                f"MSWEA {mode} mode failed with exit_code={result.get('exit_code')}"
            )

        output_text = f"{result.get('stdout', '')}\n{result.get('stderr', '')}"
        parsed = self.parse_mswea_output(output_text)
        result.update(parsed)
        result["config_path"] = MSWEA_CONFIG_PATHS[mode]
        return result

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
            raise RuntimeError(
                "Architect mode completed without parsable issue metadata from MSWEA output"
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
