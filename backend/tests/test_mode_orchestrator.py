import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/mode-orchestrator-tests.db")

from yudai.models import (  # noqa: E402
    AgentExecution,
    Base,
    ChatSession,
    ContextCard,
    Sandbox,
    SessionArtifact,
    SessionRuntime,
    User,
    UserQuestion,
    UserQuestionStatus,
)
from yudai.realtime import mode_orchestrator as mode_orchestrator_module  # noqa: E402
from yudai.realtime.mode_orchestrator import (  # noqa: E402
    BROWSER_CHECK_MODE,
    BROWSER_CHECK_REPORT_END,
    BROWSER_CHECK_REPORT_START,
    BROWSER_CHECK_SUMMARY_END,
    BROWSER_CHECK_SUMMARY_START,
    ExecutionConflictError,
    SessionExecutionOrchestrator,
)
from yudai.realtime.mode_contracts import (  # noqa: E402
    CHANGED_FILES_END,
    CHANGED_FILES_START,
)


class DummyHub:
    async def send_to_session(self, *_args, **_kwargs):
        return None


def test_start_execution_returns_non_null_execution_id_and_started_at():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        user = User(
            github_username="orchestrator",
            github_user_id="8101",
            email="orchestrator@example.com",
            display_name="Orchestrator Test",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        session = ChatSession(
            user_id=user.id,
            session_id="session_exec_test",
            title="Execution Session",
            repo_owner="octocat",
            repo_name="yudaiv3",
            repo_branch="main",
            is_active=True,
            total_messages=0,
            total_tokens=0,
            mode_metadata={},
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        orchestrator = SessionExecutionOrchestrator(
            broker=object(),
            lifecycle=object(),
            ws_hub=DummyHub(),
        )
        orchestrator._schedule_execution_task = lambda **_kwargs: None

        payload = asyncio.run(
            orchestrator.start_execution(
                db,
                session=session,
                user_id=user.id,
                objective="Fix the flaky reconnect flow",
            )
        )

        db.refresh(session)
        execution = db.query(AgentExecution).filter(AgentExecution.id == payload["execution_id"]).one()

        assert payload["execution_id"].startswith("exec_")
        assert payload["started_at"] is not None
        assert payload["status"] == "queued"
        assert execution.session_id == session.id
        assert execution.execution_metadata["trigger"] == "execution_api"
        active_execution = (session.mode_metadata or {}).get("active_execution") or {}
        assert active_execution.get("objective_with_context")
    finally:
        db.close()


def test_start_stage_execution_schedules_one_mode_with_stage_trigger():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        user = User(
            github_username="stage-orchestrator",
            github_user_id="8102",
            email="stage-orchestrator@example.com",
            display_name="Stage Orchestrator Test",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        session = ChatSession(
            user_id=user.id,
            session_id="session_stage_exec_test",
            title="Stage Execution Session",
            repo_owner="octocat",
            repo_name="yudaiv3",
            repo_branch="main",
            is_active=True,
            total_messages=0,
            total_tokens=0,
            mode_metadata={},
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        orchestrator = SessionExecutionOrchestrator(
            broker=object(),
            lifecycle=object(),
            ws_hub=DummyHub(),
        )
        payload = asyncio.run(
            orchestrator.start_stage_execution(
                db,
                session=session,
                user_id=user.id,
                objective="Resolve issue #77",
                mode="architect",
                trigger="daifu_tool:run_architect_mode",
            )
        )

        db.refresh(session)
        execution = db.query(AgentExecution).filter(AgentExecution.id == payload["execution_id"]).one()

        assert payload["detail"] == "Stage queued"
        assert payload["status"] == "queued"
        assert execution.execution_metadata["trigger"] == "daifu_tool:run_architect_mode"
        assert execution.execution_metadata["max_modes"] == 1
        assert execution.status == "queued"
        assert (session.mode_metadata or {})["active_execution"]["max_modes"] == 1
    finally:
        db.close()


def test_build_mswea_command_uses_official_mini_cli_probe(tmp_path, monkeypatch):
    monkeypatch.setenv("MSWEA_MODEL_NAME", "openrouter/x-ai/grok-4-fast")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mini = bin_dir / "mini"
    mini.write_text("#!/usr/bin/env bash\nprintf 'fake mini\\n'\n", encoding="utf-8")
    mini.chmod(0o755)

    workspace = tmp_path / "repo"
    orchestrator = SessionExecutionOrchestrator(
        broker=object(),
        lifecycle=object(),
        ws_hub=DummyHub(),
    )
    command = orchestrator._build_mswea_command(
        mode="coder",
        include_issue_number=True,
        include_test_branch=True,
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
            "WORKSPACE_PATH": str(workspace),
            "PIPELINE_EXECUTION_ID": "probe_exec",
            "YUDAI_MSWEA_COMMAND_PROBE": "1",
            "MSWEA_OBJECTIVE": "Probe coder mode",
            "MSWEA_MODEL_NAME": "openrouter/x-ai/grok-4-fast",
            "MSWEA_ISSUE_NUMBER": "123",
            "MSWEA_TEST_BRANCH": "yudai/issue-123-tests",
            "REPO_BRANCH": "main",
        }
    )

    completed = subprocess.run(
        ["bash", "-lc", command],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    argv = payload["argv"]

    assert argv[0] == "mini"
    assert argv[1:3] == ["-c", "/app/mswea_mode_configs/coder/config.yaml"]
    assert "-y" in argv
    assert argv[argv.index("-m") + 1] == "openrouter/x-ai/grok-4-fast"
    task_text = argv[argv.index("-t") + 1]
    assert "Probe coder mode" in task_text
    assert "#123" in task_text
    assert "yudai/issue-123-tests" in task_text
    assert payload["context_file"] == str(workspace / ".yudai" / "context.md")
    assert payload["context_file"] in task_text
    assert (workspace / ".yudai" / "executions" / "probe_exec" / "coder" / "command_probe.json").is_file()
    assert (workspace / ".yudai" / "context.md").is_file()


def test_build_browser_check_command_probe_preserves_existing_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("MSWEA_MODEL_NAME", "openrouter/x-ai/grok-4-fast")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mini = bin_dir / "mini"
    mini.write_text("#!/usr/bin/env bash\nprintf 'fake mini\\n'\n", encoding="utf-8")
    mini.chmod(0o755)

    workspace = tmp_path / "repo"
    workspace.mkdir()
    (workspace / "package.json").write_text('{"scripts":{"dev":"vite"}}\n', encoding="utf-8")
    orchestrator = SessionExecutionOrchestrator(
        broker=object(),
        lifecycle=object(),
        ws_hub=DummyHub(),
    )
    command = orchestrator._build_browser_check_command()

    assert "git reset" not in command
    assert "git clean" not in command

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
            "WORKSPACE_PATH": str(workspace),
            "PIPELINE_EXECUTION_ID": "browser_probe_exec",
            "YUDAI_BROWSER_CHECK_COMMAND_PROBE": "1",
            "BROWSER_CHECK_OBJECTIVE": "Verify the dashboard visually",
            "MSWEA_MODEL_NAME": "openrouter/x-ai/grok-4-fast",
            "REPO_BRANCH": "main",
        }
    )

    completed = subprocess.run(
        ["bash", "-lc", command],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    argv = payload["argv"]

    assert payload["mode"] == "browser_check"
    assert payload["config_path"] == "/app/mswea_mode_configs/browser/config.yaml"
    assert payload["screenshot_path"].endswith(
        ".yudai/executions/browser_probe_exec/browser_check/screenshot.png"
    )
    assert payload["report_path"].endswith(
        ".yudai/executions/browser_probe_exec/browser_check/visual_report.md"
    )
    assert payload["summary_path"].endswith(
        ".yudai/executions/browser_probe_exec/browser_check/summary.json"
    )
    assert argv[0] == "mini"
    assert argv[1:3] == ["-c", "/app/mswea_mode_configs/browser/config.yaml"]
    task_text = argv[argv.index("-t") + 1]
    assert "Verify the dashboard visually" in task_text
    assert payload["screenshot_path"] in task_text
    assert (workspace / ".yudai" / "executions" / "browser_probe_exec" / "browser_check" / "command_probe.json").is_file()


def test_start_browser_check_rejects_active_execution_task():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        user = User(
            github_username="browser-conflict",
            github_user_id="8103",
            email="browser-conflict@example.com",
            display_name="Browser Conflict",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        session = ChatSession(
            user_id=user.id,
            session_id="session_browser_conflict",
            title="Browser Conflict Session",
            repo_owner="octocat",
            repo_name="yudaiv3",
            repo_branch="main",
            is_active=True,
            total_messages=0,
            total_tokens=0,
            mode_metadata={},
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        orchestrator = SessionExecutionOrchestrator(
            broker=object(),
            lifecycle=object(),
            ws_hub=DummyHub(),
        )

        async def _run():
            task = asyncio.create_task(asyncio.sleep(60))
            orchestrator._browser_check_tasks[session.session_id] = task
            try:
                with pytest.raises(ExecutionConflictError):
                    await orchestrator.start_browser_check(
                        db,
                        session=session,
                        user_id=user.id,
                        objective="Verify UI",
                    )
            finally:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task

        asyncio.run(_run())
    finally:
        db.close()


def test_browser_check_mocked_broker_success_persists_artifact_and_context(tmp_path, monkeypatch):
    db_path = tmp_path / "browser-success.db"
    monkeypatch.setenv("YUDAI_IN_PROCESS_EXECUTION_FALLBACK", "true")
    monkeypatch.setenv("MSWEA_MODEL_NAME", "openrouter/x-ai/grok-4-fast")
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(mode_orchestrator_module, "SessionLocal", SessionLocal)

    class DummyCacheStore:
        async def download_and_export_bundle(self, **kwargs):
            return {
                "metadata": {
                    "cache_manifest_path": str(tmp_path / "manifest.json"),
                    "sandbox_bundle": {
                        "metadata_path": str(tmp_path / "browser-check.metadata.json"),
                    },
                    "source_paths": kwargs["source_paths"],
                },
                "metadata_path": str(tmp_path / "browser-check.metadata.json"),
                "bundle_path": str(tmp_path / "browser-check.tar.gz"),
                "bundle_sha256": "sha256-browser",
                "bundle_size": 128,
            }

    class DummyLifecycle:
        def __init__(self):
            self.cache_store = DummyCacheStore()

        async def create_runtime_for_session(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("runtime should already exist")

        def _get_latest_runtime(self, db, *, session_id=None, sandbox_id=None):
            query = db.query(SessionRuntime)
            if session_id is not None:
                query = query.filter(SessionRuntime.session_id == session_id)
            if sandbox_id is not None:
                query = query.filter(SessionRuntime.sandbox_id == sandbox_id)
            return query.order_by(SessionRuntime.id.desc()).first()

        def get_sandbox_or_404(self, db, sandbox_id):
            return db.query(Sandbox).filter(Sandbox.id == sandbox_id).one()

    class DummyBroker:
        async def run_command(self, db, *, session, command, cwd=None, env=None, timeout_seconds=1800, on_event=None):
            if on_event:
                await on_event(
                    {
                        "type": "sandbox_stream",
                        "payload": {"event": "stdout", "data": "browser output"},
                    }
                )
            summary = {
                "mode": "browser_check",
                "status": "complete",
                "route": "http://127.0.0.1:5173/",
                "dev_server_command": "npm run dev",
                "screenshot_path": env["BROWSER_CHECK_SCREENSHOT_PATH"],
                "report_path": env["BROWSER_CHECK_REPORT_PATH"],
                "console_warning_count": 1,
                "failed_request_count": 0,
                "warnings": ["one console warning"],
                "critical_failures": [],
                "changed_file_summary": {"newly_changed": [".yudai/browser-check.py"]},
            }
            stdout = (
                f"{BROWSER_CHECK_SUMMARY_START}\n"
                f"{json.dumps(summary)}\n"
                f"{BROWSER_CHECK_SUMMARY_END}\n"
                f"{BROWSER_CHECK_REPORT_START}\n"
                "Visual report: page rendered with one warning.\n"
                f"{BROWSER_CHECK_REPORT_END}\n"
            )
            return {"sandbox_id": "sbx_browser", "exit_code": 0, "stdout": stdout, "stderr": "", "duration_ms": 42}

    class CapturingHub:
        def __init__(self):
            self.events = []

        async def send_to_session(self, session_id, msg_type, payload):
            self.events.append({"session_id": session_id, "msg_type": msg_type, "payload": payload})

    async def _healthy(*_args, **_kwargs):
        return None

    monkeypatch.setattr(mode_orchestrator_module, "wait_for_sandbox_healthcheck", _healthy)
    db = SessionLocal()
    try:
        user = User(
            github_username="browser-success",
            github_user_id="8104",
            email="browser-success@example.com",
            display_name="Browser Success",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        session = ChatSession(
            user_id=user.id,
            session_id="session_browser_success",
            title="Browser Success Session",
            repo_owner="octocat",
            repo_name="yudaiv3",
            repo_branch="main",
            repo_url="https://github.com/octocat/yudaiv3.git",
            runtime_workspace_path="/workspace/repo",
            is_active=True,
            total_messages=0,
            total_tokens=0,
            mode_metadata={},
        )
        db.add(session)
        db.flush()
        sandbox = Sandbox(
            id="sbx_browser",
            identity_key="identity-browser",
            org_slug="org",
            repo_owner="octocat",
            repo_name="yudaiv3",
            environment="main",
            repo_branch="main",
            status="running",
            active_session_id=session.id,
            tunnel_url="http://sandbox.local/sbx_browser",
            lifecycle_metadata={},
        )
        db.add(sandbox)
        db.flush()
        db.add(
            SessionRuntime(
                runtime_id="rt_browser",
                session_id=session.id,
                sandbox_id=sandbox.id,
                status="running",
                tunnel_url=sandbox.tunnel_url,
            )
        )
        db.commit()
        db.refresh(session)

        hub = CapturingHub()
        orchestrator = SessionExecutionOrchestrator(
            broker=DummyBroker(),
            lifecycle=DummyLifecycle(),
            ws_hub=hub,
        )

        async def _run():
            payload = await orchestrator.start_browser_check(
                db,
                session=session,
                user_id=user.id,
                objective="Verify the frontend",
            )
            task = orchestrator._browser_check_tasks[session.session_id]
            await task
            return payload

        payload = asyncio.run(_run())
        db.expire_all()
        execution = db.query(AgentExecution).filter(AgentExecution.id == payload["execution_id"]).one()
        artifact = db.query(SessionArtifact).filter(SessionArtifact.session_id == session.id).one()
        card = db.query(ContextCard).filter(ContextCard.session_id == session.id).one()
        session_row = db.query(ChatSession).filter(ChatSession.id == session.id).one()

        assert payload["mode"] == BROWSER_CHECK_MODE
        assert execution.mode == BROWSER_CHECK_MODE
        assert execution.status == "complete"
        assert execution.output_summary["screenshot_path"].endswith("/screenshot.png")
        assert execution.output_summary["console_warning_count"] == 1
        assert artifact.artifact_type == "browser_check"
        assert artifact.bundle_path.endswith("browser-check.tar.gz")
        assert "Visual report: page rendered" in card.content
        assert (session_row.mode_metadata or {})["browser_check"]["status"] == "complete"
        assert any(event["msg_type"].value == "tool_call" for event in hub.events)
    finally:
        db.close()


def test_browser_check_mocked_broker_failure_does_not_terminate_sandbox(tmp_path, monkeypatch):
    db_path = tmp_path / "browser-failure.db"
    monkeypatch.setenv("YUDAI_IN_PROCESS_EXECUTION_FALLBACK", "true")
    monkeypatch.setenv("MSWEA_MODEL_NAME", "openrouter/x-ai/grok-4-fast")
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(mode_orchestrator_module, "SessionLocal", SessionLocal)

    class DummyLifecycle:
        def _get_latest_runtime(self, db, *, session_id=None, sandbox_id=None):
            query = db.query(SessionRuntime)
            if session_id is not None:
                query = query.filter(SessionRuntime.session_id == session_id)
            if sandbox_id is not None:
                query = query.filter(SessionRuntime.sandbox_id == sandbox_id)
            return query.order_by(SessionRuntime.id.desc()).first()

        def get_sandbox_or_404(self, db, sandbox_id):
            return db.query(Sandbox).filter(Sandbox.id == sandbox_id).one()

    class DummyBroker:
        async def run_command(self, db, *, session, command, cwd=None, env=None, timeout_seconds=1800, on_event=None):
            return {
                "sandbox_id": "sbx_browser_failure",
                "exit_code": 7,
                "stdout": "dev server failed",
                "stderr": "cannot start server",
                "duration_ms": 11,
            }

    async def _healthy(*_args, **_kwargs):
        return None

    monkeypatch.setattr(mode_orchestrator_module, "wait_for_sandbox_healthcheck", _healthy)
    db = SessionLocal()
    try:
        user = User(
            github_username="browser-failure",
            github_user_id="8105",
            email="browser-failure@example.com",
            display_name="Browser Failure",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        session = ChatSession(
            user_id=user.id,
            session_id="session_browser_failure",
            title="Browser Failure Session",
            repo_owner="octocat",
            repo_name="yudaiv3",
            repo_branch="main",
            repo_url="https://github.com/octocat/yudaiv3.git",
            runtime_workspace_path="/workspace/repo",
            is_active=True,
            total_messages=0,
            total_tokens=0,
            mode_metadata={},
        )
        db.add(session)
        db.flush()
        sandbox = Sandbox(
            id="sbx_browser_failure",
            identity_key="identity-browser-failure",
            org_slug="org",
            repo_owner="octocat",
            repo_name="yudaiv3",
            environment="main",
            repo_branch="main",
            status="running",
            active_session_id=session.id,
            tunnel_url="http://sandbox.local/sbx_browser_failure",
            lifecycle_metadata={},
        )
        db.add(sandbox)
        db.flush()
        db.add(
            SessionRuntime(
                runtime_id="rt_browser_failure",
                session_id=session.id,
                sandbox_id=sandbox.id,
                status="running",
                tunnel_url=sandbox.tunnel_url,
            )
        )
        db.commit()
        db.refresh(session)

        orchestrator = SessionExecutionOrchestrator(
            broker=DummyBroker(),
            lifecycle=DummyLifecycle(),
            ws_hub=DummyHub(),
        )

        async def _run():
            payload = await orchestrator.start_browser_check(
                db,
                session=session,
                user_id=user.id,
                objective="Verify the frontend",
            )
            task = orchestrator._browser_check_tasks[session.session_id]
            await task
            return payload

        payload = asyncio.run(_run())
        db.expire_all()
        execution = db.query(AgentExecution).filter(AgentExecution.id == payload["execution_id"]).one()
        sandbox_row = db.query(Sandbox).filter(Sandbox.id == sandbox.id).one()

        assert execution.status == "failed"
        assert "exit_code=7" in execution.error_message
        assert db.query(SessionArtifact).filter(SessionArtifact.session_id == session.id).count() == 0
        assert sandbox_row.status == "running"
    finally:
        db.close()


def _changed_files_output(files):
    return f"{CHANGED_FILES_START}\n{json.dumps(files)}\n{CHANGED_FILES_END}\n"


def _create_runtime_backed_session(db, *, session_id, user_suffix="contract"):
    user_number = sum(ord(char) for char in user_suffix)
    user = User(
        github_username=f"{user_suffix}-user",
        github_user_id=f"91{user_number}",
        email=f"{user_suffix}@example.com",
        display_name=f"{user_suffix.title()} User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session = ChatSession(
        user_id=user.id,
        session_id=session_id,
        title="MSWEA Contract Session",
        repo_owner="pranay5255",
        repo_name="YudaiV3",
        repo_branch="main",
        repo_url="https://github.com/pranay5255/YudaiV3.git",
        runtime_workspace_path="/workspace/repo",
        architect_issue_number=175,
        architect_issue_url="https://github.com/pranay5255/YudaiV3/issues/175",
        is_active=True,
        total_messages=0,
        total_tokens=0,
        mode_metadata={},
    )
    db.add(session)
    db.flush()
    sandbox = Sandbox(
        id=f"sbx_{session_id}",
        identity_key=f"identity-{session_id}",
        org_slug="org",
        repo_owner="pranay5255",
        repo_name="YudaiV3",
        environment="main",
        repo_branch="main",
        status="running",
        active_session_id=session.id,
        tunnel_url=f"http://sandbox.local/{session_id}",
        lifecycle_metadata={},
    )
    db.add(sandbox)
    db.flush()
    db.add(
        SessionRuntime(
            runtime_id=f"rt_{session_id}",
            session_id=session.id,
            sandbox_id=sandbox.id,
            status="running",
            tunnel_url=sandbox.tunnel_url,
        )
    )
    db.commit()
    db.refresh(session)
    return user, session


class ContractLifecycle:
    def __init__(self):
        self.issue_created = None
        self.pr_created = None
        self.finalized = None

    async def create_runtime_for_session(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("runtime should already exist")

    def _get_latest_runtime(self, db, *, session_id=None, sandbox_id=None):
        query = db.query(SessionRuntime)
        if session_id is not None:
            query = query.filter(SessionRuntime.session_id == session_id)
        if sandbox_id is not None:
            query = query.filter(SessionRuntime.sandbox_id == sandbox_id)
        return query.order_by(SessionRuntime.id.desc()).first()

    def get_sandbox_or_404(self, db, sandbox_id):
        return db.query(Sandbox).filter(Sandbox.id == sandbox_id).one()

    def mark_issue_created(self, db, *, session_public_id, user_id, issue_url, issue_number):
        self.issue_created = {
            "session_public_id": session_public_id,
            "user_id": user_id,
            "issue_url": issue_url,
            "issue_number": issue_number,
        }

    def mark_pr_created(self, db, *, session_db_id, session_public_id, user_id, pr_url, pr_number):
        self.pr_created = {
            "session_db_id": session_db_id,
            "session_public_id": session_public_id,
            "user_id": user_id,
            "pr_url": pr_url,
            "pr_number": pr_number,
        }

    async def finalize_session_execution(self, db, *, session, reason, execution_status, execution_id, artifact_source_paths):
        self.finalized = {
            "session_id": session.session_id,
            "reason": reason,
            "execution_status": execution_status,
            "execution_id": execution_id,
            "artifact_source_paths": list(artifact_source_paths),
        }
        return None


class ContractBroker:
    def __init__(self, *, architect_ready=True):
        self.architect_ready = architect_ready
        self.mode_calls = []
        self.summary_commands = 0

    async def run_command(self, db, *, session, command, cwd=None, env=None, timeout_seconds=1800, on_event=None):
        if "summary_path" in command:
            self.summary_commands += 1
            return {"sandbox_id": "sbx_contract", "exit_code": 0, "stdout": "", "stderr": "", "duration_ms": 1}

        if 'mode_name="architect"' in command:
            self.mode_calls.append("architect")
            payload = {
                "mode": "architect",
                "issue_number": 175,
                "issue_url": "https://github.com/pranay5255/YudaiV3/issues/175",
                "context_file": "/workspace/repo/.yudai/context.md",
                "questions": []
                if self.architect_ready
                else [{"prompt": "Which handoff metadata should Tester treat as mandatory?"}],
                "ready_for_tester": self.architect_ready,
            }
            return {
                "sandbox_id": "sbx_contract",
                "exit_code": 0,
                "stdout": json.dumps(payload) + "\n" + _changed_files_output([".yudai/context.md"]),
                "stderr": "",
                "duration_ms": 11,
            }

        if 'mode_name="tester"' in command:
            self.mode_calls.append("tester")
            payload = {
                "mode": "tester",
                "issue_number": 175,
                "context_file": "/workspace/repo/.yudai/context.md",
                "test_branch": "yudai/issue-175-tests",
                "tests_changed": ["backend/tests/test_mode_orchestrator.py"],
                "expected_failures": ["test_contract_handoff_fails_before_implementation"],
            }
            return {
                "sandbox_id": "sbx_contract",
                "exit_code": 0,
                "stdout": json.dumps(payload)
                + "\n"
                + _changed_files_output(["backend/tests/test_mode_orchestrator.py", ".yudai/context.md"]),
                "stderr": "",
                "duration_ms": 22,
            }

        if 'mode_name="coder"' in command:
            self.mode_calls.append("coder")
            payload = {
                "mode": "coder",
                "issue_number": 175,
                "context_file": "/workspace/repo/.yudai/context.md",
                "test_branch": "yudai/issue-175-tests",
                "pr_url": "https://github.com/pranay5255/YudaiV3/pull/211",
                "pr_number": 211,
                "tests_run": ["PYTHONPATH=backend pytest -q backend/tests/test_mode_orchestrator.py"],
            }
            return {
                "sandbox_id": "sbx_contract",
                "exit_code": 0,
                "stdout": json.dumps(payload)
                + "\n"
                + _changed_files_output(["backend/yudai/realtime/mode_orchestrator.py"]),
                "stderr": "",
                "duration_ms": 33,
            }

        raise AssertionError("unexpected command")


def test_architect_completion_creates_tester_stage_gate(tmp_path, monkeypatch):
    db_path = tmp_path / "contracts.db"
    monkeypatch.setenv("YUDAI_IN_PROCESS_EXECUTION_FALLBACK", "true")
    monkeypatch.setenv("MSWEA_MODEL_NAME", "openrouter/x-ai/grok-4-fast")
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(mode_orchestrator_module, "SessionLocal", SessionLocal)

    async def _healthy(*_args, **_kwargs):
        return None

    monkeypatch.setattr(mode_orchestrator_module, "wait_for_sandbox_healthcheck", _healthy)

    db = SessionLocal()
    try:
        user, session = _create_runtime_backed_session(
            db,
            session_id="session_contract_success",
            user_suffix="contract-success",
        )
        broker = ContractBroker()
        lifecycle = ContractLifecycle()
        orchestrator = SessionExecutionOrchestrator(
            broker=broker,
            lifecycle=lifecycle,
            ws_hub=DummyHub(),
        )

        async def _run():
            payload = await orchestrator.start_execution(
                db,
                session=session,
                user_id=user.id,
                objective="Harden the MSWEA contracts",
            )
            await orchestrator._session_tasks[session.session_id]
            return payload

        payload = asyncio.run(_run())
        db.expire_all()
        session_row = db.query(ChatSession).filter(ChatSession.id == session.id).one()
        contracts = (session_row.mode_metadata or {})["workflow_contracts"]
        mode_rows = (
            db.query(AgentExecution)
            .filter(
                AgentExecution.session_id == session.id,
                AgentExecution.id != payload["execution_id"],
            )
            .order_by(AgentExecution.created_at)
            .all()
        )

        question = db.query(UserQuestion).filter(UserQuestion.session_id == session.id).one()
        active_execution = (session_row.mode_metadata or {})["active_execution"]

        assert broker.mode_calls == ["architect"]
        assert broker.summary_commands == 1
        assert session_row.current_mode == "tester"
        assert session_row.mode_status == "waiting_for_input"
        assert session_row.architect_completed_at is not None
        assert session_row.tester_completed_at is None
        assert session_row.coder_pr_number is None
        assert contracts["contract_version"] == "mswea-mode-contract-v1"
        assert contracts["architect"]["ready_for_tester"] is True
        assert "tester" not in contracts
        assert question.status == UserQuestionStatus.PENDING.value
        assert question.question_metadata["origin"] == "stage_gate"
        assert question.question_metadata["approval_scope"] == "session_execution"
        assert question.question_metadata["target_type"] == "agent_stage"
        assert question.question_metadata["target_mode"] == "tester"
        assert question.question_metadata["required_actor"] == "session_user"
        assert question.question_metadata["admin_required"] is False
        assert question.question_metadata["from_mode"] == "architect"
        assert question.question_metadata["next_mode"] == "tester"
        assert question.question_metadata["pending_tool"] == "run_tester_mode"
        assert active_execution["waiting_for_input"] is True
        assert active_execution["status"] == "waiting_for_input"
        assert {row.mode: row.output_summary["contract_version"] for row in mode_rows} == {
            "architect": "mswea-mode-contract-v1",
        }
        assert lifecycle.pr_created is None
        assert lifecycle.finalized is None
    finally:
        db.close()


def test_architect_questions_pause_pipeline_and_resume_same_mode(tmp_path, monkeypatch):
    db_path = tmp_path / "contracts-pause.db"
    monkeypatch.setenv("YUDAI_IN_PROCESS_EXECUTION_FALLBACK", "true")
    monkeypatch.setenv("MSWEA_MODEL_NAME", "openrouter/x-ai/grok-4-fast")
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(mode_orchestrator_module, "SessionLocal", SessionLocal)

    async def _healthy(*_args, **_kwargs):
        return None

    monkeypatch.setattr(mode_orchestrator_module, "wait_for_sandbox_healthcheck", _healthy)

    db = SessionLocal()
    try:
        user, session = _create_runtime_backed_session(
            db,
            session_id="session_contract_pause",
            user_suffix="contract-pause",
        )
        broker = ContractBroker(architect_ready=False)
        orchestrator = SessionExecutionOrchestrator(
            broker=broker,
            lifecycle=ContractLifecycle(),
            ws_hub=DummyHub(),
        )

        async def _run_until_pause():
            payload = await orchestrator.start_execution(
                db,
                session=session,
                user_id=user.id,
                objective="Harden the MSWEA contracts",
            )
            await orchestrator._session_tasks[session.session_id]
            return payload

        payload = asyncio.run(_run_until_pause())
        db.expire_all()
        session_row = db.query(ChatSession).filter(ChatSession.id == session.id).one()
        question = db.query(UserQuestion).filter(UserQuestion.session_id == session.id).one()
        active_execution = (session_row.mode_metadata or {})["active_execution"]

        assert broker.mode_calls == ["architect"]
        assert session_row.current_mode == "architect"
        assert session_row.mode_status == "waiting_for_input"
        assert session_row.architect_completed_at is None
        assert session_row.tester_completed_at is None
        assert question.status == UserQuestionStatus.PENDING.value
        assert question.question_metadata["origin"] == "mswea_architect_contract"
        assert active_execution["waiting_for_input"] is True
        assert active_execution["status"] == "waiting_for_input"

        question.status = UserQuestionStatus.ANSWERED.value
        question.answer_text = "Tester must treat test branch and expected failures as mandatory."
        question.answered_at = mode_orchestrator_module.utc_now()
        metadata = dict(session_row.mode_metadata or {})
        metadata["pending_question_ids"] = []
        session_row.mode_metadata = metadata
        session_row.mode_status = "idle"
        db.commit()

        scheduled = {}
        orchestrator._schedule_execution_task = lambda **kwargs: scheduled.update(kwargs)
        resume_payload = asyncio.run(
            orchestrator.resume_execution(
                db,
                session=session_row,
                user_id=user.id,
                objective="Continue after Architect clarification.",
            )
        )

        assert resume_payload["mode"] == "architect"
        assert scheduled["execution_id"] == payload["execution_id"]
        assert scheduled.get("max_modes") is None
        assert "Clarifications from Q&A" in scheduled["objective"]
    finally:
        db.close()
