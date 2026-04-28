import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/mode-orchestrator-tests.db")

from yudai.models import AgentExecution, Base, ChatSession, User  # noqa: E402
from yudai.realtime.mode_orchestrator import SessionExecutionOrchestrator  # noqa: E402


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
        assert payload["status"] == "running"
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
        scheduled: dict[str, object] = {}
        orchestrator._schedule_execution_task = lambda **kwargs: scheduled.update(kwargs)

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
        assert scheduled["max_modes"] == 1
        assert execution.execution_metadata["trigger"] == "daifu_tool:run_architect_mode"
        assert execution.execution_metadata["max_modes"] == 1
        assert (session.mode_metadata or {})["active_execution"]["max_modes"] == 1
    finally:
        db.close()


def test_build_mswea_command_uses_official_mini_cli_probe(tmp_path, monkeypatch):
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


def test_parse_and_merge_extended_stage_result_fields():
    orchestrator = SessionExecutionOrchestrator(
        broker=object(),
        lifecycle=object(),
        ws_hub=DummyHub(),
    )
    payload = {
        "mode": "tester",
        "issue_number": 123,
        "test_branch": "yudai/issue-123-tests",
        "stage_result": {
            "status": "complete",
            "summary": "Added regression tests for reconnect handling.",
            "issue_number": 123,
            "test_branch": "yudai/issue-123-tests",
            "tests_changed": ["backend/tests/test_reconnect.py"],
            "expected_failures": ["test_reconnect_preserves_session"],
            "tests_run": ["uv run pytest backend/tests/test_reconnect.py"],
            "setup_commands": ["uv sync"],
            "ready_for_tester": True,
        },
    }

    parsed = orchestrator.parse_mswea_output(
        "stdout\nYUDAI_STAGE_RESULT: " + json.dumps(payload)
    )

    assert parsed["issue_number"] == 123
    assert parsed["test_branch"] == "yudai/issue-123-tests"
    assert parsed["stage_result"]["tests_changed"] == [
        "backend/tests/test_reconnect.py"
    ]

    session = ChatSession(
        user_id=1,
        session_id="session_stage_result_merge",
        title="Stage Result Merge",
        repo_owner="octocat",
        repo_name="yudaiv3",
        repo_branch="main",
        is_active=True,
        total_messages=0,
        total_tokens=0,
        mode_metadata={},
    )
    merged = orchestrator._merge_workflow_stage_result(
        session,
        mode="tester",
        result={**parsed, "execution_id": "exec_stage", "exit_code": 0},
    )

    assert merged["tests_changed"] == ["backend/tests/test_reconnect.py"]
    assert merged["expected_failures"] == ["test_reconnect_preserves_session"]
    assert merged["tests_run"] == ["uv run pytest backend/tests/test_reconnect.py"]
    assert merged["setup_commands"] == ["uv sync"]
    assert merged["ready_for_tester"] is True
    assert session.mode_metadata["workflow"]["stage_results"]["tester"] == merged
