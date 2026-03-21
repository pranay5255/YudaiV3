import asyncio
import json
import os
from pathlib import Path
import sys

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Realtime lifecycle imports db.database.SessionLocal at import time.
os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/realtime-lifecycle-tests.db")

from models import (  # noqa: E402
    Base,
    ChatSession,
    Sandbox,
    SandboxStatus,
    SessionArtifact,
    SessionRuntime,
    SessionRuntimeStatus,
    Solve,
    SolveRun,
    User,
)
from realtime.cache_store import SessionCacheStore  # noqa: E402
from realtime.lifecycle import RealtimeLifecycleService  # noqa: E402


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("SANDBOX_GIT_ROOT", str(tmp_path / "repos"))
    monkeypatch.setenv("SANDBOX_TUNNEL_TEMPLATE", "http://sandbox.local/{sandbox_id}")

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def lifecycle_service(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("SANDBOX_GIT_ROOT", str(tmp_path / "repos"))
    monkeypatch.setenv("SANDBOX_TUNNEL_TEMPLATE", "http://sandbox.local/{sandbox_id}")

    store = SessionCacheStore()
    service = RealtimeLifecycleService(cache_store=store)

    # Avoid network/git side effects in tests.
    service.sandbox_manager.ensure_git_bootstrap = lambda **_: {"status": "skipped"}
    service._start_probe_if_possible = lambda **_: None
    service._stop_probe_if_possible = lambda *_: None
    return service


def _create_user(db, username: str, github_id: str) -> User:
    user = User(
        github_username=username,
        github_user_id=github_id,
        email=f"{username}@example.com",
        display_name=username,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_session(
    db,
    user: User,
    *,
    session_id: str,
    repo_owner: str,
    repo_name: str,
    repo_branch: str,
) -> ChatSession:
    session = ChatSession(
        user_id=user.id,
        session_id=session_id,
        title=f"Chat - {repo_owner}/{repo_name}",
        repo_owner=repo_owner,
        repo_name=repo_name,
        repo_branch=repo_branch,
        is_active=True,
        total_messages=0,
        total_tokens=0,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def test_single_active_editor_conflict(db_session, lifecycle_service):
    db = db_session

    user_a = _create_user(db, "alice", "1001")
    user_b = _create_user(db, "bob", "1002")

    session_a = _create_session(
        db,
        user_a,
        session_id="session_a",
        repo_owner="octocat",
        repo_name="yudaiv3",
        repo_branch="main",
    )
    session_b = _create_session(
        db,
        user_b,
        session_id="session_b",
        repo_owner="octocat",
        repo_name="yudaiv3",
        repo_branch="main",
    )

    asyncio.run(
        lifecycle_service.create_runtime_for_session(
            db,
            session=session_a,
            user_id=user_a.id,
            org="yudai",
            repo_owner="octocat",
            repo_name="yudaiv3",
            environment="main",
            repo_branch="main",
            repo_url=None,
        )
    )
    db.commit()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            lifecycle_service.create_runtime_for_session(
                db,
                session=session_b,
                user_id=user_b.id,
                org="yudai",
                repo_owner="octocat",
                repo_name="yudaiv3",
                environment="main",
                repo_branch="main",
                repo_url=None,
            )
        )

    assert exc.value.status_code == 409


def test_finalize_session_execution_exports_artifact_and_terminates(db_session, lifecycle_service, tmp_path):
    db = db_session

    user = _create_user(db, "charlie", "2001")
    session = _create_session(
        db,
        user,
        session_id="session_complete",
        repo_owner="octocat",
        repo_name="yudaiv3",
        repo_branch="main",
    )

    envelope = asyncio.run(
        lifecycle_service.create_runtime_for_session(
            db,
            session=session,
            user_id=user.id,
            org="yudai",
            repo_owner="octocat",
            repo_name="yudaiv3",
            environment="main",
            repo_branch="main",
            repo_url=None,
        )
    )
    db.commit()

    trajectory_path = tmp_path / "run.traj.json"
    trajectory_path.write_text('{"messages": []}\n', encoding="utf-8")

    solve = Solve(
        id="solve_test",
        user_id=user.id,
        session_id=session.id,
        repo_url="https://github.com/octocat/yudaiv3",
        issue_number=42,
        base_branch="main",
        status="completed",
        matrix={},
    )
    db.add(solve)
    db.flush()

    db.add(
        SolveRun(
            id="run_test",
            solve_id=solve.id,
            model="test-model",
            temperature=0.1,
            max_edits=1,
            evolution="baseline",
            status="completed",
            trajectory_data={"local_path": str(trajectory_path)},
        )
    )
    db.commit()

    lifecycle_service.mark_issue_created(
        db,
        session_public_id=session.session_id,
        user_id=user.id,
        issue_url="https://github.com/octocat/yudaiv3/issues/42",
        issue_number=42,
    )

    runtime_before_pr = (
        db.query(SessionRuntime)
        .filter(SessionRuntime.session_id == session.id)
        .order_by(SessionRuntime.id.desc())
        .first()
    )
    assert runtime_before_pr is not None
    assert runtime_before_pr.completion_issue_created is True
    assert runtime_before_pr.completion_detected is False

    lifecycle_service.mark_pr_created(
        db,
        session_db_id=session.id,
        session_public_id=None,
        user_id=user.id,
        pr_url="https://github.com/octocat/yudaiv3/pull/99",
        pr_number=99,
    )
    bundle_path = tmp_path / "sandbox-workflow.tar.gz"
    metadata_path = tmp_path / "sandbox-workflow.metadata.json"
    bundle_path.write_bytes(b"bundle")
    metadata_path.write_text('{"ok": true}\n', encoding="utf-8")

    async def _fake_download_and_export_bundle(**kwargs):
        return {
            "metadata": {
                "cache_manifest_path": str(lifecycle_service.cache_store.manifest_path(session.session_id)),
                "sandbox_bundle": {
                    "metadata_path": str(metadata_path),
                },
            },
            "metadata_path": str(metadata_path),
            "bundle_path": str(bundle_path),
            "bundle_sha256": "abc123",
            "manifest_sha256": "def456",
            "bundle_size": bundle_path.stat().st_size,
        }

    lifecycle_service.cache_store.download_and_export_bundle = _fake_download_and_export_bundle

    artifact_info = asyncio.run(
        lifecycle_service.finalize_session_execution(
            db,
            session=session,
            reason="workflow_complete",
            execution_status="complete",
            execution_id="execp_test_complete",
            artifact_source_paths=[".yudai/executions/execp_test_complete"],
        )
    )
    db.commit()

    runtime = (
        db.query(SessionRuntime)
        .filter(SessionRuntime.session_id == session.id)
        .order_by(SessionRuntime.id.desc())
        .first()
    )
    assert runtime is not None
    assert runtime.completion_issue_created is True
    assert runtime.completion_pr_created is True
    assert runtime.completion_detected is True
    assert runtime.status == SessionRuntimeStatus.TERMINATED.value
    assert artifact_info is not None
    assert artifact_info["bundle_path"] == str(bundle_path)
    assert artifact_info["metadata_path"] == str(metadata_path)

    sandbox = db.query(Sandbox).filter(Sandbox.id == envelope.sandbox.id).first()
    assert sandbox is not None
    assert sandbox.status == SandboxStatus.TERMINATED.value

    artifact = (
        db.query(SessionArtifact)
        .filter(SessionArtifact.session_id == session.id)
        .order_by(SessionArtifact.id.desc())
        .first()
    )
    assert artifact is not None
    assert artifact.bundle_path is not None
    assert artifact.cache_manifest_path is not None

    bundle_path = Path(artifact.bundle_path)
    manifest_path = Path(artifact.cache_manifest_path)
    assert bundle_path.exists()
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    event_names = [event["event_name"] for event in manifest.get("events", [])]
    assert "github_issue_create" in event_names
    assert "pr_create" in event_names
    assert "sandbox_terminate" in event_names
