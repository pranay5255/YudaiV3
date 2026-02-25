"""Controller lifecycle routes for realtime Phase 1."""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx
from auth.github_oauth import get_current_user, validate_session_token
from config.realtime_flags import get_realtime_feature_flags
from db.database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, WebSocket, status
from models import ChatSession, Sandbox, SandboxStatus, SessionRuntime, User
from sqlalchemy.orm import Session

from .errors import RealtimeErrorCode, as_http_exception
from .lifecycle import get_realtime_lifecycle_service
from .schemas import (
    CleanupResponse,
    HeartbeatResponse,
    RuntimeEnsureRequest,
    RuntimeResponse,
    SandboxCreateRequest,
    SandboxResponse,
    TunnelResolveResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime-controller"])

# Hop-by-hop headers that must not be forwarded through a proxy
_HOP_BY_HOP_HEADERS = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
})



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
    flags = get_realtime_feature_flags()
    return RuntimeResponse(
        runtime_id=runtime.runtime_id,
        sandbox_id=runtime.sandbox_id or "",
        identity_key=(metadata.get("identity_key") if isinstance(metadata, dict) else "")
        or "",
        status=runtime.status,
        tunnel_url=None if flags.controller_proxy_enabled else runtime.tunnel_url,
        proxy_base_url=f"/api/controller/proxy/sessions/" if flags.controller_proxy_enabled else None,
        token_ttl_seconds=3600,
        tunnel_expires_at=runtime.tunnel_expires_at,
        completion_issue_created=runtime.completion_issue_created,
        completion_pr_created=runtime.completion_pr_created,
        completion_detected=runtime.completion_detected,
        metadata=metadata,
    )


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
    expected_secret = os.getenv("CONTROLLER_HEARTBEAT_SECRET")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Runtime not found")

    response = _to_runtime_response(runtime)
    sandbox = lifecycle.get_sandbox_or_404(db, runtime.sandbox_id) if runtime.sandbox_id else None
    if sandbox:
        response.identity_key = sandbox.identity_key
        response.token_ttl_seconds = sandbox.tunnel_token_ttl_seconds or 3600
    return response


# ---------------------------------------------------------------------------
# Helper: resolve sandbox tunnel_url for a session
# ---------------------------------------------------------------------------


def _resolve_sandbox_tunnel(db: Session, session_id: str) -> str:
    """Look up the tunnel_url for a session's active sandbox. Raises on failure."""
    session_obj = (
        db.query(ChatSession)
        .filter(ChatSession.session_id == session_id)
        .first()
    )
    if not session_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    lifecycle = get_realtime_lifecycle_service()
    runtime = lifecycle._get_latest_runtime(db, session_id=session_obj.id)
    if not runtime or not runtime.sandbox_id:
        raise as_http_exception(RealtimeErrorCode.TUNNEL_UNAVAILABLE)

    sandbox = db.query(Sandbox).filter(Sandbox.id == runtime.sandbox_id).first()
    if not sandbox:
        raise as_http_exception(RealtimeErrorCode.TUNNEL_UNAVAILABLE)
    if sandbox.status == SandboxStatus.TERMINATED.value:
        raise as_http_exception(RealtimeErrorCode.TUNNEL_TERMINATED)
    if not sandbox.tunnel_url:
        raise as_http_exception(RealtimeErrorCode.TUNNEL_UNAVAILABLE)

    return sandbox.tunnel_url


# ---------------------------------------------------------------------------
# Phase 2: HTTP reverse proxy
# ---------------------------------------------------------------------------


@router.api_route(
    "/controller/proxy/sessions/{session_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def proxy_http(
    request: Request,
    session_id: str,
    path: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Reverse-proxy HTTP requests to the sandbox tunnel (same origin, no CORS)."""
    tunnel_url = _resolve_sandbox_tunnel(db, session_id)

    upstream_url = f"{tunnel_url.rstrip('/')}/{path}"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    # Forward headers, stripping hop-by-hop
    forward_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP_HEADERS and k.lower() != "host"
    }

    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream_resp = await client.request(
                method=request.method,
                url=upstream_url,
                headers=forward_headers,
                content=body,
            )
    except httpx.ConnectError:
        raise as_http_exception(RealtimeErrorCode.PROXY_UPSTREAM_ERROR, detail="Sandbox unreachable")

    # Forward response headers, stripping hop-by-hop
    resp_headers = {
        k: v
        for k, v in upstream_resp.headers.items()
        if k.lower() not in _HOP_BY_HOP_HEADERS
    }

    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=resp_headers,
    )


# ---------------------------------------------------------------------------
# Phase 3: WebSocket reverse proxy
# ---------------------------------------------------------------------------


@router.websocket("/controller/proxy/sessions/{session_id}/ws/{path:path}")
async def proxy_websocket(
    websocket: WebSocket,
    session_id: str,
    path: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> None:
    """Bidirectional WebSocket relay between client and sandbox."""
    import websockets

    user = validate_session_token(db, token)
    if not user:
        await websocket.close(code=4401, reason="invalid_session_token")
        return

    tunnel_url = _resolve_sandbox_tunnel(db, session_id)
    # Convert http(s) to ws(s)
    ws_upstream_url = tunnel_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
    ws_upstream_url = f"{ws_upstream_url}/{path}?token={token}"

    await websocket.accept()

    try:
        async with websockets.connect(ws_upstream_url) as upstream_ws:

            async def client_to_upstream() -> None:
                try:
                    while True:
                        data = await websocket.receive_text()
                        await upstream_ws.send(data)
                except Exception:
                    pass

            async def upstream_to_client() -> None:
                try:
                    async for msg in upstream_ws:
                        if isinstance(msg, str):
                            await websocket.send_text(msg)
                        else:
                            await websocket.send_bytes(msg)
                except Exception:
                    pass

            import asyncio
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()

    except Exception as e:
        logger.warning("WS proxy error for session %s: %s", session_id, e)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
