from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/ws-control-plane-tests.db")

from yudai.daifuUserAgent.llm_service import LLMService  # noqa: E402
from yudai.daifuUserAgent.session_actions import SessionActionService  # noqa: E402
from yudai.models import (  # noqa: E402
    Base,
    ChatSession,
    SessionModeStatus,
    User,
    WorkflowContextUpdateRequest,
    WorkflowIssueRequest,
)
from yudai.realtime.schemas import RuntimeEnsureRequest  # noqa: E402
from yudai.realtime.ws_protocol import WSMessageType, build_envelope  # noqa: E402
from yudai import test_routes  # noqa: E402


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDBOX_GIT_ROOT", str(tmp_path / "repos"))
    monkeypatch.setenv("SANDBOX_CACHE_ROOT", str(tmp_path / "cache"))
    monkeypatch.setenv("SANDBOX_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("SANDBOX_TUNNEL_TEMPLATE", "http://sandbox.local/{sandbox_id}")
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_local()
    try:
        yield db
    finally:
        db.close()


def _user_and_session(db):
    user = User(
        github_username="ws-user",
        github_user_id="ws-user-id",
        email="ws@example.com",
        display_name="WS User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    session = ChatSession(
        user_id=user.id,
        session_id="session_ws",
        title="WS Session",
        repo_owner="octocat",
        repo_name="yudaiv3",
        repo_branch="main",
        repo_url="https://github.com/octocat/yudaiv3.git",
        runtime_workspace_path="/workspace/repo",
        is_active=True,
        total_messages=0,
        total_tokens=0,
        mode_status=SessionModeStatus.IDLE.value,
        mode_metadata={},
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return user, session


def test_ws_envelope_preserves_request_id():
    raw = build_envelope(
        WSMessageType.ACK,
        {"ok": True},
        request_id="req_123",
    )
    payload = json.loads(raw)
    assert payload["type"] == "ack"
    assert payload["request_id"] == "req_123"
    assert payload["payload"]["ok"] is True


def test_test_api_disabled_by_default(db_session, monkeypatch):
    monkeypatch.delenv("YUDAI_TEST_API_ENABLED", raising=False)
    with pytest.raises(test_routes.HTTPException) as exc:
        test_routes.create_test_session(
            test_routes.TestSessionCreateRequest(),
            db=db_session,
        )
    assert exc.value.status_code == 404


def test_test_api_creates_session_token_without_github_oauth(db_session, monkeypatch):
    monkeypatch.setenv("YUDAI_TEST_API_ENABLED", "true")
    monkeypatch.setenv("NODE_ENV", "development")

    response = test_routes.create_test_session(
        test_routes.TestSessionCreateRequest(username="ws-smoke"),
        db=db_session,
    )

    assert response.session_token
    assert response.session_id.startswith("session_test_")
    assert db_session.query(User).filter(User.id == response.user_id).one()


def test_fake_llm_stream_response(monkeypatch):
    monkeypatch.setenv("YUDAI_TEST_FAKE_LLM", "true")

    async def _collect():
        chunks = []
        async for chunk in LLMService.stream_response("hello"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(_collect())
    assert len(chunks) >= 2
    assert "backend fake mode" in "".join(chunks)


def test_session_actions_workflow_round_trip(db_session):
    user, session = _user_and_session(db_session)
    actions = SessionActionService(db_session, user)

    issue_response = actions.select_workflow_issue(
        session.session_id,
        WorkflowIssueRequest(
            number=88,
            title="Wire websocket commands",
            html_url="https://github.com/octocat/yudaiv3/issues/88",
            labels=["backend", "ws"],
        ),
    )
    context_response = actions.update_workflow_context(
        session.session_id,
        WorkflowContextUpdateRequest(
            affected_systems=["backend/yudai", "backend/yudai"],
            constraints="No GitHub OAuth required for smoke tests.",
        ),
    )

    assert issue_response.selected_issue["number"] == 88
    assert issue_response.selected_issue["labels"] == ["backend", "ws"]
    assert context_response.user_context["affected_systems"] == ["backend/yudai"]
    assert context_response.pr_readiness["checks"]["issue_selected"] is True


def test_session_actions_runtime_not_provisioned(db_session):
    user, session = _user_and_session(db_session)
    response = SessionActionService(db_session, user).get_runtime(session.session_id)
    assert response.status == "not_provisioned"
    assert response.runtime_id is None


def test_runtime_ensure_request_model_matches_ws_payload():
    request = RuntimeEnsureRequest(
        org="yudai",
        repo_owner="octocat",
        repo_name="yudaiv3",
        environment="main",
    )
    assert request.repo_branch == "main"
