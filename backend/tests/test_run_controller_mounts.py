import asyncio
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

    fake_context = types.ModuleType("yudai.context")
    fake_context.__path__ = []
    sys.modules["yudai.context"] = fake_context

    fake_githubops = types.ModuleType("yudai.daifuUserAgent.githubOps")
    fake_githubops.GitHubOps = type("GitHubOps", (), {})
    sys.modules["yudai.daifuUserAgent.githubOps"] = fake_githubops

    fake_chatops = types.ModuleType("yudai.daifuUserAgent.ChatOps")
    fake_chatops.ChatOps = type("ChatOps", (), {})
    sys.modules["yudai.daifuUserAgent.ChatOps"] = fake_chatops

    fake_llm_service = types.ModuleType("yudai.daifuUserAgent.llm_service")
    fake_llm_service.LLMService = type("LLMService", (), {})
    sys.modules["yudai.daifuUserAgent.llm_service"] = fake_llm_service


def test_run_controller_mounts_canonical_routes_only():
    _install_import_stubs()

    import importlib

    run_controller = importlib.import_module("yudai.run_controller")

    paths = {getattr(route, "path", None) for route in run_controller.fastapi_app.routes}

    # Canonical mounts
    assert "/daifu/sessions" in paths
    assert "/daifu/sessions/{session_id}/execution" in paths
    assert "/daifu/sessions/{session_id}/execution/cancel" in paths
    assert "/daifu/sessions/{session_id}/ai-context" in paths
    assert "/daifu/sessions/{session_id}/ai-turns" in paths
    assert "/daifu/sessions/{session_id}/tools/run-frontend-browser-check" in paths
    assert "/auth/api/login" in paths
    assert "/controller/sessions/{session_id}/runtime" in paths
    assert "/controller/internal/sandbox-events" in paths
    assert "/controller/internal/sandbox-executions/{mode_execution_id}/complete" in paths
    assert "/controller/sessions/{session_id}/ws/unified" in paths
    assert "/health" in paths

    # No alias mounts
    assert "/api/daifu/sessions" not in paths
    assert "/api/auth/api/login" not in paths
    assert "/api/controller/sessions/{session_id}/runtime" not in paths
    assert "/api/controller/sessions/{session_id}/ws/unified" not in paths
    assert "/api/health" not in paths
    assert "/daifu/sessions/{session_id}/chat" not in paths
    assert "/daifu/sessions/{session_id}/conversation" not in paths


def test_run_sandbox_server_mounts_internal_routes_only():
    _install_import_stubs()

    import importlib

    run_sandbox_server = importlib.import_module("yudai.run_sandbox_server")
    paths = {getattr(route, "path", None) for route in run_sandbox_server.app.routes}

    assert "/healthz" in paths
    assert "/internal/sessions/{session_id}/ws/exec" in paths
    assert "/internal/sessions/{session_id}/executions" in paths
    assert "/internal/sessions/{session_id}/executions/{sandbox_job_id}/cancel" in paths
    assert "/sessions/{session_id}/solve/start" not in paths
    assert "/sessions/{session_id}/solve/stream/{solve_id}/{run_id}" not in paths


def test_parse_allow_origins_trims_and_drops_empty_values():
    _install_import_stubs()
    import importlib

    run_controller = importlib.import_module("yudai.run_controller")
    parsed = run_controller._parse_allow_origins(" https://app.example.com, ,http://localhost:3000 ")
    assert parsed == ["https://app.example.com", "http://localhost:3000"]


async def _asgi_get(app, path: str, origin: str) -> tuple[list[dict], RuntimeError | None]:
    messages = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [
            (b"host", b"testserver"),
            (b"origin", origin.encode()),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    try:
        await app(scope, receive, send)
    except RuntimeError as exc:
        return messages, exc
    return messages, None


async def _asgi_options(
    app,
    path: str,
    origin: str,
    request_method: str,
) -> tuple[list[dict], RuntimeError | None]:
    messages = []
    request_sent = False

    async def receive():
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "OPTIONS",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [
            (b"host", b"testserver"),
            (b"origin", origin.encode()),
            (b"access-control-request-method", request_method.encode()),
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    try:
        await app(scope, receive, send)
    except RuntimeError as exc:
        return messages, exc
    return messages, None


def test_run_controller_allows_www_auth_login_preflight(monkeypatch):
    _install_import_stubs()
    monkeypatch.setenv("ALLOW_ORIGINS", "https://yudai.app,https://www.yudai.app")
    import importlib

    run_controller = importlib.reload(importlib.import_module("yudai.run_controller"))

    messages, raised = asyncio.run(
        _asgi_options(
            run_controller.app,
            "/auth/api/login",
            origin="https://www.yudai.app",
            request_method="GET",
        )
    )

    assert raised is None
    response_start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    headers = dict(response_start["headers"])

    assert response_start["status"] == 200
    assert headers[b"access-control-allow-origin"] == b"https://www.yudai.app"


def test_run_controller_adds_cors_headers_on_unhandled_500(monkeypatch):
    _install_import_stubs()
    monkeypatch.setenv("ALLOW_ORIGINS", "https://yudai.app,https://www.yudai.app")
    import importlib

    run_controller = importlib.reload(importlib.import_module("yudai.run_controller"))

    if not any(
        getattr(route, "path", None) == "/__tests__/boom"
        for route in run_controller.fastapi_app.routes
    ):

        @run_controller.fastapi_app.get("/__tests__/boom")
        async def boom():  # pragma: no cover - exercised via direct ASGI call
            raise RuntimeError("boom")

    messages, raised = asyncio.run(
        _asgi_get(
            run_controller.app,
            "/__tests__/boom",
            origin="https://www.yudai.app",
        )
    )
    assert isinstance(raised, RuntimeError)
    assert str(raised) == "boom"

    response_start = next(
        message for message in messages if message["type"] == "http.response.start"
    )
    headers = dict(response_start["headers"])

    assert response_start["status"] == 500
    assert headers[b"access-control-allow-origin"] == b"https://www.yudai.app"
