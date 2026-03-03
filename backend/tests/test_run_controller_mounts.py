import os
from pathlib import Path
import sys
import types

from fastapi import APIRouter

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/run-controller-routes-tests.db")


def _install_import_stubs() -> None:
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


def test_run_controller_mounts_canonical_routes_only():
    _install_import_stubs()

    import importlib

    run_controller = importlib.import_module("run_controller")

    paths = {getattr(route, "path", None) for route in run_controller.app.routes}

    # Canonical mounts
    assert "/daifu/sessions" in paths
    assert "/auth/api/login" in paths
    assert "/controller/sessions/{session_id}/runtime" in paths
    assert "/controller/sessions/{session_id}/ws/unified" in paths
    assert "/health" in paths

    # No alias mounts
    assert "/api/daifu/sessions" not in paths
    assert "/api/auth/api/login" not in paths
    assert "/api/controller/sessions/{session_id}/runtime" not in paths
    assert "/api/controller/sessions/{session_id}/ws/unified" not in paths
    assert "/api/health" not in paths


def test_parse_allow_origins_trims_and_drops_empty_values():
    _install_import_stubs()
    import importlib

    run_controller = importlib.import_module("run_controller")
    parsed = run_controller._parse_allow_origins(" https://app.example.com, ,http://localhost:3000 ")
    assert parsed == ["https://app.example.com", "http://localhost:3000"]
