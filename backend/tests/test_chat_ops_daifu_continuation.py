import asyncio
import importlib
import os
from dataclasses import asdict
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/chat-ops-daifu-tests.db")

stubbed_llm_service = sys.modules.get("yudai.daifuUserAgent.llm_service")
if stubbed_llm_service is not None and not hasattr(
    stubbed_llm_service, "DaifuParsedResponse"
):
    sys.modules.pop("yudai.daifuUserAgent.llm_service", None)
REAL_LLM_MODULE = importlib.import_module("yudai.daifuUserAgent.llm_service")

from yudai.daifuUserAgent.ChatOps import ChatOps  # noqa: E402
from yudai.daifuUserAgent.context_probe import ProbeResult  # noqa: E402
from yudai.daifuUserAgent.llm_service import LLMService  # noqa: E402
from yudai.models import (  # noqa: E402
    Base,
    ChatMessage,
    ChatSession,
    User,
    UserQuestion,
    UserQuestionStatus,
)


@pytest.fixture(autouse=True)
def restore_real_llm_module(monkeypatch):
    monkeypatch.setitem(sys.modules, "yudai.daifuUserAgent.llm_service", REAL_LLM_MODULE)


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    user = User(
        github_username="chatops-user",
        github_user_id="91001",
        email="chatops@example.com",
        display_name="ChatOps User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session = ChatSession(
        user_id=user.id,
        session_id="session_chatops_daifu",
        title="Daifu continuation",
        is_active=True,
        total_messages=0,
        total_tokens=0,
        mode_metadata={},
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return db, user, session


def test_continue_daifu_after_probe_completion_consumes_probe_context(monkeypatch):
    db, user, session = _make_db()
    try:
        db.add(
            ChatMessage(
                session_id=session.id,
                message_id="msg_user_probe",
                message_text="How does auth connect to the database?",
                sender_type="user",
                role="user",
                tokens=8,
            )
        )
        session.total_messages = 1
        session.mode_metadata = {
            "gathering_state": "complete",
            "probe_results": [
                asdict(
                    ProbeResult(
                        probe_id="probe_auth",
                        query="find auth database flow",
                        status="completed",
                        output_text="backend/auth/routes.py calls get_db at line 42.",
                        summary=None,
                        files=["backend/auth/routes.py"],
                        duration_ms=10,
                    )
                )
            ],
        }
        db.commit()

        captured: dict[str, object] = {}

        async def fake_generate_response_with_stored_context(**kwargs):
            captured["probe_context"] = kwargs.get("probe_context")
            captured["conversation_history"] = kwargs.get("conversation_history")
            return {
                "text": "Auth routes use the database dependency in backend/auth/routes.py.",
                "actions": [],
                "questions": [],
                "probes": [],
                "tool_calls": [],
            }

        monkeypatch.setattr(
            LLMService,
            "generate_response_with_stored_context",
            fake_generate_response_with_stored_context,
        )

        result = asyncio.run(
            ChatOps(db)._continue_daifu_after_gathering(
                session_id=session.session_id,
                user_id=user.id,
                trigger="probe completion",
            )
        )

        db.refresh(session)
        assistant = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id, ChatMessage.role == "assistant")
            .one()
        )

        assert result["reply"].startswith("Auth routes use")
        assert "backend/auth/routes.py" in captured["probe_context"]
        assert captured["conversation_history"][-1][0] == "System"
        assert assistant.message_text == result["reply"]
        assert (session.mode_metadata or {}).get("probe_results") is None
        assert (session.mode_metadata or {}).get("gathering_state") == "complete"
    finally:
        db.close()


def test_continue_daifu_after_last_question_includes_answered_clarification(monkeypatch):
    db, user, session = _make_db()
    try:
        question = UserQuestion(
            question_id="q_daifu_last",
            session_id=session.id,
            user_id=user.id,
            mode=None,
            question_text="Which auth flow should we prioritize?",
            options=[{"id": "jwt", "label": "JWT"}],
            multi_select=False,
            selected_option_ids=["jwt"],
            answer_text="Prioritize the JWT callback regression.",
            status=UserQuestionStatus.ANSWERED.value,
            question_metadata={"origin": "daifu_directive"},
        )
        session.mode_metadata = {
            "gathering_state": "complete",
            "pending_question_ids": [],
        }
        db.add(question)
        db.commit()

        captured: dict[str, object] = {}

        async def fake_generate_response_with_stored_context(**kwargs):
            captured["file_contexts"] = kwargs.get("file_contexts")
            return {
                "text": "I will focus the issue on the JWT callback regression.",
                "actions": [],
                "questions": [],
                "probes": [],
                "tool_calls": [],
            }

        monkeypatch.setattr(
            LLMService,
            "generate_response_with_stored_context",
            fake_generate_response_with_stored_context,
        )

        asyncio.run(
            ChatOps(db)._continue_daifu_after_gathering(
                session_id=session.session_id,
                user_id=user.id,
                trigger="clarification answer",
            )
        )

        rendered_context = "\n".join(captured["file_contexts"])
        assert "Which auth flow should we prioritize?" in rendered_context
        assert "JWT" in rendered_context
        assert "Prioritize the JWT callback regression." in rendered_context
    finally:
        db.close()


def test_continue_daifu_after_gathering_stops_at_loop_limit(monkeypatch):
    db, user, session = _make_db()
    try:
        session.mode_metadata = {
            "gathering_state": "complete",
            "daifu_continuation_depth": ChatOps(db).DAIFU_MAX_CONTINUATION_DEPTH,
        }
        db.commit()

        async def fail_if_called(**_kwargs):
            raise AssertionError("LLM should not be called after loop limit")

        monkeypatch.setattr(
            LLMService,
            "generate_response_with_stored_context",
            fail_if_called,
        )

        result = asyncio.run(
            ChatOps(db)._continue_daifu_after_gathering(
                session_id=session.session_id,
                user_id=user.id,
                trigger="loop test",
            )
        )

        db.refresh(session)
        assert result is None
        assert (session.mode_metadata or {}).get("gathering_state") == "blocked"
        assert db.query(ChatMessage).filter(ChatMessage.session_id == session.id).count() == 0
    finally:
        db.close()


def test_execute_daifu_tool_calls_dispatches_only_create_github_issue(monkeypatch):
    db, user, session = _make_db()
    try:
        from yudai.daifuUserAgent import session_routes

        calls: list[dict[str, object]] = []

        async def fake_run_create_github_issue_tool(
            db_arg,
            *,
            session_id,
            db_session,
            current_user,
            issue_id,
        ):
            calls.append(
                {
                    "db": db_arg,
                    "session_id": session_id,
                    "db_session": db_session.session_id,
                    "user_id": current_user.id,
                    "issue_id": issue_id,
                }
            )
            return None

        monkeypatch.setattr(
            session_routes,
            "_run_create_github_issue_tool",
            fake_run_create_github_issue_tool,
        )

        asyncio.run(
            ChatOps(db)._execute_daifu_tool_calls(
                session=session,
                user_id=user.id,
                tool_calls=[
                    {
                        "name": "run_architect_mode",
                        "args": {"objective": "Implement this"},
                    },
                    {
                        "name": "create_github_issue",
                        "args": {"issue_id": "issue_publish"},
                    },
                ],
            )
        )

        assert calls == [
            {
                "db": db,
                "session_id": session.session_id,
                "db_session": session.session_id,
                "user_id": user.id,
                "issue_id": "issue_publish",
            }
        ]
    finally:
        db.close()
