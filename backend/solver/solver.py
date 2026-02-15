"""
Solver API router exposing start/status/cancel endpoints.
"""

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
from solver.manager import DefaultSolverManager
from sqlalchemy.orm import Session

solver_manager = DefaultSolverManager()
router = APIRouter(tags=["solver"])


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
    """
    Launch a new solver session for the given chat session and GitHub issue.
    """
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
    """
    Retrieve the latest status for a solver session.
    """
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
    """
    Cancel an in-flight solver session and tear down its sandbox.
    """
    return await solver_manager.cancel_solve(
        session_id=session_id,
        solve_id=solve_id,
        user=current_user,
    )


# ============================================================================
# SSE TRAJECTORY STREAMING
# ============================================================================


def _sse_event(event_type: str, data: dict) -> str:
    """Format SSE event with type and JSON data."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def _get_user_from_token_param(
    token: str = Query(..., description="Session token for authentication"),
    db: Session = Depends(get_db),
) -> User:
    """Validate JWT from query parameter (EventSource doesn't support headers)."""
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
    Generate SSE events for trajectory updates.

    Polls the live executor every 3s for new trajectory messages and streams
    them to the client until the run completes.
    """
    last_message_count = 0
    heartbeat_counter = 0

    try:
        while True:
            # Check for client disconnect
            if await request.is_disconnected():
                break

            # Get live executor
            executor = solver_manager.get_executor_for_run(solve_id, run_id)

            if not executor or not executor.is_active:
                # Run completed or executor gone
                yield _sse_event("status", {"status": "completed"})
                yield _sse_event("done", {})
                break

            # Read current trajectory
            try:
                trajectory = await executor.read_trajectory()

                if trajectory:
                    messages = trajectory.get("messages", [])
                    info = trajectory.get("info", {})
                    current_count = len(messages)

                    # Send delta if new messages
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

            # Send heartbeat every 15s (5 polls)
            heartbeat_counter += 1
            if heartbeat_counter >= 5:
                yield _sse_event("heartbeat", {})
                heartbeat_counter = 0

            # Poll interval
            await asyncio.sleep(3)

    except asyncio.CancelledError:
        # Client disconnected
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
    Stream trajectory data via Server-Sent Events.

    Authentication via ?token= query parameter (EventSource doesn't support headers).
    Sends trajectory_update events with new messages every 3s.
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
