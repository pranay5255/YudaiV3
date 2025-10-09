import asyncio
import os
from typing import List
from uuid import uuid4

from auth.github_oauth import get_current_user
from db.database import SessionLocal, get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from models import (
    AuthToken,
    Solve,
    SolveDetailOut,
    SolveOut,
    SolveRun,
    SolveRunOut,
    SolveStatus,
    User,
)
from sqlalchemy.orm import Session, selectinload

from .models import SolveRequest, SolveResponse
from .services import SolveRunner

router = APIRouter(prefix="/solve", tags=["solver"])


def _resolve_template_id() -> str:
    template_id = os.getenv("E2B_TEMPLATE_ID")
    if not template_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="E2B_TEMPLATE_ID environment variable is not set",
        )
    return template_id


def _resolve_github_token(db: Session, user_id: int) -> str:
    token = (
        db.query(AuthToken)
        .filter(AuthToken.user_id == user_id, AuthToken.is_active.is_(True))
        .order_by(AuthToken.created_at.desc())
        .first()
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GitHub token not available for the current user",
        )
    return token.access_token


@router.post("/", response_model=SolveResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_solve(
    request: SolveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SolveResponse:
    template_id = _resolve_template_id()
    gh_token = _resolve_github_token(db, current_user.id)

    solve_id = str(uuid4())
    solve = Solve(
        id=solve_id,
        user_id=current_user.id,
        repo_url=request.repo_url,
        issue_number=request.issue_number,
        base_branch=request.base_branch,
        status=SolveStatus.PENDING.value,
        matrix=request.matrix.model_dump(),
        limits=request.limits.model_dump() if request.limits else None,
        requested_by=request.requested_by or current_user.github_username,
    )
    db.add(solve)
    db.commit()
    db.refresh(solve)

    base_cfg = {
        "repo_url": request.repo_url,
        "issue_number": request.issue_number,
        "base_branch": request.base_branch,
    }

    runner = SolveRunner(SessionLocal, gh_token, template_id)
    asyncio.create_task(runner.run(solve_id, base_cfg, request.matrix, request.limits))

    return SolveResponse(solve_id=solve.id, status=solve.status)


@router.get("/", response_model=List[SolveOut])
def list_solves(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SolveOut]:
    solves = (
        db.query(Solve)
        .filter(Solve.user_id == current_user.id)
        .order_by(Solve.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [SolveOut.model_validate(item) for item in solves]


@router.get("/{solve_id}", response_model=SolveDetailOut)
def get_solve(
    solve_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SolveDetailOut:
    solve = (
        db.query(Solve)
        .options(selectinload(Solve.runs), selectinload(Solve.champion_run))
        .filter(Solve.id == solve_id, Solve.user_id == current_user.id)
        .one_or_none()
    )
    if not solve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solve not found")

    detail = SolveDetailOut.model_validate(solve)
    if solve.champion_run:
        detail.champion_run = SolveRunOut.model_validate(solve.champion_run)
    detail.runs = [SolveRunOut.model_validate(run) for run in solve.runs]
    return detail


@router.get("/{solve_id}/runs", response_model=List[SolveRunOut])
def list_runs(
    solve_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[SolveRunOut]:
    runs = (
        db.query(SolveRun)
        .join(Solve, SolveRun.solve_id == Solve.id)
        .filter(Solve.id == solve_id, Solve.user_id == current_user.id)
        .order_by(SolveRun.created_at.asc())
        .all()
    )
    if not runs:
        solve_exists = (
            db.query(Solve)
            .filter(Solve.id == solve_id, Solve.user_id == current_user.id)
            .first()
        )
        if not solve_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solve not found")
    return [SolveRunOut.model_validate(run) for run in runs]
