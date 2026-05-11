"""Controller lifecycle routes for realtime Phase 1."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
from typing import Any, Dict, Optional

from yudai.auth.github_oauth import get_current_user, validate_internal_middleware_user
from yudai.config import get_sandbox_config
from yudai.db.database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, WebSocket, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.attributes import flag_modified
from yudai.models import (
    AgentExecution,
    AuthToken,
    ChatSession,
    SandboxExecutionEvent,
    SandboxExecutionRun,
    SessionRuntime,
    User,
)
from yudai.utils import utc_now
from yudai.types import (
    CleanupResponse,
    HeartbeatResponse,
    RuntimeEnsureRequest,
    RuntimeResponse,
    SandboxCreateRequest,
    SandboxResponse,
    TunnelResolveResponse,
)
from sqlalchemy.orm import Session

from .lifecycle import get_realtime_lifecycle_service
from .ws_protocol import WSMessageType, build_envelope, get_ws_hub

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime-controller"])
RUNTIME_STATUS_NOT_PROVISIONED = "not_provisioned"
_CALLBACK_CHUNK_LIMIT = 16_000
_CALLBACK_OUTPUT_LIMIT = 64_000


class SandboxEventRequest(BaseModel):
    session_id: str
    controller_job_id: Optional[str] = None
    sandbox_job_id: str
    mode_execution_id: str
    attempt: int = 1
    sequence: Optional[int] = None
    stream: str = "sandbox"
    event: str
    data: Optional[str] = None
    exit_code: Optional[int] = None
    pid: Optional[int] = None
    command: Optional[str] = None


class SandboxCompletionRequest(BaseModel):
    session_id: str
    controller_job_id: Optional[str] = None
    sandbox_job_id: str
    mode_execution_id: str
    attempt: int = 1
    sequence: Optional[int] = None
    status: str = "complete"
    exit_code: int
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    duration_ms: int = 0
    parsed_payload: Optional[Dict[str, Any]] = None


def _to_sandbox_response(sandbox) -> SandboxResponse:
    return SandboxResponse(
        sandbox_id=sandbox.id,
        identity_key=sandbox.identity_key,
        status=sandbox.status,
        tunnel_url=sandbox.tunnel_url,
        tunnel_token_ttl_seconds=sandbox.tunnel_token_ttl_seconds or 3600,
        last_heartbeat_at=sandbox.last_heartbeat_at,
        terminated_at=sandbox.terminated_at,
    )



def _to_runtime_response(runtime: SessionRuntime) -> RuntimeResponse:
    metadata = runtime.runtime_metadata if isinstance(runtime.runtime_metadata, dict) else {}
    return RuntimeResponse(
        runtime_id=runtime.runtime_id,
        sandbox_id=runtime.sandbox_id or "",
        identity_key=(metadata.get("identity_key") if isinstance(metadata, dict) else "")
        or "",
        status=runtime.status,
        tunnel_url=None,
        token_ttl_seconds=3600,
        tunnel_expires_at=runtime.tunnel_expires_at,
        completion_issue_created=runtime.completion_issue_created,
        completion_pr_created=runtime.completion_pr_created,
        completion_detected=runtime.completion_detected,
        metadata=metadata,
    )


def _not_provisioned_runtime_response() -> RuntimeResponse:
    return RuntimeResponse(
        status=RUNTIME_STATUS_NOT_PROVISIONED,
        completion_issue_created=False,
        completion_pr_created=False,
        completion_detected=False,
        metadata={},
    )


def _bounded_text(value: Optional[str], limit: int) -> str:
    text = value or ""
    if len(text) <= limit:
        return text
    return text[-limit:]


def _validate_callback_secret(secret: Optional[str]) -> None:
    expected_secret = get_sandbox_config().controller_callback_secret
    if expected_secret and not (
        secret and hmac.compare_digest(secret, expected_secret)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized sandbox callback",
        )


def _parse_completion_payload(stdout: str, stderr: str) -> Optional[Dict[str, Any]]:
    for line in reversed(f"{stdout}\n{stderr}".splitlines()):
        raw = line.strip()
        if not raw or not raw.startswith("{"):
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _controller_job_id_for(mode_execution_id: str, sandbox_job_id: str) -> str:
    return f"ctrljob_legacy_{mode_execution_id}_{sandbox_job_id}"[:64]


def _upsert_sandbox_run_for_callback(
    db: Session,
    *,
    execution: AgentExecution,
    session_public_id: str,
    controller_job_id: str,
    sandbox_job_id: str,
    attempt: int,
    status_value: str,
    sequence: Optional[int],
) -> Optional[SandboxExecutionRun]:
    session_obj = execution.session
    if not isinstance(session_obj, ChatSession):
        return None
    metadata = execution.execution_metadata if isinstance(execution.execution_metadata, dict) else {}
    run = (
        db.query(SandboxExecutionRun)
        .filter(SandboxExecutionRun.controller_job_id == controller_job_id)
        .first()
    )
    now = utc_now()
    if run is None:
        run = SandboxExecutionRun(
            controller_job_id=controller_job_id,
            sandbox_job_id=sandbox_job_id,
            session_id=session_obj.id,
            pipeline_execution_id=metadata.get("pipeline_execution_id"),
            mode_execution_id=execution.id,
            mode=execution.mode,
            attempt=max(1, int(attempt or 1)),
            status=status_value,
            started_at=now,
            heartbeat_at=now,
            last_sequence=int(sequence or 0),
        )
        db.add(run)
        db.flush()
    else:
        run.sandbox_job_id = run.sandbox_job_id or sandbox_job_id
        run.status = status_value
        run.heartbeat_at = now
        run.last_sequence = max(run.last_sequence or 0, int(sequence or 0))
    return run


def _get_user_github_token(db: Session, user_id: int) -> Optional[str]:
    auth_token = (
        db.query(AuthToken)
        .filter(
            AuthToken.user_id == user_id,
            AuthToken.is_active.is_(True),
        )
        .order_by(AuthToken.created_at.desc())
        .first()
    )
    return auth_token.access_token if auth_token else None


@router.post(
    "/controller/sandboxes",
    response_model=SandboxResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_sandbox(
    request: SandboxCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SandboxResponse:
    lifecycle = get_realtime_lifecycle_service()
    github_token = _get_user_github_token(db, current_user.id)

    session_obj: Optional[ChatSession] = None
    if request.session_id:
        session_obj = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == request.session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )
    else:
        session_obj = (
            db.query(ChatSession)
            .filter(
                ChatSession.user_id == current_user.id,
                ChatSession.repo_owner == request.repo_owner,
                ChatSession.repo_name == request.repo_name,
                ChatSession.repo_branch == (request.repo_branch or request.environment or "main"),
            )
            .order_by(ChatSession.created_at.desc())
            .first()
        )

    if not session_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found for sandbox provisioning",
        )

    envelope = await lifecycle.create_runtime_for_session(
        db,
        session=session_obj,
        user_id=current_user.id,
        org=request.org,
        repo_owner=request.repo_owner,
        repo_name=request.repo_name,
        environment=request.environment,
        repo_branch=request.repo_branch,
        repo_url=f"https://github.com/{request.repo_owner}/{request.repo_name}.git",
        github_token=github_token,
        env_inputs={
            "SESSION_PUBLIC_ID": session_obj.session_id,
            "WORKSPACE_PATH": session_obj.runtime_workspace_path or "/workspace/repo",
        },
    )

    db.commit()
    db.refresh(envelope.sandbox)

    return _to_sandbox_response(envelope.sandbox)


@router.get("/controller/sandboxes/{sandbox_id}", response_model=SandboxResponse)
def get_sandbox(
    sandbox_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SandboxResponse:
    lifecycle = get_realtime_lifecycle_service()
    sandbox = lifecycle.get_sandbox_or_404(db, sandbox_id)

    if sandbox.created_by_user_id and sandbox.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox not found")

    return _to_sandbox_response(sandbox)


@router.delete("/controller/sandboxes/{sandbox_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sandbox(
    sandbox_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    lifecycle = get_realtime_lifecycle_service()
    lifecycle.terminate_sandbox(
        db,
        sandbox_id=sandbox_id,
        reason="manual_delete",
        actor_user_id=current_user.id,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/controller/sandboxes/{sandbox_id}/resolve-tunnel",
    response_model=TunnelResolveResponse,
)
def resolve_tunnel(
    sandbox_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TunnelResolveResponse:
    lifecycle = get_realtime_lifecycle_service()
    sandbox, runtime = lifecycle.resolve_tunnel(db, sandbox_id)

    if sandbox.created_by_user_id and sandbox.created_by_user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sandbox not found")

    runtime_metadata = runtime.runtime_metadata if isinstance(runtime.runtime_metadata, dict) else {}
    runtime_metadata["identity_key"] = sandbox.identity_key
    runtime.runtime_metadata = runtime_metadata

    db.commit()

    return TunnelResolveResponse(
        sandbox_id=sandbox.id,
        tunnel_url=sandbox.tunnel_url or "",
        signed_tunnel_url=sandbox.tunnel_url,
        token_strategy=sandbox.tunnel_auth_mode or "session_jwt_passthrough",
        token_ttl_seconds=sandbox.tunnel_token_ttl_seconds or 3600,
        signed_url_ttl_seconds=300,
    )


@router.post(
    "/controller/sandboxes/{sandbox_id}/heartbeat",
    response_model=HeartbeatResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def record_heartbeat(
    sandbox_id: str,
    db: Session = Depends(get_db),
    x_controller_heartbeat_secret: Optional[str] = Header(default=None),
) -> HeartbeatResponse:
    expected_secret = get_sandbox_config().controller_heartbeat_secret
    if expected_secret and x_controller_heartbeat_secret != expected_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized heartbeat")

    lifecycle = get_realtime_lifecycle_service()
    sandbox = lifecycle.record_heartbeat(db, sandbox_id)
    db.commit()

    return HeartbeatResponse(
        sandbox_id=sandbox.id,
        status=sandbox.status,
        last_heartbeat_at=sandbox.last_heartbeat_at,
    )


@router.post("/controller/sandboxes/cleanup", response_model=CleanupResponse)
def cleanup_sandboxes(
    stale_seconds: int = Query(default=600, ge=10, le=86400),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CleanupResponse:
    lifecycle = get_realtime_lifecycle_service()
    scanned, terminated = lifecycle.cleanup_stale_sandboxes(db, stale_seconds=stale_seconds)
    db.commit()
    return CleanupResponse(scanned=scanned, terminated=terminated)


@router.post(
    "/controller/sessions/{session_id}/runtime",
    response_model=RuntimeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ensure_runtime_for_session(
    session_id: str,
    request: RuntimeEnsureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuntimeResponse:
    lifecycle = get_realtime_lifecycle_service()
    github_token = _get_user_github_token(db, current_user.id)

    session_obj = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id,
        )
        .first()
    )
    if not session_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    envelope = await lifecycle.create_runtime_for_session(
        db,
        session=session_obj,
        user_id=current_user.id,
        org=request.org,
        repo_owner=request.repo_owner,
        repo_name=request.repo_name,
        environment=request.environment,
        repo_branch=request.repo_branch,
        repo_url=request.repo_url
        or f"https://github.com/{request.repo_owner}/{request.repo_name}.git",
        github_token=github_token,
        env_inputs={
            "SESSION_PUBLIC_ID": session_obj.session_id,
            "WORKSPACE_PATH": session_obj.runtime_workspace_path or "/workspace/repo",
        },
    )

    runtime_metadata = envelope.runtime.runtime_metadata or {}
    runtime_metadata["identity_key"] = envelope.sandbox.identity_key
    envelope.runtime.runtime_metadata = runtime_metadata

    db.commit()
    db.refresh(envelope.runtime)

    response = _to_runtime_response(envelope.runtime)
    response.identity_key = envelope.sandbox.identity_key
    response.token_ttl_seconds = envelope.sandbox.tunnel_token_ttl_seconds or 3600
    return response


@router.get("/controller/sessions/{session_id}/runtime", response_model=RuntimeResponse)
def get_runtime_for_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RuntimeResponse:
    lifecycle = get_realtime_lifecycle_service()

    session_obj = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == current_user.id,
        )
        .first()
    )
    if not session_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    runtime = lifecycle._get_latest_runtime(db, session_id=session_obj.id)
    if not runtime:
        return _not_provisioned_runtime_response()

    response = _to_runtime_response(runtime)
    sandbox = lifecycle.get_sandbox_or_404(db, runtime.sandbox_id) if runtime.sandbox_id else None
    if sandbox:
        response.identity_key = sandbox.identity_key
        response.token_ttl_seconds = sandbox.tunnel_token_ttl_seconds or 3600
    return response


@router.post("/controller/internal/sandbox-events", status_code=status.HTTP_202_ACCEPTED)
async def record_sandbox_event(
    request: SandboxEventRequest,
    db: Session = Depends(get_db),
    x_controller_callback_secret: Optional[str] = Header(default=None),
) -> Dict[str, str]:
    _validate_callback_secret(x_controller_callback_secret)

    execution = (
        db.query(AgentExecution)
        .filter(AgentExecution.id == request.mode_execution_id)
        .first()
    )
    session_public_id = request.session_id
    mode = None
    pipeline_execution_id = None
    controller_job_id = request.controller_job_id or _controller_job_id_for(
        request.mode_execution_id,
        request.sandbox_job_id,
    )
    if execution:
        mode = execution.mode
        if isinstance(execution.execution_metadata, dict):
            pipeline_execution_id = execution.execution_metadata.get("pipeline_execution_id")
        if execution.session and execution.session.session_id:
            session_public_id = execution.session.session_id
        run = _upsert_sandbox_run_for_callback(
            db,
            execution=execution,
            session_public_id=session_public_id,
            controller_job_id=controller_job_id,
            sandbox_job_id=request.sandbox_job_id,
            attempt=request.attempt,
            status_value="running" if request.event != "exit" else "exiting",
            sequence=request.sequence,
        )
        if run is not None and request.sequence is not None:
            db.add(
                SandboxExecutionEvent(
                    controller_job_id=controller_job_id,
                    sandbox_job_id=request.sandbox_job_id,
                    session_id=run.session_id,
                    mode_execution_id=request.mode_execution_id,
                    sequence=request.sequence,
                    stream=request.stream,
                    event=request.event,
                    data=_bounded_text(request.data, _CALLBACK_CHUNK_LIMIT) if request.data else None,
                    event_metadata={
                        "exit_code": request.exit_code,
                        "pid": request.pid,
                        "command": request.command,
                    },
                )
            )
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
        else:
            db.commit()

    payload: Dict[str, Any] = {
        "stream": request.stream,
        "event": request.event,
        "controller_job_id": controller_job_id,
        "mode_execution_id": request.mode_execution_id,
        "execution_id": request.mode_execution_id,
        "sandbox_job_id": request.sandbox_job_id,
    }
    if request.sequence is not None:
        payload["sequence"] = request.sequence
    if mode:
        payload["mode"] = mode
    if pipeline_execution_id:
        payload["pipeline_execution_id"] = pipeline_execution_id
    if request.data:
        payload["data"] = _bounded_text(request.data, _CALLBACK_CHUNK_LIMIT)
    if request.exit_code is not None:
        payload["exit_code"] = request.exit_code
    if request.pid is not None:
        payload["pid"] = request.pid
    if request.command:
        payload["command"] = request.command

    await get_ws_hub().send_to_session(
        session_public_id,
        WSMessageType.SANDBOX_STREAM,
        payload,
    )
    return {"status": "accepted"}


@router.post(
    "/controller/internal/sandbox-executions/{mode_execution_id}/complete",
    status_code=status.HTTP_202_ACCEPTED,
)
def complete_sandbox_execution(
    mode_execution_id: str,
    request: SandboxCompletionRequest,
    db: Session = Depends(get_db),
    x_controller_callback_secret: Optional[str] = Header(default=None),
) -> Dict[str, str]:
    _validate_callback_secret(x_controller_callback_secret)
    if request.mode_execution_id != mode_execution_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="mode_execution_id mismatch",
        )

    execution = (
        db.query(AgentExecution)
        .filter(AgentExecution.id == mode_execution_id)
        .first()
    )
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Execution not found",
        )

    stdout = _bounded_text(request.stdout, _CALLBACK_OUTPUT_LIMIT)
    stderr = _bounded_text(request.stderr, _CALLBACK_OUTPUT_LIMIT)
    parsed_payload = request.parsed_payload or _parse_completion_payload(stdout, stderr)
    controller_job_id = request.controller_job_id or _controller_job_id_for(
        mode_execution_id,
        request.sandbox_job_id,
    )

    metadata = dict(execution.execution_metadata or {})
    existing_completion = metadata.get("sandbox_completion")
    if isinstance(existing_completion, dict) and existing_completion.get("sandbox_job_id") == request.sandbox_job_id:
        return {"status": "duplicate", "sandbox_job_id": request.sandbox_job_id}

    run = _upsert_sandbox_run_for_callback(
        db,
        execution=execution,
        session_public_id=request.session_id,
        controller_job_id=controller_job_id,
        sandbox_job_id=request.sandbox_job_id,
        attempt=request.attempt,
        status_value=request.status,
        sequence=request.sequence,
    )
    if run is not None:
        if run.completed_at is not None and run.sandbox_job_id == request.sandbox_job_id:
            return {"status": "duplicate", "sandbox_job_id": request.sandbox_job_id}
        run.status = request.status
        run.completed_at = utc_now()
        run.exit_code = request.exit_code
        run.duration_ms = request.duration_ms
        run.stdout_tail = stdout
        run.stderr_tail = stderr
        run.parsed_payload = parsed_payload
        run.last_sequence = max(run.last_sequence or 0, int(request.sequence or 0))
        run.run_metadata = {
            **(run.run_metadata or {}),
            "completion_callback_at": utc_now().isoformat(),
        }

    metadata["sandbox_completion"] = {
        "session_id": request.session_id,
        "controller_job_id": controller_job_id,
        "sandbox_job_id": request.sandbox_job_id,
        "mode_execution_id": mode_execution_id,
        "status": request.status,
        "exit_code": request.exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_ms": request.duration_ms,
        "parsed_payload": parsed_payload,
    }
    metadata["sandbox_job_id"] = request.sandbox_job_id
    execution.execution_metadata = metadata
    flag_modified(execution, "execution_metadata")
    db.commit()
    return {"status": "accepted", "sandbox_job_id": request.sandbox_job_id}


@router.websocket("/controller/sessions/{session_id}/ws/unified")
async def unified_session_websocket(
    websocket: WebSocket,
    session_id: str,
    internal_secret: str = Query(...),
    internal_user_id: str = Query(...),
    db: Session = Depends(get_db),
) -> None:
    """Internal unified websocket endpoint for the Node SSE bridge."""
    user = validate_internal_middleware_user(
        db,
        internal_secret=internal_secret,
        internal_user_id=internal_user_id,
    )
    if not user:
        await websocket.close(code=4401, reason="invalid_internal_auth")
        return

    session_obj = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == session_id,
            ChatSession.user_id == user.id,
        )
        .first()
    )
    if not session_obj:
        await websocket.close(code=4404, reason="session_not_found")
        return

    await websocket.accept()
    ws_hub = get_ws_hub()
    await ws_hub.register(session_id, websocket)

    await websocket.send_text(
        build_envelope(
            WSMessageType.STATUS,
            {"status": "connected", "session_id": session_id},
        )
    )
    await websocket.send_text(
        build_envelope(
            WSMessageType.MODE_EVENT,
            {
                "mode": session_obj.current_mode,
                "state": session_obj.mode_status,
            },
        )
    )

    shutdown = asyncio.Event()
    async def heartbeat_loop() -> None:
        while not shutdown.is_set():
            await asyncio.sleep(5)
            if shutdown.is_set():
                return
            try:
                await websocket.send_text(build_envelope(WSMessageType.HEARTBEAT))
            except Exception:
                shutdown.set()
                return

    async def receive_loop() -> None:
        while not shutdown.is_set():
            try:
                raw = await websocket.receive_text()
            except Exception:
                shutdown.set()
                return

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    build_envelope(
                        WSMessageType.ERROR,
                        {"message": "Invalid JSON", "code": "WS_MESSAGE_PARSE_ERROR"},
                    )
                )
                continue

            msg_type = message.get("type")
            if msg_type == WSMessageType.USER_RESPONSE.value:
                await websocket.send_text(
                    build_envelope(
                        WSMessageType.STATUS,
                        {"status": "received", "detail": "User response acknowledged"},
                    )
                )
            else:
                await websocket.send_text(
                    build_envelope(
                        WSMessageType.ERROR,
                        {"message": f"Unknown message type: {msg_type}"},
                    )
                )

    try:
        await asyncio.gather(heartbeat_loop(), receive_loop())
    finally:
        shutdown.set()
        await ws_hub.unregister(session_id, websocket)
        try:
            await websocket.close()
        except Exception:
            pass
