import asyncio
import os
from pathlib import Path
import sys
import types

from fastapi import APIRouter, BackgroundTasks
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/session-routes-realtime-tests.db")


def _install_import_stubs() -> None:
    """Stub heavy modules imported by session_routes that are irrelevant to these tests."""
    fake_solver = types.ModuleType("solver.solver")
    fake_solver.router = APIRouter()
    fake_solver.solver_manager = type("DummySolverManager", (), {})()
    sys.modules["solver.solver"] = fake_solver

    fake_context = types.ModuleType("context")
    for name in (
        "EmbeddingPipeline",
        "FactsAndMemoriesService",
        "RepositoryFile",
        "RepositorySnapshotService",
    ):
        setattr(fake_context, name, type(name, (), {}))
    sys.modules["context"] = fake_context

    fake_githubops = types.ModuleType("daifuUserAgent.githubOps")
    fake_githubops.GitHubOps = type("GitHubOps", (), {})
    sys.modules["daifuUserAgent.githubOps"] = fake_githubops

    fake_llm_service = types.ModuleType("daifuUserAgent.llm_service")
    fake_llm_service.LLMService = type("LLMService", (), {})
    sys.modules["daifuUserAgent.llm_service"] = fake_llm_service


_install_import_stubs()

from config.realtime_flags import RealtimeFeatureFlags  # noqa: E402
from daifuUserAgent import session_routes  # noqa: E402
from models import Base, ChatSession, CreateSessionRequest, Sandbox, SessionRuntime, User  # noqa: E402
from realtime.cache_store import SessionCacheStore  # noqa: E402
from realtime.lifecycle import RealtimeLifecycleService  # noqa: E402


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
        github_user_id="7001",
        email="tester@example.com",
        display_name="Test User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    service = RealtimeLifecycleService(cache_store=SessionCacheStore())
    service.sandbox_manager.ensure_git_bootstrap = lambda **_: {"status": "skipped"}
    service._start_probe_if_possible = lambda **_: None
    service._stop_probe_if_possible = lambda *_: None

    try:
        yield db, user, service
    finally:
        db.close()


def _flags(*, enabled: bool) -> RealtimeFeatureFlags:
    return RealtimeFeatureFlags(
        controller_split_enabled=enabled,
        controller_broker_enabled=False,
        sandbox_internal_exec_enabled=True,
        mode_orchestrator_enabled=True,
        ws_chat_enabled=False,
        sse_stream_enabled=False,
        modal_provisioning_enabled=False,
        ws_unified_enabled=False,
        contract_version="test",
    )


def test_create_session_provisions_runtime_when_realtime_enabled(db_and_user, monkeypatch):
    db, user, service = db_and_user
    monkeypatch.setattr(session_routes, "get_realtime_feature_flags", lambda: _flags(enabled=True))
    monkeypatch.setattr(session_routes, "get_realtime_lifecycle_service", lambda: service)

    response = asyncio.run(
        session_routes.create_session(
            request=CreateSessionRequest(
                repo_owner="octocat",
                repo_name="yudaiv3",
                repo_branch="main",
                index_codebase=False,
                generate_embeddings=False,
                generate_facts_memories=False,
            ),
            current_user=user,
            db=db,
            background_tasks=BackgroundTasks(),
        )
    )

    assert response.session_id.startswith("session_")
    assert response.runtime_id and response.runtime_id.startswith("rt_")
    assert response.sandbox_id and response.sandbox_id.startswith("sbx_")
    assert response.tunnel_url and response.tunnel_url.startswith("http://sandbox.local/")

    session_row = db.query(ChatSession).filter(ChatSession.session_id == response.session_id).first()
    runtime_row = db.query(SessionRuntime).filter(SessionRuntime.runtime_id == response.runtime_id).first()
    sandbox_row = db.query(Sandbox).filter(Sandbox.id == response.sandbox_id).first()

    assert session_row is not None
    assert runtime_row is not None
    assert sandbox_row is not None
    assert runtime_row.status == "running"
    assert sandbox_row.status == "running"


def test_create_session_skips_runtime_when_realtime_disabled(db_and_user, monkeypatch):
    db, user, service = db_and_user
    monkeypatch.setattr(session_routes, "get_realtime_feature_flags", lambda: _flags(enabled=False))
    monkeypatch.setattr(session_routes, "get_realtime_lifecycle_service", lambda: service)

    response = asyncio.run(
        session_routes.create_session(
            request=CreateSessionRequest(
                repo_owner="octocat",
                repo_name="yudaiv3",
                repo_branch="main",
                index_codebase=False,
                generate_embeddings=False,
                generate_facts_memories=False,
            ),
            current_user=user,
            db=db,
            background_tasks=BackgroundTasks(),
        )
    )

    assert response.session_id.startswith("session_")
    assert response.runtime_id is None
    assert response.sandbox_id is None
    assert response.tunnel_url is None
    assert db.query(SessionRuntime).count() == 0
    assert db.query(Sandbox).count() == 0
