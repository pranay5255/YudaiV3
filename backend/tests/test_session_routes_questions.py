import asyncio
import os
from pathlib import Path
import sys
import types

from fastapi import APIRouter
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/session-routes-question-tests.db")


def _install_import_stubs() -> None:
    """Stub heavy modules imported by session_routes that are irrelevant to these tests."""
    fake_solver = types.ModuleType("solver.solver")
    fake_solver.router = APIRouter()
    fake_solver.solver_manager = type("DummySolverManager", (), {})()
    sys.modules["solver.solver"] = fake_solver

    fake_context = types.ModuleType("yudai.context")
    fake_context.__path__ = []
    sys.modules["yudai.context"] = fake_context

    fake_githubops = types.ModuleType("yudai.daifuUserAgent.githubOps")
    fake_githubops.GitHubOps = type("GitHubOps", (), {})
    sys.modules["yudai.daifuUserAgent.githubOps"] = fake_githubops

    fake_llm_service = types.ModuleType("yudai.daifuUserAgent.llm_service")
    fake_llm_service.LLMService = type("LLMService", (), {})
    sys.modules["yudai.daifuUserAgent.llm_service"] = fake_llm_service


_install_import_stubs()

from yudai.config.realtime_flags import RealtimeFeatureFlags  # noqa: E402
from yudai.daifuUserAgent import session_routes  # noqa: E402
from yudai.models import (  # noqa: E402
    Base,
    ChatMessage,
    ChatSession,
    User,
    UserIssue,
    UserQuestion,
    UserQuestionStatus,
)
from yudai.types import AnswerQuestionRequest, AskQuestionRequest  # noqa: E402


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
        github_user_id="7101",
        email="tester@example.com",
        display_name="Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session = ChatSession(
        user_id=user.id,
        session_id="session_questions_test",
        title="Question Session",
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

    class DummyHub:
        async def send_to_session(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr(session_routes, "get_ws_hub", lambda: DummyHub())

    try:
        yield db, user, session
    finally:
        db.close()


def _flags(*, orchestrator_enabled: bool) -> RealtimeFeatureFlags:
    return RealtimeFeatureFlags(
        controller_split_enabled=True,
        controller_broker_enabled=False,
        sandbox_internal_exec_enabled=True,
        mode_orchestrator_enabled=orchestrator_enabled,
        ws_chat_enabled=False,
        modal_provisioning_enabled=False,
        ws_unified_enabled=False,
        contract_version="test",
    )


def test_ask_question_persists_record_and_waiting_status(db_and_user):
    db, user, session = db_and_user

    response = asyncio.run(
        session_routes.ask_question_for_session(
            session_id=session.session_id,
            request=AskQuestionRequest(
                prompt="Which strategy should we prioritize?",
                options=[
                    {"id": "behavior", "label": "Behavior first"},
                    {"id": "tests", "label": "Tests first"},
                ],
                multi_select=True,
                objective="Fix login race condition",
            ),
            db=db,
            current_user=user,
        )
    )

    db.refresh(session)
    question = db.query(UserQuestion).filter(UserQuestion.session_id == session.id).one()

    assert response.mode_status == "waiting_for_input"
    assert response.question.question_id == question.question_id
    assert question.status == UserQuestionStatus.PENDING.value
    assert question.multi_select is True
    assert session.mode_status == "waiting_for_input"
    assert (session.mode_metadata or {}).get("pending_resume_objective") == "Fix login race condition"


def test_answer_question_marks_answered_and_resumes_pipeline(db_and_user, monkeypatch):
    db, user, session = db_and_user

    message = ChatMessage(
        session_id=session.id,
        message_id="msg_ctx_1",
        message_text="The bug appears when token refresh and websocket reconnect happen together.",
        sender_type="user",
        role="user",
        tokens=0,
    )
    question = UserQuestion(
        question_id="q_test_01",
        session_id=session.id,
        user_id=user.id,
        mode="architect",
        question_text="Which focus should architect use?",
        options=[
            {"id": "behavior", "label": "Behavior first"},
            {"id": "tests", "label": "Tests first"},
        ],
        multi_select=False,
        status=UserQuestionStatus.PENDING.value,
    )
    session.mode_status = "waiting_for_input"
    session.mode_metadata = {"pending_resume_objective": "Fix auth reconnection bug"}
    db.add(message)
    db.add(question)
    db.commit()

    monkeypatch.setattr(
        session_routes,
        "get_realtime_feature_flags",
        lambda: _flags(orchestrator_enabled=True),
    )

    captured: dict[str, object] = {}

    class DummyOrchestrator:
        async def resume_execution(self, db, *, session, user_id, objective):
            session.mode_status = "running"
            captured["resume_execution"] = {
                "session_id": session.session_id,
                "user_id": user_id,
                "objective": objective,
            }
            return {
                "execution_id": "execp_test_resume",
                "mode": "architect",
                "status": "running",
            }

    monkeypatch.setattr(
        session_routes,
        "get_session_execution_orchestrator",
        lambda: DummyOrchestrator(),
    )

    response = asyncio.run(
        session_routes.answer_session_question(
            session_id=session.session_id,
            question_id=question.question_id,
            request=AnswerQuestionRequest(
                selected_option_ids=["tests"],
                answer_text="Prioritize test coverage and regression-proofing.",
                resume_execution=True,
            ),
            db=db,
            current_user=user,
        )
    )

    db.refresh(session)
    db.refresh(question)

    assert response.resumed is True
    assert response.resumed_mode == "architect"
    assert response.mode_status == "running"
    assert question.status == UserQuestionStatus.ANSWERED.value
    assert question.selected_option_ids == ["tests"]
    assert captured["resume_execution"]["session_id"] == session.session_id
    assert captured["resume_execution"]["user_id"] == user.id
    assert captured["resume_execution"]["objective"] == "Prioritize test coverage and regression-proofing."


def test_answer_question_keeps_gathering_open_for_pending_questions(db_and_user):
    db, user, session = db_and_user

    first_question = UserQuestion(
        question_id="q_gather_01",
        session_id=session.id,
        user_id=user.id,
        mode=None,
        question_text="Which auth flow?",
        options=[
            {"id": "jwt", "label": "JWT"},
            {"id": "oauth", "label": "OAuth"},
        ],
        multi_select=False,
        status=UserQuestionStatus.PENDING.value,
    )
    second_question = UserQuestion(
        question_id="q_gather_02",
        session_id=session.id,
        user_id=user.id,
        mode=None,
        question_text="Which tests should be prioritized?",
        options=[],
        multi_select=False,
        status=UserQuestionStatus.PENDING.value,
    )
    session.mode_status = "waiting_for_input"
    session.mode_metadata = {
        "gathering_state": "active",
        "pending_question_ids": ["q_gather_01", "q_gather_02"],
        "pending_probe_ids": ["probe_abc"],
    }
    db.add(first_question)
    db.add(second_question)
    db.commit()

    response = asyncio.run(
        session_routes.answer_session_question(
            session_id=session.session_id,
            question_id=first_question.question_id,
            request=AnswerQuestionRequest(
                selected_option_ids=["jwt"],
                resume_execution=True,
            ),
            db=db,
            current_user=user,
        )
    )

    db.refresh(session)
    db.refresh(first_question)

    assert response.resumed is False
    assert response.mode_status == "waiting_for_input"
    assert first_question.status == UserQuestionStatus.ANSWERED.value
    assert (session.mode_metadata or {}).get("pending_question_ids") == ["q_gather_02"]
    assert (session.mode_metadata or {}).get("gathering_state") == "active"


def test_create_github_issue_seeds_existing_issue_and_autostarts_pipeline(
    db_and_user,
    monkeypatch,
):
    db, user, session = db_and_user

    issue = UserIssue(
        user_id=user.id,
        issue_id="issue_auto_start",
        title="Fix controller stream handoff",
        description="Execution should start after GitHub issue creation.",
        issue_text_raw="The pipeline must run Architect, Tester, and Coder after issue creation.",
        issue_steps=["Create issue", "Run pipeline"],
        session_id=session.session_id,
        repo_owner="octocat",
        repo_name="yudaiv3",
        priority="medium",
        status="pending",
        tokens_used=1,
    )
    db.add(issue)
    db.commit()

    fake_issue_ops = types.ModuleType("yudai.daifuUserAgent.IssueOps")

    class FakeIssueService:
        def __init__(self, db):
            self.db = db

        async def create_github_issue_from_user_issue(self, user_id, issue_id, context_bundle=None):
            row = (
                self.db.query(UserIssue)
                .filter(UserIssue.user_id == user_id, UserIssue.issue_id == issue_id)
                .one()
            )
            row.github_issue_url = "https://github.com/octocat/yudaiv3/issues/77"
            row.github_issue_number = 77
            row.status = "completed"
            self.db.commit()
            return row

    fake_issue_ops.IssueService = FakeIssueService
    monkeypatch.setitem(sys.modules, "yudai.daifuUserAgent.IssueOps", fake_issue_ops)
    monkeypatch.setattr(session_routes.MemoryService, "save_session_snapshot", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        session_routes,
        "get_realtime_feature_flags",
        lambda: _flags(orchestrator_enabled=True),
    )

    lifecycle_calls: list[dict[str, object]] = []

    class DummyLifecycle:
        def mark_issue_created(self, db, *, session_public_id, user_id, issue_url, issue_number):
            lifecycle_calls.append(
                {
                    "session_public_id": session_public_id,
                    "user_id": user_id,
                    "issue_url": issue_url,
                    "issue_number": issue_number,
                }
            )

    monkeypatch.setattr(session_routes, "get_realtime_lifecycle_service", lambda: DummyLifecycle())

    captured: dict[str, object] = {}

    class DummyOrchestrator:
        async def start_execution(self, db, *, session, user_id, objective, force_mode=None):
            captured["start_execution"] = {
                "session_id": session.session_id,
                "user_id": user_id,
                "objective": objective,
                "force_mode": force_mode,
                "architect_issue_number": session.architect_issue_number,
                "architect_issue_url": session.architect_issue_url,
            }
            return {
                "execution_id": "exec_auto_start",
                "status": "running",
            }

    monkeypatch.setattr(
        session_routes,
        "get_session_execution_orchestrator",
        lambda: DummyOrchestrator(),
    )

    response = asyncio.run(
        session_routes.create_github_issue_from_user_issue_for_session(
            session_id=session.session_id,
            issue_id=issue.issue_id,
            db=db,
            current_user=user,
        )
    )

    db.refresh(session)

    assert response.success is True
    assert response.github_issue_number == 77
    assert response.execution_started is True
    assert response.execution_id == "exec_auto_start"
    assert session.architect_issue_number == 77
    assert session.architect_issue_url == "https://github.com/octocat/yudaiv3/issues/77"
    assert "GitHub issue URL: https://github.com/octocat/yudaiv3/issues/77" in captured["start_execution"]["objective"]
    assert captured["start_execution"]["architect_issue_number"] == 77
    assert lifecycle_calls[0]["issue_number"] == 77
