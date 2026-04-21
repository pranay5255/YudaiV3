"""
Unified Modal sandbox image and provisioning.

Single image runs both the sandbox FastAPI server (uvicorn) and
mini-swe-agent solver runs as subprocesses — no nested Modal sandboxes.
The sandbox is long-lived and reused across multiple solve runs within
a session. The cloned repo persists between runs (git fetch + reset).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import modal

logger = logging.getLogger(__name__)

_BACKEND_SOURCE_DIR = Path(__file__).resolve().parents[1]
_MSWEA_CONFIG_DIR = Path(__file__).resolve().parent / "mswea_mode_configs"

SANDBOX_SERVER_PIP_PACKAGES = (
    "fastapi",
    "uvicorn[standard]",
    "httpx",
    "sqlalchemy",
    "pydantic",
    "pyyaml",
    "requests",
    "websockets",
    "python-jose[cryptography]",
    "passlib",
    "psycopg2-binary",
)

# Import path stays `minisweagent`, but the published distribution is hyphenated.
SANDBOX_SOLVER_PIP_PACKAGES = (
    "mini-swe-agent",
)

SANDBOX_ENV_PASSTHROUGH_KEYS = (
    "OPENROUTER_API_KEY",
    "OPENROUTER_API_URL",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "MISTRAL_API_KEY",
    "MSWEA_MODEL_NAME",
    "OPENROUTER_MODEL",
)

_unified_sandbox_image: Optional[modal.Image] = None

_modal_app: Optional[modal.App] = None
_modal_app_lock = asyncio.Lock()

# ── GitHub CLI install script (gh) ──────────────────────────────────────
_GH_CLI_INSTALL = (
    "curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg "
    "| dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg "
    "&& chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg "
    "&& printf 'deb [arch=%s signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] "
    "https://cli.github.com/packages stable main\\n' "
    "\"$(dpkg --print-architecture)\" "
    "| tee /etc/apt/sources.list.d/github-cli.list > /dev/null "
    "&& apt-get update && apt-get install -y gh"
)


def _copy_local_dir(image: modal.Image, local_path: str, remote_path: str) -> modal.Image:
    """Attach a local directory, supporting Modal SDK API variants."""
    copy_fn = getattr(image, "copy_local_dir", None)
    if callable(copy_fn):
        return copy_fn(local_path, remote_path)

    add_fn = getattr(image, "add_local_dir", None)
    if callable(add_fn):
        return add_fn(local_path, remote_path=remote_path, copy=True)

    raise AttributeError("Modal Image API missing copy_local_dir/add_local_dir")


def _get_unified_sandbox_image() -> modal.Image:
    """Build the unified image: server + solver + gh CLI + mode configs.

    Layers (top to bottom):
      1. debian-slim 3.11 + system packages (git, curl, gh, gcc, libpq)
      2. Python packages for server (fastapi, uvicorn, sqlalchemy, …)
      3. Python packages for solver (minisweagent + its deps)
      4. Backend source code  →  /app/backend/
      5. MSWEA mode configs   →  /app/mswea_mode_configs/
      6. Workspace directory   →  /workspace/  (empty, created at build)
    """
    global _unified_sandbox_image
    if _unified_sandbox_image is not None:
        return _unified_sandbox_image

    image = (
        modal.Image.debian_slim(python_version="3.11")
        # ── System packages ──
        .apt_install(
            "git",
            "curl",
            "ca-certificates",
            "libpq-dev",
            "gcc",
            "g++",
            "make",
            "build-essential",
            "gnupg",
            "nodejs",
            "npm",
            "ripgrep",
            "jq",
        )
        # ── GitHub CLI (gh) ──
        .run_commands(_GH_CLI_INSTALL)
        # ── Common JS package managers for frontend repositories ──
        .run_commands("npm install -g pnpm yarn")
        # ── Server Python deps ──
        .pip_install(*SANDBOX_SERVER_PIP_PACKAGES)
        # ── Solver Python deps (mini-swe-agent) ──
        .pip_install(*SANDBOX_SOLVER_PIP_PACKAGES)
        # ── Workspace dir for cloned repos ──
        .run_commands("mkdir -p /workspace")
        .env({
            "PYTHONPATH": "/app/backend",
            "WORKSPACE_PATH": "/workspace/repo",
        })
    )

    # Attach backend source code
    image = _copy_local_dir(image, str(_BACKEND_SOURCE_DIR), "/app/backend/")

    # Attach MSWEA mode configs (architect/tester/coder yamls)
    if _MSWEA_CONFIG_DIR.is_dir():
        image = _copy_local_dir(image, str(_MSWEA_CONFIG_DIR), "/app/mswea_mode_configs/")

    _unified_sandbox_image = image
    return _unified_sandbox_image


# ── Default workspace path (single canonical location) ──────────────────
SANDBOX_WORKSPACE_PATH = "/workspace/repo"

# ── MSWEA mode config paths inside the sandbox ──────────────────────────
SANDBOX_MSWEA_CONFIG_ROOT = "/app/mswea_mode_configs"


async def _call_modal_async(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call Modal APIs using async variants when available."""
    aio_fn = getattr(fn, "aio", None)
    if aio_fn is not None:
        return await aio_fn(*args, **kwargs)
    return await asyncio.to_thread(fn, *args, **kwargs)


async def _get_modal_app() -> modal.App:
    """Lazily initialize and cache the Modal app."""
    global _modal_app
    if _modal_app is not None:
        return _modal_app

    async with _modal_app_lock:
        if _modal_app is None:
            _modal_app = await _call_modal_async(
                modal.App.lookup,
                "yudai-realtime",
                create_if_missing=True,
            )
    return _modal_app


@dataclass
class RealtimeModalSandbox:
    """Manages a single unified Modal sandbox.

    The sandbox runs:
      - uvicorn (sandbox server) as the main process
      - mini-swe-agent solve runs as subprocesses (via exec broker WS)
      - gh CLI for PR creation as subprocesses

    The sandbox persists across multiple solve runs within a session.
    The cloned repo at /workspace/repo is reused (git fetch + reset).
    """

    _sandbox: modal.Sandbox
    _tunnel_url: str
    _modal_sandbox_id: str

    @classmethod
    async def create(
        cls,
        sandbox_db_id: str,
        controller_base_url: str,
        github_token: Optional[str] = None,
        session_public_id: Optional[str] = None,
        repo_url: Optional[str] = None,
        repo_branch: Optional[str] = None,
        workspace_path: Optional[str] = None,
        env_inputs: Optional[Dict[str, str]] = None,
        timeout: int = 7200,
    ) -> "RealtimeModalSandbox":
        app = await _get_modal_app()

        # ── Build environment ────────────────────────────────────────
        sandbox_env: Dict[str, str] = {
            "SANDBOX_ID": sandbox_db_id,
            "CONTROLLER_BASE_URL": controller_base_url,
            "WORKSPACE_PATH": workspace_path or SANDBOX_WORKSPACE_PATH,
            "MSWEA_CONFIG_ROOT": SANDBOX_MSWEA_CONFIG_ROOT,
        }

        controller_internal_ws_secret = os.getenv("CONTROLLER_INTERNAL_WS_SECRET")
        if controller_internal_ws_secret:
            sandbox_env["CONTROLLER_INTERNAL_WS_SECRET"] = controller_internal_ws_secret

        # GitHub token is passed at sandbox creation for repo cloning.
        # Per-solve tokens are forwarded via the exec broker env dict.
        if github_token:
            sandbox_env["GITHUB_TOKEN"] = github_token
        if session_public_id:
            sandbox_env["SESSION_PUBLIC_ID"] = session_public_id
        if repo_url:
            sandbox_env["REPO_URL"] = repo_url
        if repo_branch:
            sandbox_env["REPO_BRANCH"] = repo_branch

        for key in SANDBOX_ENV_PASSTHROUGH_KEYS:
            value = os.getenv(key)
            if value:
                sandbox_env[key] = value

        if env_inputs:
            for key, value in env_inputs.items():
                if key and value is not None:
                    sandbox_env[key] = str(value)

        logger.info(
            "Creating unified sandbox db_id=%s controller=%s timeout=%d",
            sandbox_db_id,
            controller_base_url,
            timeout,
        )

        sandbox = await _call_modal_async(
            modal.Sandbox.create,
            "python",
            "-m",
            "uvicorn",
            "run_sandbox_server:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8100",
            app=app,
            image=_get_unified_sandbox_image(),
            encrypted_ports=[8100],
            env=sandbox_env,
            timeout=timeout,
            workdir="/app/backend",
        )

        try:
            tunnels = await _call_modal_async(sandbox.tunnels)
            tunnel_info = tunnels[8100]
            tunnel_url = tunnel_info.url
            modal_sandbox_id = str(sandbox.object_id)
        except Exception as exc:
            logger.warning(
                "Sandbox provisioned but tunnel lookup failed for db_id=%s; terminating to avoid leak: %s",
                sandbox_db_id,
                exc,
            )
            try:
                await _call_modal_async(sandbox.terminate)
            except Exception as term_exc:
                logger.warning("Failed to terminate sandbox after tunnel lookup failure: %s", term_exc)
            raise RuntimeError(
                f"Modal sandbox provisioned but tunnel for port 8100 was not available: {exc}"
            ) from exc

        logger.info(
            "Unified sandbox created: modal_id=%s tunnel_url=%s",
            modal_sandbox_id,
            tunnel_url,
        )

        return cls(
            _sandbox=sandbox,
            _tunnel_url=tunnel_url,
            _modal_sandbox_id=modal_sandbox_id,
        )

    @property
    def tunnel_url(self) -> str:
        return self._tunnel_url

    @property
    def modal_sandbox_id(self) -> str:
        return self._modal_sandbox_id

    async def terminate(self) -> None:
        try:
            await _call_modal_async(self._sandbox.terminate)
            logger.info("Unified sandbox terminated: %s", self._modal_sandbox_id)
        except Exception as e:
            logger.warning("Failed to terminate sandbox %s: %s", self._modal_sandbox_id, e)

    async def exec(self, command: str) -> Any:
        return await _call_modal_async(self._sandbox.exec, "bash", "-c", command)


# ---------------------------------------------------------------------------
# In-memory registry for active Modal sandbox instances
# (consolidated from modal_registry.py)
# ---------------------------------------------------------------------------


class ModalSandboxRegistry:
    """Thread-safe in-memory mapping from sandbox DB IDs to Modal instances."""

    def __init__(self) -> None:
        self._sandboxes: Dict[str, "RealtimeModalSandbox"] = {}
        self._lock = asyncio.Lock()

    async def register(self, sandbox_db_id: str, sandbox: "RealtimeModalSandbox") -> None:
        async with self._lock:
            self._sandboxes[sandbox_db_id] = sandbox
            logger.info("Registered Modal sandbox: db_id=%s modal_id=%s", sandbox_db_id, sandbox.modal_sandbox_id)

    async def get(self, sandbox_db_id: str) -> Optional["RealtimeModalSandbox"]:
        async with self._lock:
            return self._sandboxes.get(sandbox_db_id)

    async def remove(self, sandbox_db_id: str) -> Optional["RealtimeModalSandbox"]:
        async with self._lock:
            return self._sandboxes.pop(sandbox_db_id, None)

    async def terminate_and_remove(self, sandbox_db_id: str) -> None:
        sandbox = await self.remove(sandbox_db_id)
        if sandbox:
            await sandbox.terminate()


_registry_singleton: Optional[ModalSandboxRegistry] = None


def get_modal_registry() -> ModalSandboxRegistry:
    global _registry_singleton
    if _registry_singleton is None:
        _registry_singleton = ModalSandboxRegistry()
    return _registry_singleton
