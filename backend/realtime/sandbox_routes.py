"""Sandbox-session specific realtime routes."""

from __future__ import annotations

import os

from auth.github_oauth import validate_session_token
from db.database import get_db
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from .schemas import HealthzResponse

router = APIRouter(tags=["realtime-sandbox"])


@router.get("/healthz", response_model=HealthzResponse)
def healthz() -> HealthzResponse:
    controller_base_url = os.getenv("CONTROLLER_BASE_URL")
    sandbox_id = os.getenv("SANDBOX_ID")
    heartbeat_enabled = bool(controller_base_url and sandbox_id)
    return HealthzResponse(
        status="ok",
        service="sandbox-session-server",
        controller_base_url=controller_base_url,
        sandbox_id=sandbox_id,
        heartbeat_enabled=heartbeat_enabled,
    )


@router.websocket("/sessions/{session_id}/ws/chat")
async def websocket_chat(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> None:
    """Phase 1 websocket shell endpoint with session token auth."""
    user = validate_session_token(db, token)
    if not user:
        await websocket.close(code=4401, reason="invalid_session_token")
        return

    await websocket.accept()
    await websocket.send_json(
        {
            "type": "status",
            "status": "connected",
            "session_id": session_id,
            "message": "WebSocket chat shell active",
        }
    )

    try:
        while True:
            payload = await websocket.receive_text()
            await websocket.send_json(
                {
                    "type": "echo",
                    "session_id": session_id,
                    "payload": payload,
                }
            )
    except WebSocketDisconnect:
        return
