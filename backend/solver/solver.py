"""
Solver API router exposing start/status/cancel endpoints.
"""

from auth.github_oauth import get_current_user
from fastapi import APIRouter, Depends
from models import (
    CancelSolveResponse,
    SolveStatusResponse,
    StartSolveRequest,
    StartSolveResponse,
    User,
)
from solver.manager import DefaultSolverManager

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
