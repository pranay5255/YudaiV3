import asyncio
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/workflow-metadata-tests.db")

from yudai.daifuUserAgent import session_routes  # noqa: E402
from yudai.models import (  # noqa: E402
    Base,
    ChatSession,
    ContextCard,
    User,
    WorkflowContextUpdateRequest,
    WorkflowIssueRequest,
)
from yudai.realtime.mode_orchestrator import SessionExecutionOrchestrator  # noqa: E402


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    db = session_local()
    user = User(
        github_username="workflow-user",
        github_user_id="99001",
        email="workflow@example.com",
        display_name="Workflow User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    chat_session = ChatSession(
        user_id=user.id,
        session_id="session_workflow",
        title="Workflow",
        repo_owner="octocat",
        repo_name="yudaiv3",
        repo_branch="main",
        is_active=True,
        total_messages=0,
        total_tokens=0,
        mode_metadata={},
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return db, user, chat_session


def test_select_workflow_issue_persists_selected_issue():
    db, user, chat_session = _make_db()
    try:
        response = asyncio.run(
            session_routes.select_session_workflow_issue(
                chat_session.session_id,
                WorkflowIssueRequest(
                    number=42,
                    title="Fix auth callback state",
                    body="Callback state is dropped.",
                    html_url="https://github.com/octocat/yudaiv3/issues/42",
                    labels=["bug", "auth"],
                    state="open",
                ),
                current_user=user,
                db=db,
            )
        )

        db.refresh(chat_session)
        workflow = chat_session.mode_metadata["workflow"]
        assert workflow["selected_issue"]["number"] == 42
        assert workflow["selected_issue"]["labels"] == ["bug", "auth"]
        assert chat_session.architect_issue_number == 42
        assert chat_session.architect_issue_url.endswith("/issues/42")
        assert response.selected_issue["title"] == "Fix auth callback state"
        assert response.pr_readiness["checks"]["issue_selected"] is True
    finally:
        db.close()


def test_workflow_context_is_included_in_execution_objective():
    db, user, chat_session = _make_db()
    try:
        asyncio.run(
            session_routes.select_session_workflow_issue(
                chat_session.session_id,
                WorkflowIssueRequest(
                    number=42,
                    title="Fix auth callback state",
                    body="Callback state is dropped.",
                    html_url="https://github.com/octocat/yudaiv3/issues/42",
                    labels=["bug"],
                    state="open",
                ),
                current_user=user,
                db=db,
            )
        )
        asyncio.run(
            session_routes.update_session_workflow_context(
                chat_session.session_id,
                WorkflowContextUpdateRequest(
                    affected_systems=["auth", "sessions"],
                    constraints="Do not change OAuth scopes.",
                    acceptance_criteria="Callback state survives redirects.",
                ),
                current_user=user,
                db=db,
            )
        )
        db.add(
            ContextCard(
                user_id=user.id,
                session_id=chat_session.id,
                title="Auth callback context",
                content="Auth callback stores state in session metadata.",
                source="chat",
                tokens=12,
                is_active=True,
            )
        )
        db.commit()
        db.refresh(chat_session)

        objective = SessionExecutionOrchestrator(
            broker=object(),
            lifecycle=object(),
            ws_hub=object(),
        )._build_objective_with_context(
            db,
            session=chat_session,
            objective="Prepare the PR",
        )

        assert "Selected GitHub Issue" in objective
        assert "Fix auth callback state" in objective
        assert "Affected systems: auth, sessions" in objective
        assert "Do not change OAuth scopes." in objective
        assert "Auth callback context" in objective
    finally:
        db.close()
