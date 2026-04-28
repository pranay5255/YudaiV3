"""Disabled-by-default backend-only test routes.

These routes exist for local/manual API verification without GitHub OAuth.
They must never be enabled in production.
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from yudai.auth.github_oauth import create_session_token
from yudai.db.database import get_db
from yudai.models import (
    AgentExecution,
    AuthToken,
    ChatMessage,
    ChatSession,
    ContextCard,
    Sandbox,
    SessionArtifact,
    SessionAuditEvent,
    SessionMode,
    SessionModeStatus,
    SessionRuntime,
    SessionToken,
    Solve,
    User,
    UserIssue,
    UserQuestion,
)
from yudai.utils import utc_now


router = APIRouter(prefix="/test", tags=["test"])


class TestSessionCreateRequest(BaseModel):
    username: str = Field(default="backend-test", min_length=1, max_length=80)
    repo_owner: str = Field(default="octocat", min_length=1, max_length=255)
    repo_name: str = Field(default="yudaiv3", min_length=1, max_length=255)
    repo_branch: str = Field(default="main", min_length=1, max_length=255)
    title: Optional[str] = Field(default=None, max_length=255)


class TestSessionCreateResponse(BaseModel):
    user_id: int
    username: str
    session_token: str
    session_id: str
    repo_owner: str
    repo_name: str
    repo_branch: str


class TestResetResponse(BaseModel):
    deleted_users: int


def test_api_enabled() -> bool:
    enabled = os.getenv("YUDAI_TEST_API_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "enabled",
    }
    node_env = os.getenv("NODE_ENV", "development").strip().lower()
    return enabled and node_env != "production"


def _require_enabled() -> None:
    if not test_api_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Test API is disabled",
        )


def _test_user_id(username: str) -> str:
    normalized = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in username.lower())
    normalized = normalized.strip("-_") or "backend-test"
    return f"test-{normalized}"


@router.post("/auth/session", response_model=TestSessionCreateResponse)
def create_test_session(
    request: TestSessionCreateRequest,
    db: Session = Depends(get_db),
) -> TestSessionCreateResponse:
    _require_enabled()

    github_user_id = _test_user_id(request.username)
    github_username = f"test-{request.username.strip().lower()}"
    email = f"{github_user_id}@example.invalid"

    user = db.query(User).filter(User.github_user_id == github_user_id).first()
    if user is None:
        user = User(
            github_username=github_username,
            github_user_id=github_user_id,
            email=email,
            display_name=f"Test User {request.username}",
            last_login=utc_now(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_session_token(db, user.id, expires_in_hours=8)
    session_id = f"session_test_{uuid.uuid4().hex[:10]}"
    chat_session = ChatSession(
        user_id=user.id,
        session_id=session_id,
        title=request.title or f"Test - {request.repo_owner}/{request.repo_name}",
        repo_owner=request.repo_owner,
        repo_name=request.repo_name,
        repo_branch=request.repo_branch,
        repo_url=f"https://github.com/{request.repo_owner}/{request.repo_name}.git",
        runtime_workspace_path="/workspace/repo",
        is_active=True,
        total_messages=0,
        total_tokens=0,
        current_mode=SessionMode.PENDING.value,
        mode_status=SessionModeStatus.IDLE.value,
        mode_updated_at=utc_now(),
        last_activity=utc_now(),
        mode_metadata={},
    )
    db.add(chat_session)
    db.commit()

    return TestSessionCreateResponse(
        user_id=user.id,
        username=user.github_username,
        session_token=token.session_token,
        session_id=session_id,
        repo_owner=request.repo_owner,
        repo_name=request.repo_name,
        repo_branch=request.repo_branch,
    )


@router.post("/reset", response_model=TestResetResponse)
def reset_test_data(db: Session = Depends(get_db)) -> TestResetResponse:
    _require_enabled()

    users = db.query(User).filter(User.github_user_id.like("test-%")).all()
    user_ids = [user.id for user in users]
    session_ids = [
        session.id
        for session in db.query(ChatSession).filter(ChatSession.user_id.in_(user_ids)).all()
    ] if user_ids else []
    sandbox_ids = [
        sandbox.id
        for sandbox in db.query(Sandbox)
        .filter(
            (Sandbox.created_by_user_id.in_(user_ids))
            | (Sandbox.active_session_id.in_(session_ids or [-1]))
        )
        .all()
    ] if user_ids else []

    if session_ids:
        db.query(AgentExecution).filter(AgentExecution.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(SessionAuditEvent).filter(SessionAuditEvent.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(SessionArtifact).filter(SessionArtifact.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(SessionRuntime).filter(SessionRuntime.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(UserQuestion).filter(UserQuestion.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(ContextCard).filter(ContextCard.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(ChatMessage).filter(ChatMessage.session_id.in_(session_ids)).delete(synchronize_session=False)
        db.query(Solve).filter(Solve.session_id.in_(session_ids)).delete(synchronize_session=False)

    if sandbox_ids:
        db.query(SessionAuditEvent).filter(SessionAuditEvent.sandbox_id.in_(sandbox_ids)).delete(synchronize_session=False)
        db.query(Sandbox).filter(Sandbox.id.in_(sandbox_ids)).delete(synchronize_session=False)

    if session_ids:
        db.query(ChatSession).filter(ChatSession.id.in_(session_ids)).delete(synchronize_session=False)

    if user_ids:
        db.query(UserIssue).filter(UserIssue.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(SessionAuditEvent).filter(SessionAuditEvent.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(AuthToken).filter(AuthToken.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(SessionToken).filter(SessionToken.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(User).filter(User.id.in_(user_ids)).delete(synchronize_session=False)

    db.commit()
    return TestResetResponse(deleted_users=len(user_ids))
