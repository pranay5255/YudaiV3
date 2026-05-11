import json
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/context-probe-tests.db")

from yudai.daifuUserAgent.context_probe import (  # noqa: E402
    ContextProbeService,
    ProbeRequest,
    ProbeResult,
)
from yudai.models import (  # noqa: E402
    Base,
    ChatMessage,
    ChatSession,
    User,
    UserIssue,
    UserQuestion,
    UserQuestionStatus,
)


def _probe_db():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    user = User(
        github_username="probe-user",
        github_user_id="81001",
        email="probe@example.com",
        display_name="Probe User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session = ChatSession(
        user_id=user.id,
        session_id="session_probe_task",
        title="Probe Session",
        repo_owner="octocat",
        repo_name="yudaiv3",
        repo_branch="feature/auth",
        is_active=True,
        total_messages=0,
        total_tokens=0,
        mode_metadata={},
        architect_issue_number=173,
        architect_issue_url="https://github.com/octocat/yudaiv3/issues/173",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return db, user, session


def test_format_as_context_includes_successful_probe_outputs_only():
    context = ContextProbeService.format_as_context(
        [
            ProbeResult(
                probe_id="probe_done",
                query="how auth connects to the DB",
                status="completed",
                output_text="Auth routes call `get_db()` in backend/auth/auth_routes.py:42.",
                summary="Auth uses FastAPI dependencies.",
                files=["backend/auth/auth_routes.py"],
                duration_ms=123,
            ),
            ProbeResult(
                probe_id="probe_failed",
                query="failing query",
                status="error",
                output_text="",
                summary=None,
                files=[],
                duration_ms=1,
            ),
        ]
    )

    assert context is not None
    assert '[CODE_EXPLORATION_CONTEXT]' in context
    assert '## Query: "how auth connects to the DB"' in context
    assert "backend/auth/auth_routes.py" in context
    assert "failing query" not in context


def test_build_probe_command_uses_probe_config_and_query(tmp_path, monkeypatch):
    monkeypatch.setenv("MSWEA_MODEL_NAME", "openrouter/x-ai/grok-4-fast")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mini = bin_dir / "mini"
    mini.write_text("#!/usr/bin/env bash\nprintf 'fake mini\\n'\n", encoding="utf-8")
    mini.chmod(0o755)

    workspace = tmp_path / "repo"
    service = ContextProbeService(broker=object())
    command = service._build_probe_command(
        ProbeRequest(probe_id="probe_test", query="How does auth connect to DB?"),
        str(workspace),
    )

    env = os.environ.copy()
    task_text = "\n".join(
        [
            "Answer this code exploration question:",
            "How does auth connect to DB?",
            "",
            "Session metadata:",
            "- Session: session_probe_task",
            "- Repository: octocat/yudaiv3",
        ]
    )

    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
            "WORKSPACE_PATH": str(workspace),
            "YUDAI_PROBE_ID": "probe_test",
            "YUDAI_PROBE_OUTPUT": str(workspace / ".yudai" / "probes" / "probe_test.md"),
            "MSWEA_PROBE_QUERY": task_text,
            "MSWEA_MODEL_NAME": "openrouter/x-ai/grok-4-fast",
            "YUDAI_MSWEA_COMMAND_PROBE": "1",
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
    assert argv[1:3] == ["-c", "/app/mswea_mode_configs/probe/config.yaml"]
    assert "-y" in argv
    assert argv[argv.index("-m") + 1] == "openrouter/x-ai/grok-4-fast"
    assert "How does auth connect to DB?" in argv[argv.index("-t") + 1]
    assert "Session metadata:" in argv[argv.index("-t") + 1]
    assert payload["output_file"] == str(workspace / ".yudai" / "probes" / "probe_test.md")
    assert (workspace / ".yudai" / "probes" / "probe_test.query.txt").is_file()


def test_build_probe_task_includes_bounded_session_context():
    db, user, session = _probe_db()
    try:
        issue = UserIssue(
            user_id=user.id,
            issue_id="issue_probe_context",
            title="Fix auth callback",
            description="Auth callback fails after reconnect.",
            issue_text_raw="Fix auth callback behavior and preserve session tokens.",
            issue_steps=["Inspect auth", "Patch callback"],
            session_id=session.session_id,
            repo_owner="octocat",
            repo_name="yudaiv3",
            priority="medium",
            status="pending",
            tokens_used=1,
        )
        question = UserQuestion(
            question_id="q_probe_answered",
            session_id=session.id,
            user_id=user.id,
            mode=None,
            question_text="Which flow?",
            options=[{"id": "jwt", "label": "JWT"}],
            multi_select=False,
            selected_option_ids=["jwt"],
            answer_text="Focus on JWT refresh.",
            status=UserQuestionStatus.ANSWERED.value,
        )
        db.add(issue)
        db.add(question)
        for index in range(20):
            db.add(
                ChatMessage(
                    session_id=session.id,
                    message_id=f"msg_probe_{index}",
                    message_text=("message " + str(index) + " ") * 80,
                    sender_type="user" if index % 2 == 0 else "assistant",
                    role="user" if index % 2 == 0 else "assistant",
                    tokens=80,
                )
            )
        db.commit()

        task = ContextProbeService._build_probe_task(
            db,
            session=session,
            query="Find the auth callback and token refresh flow.",
        )

        assert "Find the auth callback and token refresh flow." in task
        assert "- Session: session_probe_task" in task
        assert "- Repository: octocat/yudaiv3" in task
        assert "- Branch: feature/auth" in task
        assert "Linked GitHub issue:" in task
        assert "issue_probe_context" in task
        assert "Answered clarification questions:" in task
        assert "Focus on JWT refresh." in task
        assert "Conversation context:" in task
        assert len(task) <= ContextProbeService.MAX_PROBE_TASK_CHARS + len("\n[truncated]")
    finally:
        db.close()
