"""Sandbox-session specific realtime routes."""

from __future__ import annotations

import asyncio
import json
import logging
import os

from auth.github_oauth import validate_session_token
from db.database import get_db
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from .schemas import HealthzResponse
from .ws_protocol import WSMessageType, build_envelope

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Phase 4: Unified WS handler (trajectory + chat + agent questions)
# ---------------------------------------------------------------------------


@router.websocket("/sessions/{session_id}/ws/unified")
async def websocket_unified(
    websocket: WebSocket,
    session_id: str,
    token: str = Query(...),
    db: Session = Depends(get_db),
) -> None:
    """Unified WS endpoint: heartbeat, trajectory polling, bidirectional chat."""
    user = validate_session_token(db, token)
    if not user:
        await websocket.close(code=4401, reason="invalid_session_token")
        return

    await websocket.accept()
    await websocket.send_text(
        build_envelope(WSMessageType.STATUS, {"status": "connected", "session_id": session_id})
    )

    shutdown = asyncio.Event()

    async def heartbeat_loop() -> None:
        """Send heartbeat every 3 seconds."""
        while not shutdown.is_set():
            try:
                await websocket.send_text(build_envelope(WSMessageType.HEARTBEAT))
            except Exception:
                shutdown.set()
                return
            await asyncio.sleep(3)

    async def trajectory_poll_loop() -> None:
        """Poll solver executor for trajectory updates every 3 seconds."""
        from solver.solver import solver_manager

        last_message_count = 0

        while not shutdown.is_set():
            await asyncio.sleep(3)
            if shutdown.is_set():
                return

            # Find any active executor for this session's solves
            # The executor key is (solve_id, run_id) — iterate to find active ones
            active_executors = solver_manager.get_active_executors()
            for (solve_id, run_id), executor in active_executors:
                if not executor.is_active:
                    continue

                try:
                    trajectory = await executor.read_trajectory()
                    if not trajectory:
                        continue

                    messages = trajectory.get("messages", [])
                    info = trajectory.get("info", {})
                    current_count = len(messages)

                    if current_count > last_message_count:
                        new_messages = messages[last_message_count:]
                        await websocket.send_text(
                            build_envelope(
                                WSMessageType.TRAJECTORY_UPDATE,
                                {
                                    "messages": new_messages,
                                    "info": info,
                                    "message_count": current_count,
                                    "new_message_start_index": last_message_count,
                                },
                            )
                        )
                        last_message_count = current_count

                        # Detect tool calls in new messages
                        for msg in new_messages:
                            extra = msg.get("extra", {})
                            if isinstance(extra, dict) and extra.get("tool_call"):
                                await websocket.send_text(
                                    build_envelope(
                                        WSMessageType.TOOL_CALL,
                                        {
                                            "tool_name": extra["tool_call"].get("name", "unknown"),
                                            "tool_input": extra["tool_call"].get("input", {}),
                                            "call_id": extra["tool_call"].get("id"),
                                        },
                                    )
                                )

                            if isinstance(extra, dict) and extra.get("agent_question"):
                                await websocket.send_text(
                                    build_envelope(
                                        WSMessageType.AGENT_QUESTION,
                                        {
                                            "question_id": extra["agent_question"].get("id", ""),
                                            "question_text": extra["agent_question"].get("text", ""),
                                            "options": extra["agent_question"].get("options", []),
                                        },
                                    )
                                )

                except Exception as e:
                    logger.debug("Trajectory poll error: %s", e)

            # Check if all executors finished
            if not any(ex.is_active for (_, _), ex in active_executors):
                if active_executors:
                    # Had executors but they all finished
                    try:
                        await websocket.send_text(
                            build_envelope(WSMessageType.STATUS, {"status": "completed"})
                        )
                        await websocket.send_text(build_envelope(WSMessageType.DONE))
                    except Exception:
                        pass
                    shutdown.set()
                    return

    async def receive_loop() -> None:
        """Listen for client messages (chat_message, user_response)."""
        while not shutdown.is_set():
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                shutdown.set()
                return
            except Exception:
                shutdown.set()
                return

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    build_envelope(
                        WSMessageType.ERROR,
                        {"message": "Invalid JSON", "code": "WS_MESSAGE_PARSE_ERROR"},
                    )
                )
                continue

            msg_type = msg.get("type")

            if msg_type == WSMessageType.CHAT_MESSAGE.value:
                content = msg.get("payload", {}).get("content", "")
                await websocket.send_text(
                    build_envelope(
                        WSMessageType.STATUS,
                        {"status": "received", "detail": f"Chat message received ({len(content)} chars)"},
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
        await asyncio.gather(
            heartbeat_loop(),
            trajectory_poll_loop(),
            receive_loop(),
        )
    except Exception as e:
        logger.warning("Unified WS error for session %s: %s", session_id, e)
    finally:
        shutdown.set()
        try:
            await websocket.close()
        except Exception:
            pass
