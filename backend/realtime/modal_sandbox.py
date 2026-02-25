"""Modal compute provisioning for realtime sandbox sessions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import modal

logger = logging.getLogger(__name__)

_BACKEND_SOURCE_DIR = Path(__file__).resolve().parents[1]
_realtime_sandbox_image: Optional[modal.Image] = None

_modal_app: Optional[modal.App] = None
_modal_app_lock = asyncio.Lock()


def _with_backend_source(image: modal.Image) -> modal.Image:
    """Attach local backend source code, supporting Modal SDK API variants."""
    copy_local_dir = getattr(image, "copy_local_dir", None)
    if callable(copy_local_dir):
        return copy_local_dir(str(_BACKEND_SOURCE_DIR), "/app/backend/")

    add_local_dir = getattr(image, "add_local_dir", None)
    if callable(add_local_dir):
        return add_local_dir(str(_BACKEND_SOURCE_DIR), remote_path="/app/backend/", copy=True)

    raise AttributeError("Modal Image API missing copy_local_dir/add_local_dir")


def _get_realtime_sandbox_image() -> modal.Image:
    """Lazily build the Modal image so non-Modal tests can import this module."""
    global _realtime_sandbox_image
    if _realtime_sandbox_image is None:
        image = (
            modal.Image.debian_slim(python_version="3.11")
            .apt_install("git", "curl")
            .pip_install(
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
            )
            .env({"PYTHONPATH": "/app/backend"})
        )
        _realtime_sandbox_image = _with_backend_source(image)
    return _realtime_sandbox_image


async def _call_modal_async(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call Modal APIs using async variants when available."""
    aio_fn = getattr(fn, "aio", None)
    if aio_fn is not None:
        return await aio_fn(*args, **kwargs)
    return await asyncio.to_thread(fn, *args, **kwargs)


async def _get_modal_app() -> modal.App:
    """Lazily initialize and cache the Modal app for realtime sandboxes."""
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
    """Manages a single Modal sandbox running run_sandbox_server.py."""

    _sandbox: modal.Sandbox
    _tunnel_url: str
    _modal_sandbox_id: str

    @classmethod
    async def create(
        cls,
        sandbox_db_id: str,
        controller_base_url: str,
        github_token: Optional[str] = None,
        timeout: int = 7200,
    ) -> "RealtimeModalSandbox":
        app = await _get_modal_app()

        sandbox_env: Dict[str, str] = {
            "SANDBOX_ID": sandbox_db_id,
            "CONTROLLER_BASE_URL": controller_base_url,
        }
        if github_token:
            sandbox_env["GITHUB_TOKEN"] = github_token

        logger.info(
            "Creating Modal sandbox for db_id=%s controller=%s timeout=%d",
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
            image=_get_realtime_sandbox_image(),
            encrypted_ports=[8100],
            env=sandbox_env,
            timeout=timeout,
            workdir="/app/backend",
        )

        tunnel_info = sandbox.tunnels()[8100]
        tunnel_url = tunnel_info.url

        modal_sandbox_id = str(sandbox.object_id)
        logger.info(
            "Modal sandbox created: modal_id=%s tunnel_url=%s",
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
            logger.info("Modal sandbox terminated: %s", self._modal_sandbox_id)
        except Exception as e:
            logger.warning("Failed to terminate Modal sandbox %s: %s", self._modal_sandbox_id, e)

    async def exec(self, command: str) -> Any:
        return await _call_modal_async(self._sandbox.exec, "bash", "-c", command)
