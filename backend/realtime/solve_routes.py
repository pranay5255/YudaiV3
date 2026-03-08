"""Solver API endpoints for the sandbox session server."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator, Optional

from auth.github_oauth import get_current_user, validate_session_token
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from models import (
    CancelSolveResponse,
    SolveStatusResponse,
    StartSolveRequest,
    StartSolveResponse,
    User,
)
from sqlalchemy.orm import Session

from .solve_manager import DefaultSolverManager

solver_manager = DefaultSolverManager()
router = APIRouter(tags=["solve"])


@router.post(
    "/sessions/{session_id}/solve/start",
    response_model=StartSolveResponse,
    status_code=201,
)
async def start_solve(
    session_id: str,
    request: StartSolveRequest,
    current_user: User = Depends(get_current_user),
) -> StartSolveResponse:
    return await solver_manager.start_solve(
        session_id=session_id,
        request=request,
        user=current_user,
    )


@router.get(
    "/sessions/{session_id}/solve/status/{solve_id}",
    response_model=SolveStatusResponse,
)
async def get_solve_status(
    session_id: str,
    solve_id: str,
    current_user: User = Depends(get_current_user),
) -> SolveStatusResponse:
    return await solver_manager.get_status(
        session_id=session_id,
        solve_id=solve_id,
        user=current_user,
    )


@router.post(
    "/sessions/{session_id}/solve/cancel/{solve_id}",
    response_model=CancelSolveResponse,
)
async def cancel_solve(
    session_id: str,
    solve_id: str,
    current_user: User = Depends(get_current_user),
) -> CancelSolveResponse:
    return await solver_manager.cancel_solve(
        session_id=session_id,
        solve_id=solve_id,
        user=current_user,
    )


# ============================================================================
# SSE TRAJECTORY STREAMING (P3-1 / P3-2)
# ============================================================================

_SSE_HEARTBEAT_INTERVAL = 5  # polls before a heartbeat event (5 * 3s = 15s)
_SSE_POLL_INTERVAL = 3.0     # seconds between trajectory polls


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _get_user_from_token_param(
    token: str = Query(..., description="Session token for SSE auth"),
    db: Session = Depends(get_db),
) -> User:
    user = validate_session_token(db, token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
        )
    return user


async def _trajectory_stream_generator(
    request: Request,
    solve_id: str,
    run_id: str,
) -> AsyncGenerator[str, None]:
    """
    Stream SSE trajectory events for a live solve run.

    Polls the executor every 3s, emits delta messages, sends a heartbeat
    every 15s, and emits a terminal event when the run ends.
    """
    last_message_count = 0
    heartbeat_counter = 0

    try:
        while True:
            if await request.is_disconnected():
                break

            executor = solver_manager.get_executor_for_run(solve_id, run_id)

            if not executor or not executor.is_active:
                yield _sse_event("status", {"status": "completed"})
                yield _sse_event("done", {})
                break

            try:
                trajectory = await executor.read_trajectory()
                if trajectory:
                    messages = trajectory.get("messages", [])
                    info = trajectory.get("info", {})
                    current_count = len(messages)

                    if current_count > last_message_count:
                        new_messages = messages[last_message_count:]
                        yield _sse_event(
                            "trajectory_update",
                            {
                                "messages": new_messages,
                                "info": info,
                                "message_count": current_count,
                                "new_message_start_index": last_message_count,
                            },
                        )
                        last_message_count = current_count

            except Exception as e:
                yield _sse_event("error", {"message": f"Failed to read trajectory: {str(e)}"})

            heartbeat_counter += 1
            if heartbeat_counter >= _SSE_HEARTBEAT_INTERVAL:
                yield _sse_event("heartbeat", {})
                heartbeat_counter = 0

            await asyncio.sleep(_SSE_POLL_INTERVAL)

    except asyncio.CancelledError:
        pass


@router.get("/sessions/{session_id}/solve/stream/{solve_id}/{run_id}")
async def stream_trajectory(
    request: Request,
    session_id: str,
    solve_id: str,
    run_id: str,
    current_user: User = Depends(_get_user_from_token_param),
) -> StreamingResponse:
    """
    Stream solver trajectory via Server-Sent Events.

    Authentication via ?token= query parameter (EventSource doesn't support headers).
    Emits trajectory_update, heartbeat, status, done, and error events.
    """
    return StreamingResponse(
        _trajectory_stream_generator(request, solve_id, run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
