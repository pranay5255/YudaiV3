import asyncio
import os
from pathlib import Path
import sys
from datetime import timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/execution-worker-tests.db")

from yudai.models import AgentExecution, AgentExecutionLease, Base, ChatSession, SessionModeStatus, User  # noqa: E402
from yudai.realtime import execution_worker as execution_worker_module  # noqa: E402
from yudai.realtime.execution_worker import ExecutionWorker  # noqa: E402
from yudai.utils import utc_now  # noqa: E402


def test_worker_claims_one_queued_execution_once(tmp_path, monkeypatch):
    db_path = tmp_path / "worker-claim.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(execution_worker_module, "SessionLocal", SessionLocal)

    db = SessionLocal()
    try:
        user = User(
            github_username="worker",
            github_user_id="9101",
            email="worker@example.com",
            display_name="Worker Test",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        session = ChatSession(
            user_id=user.id,
            session_id="session_worker_claim",
            title="Worker Claim",
            repo_owner="octocat",
            repo_name="yudaiv3",
            repo_branch="main",
            is_active=True,
            total_messages=0,
            total_tokens=0,
            mode_metadata={
                "active_execution": {
                    "execution_id": "exec_worker_claim",
                    "status": "queued",
                }
            },
        )
        db.add(session)
        db.flush()
        db.add(
            AgentExecution(
                id="exec_worker_claim",
                session_id=session.id,
                mode="architect",
                status=SessionModeStatus.QUEUED.value,
                execution_plan=["Run Architect"],
                execution_metadata={"user_id": user.id, "objective": "Fix login"},
            )
        )
        db.commit()

        worker = ExecutionWorker()
        claimed = worker.claim_next(db)
        assert claimed is not None
        assert claimed.id == "exec_worker_claim"
        assert claimed.status == "running"
        assert claimed.execution_metadata["claimed_at"]

        db.expire_all()
        session_row = db.query(ChatSession).filter(ChatSession.id == session.id).one()
        assert session_row.mode_status == "running"
        assert session_row.mode_metadata["active_execution"]["status"] == "running"
        assert worker.claim_next(db) is None
    finally:
        db.close()


def test_worker_requeues_execution_when_lease_expires(tmp_path, monkeypatch):
    db_path = tmp_path / "worker-expired-lease.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(execution_worker_module, "SessionLocal", SessionLocal)

    db = SessionLocal()
    try:
        user = User(
            github_username="worker-expired",
            github_user_id="9104",
            email="worker-expired@example.com",
            display_name="Worker Expired Test",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        session = ChatSession(
            user_id=user.id,
            session_id="session_worker_expired",
            title="Worker Expired",
            repo_owner="octocat",
            repo_name="yudaiv3",
            repo_branch="main",
            is_active=True,
            total_messages=0,
            total_tokens=0,
            mode_metadata={
                "active_execution": {
                    "execution_id": "exec_worker_expired",
                    "status": "running",
                }
            },
        )
        db.add(session)
        db.flush()
        execution = AgentExecution(
            id="exec_worker_expired",
            session_id=session.id,
            mode="architect",
            status=SessionModeStatus.RUNNING.value,
            execution_plan=["Run Architect"],
            execution_metadata={"user_id": user.id, "objective": "Fix login"},
        )
        db.add(execution)
        now = utc_now()
        db.add(
            AgentExecutionLease(
                lease_id="lease_expired",
                execution_id=execution.id,
                worker_id="old-worker",
                lease_token="token",
                attempt=1,
                acquired_at=now - timedelta(minutes=10),
                heartbeat_at=now - timedelta(minutes=10),
                expires_at=now - timedelta(minutes=5),
            )
        )
        db.commit()

        worker = ExecutionWorker()
        claimed = worker.claim_next(db)
        assert claimed is not None
        assert claimed.id == "exec_worker_expired"
        assert claimed.status == "running"

        expired = db.query(AgentExecutionLease).filter(AgentExecutionLease.lease_id == "lease_expired").one()
        assert expired.release_reason == "expired"
    finally:
        db.close()


def test_worker_run_once_dispatches_claimed_pipeline(tmp_path, monkeypatch):
    db_path = tmp_path / "worker-run-once.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(execution_worker_module, "SessionLocal", SessionLocal)

    db = SessionLocal()
    try:
        user = User(
            github_username="worker-run",
            github_user_id="9102",
            email="worker-run@example.com",
            display_name="Worker Run Test",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        session = ChatSession(
            user_id=user.id,
            session_id="session_worker_run",
            title="Worker Run",
            repo_owner="octocat",
            repo_name="yudaiv3",
            repo_branch="main",
            is_active=True,
            total_messages=0,
            total_tokens=0,
            mode_metadata={},
        )
        db.add(session)
        db.flush()
        db.add(
            AgentExecution(
                id="exec_worker_run",
                session_id=session.id,
                mode="architect",
                status=SessionModeStatus.QUEUED.value,
                execution_plan=["Run Architect"],
                execution_metadata={
                    "user_id": user.id,
                    "objective": "Fix auth race",
                    "max_modes": 1,
                },
            )
        )
        db.commit()
    finally:
        db.close()

    captured = {}

    class DummyOrchestrator:
        async def run_full_pipeline(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(
        execution_worker_module,
        "get_session_execution_orchestrator",
        lambda: DummyOrchestrator(),
    )

    worker = ExecutionWorker()
    claimed_id = asyncio.run(worker.run_once())

    assert claimed_id == "exec_worker_run"
    assert captured["session_public_id"] == "session_worker_run"
    assert captured["execution_id"] == "exec_worker_run"
    assert captured["objective"] == "Fix auth race"
    assert captured["max_modes"] == 1
