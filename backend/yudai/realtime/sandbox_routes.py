"""Sandbox-session specific realtime routes."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
import hmac
import json
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from yudai.config import get_sandbox_config
from yudai.types import HealthzResponse

from .ws_protocol import WSMessageType, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime-sandbox"])


@dataclass
class _SessionExecutionState:
    process: asyncio.subprocess.Process
    owner_connection_id: int


@dataclass
class _BackgroundExecutionState:
    process: asyncio.subprocess.Process
    session_id: str
    mode_execution_id: str
    controller_job_id: str
    attempt: int
    started_at_monotonic: float
    task: asyncio.Task[None]


class SandboxExecutionStartRequest(BaseModel):
    command: str = Field(..., min_length=1)
    cwd: Optional[str] = None
    env: Dict[str, str] = Field(default_factory=dict)
    mode_execution_id: str = Field(..., min_length=1, max_length=64)
    controller_job_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    attempt: int = Field(default=1, ge=1)
    timeout_seconds: Optional[int] = Field(default=None, ge=1)


class SandboxExecutionStartResponse(BaseModel):
    sandbox_job_id: str
    status: str
    controller_job_id: Optional[str] = None


_SESSION_EXECUTIONS: dict[str, _SessionExecutionState] = {}
_BACKGROUND_EXECUTIONS: dict[str, _BackgroundExecutionState] = {}
_SESSION_EXECUTION_LOCK = asyncio.Lock()
_BACKGROUND_EXECUTION_LOCK = asyncio.Lock()
_CALLBACK_CHUNK_LIMIT = 16_000
_CALLBACK_OUTPUT_LIMIT = 64_000


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


@router.post(
    "/internal/sessions/{session_id}/executions",
    response_model=SandboxExecutionStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_internal_execution(
    session_id: str,
    request: SandboxExecutionStartRequest,
    x_controller_internal_secret: Optional[str] = Header(default=None),
) -> SandboxExecutionStartResponse:
    """Start a sandbox command in the background and report progress to the controller."""
    if not _is_internal_header_authorized(x_controller_internal_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    controller_job_id = request.controller_job_id or f"ctrljob_{uuid.uuid4().hex[:24]}"
    sandbox_job_id = f"sbjob_{uuid.uuid4().hex[:24]}"

    async with _BACKGROUND_EXECUTION_LOCK:
        for state in _BACKGROUND_EXECUTIONS.values():
            if state.controller_job_id == controller_job_id:
                return SandboxExecutionStartResponse(
                    sandbox_job_id=next(
                        key
                        for key, value in _BACKGROUND_EXECUTIONS.items()
                        if value.controller_job_id == controller_job_id
                    ),
                    status="running",
                    controller_job_id=controller_job_id,
                )
            if state.session_id == session_id and state.process.returncode is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A sandbox command is already running for this session",
                )

    resolved_cwd = request.cwd or get_sandbox_config().workspace_path
    if resolved_cwd and not os.path.isdir(resolved_cwd):
        resolved_cwd = None

    merged_env = os.environ.copy()
    for key, value in (request.env or {}).items():
        if key:
            merged_env[str(key)] = str(value)

    process = await asyncio.create_subprocess_exec(
        "bash",
        "-lc",
        request.command,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=resolved_cwd,
        env=merged_env,
    )

    async def _run_background() -> None:
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        started_at = time.monotonic()
        sequence = 0

        async def _send_stream(event_name: str, data: str = "", **extra: Any) -> None:
            nonlocal sequence
            sequence += 1
            payload = {
                "session_id": session_id,
                "controller_job_id": controller_job_id,
                "sandbox_job_id": sandbox_job_id,
                "mode_execution_id": request.mode_execution_id,
                "attempt": request.attempt,
                "sequence": sequence,
                "stream": "sandbox",
                "event": event_name,
                **extra,
            }
            if data:
                payload["data"] = _bounded_text(data, _CALLBACK_CHUNK_LIMIT)
            try:
                await _post_controller_event(payload)
            except Exception as exc:  # pragma: no cover - callback network path
                logger.warning("Sandbox callback event failed: %s", exc)

        async def _stream_reader(
            stream: Optional[asyncio.StreamReader],
            event_name: str,
            chunks: list[str],
        ) -> None:
            if stream is None:
                return
            while True:
                chunk = await stream.read(2048)
                if not chunk:
                    return
                text = chunk.decode("utf-8", errors="replace")
                chunks.append(text)
                await _send_stream(event_name, text)

        async def _heartbeat() -> None:
            while process.returncode is None:
                await asyncio.sleep(10)
                if process.returncode is None:
                    await _send_stream("heartbeat")

        exit_code = 1
        heartbeat_task: Optional[asyncio.Task[None]] = None
        try:
            await _send_stream("start", command=request.command, pid=process.pid)
            heartbeat_task = asyncio.create_task(_heartbeat(), name=f"sandbox-heartbeat-{sandbox_job_id}")
            await asyncio.gather(
                _stream_reader(process.stdout, "stdout", stdout_chunks),
                _stream_reader(process.stderr, "stderr", stderr_chunks),
            )
            exit_code = await process.wait()
            await _send_stream("exit", exit_code=exit_code)
        except asyncio.CancelledError:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                    with contextlib.suppress(Exception):
                        await process.wait()
            exit_code = process.returncode if process.returncode is not None else 1
            await _send_stream("cancelled", exit_code=exit_code)
            raise
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await heartbeat_task
            async with _BACKGROUND_EXECUTION_LOCK:
                _BACKGROUND_EXECUTIONS.pop(sandbox_job_id, None)
            completion = {
                "session_id": session_id,
                "controller_job_id": controller_job_id,
                "sandbox_job_id": sandbox_job_id,
                "mode_execution_id": request.mode_execution_id,
                "attempt": request.attempt,
                "sequence": sequence + 1,
                "status": "cancelled" if process.returncode is not None and exit_code < 0 else "complete",
                "exit_code": exit_code,
                "stdout": _bounded_text("".join(stdout_chunks), _CALLBACK_OUTPUT_LIMIT),
                "stderr": _bounded_text("".join(stderr_chunks), _CALLBACK_OUTPUT_LIMIT),
                "duration_ms": int((time.monotonic() - started_at) * 1000),
            }
            for retry_index in range(10):
                try:
                    await _post_controller_completion(request.mode_execution_id, completion)
                    break
                except Exception as exc:  # pragma: no cover - callback network path
                    logger.warning("Sandbox completion callback failed: %s", exc)
                    if retry_index == 9:
                        break
                    await asyncio.sleep(min(30, 2 ** retry_index))

    task = asyncio.create_task(_run_background(), name=f"sandbox-exec-{sandbox_job_id}")
    state = _BackgroundExecutionState(
        process=process,
        session_id=session_id,
        mode_execution_id=request.mode_execution_id,
        controller_job_id=controller_job_id,
        attempt=request.attempt,
        started_at_monotonic=time.monotonic(),
        task=task,
    )
    async with _BACKGROUND_EXECUTION_LOCK:
        _BACKGROUND_EXECUTIONS[sandbox_job_id] = state

    return SandboxExecutionStartResponse(
        sandbox_job_id=sandbox_job_id,
        status="running",
        controller_job_id=controller_job_id,
    )


@router.post("/internal/sessions/{session_id}/executions/{sandbox_job_id}/cancel")
async def cancel_internal_execution(
    session_id: str,
    sandbox_job_id: str,
    x_controller_internal_secret: Optional[str] = Header(default=None),
) -> Dict[str, str]:
    if not _is_internal_header_authorized(x_controller_internal_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    async with _BACKGROUND_EXECUTION_LOCK:
        state = _BACKGROUND_EXECUTIONS.get(sandbox_job_id)
    if state is None or state.session_id != session_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")

    if state.process.returncode is None:
        state.process.terminate()
        try:
            await asyncio.wait_for(state.process.wait(), timeout=5)
        except asyncio.TimeoutError:
            state.process.kill()
            with contextlib.suppress(Exception):
                await state.process.wait()
    return {"sandbox_job_id": sandbox_job_id, "status": "cancelled"}


def _is_internal_ws_authorized(secret: Optional[str]) -> bool:
    expected = get_sandbox_config().controller_internal_ws_secret
    if not expected:
        return True
    return bool(secret and hmac.compare_digest(secret, expected))


def _is_internal_header_authorized(secret: Optional[str]) -> bool:
    expected = get_sandbox_config().controller_internal_ws_secret
    if not expected:
        return True
    return bool(secret and hmac.compare_digest(secret, expected))


def _callback_headers() -> Dict[str, str]:
    secret = get_sandbox_config().controller_callback_secret
    return {"X-Controller-Callback-Secret": secret} if secret else {}


def _bounded_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


async def _post_controller_event(payload: Dict[str, Any]) -> None:
    controller_base_url = get_sandbox_config().controller_base_url.rstrip("/")
    if not controller_base_url:
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{controller_base_url}/controller/internal/sandbox-events",
            headers=_callback_headers(),
            json=payload,
        )
        response.raise_for_status()


async def _post_controller_completion(
    mode_execution_id: str,
    payload: Dict[str, Any],
) -> None:
    controller_base_url = get_sandbox_config().controller_base_url.rstrip("/")
    if not controller_base_url:
        return
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{controller_base_url}/controller/internal/sandbox-executions/{mode_execution_id}/complete",
            headers=_callback_headers(),
            json=payload,
        )
        response.raise_for_status()


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
