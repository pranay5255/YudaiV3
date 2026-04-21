"""Sandbox-session specific realtime routes."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import json
import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from yudai.config import get_sandbox_config
from yudai.types import HealthzResponse

from .ws_protocol import WSMessageType, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime-sandbox"])


@dataclass
class _SessionExecutionState:
    process: asyncio.subprocess.Process
    owner_connection_id: int


_SESSION_EXECUTIONS: dict[str, _SessionExecutionState] = {}
_SESSION_EXECUTION_LOCK = asyncio.Lock()


@router.get("/healthz", response_model=HealthzResponse)
def healthz() -> HealthzResponse:
    sandbox_config = get_sandbox_config()
    controller_base_url = sandbox_config.controller_base_url
    sandbox_id = os.getenv("SANDBOX_ID")
    heartbeat_enabled = bool(controller_base_url and sandbox_id)
    return HealthzResponse(
        status="ok",
        service="sandbox-session-server",
        controller_base_url=controller_base_url,
        sandbox_id=sandbox_id,
        heartbeat_enabled=heartbeat_enabled,
    )


def _is_internal_ws_authorized(secret: Optional[str]) -> bool:
    expected = get_sandbox_config().controller_internal_ws_secret
    if not expected:
        return True
    return bool(secret and secret == expected)


@router.websocket("/internal/sessions/{session_id}/ws/exec")
async def websocket_internal_exec(
    websocket: WebSocket,
    session_id: str,
    secret: Optional[str] = Query(default=None),
) -> None:
    """Internal controller-only command execution websocket."""
    if not _is_internal_ws_authorized(secret):
        await websocket.close(code=4403, reason="forbidden")
        return

    await websocket.accept()
    await websocket.send_text(
        build_envelope(
            WSMessageType.STATUS,
            {"status": "connected", "session_id": session_id, "channel": "internal_exec"},
        )
    )

    process: Optional[asyncio.subprocess.Process] = None
    stream_tasks: list[asyncio.Task[Any]] = []
    wait_task: Optional[asyncio.Task[Any]] = None
    connection_id = id(websocket)
    owns_process = False

    async def _safe_send(msg_type: WSMessageType, payload: Dict[str, Any]) -> None:
        try:
            await websocket.send_text(build_envelope(msg_type, payload))
        except Exception:
            # Caller handles shutdown; avoid exploding background tasks on disconnect.
            pass

    async def _stream_reader(
        stream: Optional[asyncio.StreamReader],
        event_name: str,
    ) -> None:
        if stream is None:
            return
        while True:
            chunk = await stream.read(2048)
            if not chunk:
                return
            await _safe_send(
                WSMessageType.SANDBOX_STREAM,
                {
                    "stream": "sandbox",
                    "event": event_name,
                    "data": chunk.decode("utf-8", errors="replace"),
                },
            )

    async def _clear_tasks() -> None:
        nonlocal stream_tasks, wait_task
        for task in stream_tasks:
            task.cancel()
        if wait_task:
            wait_task.cancel()
        for task in [*stream_tasks, wait_task]:
            if task is None:
                continue
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        stream_tasks = []
        wait_task = None

    async def _terminate_process() -> None:
        nonlocal process, owns_process
        if process is None:
            return
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                with contextlib.suppress(Exception):
                    await process.wait()
        process = None
        async with _SESSION_EXECUTION_LOCK:
            current = _SESSION_EXECUTIONS.get(session_id)
            if current and current.owner_connection_id == connection_id:
                _SESSION_EXECUTIONS.pop(session_id, None)
        owns_process = False
        await _clear_tasks()

    async def _launch_process(command: str, cwd: Optional[str], env: Dict[str, Any]) -> None:
        nonlocal process, stream_tasks, wait_task, owns_process
        await _terminate_process()

        async with _SESSION_EXECUTION_LOCK:
            existing = _SESSION_EXECUTIONS.get(session_id)
            if existing and existing.process.returncode is None:
                await _safe_send(
                    WSMessageType.ERROR,
                    {
                        "message": "A sandbox command is already running for this session",
                        "code": "EXEC_ALREADY_RUNNING",
                    },
                )
                return

        resolved_cwd = cwd or get_sandbox_config().workspace_path
        if resolved_cwd and not os.path.isdir(resolved_cwd):
            resolved_cwd = None

        merged_env = os.environ.copy()
        for key, value in env.items():
            if key:
                merged_env[str(key)] = str(value)

        process = await asyncio.create_subprocess_exec(
            "bash",
            "-lc",
            command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=resolved_cwd,
            env=merged_env,
        )
        async with _SESSION_EXECUTION_LOCK:
            _SESSION_EXECUTIONS[session_id] = _SessionExecutionState(
                process=process,
                owner_connection_id=connection_id,
            )
        owns_process = True

        await _safe_send(
            WSMessageType.SANDBOX_STREAM,
            {
                "stream": "sandbox",
                "event": "start",
                "pid": process.pid,
                "command": command,
            },
        )

        stream_tasks = [
            asyncio.create_task(_stream_reader(process.stdout, "stdout")),
            asyncio.create_task(_stream_reader(process.stderr, "stderr")),
        ]

        async def _wait_for_exit() -> None:
            assert process is not None
            exit_code = await process.wait()
            async with _SESSION_EXECUTION_LOCK:
                current = _SESSION_EXECUTIONS.get(session_id)
                if (
                    current
                    and current.owner_connection_id == connection_id
                    and current.process is process
                ):
                    _SESSION_EXECUTIONS.pop(session_id, None)
            await _safe_send(
                WSMessageType.SANDBOX_STREAM,
                {
                    "stream": "sandbox",
                    "event": "exit",
                    "exit_code": exit_code,
                },
            )

        wait_task = asyncio.create_task(_wait_for_exit())

    try:
        while True:
            raw_message = await websocket.receive_text()
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                await _safe_send(
                    WSMessageType.ERROR,
                    {"message": "Invalid JSON", "code": "WS_MESSAGE_PARSE_ERROR"},
                )
                continue

            msg_type = message.get("type")
            payload = message.get("payload", {}) or {}
            if not isinstance(payload, dict):
                payload = {}

            if msg_type == WSMessageType.EXEC_START.value:
                command = str(payload.get("command") or "").strip()
                if not command:
                    await _safe_send(
                        WSMessageType.ERROR,
                        {"message": "Missing command for exec.start", "code": "EXEC_COMMAND_MISSING"},
                    )
                    continue

                env = payload.get("env", {})
                if not isinstance(env, dict):
                    env = {}

                await _launch_process(command, payload.get("cwd"), env)
                continue

            if msg_type == WSMessageType.EXEC_STDIN.value:
                if process is None or process.returncode is not None or process.stdin is None:
                    await _safe_send(
                        WSMessageType.ERROR,
                        {"message": "No active process for stdin", "code": "EXEC_NOT_RUNNING"},
                    )
                    continue

                data = str(payload.get("data") or "")
                if data:
                    process.stdin.write(data.encode("utf-8"))
                    await process.stdin.drain()
                continue

            if msg_type == WSMessageType.EXEC_CANCEL.value:
                active_state: Optional[_SessionExecutionState] = None
                async with _SESSION_EXECUTION_LOCK:
                    current = _SESSION_EXECUTIONS.get(session_id)
                    if current and current.process.returncode is None:
                        active_state = current

                if active_state is None:
                    await _safe_send(
                        WSMessageType.ERROR,
                        {"message": "No active process to cancel", "code": "EXEC_NOT_RUNNING"},
                    )
                    continue

                if active_state.owner_connection_id == connection_id:
                    await _terminate_process()
                else:
                    active_process = active_state.process
                    active_process.terminate()
                    try:
                        await asyncio.wait_for(active_process.wait(), timeout=5)
                    except asyncio.TimeoutError:
                        active_process.kill()
                        with contextlib.suppress(Exception):
                            await active_process.wait()

                await _safe_send(
                    WSMessageType.SANDBOX_STREAM,
                    {"stream": "sandbox", "event": "cancelled"},
                )
                continue

            await _safe_send(
                WSMessageType.ERROR,
                {"message": f"Unknown message type: {msg_type}", "code": "EXEC_UNKNOWN_MESSAGE"},
            )
    except WebSocketDisconnect:
        pass
    finally:
        if owns_process:
            await _terminate_process()
        with contextlib.suppress(Exception):
            await websocket.close()
