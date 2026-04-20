"""
Tests for the consolidated realtime modules.

Covers functionality that moved between files:
  - ModalSandboxRegistry  (modal_sandbox.py)
  - SessionWebSocketHub   (ws_protocol.py)
  - SandboxManager        (lifecycle.py) — probe/git helpers
  - SandboxExecBroker     (lifecycle.py)
  - build_artifact_archive_command / download_sandbox_artifact_bundle (cache_store.py)
  - Stream protocol constants   (agentScriptGen.py)
  - sandbox_transport helpers   (sandbox_transport.py)
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/consolidation-tests.db")


# ---------------------------------------------------------------------------
# ModalSandboxRegistry (now in modal_sandbox)
# ---------------------------------------------------------------------------

from realtime.modal_sandbox import ModalSandboxRegistry, get_modal_registry  # noqa: E402


def test_modal_registry_register_and_get():
    registry = ModalSandboxRegistry()
    fake_sandbox = MagicMock()
    fake_sandbox.modal_sandbox_id = "sbx_test_001"

    asyncio.run(registry.register("db_id_1", fake_sandbox))
    result = asyncio.run(registry.get("db_id_1"))
    assert result is fake_sandbox


def test_modal_registry_remove_returns_sandbox():
    registry = ModalSandboxRegistry()
    fake_sandbox = MagicMock()
    fake_sandbox.modal_sandbox_id = "sbx_test_002"

    asyncio.run(registry.register("db_id_2", fake_sandbox))
    removed = asyncio.run(registry.remove("db_id_2"))
    assert removed is fake_sandbox
    missing = asyncio.run(registry.get("db_id_2"))
    assert missing is None


def test_modal_registry_terminate_and_remove_calls_terminate():
    registry = ModalSandboxRegistry()
    fake_sandbox = AsyncMock()
    fake_sandbox.modal_sandbox_id = "sbx_test_003"

    asyncio.run(registry.register("db_id_3", fake_sandbox))
    asyncio.run(registry.terminate_and_remove("db_id_3"))
    fake_sandbox.terminate.assert_awaited_once()


def test_modal_registry_get_modal_registry_singleton():
    r1 = get_modal_registry()
    r2 = get_modal_registry()
    assert r1 is r2


# ---------------------------------------------------------------------------
# SessionWebSocketHub (now in ws_protocol)
# ---------------------------------------------------------------------------

from realtime.ws_protocol import SessionWebSocketHub, get_ws_hub, WSMessageType  # noqa: E402


def _run(coro):
    return asyncio.run(coro)


def test_ws_hub_register_and_send_to_session():
    hub = SessionWebSocketHub()
    mock_ws = AsyncMock()
    mock_ws.send_text = AsyncMock()

    _run(hub.register("sess_abc", mock_ws))
    count = _run(hub.send_to_session("sess_abc", WSMessageType.HEARTBEAT, {}))
    assert count == 1
    mock_ws.send_text.assert_awaited_once()


def test_ws_hub_unregister_removes_socket():
    hub = SessionWebSocketHub()
    mock_ws = AsyncMock()

    _run(hub.register("sess_xyz", mock_ws))
    _run(hub.unregister("sess_xyz", mock_ws))
    count = _run(hub.send_to_session("sess_xyz", WSMessageType.HEARTBEAT, {}))
    assert count == 0


def test_ws_hub_send_to_empty_session_returns_zero():
    hub = SessionWebSocketHub()
    count = _run(hub.send_to_session("no_such_session", WSMessageType.STATUS, {}))
    assert count == 0


def test_ws_hub_stale_socket_pruned_on_send():
    hub = SessionWebSocketHub()
    broken_ws = AsyncMock()
    broken_ws.send_text.side_effect = RuntimeError("connection closed")

    _run(hub.register("sess_stale", broken_ws))
    count = _run(hub.send_to_session("sess_stale", WSMessageType.HEARTBEAT, {}))
    assert count == 0
    # Session bucket should be cleaned up
    count2 = _run(hub.send_to_session("sess_stale", WSMessageType.HEARTBEAT, {}))
    assert count2 == 0


def test_get_ws_hub_singleton():
    h1 = get_ws_hub()
    h2 = get_ws_hub()
    assert h1 is h2


# ---------------------------------------------------------------------------
# SandboxManager (now in lifecycle)
# ---------------------------------------------------------------------------

from realtime.lifecycle import SandboxManager  # noqa: E402


def test_sandbox_manager_build_tunnel_url_with_template():
    mgr = SandboxManager.__new__(SandboxManager)
    mgr.tunnel_template = "http://modal-tunnel/{sandbox_id}"
    mgr._probe_tasks = {}
    assert mgr.build_tunnel_url("sandbox123") == "http://modal-tunnel/sandbox123"


def test_sandbox_manager_build_tunnel_url_no_placeholder():
    mgr = SandboxManager.__new__(SandboxManager)
    mgr.tunnel_template = "http://localhost:8100"
    mgr._probe_tasks = {}
    assert mgr.build_tunnel_url("any_id") == "http://localhost:8100"


def test_sandbox_manager_git_auth_args_no_token():
    mgr = SandboxManager.__new__(SandboxManager)
    args = mgr._git_auth_args(repo_url="https://github.com/org/repo", github_token=None)
    assert args == []


def test_sandbox_manager_git_auth_args_non_github():
    mgr = SandboxManager.__new__(SandboxManager)
    args = mgr._git_auth_args(repo_url="https://gitlab.com/org/repo", github_token="tok")
    assert args == []


def test_sandbox_manager_git_auth_args_github_encodes_token():
    import base64
    mgr = SandboxManager.__new__(SandboxManager)
    args = mgr._git_auth_args(repo_url="https://github.com/org/repo", github_token="mytoken")
    assert len(args) == 2
    assert args[0] == "-c"
    encoded = base64.b64encode(b"x-access-token:mytoken").decode("ascii")
    assert encoded in args[1]


def test_sandbox_manager_ensure_git_bootstrap_skips_missing_url(tmp_path):
    mgr = SandboxManager.__new__(SandboxManager)
    mgr.repo_root = tmp_path
    mgr.git_fetch_interval_seconds = 300
    result = mgr.ensure_git_bootstrap(
        identity_key="test_id", repo_url=None, repo_branch="main"
    )
    assert result["status"] == "skipped"
    assert result["reason"] == "repo_url_missing"


def test_sandbox_manager_probe_stop_no_task():
    mgr = SandboxManager.__new__(SandboxManager)
    mgr._probe_tasks = {}
    # Should not raise when no task exists
    _run(mgr.stop_probe("nonexistent_sandbox"))


# ---------------------------------------------------------------------------
# Stream protocol constants (now in agentScriptGen)
# ---------------------------------------------------------------------------

from realtime.agentScriptGen import TRAJECTORY_UPDATE_PREFIX, SOLVE_RESULT_PREFIX  # noqa: E402


def test_stream_protocol_trajectory_prefix():
    assert TRAJECTORY_UPDATE_PREFIX == "__YUDAI_TRAJECTORY_UPDATE__"


def test_stream_protocol_solve_result_prefix():
    assert SOLVE_RESULT_PREFIX == "__YUDAI_SOLVE_RESULT__"


# ---------------------------------------------------------------------------
# build_artifact_archive_command (now in cache_store)
# ---------------------------------------------------------------------------

from realtime.cache_store import (  # noqa: E402
    ARTIFACT_STREAM_START,
    ARTIFACT_STREAM_END,
    SandboxArtifactStore,
    build_artifact_archive_command,
    DownloadedArtifactBundle,
)


def test_artifact_archive_command_contains_stream_markers():
    cmd = build_artifact_archive_command(
        source_paths=["/workspace/repo/output.txt"],
        archive_prefix="my-workflow",
    )
    assert ARTIFACT_STREAM_START in cmd
    assert ARTIFACT_STREAM_END in cmd


def test_artifact_archive_command_contains_source_paths():
    cmd = build_artifact_archive_command(
        source_paths=["output.txt", "results/"],
        archive_prefix="wf",
    )
    assert "output.txt" in cmd
    assert "results/" in cmd


def test_artifact_archive_command_contains_archive_prefix():
    cmd = build_artifact_archive_command(
        source_paths=["file.txt"],
        archive_prefix="test-prefix",
    )
    assert "test-prefix" in cmd


def test_sandbox_artifact_store_creates_bundle_dir(tmp_path):
    store = SandboxArtifactStore(root=str(tmp_path))
    bundle_dir = store.bundle_dir("sess_abc", "workflow_xyz")
    assert bundle_dir.exists()
    assert bundle_dir.is_dir()


def test_sandbox_artifact_store_sanitizes_session_id(tmp_path):
    store = SandboxArtifactStore(root=str(tmp_path))
    bundle_dir = store.bundle_dir("sess/../../etc/passwd", "safe-workflow")
    # Must be inside root
    assert str(bundle_dir).startswith(str(tmp_path))


def test_downloaded_artifact_bundle_is_immutable():
    bundle = DownloadedArtifactBundle(
        bundle_path="/data/bundle.tar.gz",
        metadata_path="/data/bundle.metadata.json",
        checksum_sha256="abc123",
        byte_size=1024,
        source_paths=["file.txt"],
    )
    with pytest.raises(Exception):
        bundle.byte_size = 999  # type: ignore[misc]


# ---------------------------------------------------------------------------
# sandbox_transport — URL conversion
# ---------------------------------------------------------------------------

from realtime.sandbox_transport import to_websocket_url  # noqa: E402


def test_to_websocket_url_https():
    assert to_websocket_url("https://example.modal.run") == "wss://example.modal.run"


def test_to_websocket_url_http():
    assert to_websocket_url("http://localhost:8100") == "ws://localhost:8100"


def test_to_websocket_url_strips_trailing_slash():
    assert to_websocket_url("https://example.modal.run/") == "wss://example.modal.run"


def test_to_websocket_url_passthrough_wss():
    # Already a WS URL — returned as-is
    assert to_websocket_url("wss://already.ws") == "wss://already.ws"


# ---------------------------------------------------------------------------
# Shim backward-compat smoke tests
# ---------------------------------------------------------------------------

def test_shim_modal_registry():
    from realtime.modal_registry import get_modal_registry as gmr
    assert callable(gmr)
