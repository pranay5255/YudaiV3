"""Controller-side broker for internal sandbox command execution over WebSocket."""

from __future__ import annotations

import asyncio
import json
import os
import time
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urlencode

import websockets
from sqlalchemy.orm import Session

from models import ChatSession, Sandbox, SandboxStatus

from .errors import RealtimeErrorCode, as_http_exception
from .lifecycle import RealtimeLifecycleService, get_realtime_lifecycle_service
from .ws_protocol import WSMessageType

SandboxEventCallback = Callable[[Dict[str, Any]], Awaitable[None]]


def _to_websocket_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.startswith("https://"):
        return "wss://" + normalized[len("https://") :]
    if normalized.startswith("http://"):
        return "ws://" + normalized[len("http://") :]
    return normalized


class SandboxExecBroker:
    """Sends exec.start/stdin/cancel to sandbox internal WS and streams events back."""

    def __init__(self, lifecycle: Optional[RealtimeLifecycleService] = None) -> None:
        self.lifecycle = lifecycle or get_realtime_lifecycle_service()

    def _resolve_runtime(self, db: Session, session: ChatSession) -> tuple[Sandbox, str]:
        runtime = self.lifecycle._get_latest_runtime(db, session_id=session.id)
        if not runtime or not runtime.sandbox_id:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_UNAVAILABLE)

        sandbox = self.lifecycle.get_sandbox_or_404(db, runtime.sandbox_id)
        if sandbox.status == SandboxStatus.TERMINATED.value:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_TERMINATED)
        if not sandbox.tunnel_url:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_UNAVAILABLE)

        return sandbox, sandbox.tunnel_url

    async def run_command(
        self,
        db: Session,
        *,
        session: ChatSession,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 1800,
        on_event: Optional[SandboxEventCallback] = None,
    ) -> Dict[str, Any]:
        sandbox, tunnel_url = self._resolve_runtime(db, session)

        internal_path = f"/internal/sessions/{session.session_id}/ws/exec"
        query: Dict[str, str] = {}
        internal_secret = os.getenv("CONTROLLER_INTERNAL_WS_SECRET")
        if internal_secret:
            query["secret"] = internal_secret

        ws_url = _to_websocket_url(tunnel_url) + internal_path
        if query:
            ws_url += "?" + urlencode(query)

        request_payload: Dict[str, Any] = {
            "type": WSMessageType.EXEC_START.value,
            "payload": {
                "command": command,
                "cwd": cwd,
                "env": env or {},
            },
        }

        started_at = time.monotonic()
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        exit_code: Optional[int] = None

        try:
            async with websockets.connect(ws_url, max_size=None, open_timeout=10) as upstream:
                await upstream.send(json.dumps(request_payload))

                while True:
                    remaining = max(timeout_seconds - int(time.monotonic() - started_at), 1)
                    raw = await asyncio.wait_for(upstream.recv(), timeout=remaining)
                    if isinstance(raw, bytes):
                        raw = raw.decode("utf-8", errors="replace")
                    event = json.loads(raw)

                    event_type = event.get("type")
                    payload = event.get("payload", {}) or {}

                    if on_event is not None:
                        await on_event(event)

                    if event_type == WSMessageType.SANDBOX_STREAM.value:
                        chunk = payload.get("data")
                        if payload.get("event") == "stdout" and isinstance(chunk, str):
                            stdout_chunks.append(chunk)
                        elif payload.get("event") == "stderr" and isinstance(chunk, str):
                            stderr_chunks.append(chunk)
                        elif payload.get("event") == "exit":
                            exit_code = int(payload.get("exit_code") or 0)
                            break

                    if event_type == WSMessageType.ERROR.value:
                        raise RuntimeError(str(payload.get("message") or "Sandbox execution failed"))
        except asyncio.TimeoutError:
            raise RuntimeError("Sandbox execution timed out")
        except Exception as exc:
            raise RuntimeError(f"Sandbox execution broker error: {exc}") from exc

        duration_ms = int((time.monotonic() - started_at) * 1000)
        return {
            "sandbox_id": sandbox.id,
            "exit_code": exit_code if exit_code is not None else 1,
            "stdout": "".join(stdout_chunks),
            "stderr": "".join(stderr_chunks),
            "duration_ms": duration_ms,
        }


_exec_broker_singleton: Optional[SandboxExecBroker] = None


def get_sandbox_exec_broker() -> SandboxExecBroker:
    global _exec_broker_singleton
    if _exec_broker_singleton is None:
        _exec_broker_singleton = SandboxExecBroker()
    return _exec_broker_singleton
