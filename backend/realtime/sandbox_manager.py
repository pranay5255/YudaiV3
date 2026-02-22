"""Sandbox lifecycle helpers for Phase 1 controller orchestration."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Awaitable, Callable, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

ProbeCallback = Callable[[str, bool, Optional[str]], Awaitable[None]]


class SandboxManager:
    """Manages tunnel probes plus git bootstrap for sandbox identities."""

    def __init__(self):
        self.probe_interval_seconds = int(os.getenv("SANDBOX_LIVENESS_INTERVAL_SECONDS", "10"))
        self.probe_timeout_seconds = float(os.getenv("SANDBOX_LIVENESS_TIMEOUT_SECONDS", "3"))
        self.git_fetch_interval_seconds = int(os.getenv("SANDBOX_GIT_FETCH_INTERVAL_SECONDS", "300"))

        self.tunnel_template = os.getenv(
            "SANDBOX_TUNNEL_TEMPLATE",
            "http://localhost:8100/{sandbox_id}",
        )

        self.repo_root = Path(os.getenv("SANDBOX_GIT_ROOT", "/home/yudai/.cache/repos"))
        self.repo_root.mkdir(parents=True, exist_ok=True)

        self._probe_tasks: Dict[str, asyncio.Task] = {}

    def build_tunnel_url(self, sandbox_id: str) -> str:
        template = self.tunnel_template
        if "{sandbox_id}" in template:
            return template.format(sandbox_id=sandbox_id)
        return template.rstrip("/")

    def _identity_repo_dir(self, identity_key: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", identity_key).strip("-")
        safe = safe or "sandbox"
        return self.repo_root / safe

    def ensure_git_bootstrap(
        self,
        *,
        identity_key: str,
        repo_url: Optional[str],
        repo_branch: Optional[str],
    ) -> Dict[str, object]:
        """
        Clone repository once for this sandbox identity and fetch periodically.
        """
        if not repo_url:
            return {
                "status": "skipped",
                "reason": "repo_url_missing",
            }

        repo_dir = self._identity_repo_dir(identity_key)
        marker_file = repo_dir / ".last_fetch"
        branch = (repo_branch or "main").strip() or "main"

        if not repo_dir.exists():
            repo_dir.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                "git",
                "clone",
                "--branch",
                branch,
                "--single-branch",
                repo_url,
                str(repo_dir),
            ]
            self._run_git_command(cmd)
            marker_file.write_text(str(int(time.time())), encoding="utf-8")
            return {
                "status": "cloned",
                "path": str(repo_dir),
                "branch": branch,
            }

        now = int(time.time())
        last_fetch = 0
        if marker_file.exists():
            try:
                last_fetch = int(marker_file.read_text(encoding="utf-8").strip() or "0")
            except ValueError:
                last_fetch = 0

        elapsed = now - last_fetch
        if elapsed >= self.git_fetch_interval_seconds:
            self._run_git_command(["git", "-C", str(repo_dir), "fetch", "--all", "--prune"])
            marker_file.write_text(str(now), encoding="utf-8")
            return {
                "status": "fetched",
                "path": str(repo_dir),
                "branch": branch,
                "elapsed_seconds": elapsed,
            }

        return {
            "status": "reused",
            "path": str(repo_dir),
            "branch": branch,
            "elapsed_seconds": elapsed,
        }

    def _run_git_command(self, cmd: list[str]) -> None:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            stderr_tail = (result.stderr or "")[-2000:]
            raise RuntimeError(
                f"Git bootstrap command failed ({' '.join(cmd)}): {stderr_tail}"
            )

    async def start_probe(
        self,
        *,
        sandbox_id: str,
        tunnel_url: str,
        callback: ProbeCallback,
    ) -> None:
        """Start a recurring liveness probe against the sandbox tunnel."""
        existing = self._probe_tasks.get(sandbox_id)
        if existing and not existing.done():
            return

        async def _probe_loop() -> None:
            health_url = f"{tunnel_url.rstrip('/')}/healthz"
            while True:
                healthy = False
                error_text: Optional[str] = None

                try:
                    async with httpx.AsyncClient(timeout=self.probe_timeout_seconds) as client:
                        response = await client.get(health_url)
                    healthy = response.status_code == 200
                    if not healthy:
                        error_text = f"probe_status_{response.status_code}"
                except Exception as exc:  # pragma: no cover - defensive
                    healthy = False
                    error_text = str(exc)

                try:
                    await callback(sandbox_id, healthy, error_text)
                except Exception as callback_error:  # pragma: no cover
                    logger.warning(
                        "Probe callback failed for sandbox %s: %s",
                        sandbox_id,
                        callback_error,
                    )

                await asyncio.sleep(self.probe_interval_seconds)

        task = asyncio.create_task(_probe_loop(), name=f"sandbox-probe-{sandbox_id}")
        self._probe_tasks[sandbox_id] = task

    async def stop_probe(self, sandbox_id: str) -> None:
        task = self._probe_tasks.pop(sandbox_id, None)
        if not task:
            return

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
