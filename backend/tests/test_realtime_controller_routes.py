import asyncio
import json
import os
from pathlib import Path
import sys
import types

from fastapi import HTTPException
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/realtime-controller-tests.db")


def _install_import_stubs() -> None:
    fake_chatops_module = types.ModuleType("yudai.daifuUserAgent.ChatOps")

    class DummyChatOps:  # pragma: no cover - test import stub only
        pass

    fake_chatops_module.ChatOps = DummyChatOps
    sys.modules["yudai.daifuUserAgent.ChatOps"] = fake_chatops_module


_install_import_stubs()

from yudai.config.realtime_flags import RealtimeFeatureFlags  # noqa: E402
from yudai.config import get_sandbox_config  # noqa: E402
from yudai.models import AgentExecution, AuthToken, Base, ChatSession, SandboxExecutionEvent, SandboxExecutionRun, User  # noqa: E402
from yudai.realtime.cache_store import SessionCacheStore  # noqa: E402
from yudai.realtime.controller_routes import (  # noqa: E402
    SandboxEventRequest,
    SandboxCompletionRequest,
    complete_sandbox_execution,
    delete_sandbox,
    ensure_runtime_for_session,
    get_runtime_for_session,
    get_sandbox,
    record_sandbox_event,
    resolve_tunnel,
    unified_session_websocket,
)
from yudai.realtime.lifecycle import RealtimeLifecycleService  # noqa: E402
import yudai.realtime.lifecycle as lifecycle_module  # noqa: E402
from yudai.realtime.schemas import RuntimeEnsureRequest  # noqa: E402


@pytest.fixture
def db_and_user(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("SANDBOX_GIT_ROOT", str(tmp_path / "repos"))
    monkeypatch.setenv("SANDBOX_TUNNEL_TEMPLATE", "http://sandbox.local/{sandbox_id}")

    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    db = SessionLocal()
    user = User(
        github_username="tester",
        github_user_id="5001",
        email="tester@example.com",
        display_name="Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session = ChatSession(
        user_id=user.id,
        session_id="session_controller_test",
        title="Controller Session",
        repo_owner="octocat",
        repo_name="yudaiv3",
        repo_branch="main",
        is_active=True,
        total_messages=0,
        total_tokens=0,
    )
    db.add(session)
    db.commit()

    service = RealtimeLifecycleService(cache_store=SessionCacheStore())
    service.sandbox_manager.ensure_git_bootstrap = lambda **_: {"status": "skipped"}
    service._start_probe_if_possible = lambda **_: None
    service._stop_probe_if_possible = lambda *_: None
    monkeypatch.setattr(
        lifecycle_module,
        "get_realtime_feature_flags",
        lambda: RealtimeFeatureFlags(
            controller_split_enabled=True,
            controller_broker_enabled=False,
            sandbox_internal_exec_enabled=True,
            mode_orchestrator_enabled=True,
            ws_chat_enabled=False,
            modal_provisioning_enabled=False,
            ws_unified_enabled=False,
            contract_version="test",
        ),
    )
    lifecycle_module._service_singleton = service

    try:
        yield db, user, session
    finally:
        lifecycle_module._service_singleton = None
        db.close()


def test_runtime_ensure_and_resolve_tunnel(db_and_user):
    db, user, session = db_and_user

    runtime_response = asyncio.run(
        ensure_runtime_for_session(
            session_id=session.session_id,
            request=RuntimeEnsureRequest(
                org="yudai",
                repo_owner="octocat",
                repo_name="yudaiv3",
                environment="main",
                repo_branch="main",
                repo_url="file:///tmp/unused",
            ),
            db=db,
            current_user=user,
        ),
    )

    assert runtime_response.runtime_id.startswith("rt_")
    assert runtime_response.sandbox_id.startswith("sbx_")
    assert runtime_response.tunnel_url is None

    sandbox_id = runtime_response.sandbox_id

    resolve_response = resolve_tunnel(
        sandbox_id=sandbox_id,
        db=db,
        current_user=user,
    )
    assert resolve_response.sandbox_id == sandbox_id
    assert resolve_response.token_strategy == "session_jwt_passthrough"

    sandbox_response = get_sandbox(
        sandbox_id=sandbox_id,
        db=db,
        current_user=user,
    )
    assert sandbox_response.status == "running"


def test_runtime_ensure_forwards_user_github_token(db_and_user):
    db, user, session = db_and_user

    db.add(
        AuthToken(
            user_id=user.id,
            access_token="gho_test_access_token",
            is_active=True,
        )
    )
    db.commit()

    captured: dict[str, object] = {}
    service = lifecycle_module.get_realtime_lifecycle_service()
    original_create_runtime = service.create_runtime_for_session

    async def _capture_create_runtime(*args, **kwargs):
        captured.update(kwargs)
        return await original_create_runtime(*args, **kwargs)

    service.create_runtime_for_session = _capture_create_runtime

    runtime_response = asyncio.run(
        ensure_runtime_for_session(
            session_id=session.session_id,
            request=RuntimeEnsureRequest(
                org="yudai",
                repo_owner="octocat",
                repo_name="yudaiv3",
                environment="main",
                repo_branch="main",
                repo_url="https://github.com/octocat/yudaiv3.git",
            ),
            db=db,
            current_user=user,
        ),
    )

    assert runtime_response.runtime_id.startswith("rt_")
    assert captured["github_token"] == "gho_test_access_token"


def test_runtime_detail_returns_not_provisioned_when_runtime_absent(db_and_user):
    db, user, session = db_and_user

    runtime_response = get_runtime_for_session(
        session_id=session.session_id,
        db=db,
        current_user=user,
    )

    assert runtime_response.status == "not_provisioned"
    assert runtime_response.runtime_id is None
    assert runtime_response.sandbox_id is None
    assert runtime_response.identity_key is None


def test_sandbox_completion_callback_validates_secret_and_is_idempotent(db_and_user, monkeypatch):
    db, user, session = db_and_user
    monkeypatch.setenv("CONTROLLER_CALLBACK_SECRET", "callback-secret")
    get_sandbox_config.cache_clear()

    execution = AgentExecution(
        id="exec_callback_mode",
        session_id=session.id,
        mode="architect",
        status="running",
        execution_plan=["Run Architect"],
        execution_metadata={"pipeline_execution_id": "exec_pipeline"},
    )
    db.add(execution)
    db.commit()

    request = SandboxCompletionRequest(
        session_id=session.session_id,
        sandbox_job_id="sbjob_1",
        mode_execution_id=execution.id,
        status="complete",
        exit_code=0,
        stdout='{"status":"complete","issue_number":42}\n',
        stderr="",
        duration_ms=25,
    )

    with pytest.raises(HTTPException) as exc_info:
        complete_sandbox_execution(
            mode_execution_id=execution.id,
            request=request,
            db=db,
            x_controller_callback_secret="wrong",
        )
    assert exc_info.value.status_code == 401

    accepted = complete_sandbox_execution(
        mode_execution_id=execution.id,
        request=request,
        db=db,
        x_controller_callback_secret="callback-secret",
    )
    assert accepted["status"] == "accepted"

    db.expire_all()
    updated = db.query(AgentExecution).filter(AgentExecution.id == execution.id).one()
    completion = updated.execution_metadata["sandbox_completion"]
    assert completion["exit_code"] == 0
    assert completion["parsed_payload"]["issue_number"] == 42

    duplicate = complete_sandbox_execution(
        mode_execution_id=execution.id,
        request=request,
        db=db,
        x_controller_callback_secret="callback-secret",
    )
    assert duplicate["status"] == "duplicate"


def test_sandbox_callbacks_persist_run_and_events(db_and_user, monkeypatch):
    db, user, session = db_and_user
    monkeypatch.setenv("CONTROLLER_CALLBACK_SECRET", "callback-secret")
    get_sandbox_config.cache_clear()

    execution = AgentExecution(
        id="exec_callback_durable",
        session_id=session.id,
        mode="tester",
        status="running",
        execution_plan=["Run Tester"],
        execution_metadata={"pipeline_execution_id": "exec_pipeline_durable"},
    )
    db.add(execution)
    db.commit()

    event_request = SandboxEventRequest(
        session_id=session.session_id,
        controller_job_id="ctrljob_durable",
        sandbox_job_id="sbjob_durable",
        mode_execution_id=execution.id,
        attempt=1,
        sequence=1,
        event="stdout",
        data="hello",
    )
    accepted = asyncio.run(
        record_sandbox_event(
            request=event_request,
            db=db,
            x_controller_callback_secret="callback-secret",
        )
    )
    assert accepted["status"] == "accepted"

    completion_request = SandboxCompletionRequest(
        session_id=session.session_id,
        controller_job_id="ctrljob_durable",
        sandbox_job_id="sbjob_durable",
        mode_execution_id=execution.id,
        status="complete",
        exit_code=0,
        stdout='{"status":"complete","test_branch":"tests"}',
        stderr="",
        duration_ms=12,
        sequence=2,
    )
    complete_sandbox_execution(
        mode_execution_id=execution.id,
        request=completion_request,
        db=db,
        x_controller_callback_secret="callback-secret",
    )

    run = db.query(SandboxExecutionRun).filter(SandboxExecutionRun.controller_job_id == "ctrljob_durable").one()
    assert run.status == "complete"
    assert run.exit_code == 0
    assert run.parsed_payload["test_branch"] == "tests"
    event = db.query(SandboxExecutionEvent).filter(SandboxExecutionEvent.controller_job_id == "ctrljob_durable").one()
    assert event.sequence == 1
    assert event.data == "hello"


def test_terminated_sandbox_returns_hard_error(db_and_user):
    db, user, session = db_and_user

    runtime_response = asyncio.run(
        ensure_runtime_for_session(
            session_id=session.session_id,
            request=RuntimeEnsureRequest(
                org="yudai",
                repo_owner="octocat",
                repo_name="yudaiv3",
                environment="main",
                repo_branch="main",
                repo_url="file:///tmp/unused",
            ),
            db=db,
            current_user=user,
        ),
    )

    sandbox_id = runtime_response.sandbox_id

    delete_response = delete_sandbox(
        sandbox_id=sandbox_id,
        db=db,
        current_user=user,
    )
    assert delete_response.status_code == 204

    with pytest.raises(HTTPException) as exc:
        resolve_tunnel(
            sandbox_id=sandbox_id,
            db=db,
            current_user=user,
        )

    assert exc.value.status_code == 410
    assert exc.value.detail.get("code") == "TUNNEL_TERMINATED"


def test_runtime_detail_requires_session_owner(db_and_user):
    db, user, session = db_and_user

    runtime_response = asyncio.run(
        ensure_runtime_for_session(
            session_id=session.session_id,
            request=RuntimeEnsureRequest(
                org="yudai",
                repo_owner="octocat",
                repo_name="yudaiv3",
                environment="main",
                repo_branch="main",
                repo_url="file:///tmp/unused",
            ),
            db=db,
            current_user=user,
        ),
    )
    assert runtime_response.sandbox_id.startswith("sbx_")

    other_user = User(
        github_username="intruder",
        github_user_id="5002",
        email="intruder@example.com",
        display_name="Intruder",
    )
    db.add(other_user)
    db.commit()
    db.refresh(other_user)

    with pytest.raises(HTTPException) as exc:
        get_runtime_for_session(
            session_id=session.session_id,
            db=db,
            current_user=other_user,
        )

    assert exc.value.status_code == 404


def test_unified_websocket_rejects_missing_internal_auth(db_and_user):
    db, _user, session = db_and_user

    class FakeWebSocket:
        def __init__(self):
            self.closed = []

        async def close(self, code=None, reason=None):
            self.closed.append((code, reason))

    websocket = FakeWebSocket()

    asyncio.run(
        unified_session_websocket(
            websocket=websocket,
            session_id=session.session_id,
            internal_secret="",
            internal_user_id="",
            db=db,
        )
    )

    assert websocket.closed == [(4401, "invalid_internal_auth")]


def test_unified_websocket_accepts_valid_internal_identity(
    db_and_user,
    monkeypatch,
):
    db, user, session = db_and_user
    monkeypatch.setenv("YUDAI_INTERNAL_MIDDLEWARE_SECRET", "internal-test-secret")
    original_sleep = asyncio.sleep

    async def fast_sleep(_seconds):
        await original_sleep(0)

    monkeypatch.setattr("yudai.realtime.controller_routes.asyncio.sleep", fast_sleep)

    class FakeWebSocket:
        def __init__(self):
            self.accepted = False
            self.closed = []
            self.sent = []

        async def accept(self):
            self.accepted = True

        async def close(self, code=None, reason=None):
            self.closed.append((code, reason))

        async def send_text(self, text):
            self.sent.append(text)

        async def receive_text(self):
            raise RuntimeError("client disconnected")

    websocket = FakeWebSocket()

    asyncio.run(
        unified_session_websocket(
            websocket=websocket,
            session_id=session.session_id,
            internal_secret="internal-test-secret",
            internal_user_id=str(user.id),
            db=db,
        )
    )

    assert websocket.accepted is True
    sent_types = [json.loads(message).get("type") for message in websocket.sent]
    assert "status" in sent_types
    assert "mode_event" in sent_types
