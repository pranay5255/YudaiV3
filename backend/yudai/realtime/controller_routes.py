"""Controller lifecycle routes for realtime Phase 1."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from yudai.auth.github_oauth import get_current_user, validate_session_token
from yudai.config import get_sandbox_config
from yudai.daifuUserAgent.ChatOps import ChatOps
from yudai.db.database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, WebSocket, status
from yudai.models import AuthToken, ChatSession, SessionRuntime, User
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


def _normalize_context_cards(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw:
        candidate = str(item or "").strip()
        if candidate:
            values.append(candidate)
    return values


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


@router.websocket("/controller/sessions/{session_id}/ws/unified")
async def unified_session_websocket(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> None:
    """Public unified websocket endpoint (controller only, no direct sandbox WS)."""
    user = validate_session_token(db, token)
    if not user:
        await websocket.close(code=4401, reason="invalid_session_token")
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

    async def send_llm_delta(chunk: str) -> None:
        await websocket.send_text(
            build_envelope(
                WSMessageType.LLM_STREAM,
                {
                    "stream": "llm",
                    "text": chunk,
                    "final": False,
                },
            )
        )

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
            if msg_type == WSMessageType.CHAT_MESSAGE.value:
                payload = message.get("payload", {}) or {}
                content = str(payload.get("content") or "").strip()
                context_cards = _normalize_context_cards(payload.get("context_cards"))
                repository = payload.get("repository")
                if not isinstance(repository, dict):
                    repository = None

                if not content:
                    await websocket.send_text(
                        build_envelope(
                            WSMessageType.ERROR,
                            {"message": "Missing chat content", "code": "CHAT_CONTENT_MISSING"},
                        )
                    )
                    continue

                await websocket.send_text(
                    build_envelope(
                        WSMessageType.STATUS,
                        {"status": "chat_processing"},
                    )
                )

                try:
                    chat_ops = ChatOps(db)
                    result = await chat_ops.process_chat_message_stream(
                        session_id=session_id,
                        user_id=user.id,
                        message_text=content,
                        on_chunk=send_llm_delta,
                        context_cards=context_cards or None,
                        repository=repository,
                    )
                    reply_text = str(result.get("reply") or "")
                    message_id = str(result.get("message_id") or "").strip() or None
                except Exception as chat_error:
                    logger.error(
                        "Unified websocket chat processing failed for session %s: %s",
                        session_id,
                        chat_error,
                    )
                    await websocket.send_text(
                        build_envelope(
                            WSMessageType.ERROR,
                            {"message": "Chat processing failed", "code": "CHAT_PROCESSING_FAILED"},
                        )
                    )
                    continue

                final_payload: Dict[str, Any] = {
                    "stream": "llm",
                    "text": "",
                    "final": True,
                    "final_text": reply_text,
                }
                if message_id:
                    final_payload["message_id"] = message_id
                await websocket.send_text(
                    build_envelope(WSMessageType.LLM_STREAM, final_payload)
                )
                await websocket.send_text(
                    build_envelope(
                        WSMessageType.STATUS,
                        {"status": "chat_completed"},
                    )
                )
            elif msg_type == WSMessageType.USER_RESPONSE.value:
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
