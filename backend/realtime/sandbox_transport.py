"""Shared transport helpers for sandbox internal websocket execution."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urlencode

import websockets

from .ws_protocol import WSMessageType

SandboxEventCallback = Callable[[Dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class SandboxCommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


def to_websocket_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.startswith("https://"):
        return "wss://" + normalized[len("https://") :]
    if normalized.startswith("http://"):
        return "ws://" + normalized[len("http://") :]
    return normalized


async def run_sandbox_command(
    *,
    tunnel_url: str,
    session_public_id: str,
    command: str,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    timeout_seconds: int = 1800,
    on_event: Optional[SandboxEventCallback] = None,
    capture_stdout: bool = True,
    capture_stderr: bool = True,
) -> SandboxCommandResult:
    query: Dict[str, str] = {}
    internal_secret = os.getenv("CONTROLLER_INTERNAL_WS_SECRET")
    if internal_secret:
        query["secret"] = internal_secret

    ws_url = to_websocket_url(tunnel_url) + f"/internal/sessions/{session_public_id}/ws/exec"
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

                if on_event is not None:
                    await on_event(event)

                event_type = event.get("type")
                payload = event.get("payload", {}) or {}

                if event_type == WSMessageType.SANDBOX_STREAM.value:
                    chunk = payload.get("data")
                    stream_event = payload.get("event")
                    if stream_event == "stdout" and isinstance(chunk, str) and capture_stdout:
                        stdout_chunks.append(chunk)
                    elif stream_event == "stderr" and isinstance(chunk, str) and capture_stderr:
                        stderr_chunks.append(chunk)
                    elif stream_event == "exit":
                        exit_code = int(payload.get("exit_code") or 0)
                        break
                    continue

                if event_type == WSMessageType.ERROR.value:
                    raise RuntimeError(str(payload.get("message") or "Sandbox execution failed"))
    except asyncio.CancelledError:
        with contextlib.suppress(Exception):
            async with websockets.connect(ws_url, max_size=None, open_timeout=5) as upstream:
                await upstream.send(
                    json.dumps({"type": WSMessageType.EXEC_CANCEL.value, "payload": {}})
                )
        raise
    except asyncio.TimeoutError:
        raise RuntimeError("Sandbox execution timed out")
    except Exception as exc:
        raise RuntimeError(f"Sandbox execution broker error: {exc}") from exc

    return SandboxCommandResult(
        exit_code=exit_code if exit_code is not None else 1,
        stdout="".join(stdout_chunks),
        stderr="".join(stderr_chunks),
        duration_ms=int((time.monotonic() - started_at) * 1000),
    )
