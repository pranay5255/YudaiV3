"""Controller lifecycle routes for realtime Phase 1."""

from __future__ import annotations

import os
from typing import Optional

from auth.github_oauth import get_current_user
from db.database import get_db
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from models import ChatSession, SessionRuntime, User
from sqlalchemy.orm import Session

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

router = APIRouter(tags=["realtime-controller"])



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
        tunnel_url=runtime.tunnel_url,
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
def create_sandbox(
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

    envelope = lifecycle.create_runtime_for_session(
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
def ensure_runtime_for_session(
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

    envelope = lifecycle.create_runtime_for_session(
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
