import asyncio
import os
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/mode-orchestrator-tests.db")

from models import AgentExecution, Base, ChatSession, User  # noqa: E402
from realtime.mode_orchestrator import SessionExecutionOrchestrator  # noqa: E402


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
