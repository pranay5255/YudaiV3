"""
Solver manager orchestrating asynchronous mini-swe-agent solve sessions.

This module handles:
- Solve session orchestration and lifecycle management
- Database updates and state tracking
- Async task management and cleanup
- Integration with sandbox executor for agent execution
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from db.database import SessionLocal
from fastapi import HTTPException, status
from models import (
    AIModel,
    CancelSolveResponse,
    ChatSession,
    Issue,
    Solve,
    SolveProgress,
    SolveRun,
    SolveRunOut,
    SolveStatus,
    SolveStatusResponse,
    StartSolveRequest,
    StartSolveResponse,
    User,
)
from solver.sandbox import (
    HeadlessSandboxExecutor,
    HeadlessSandboxRequest,
    SandboxExecutionError,
    SandboxRunResult,
)
from sqlalchemy.orm import Session

from utils import utc_now

logger = logging.getLogger(__name__)


# ============================================================================
# SOLVER MANAGER - ORCHESTRATION & DATABASE MANAGEMENT
# ============================================================================


@dataclass
class SolveTaskState:
    """Tracks background task metadata for running solves."""

    solve_id: str
    run_ids: List[str]
    executors: Dict[str, HeadlessSandboxExecutor]
    task: asyncio.Task


@dataclass
class ModelRunPlan:
    """Plan for executing a single model configuration inside a solve."""

    run_id: str
    ai_model_id: int
    model_identifier: str
    temperature: float


class SolverManager(ABC):
    """Base interface describing solver manager operations."""

    @abstractmethod
    async def start_solve(
        self, *, session_id: str, request: StartSolveRequest, user: User
    ) -> StartSolveResponse: ...

    @abstractmethod
    async def get_status(
        self, *, session_id: str, solve_id: str, user: User
    ) -> SolveStatusResponse: ...

    @abstractmethod
    async def cancel_solve(
        self, *, session_id: str, solve_id: str, user: User
    ) -> CancelSolveResponse: ...


class DefaultSolverManager(SolverManager):
    """Concrete solver manager that runs one experiment per solve session."""

    def __init__(
        self, session_factory=SessionLocal, *, max_parallel: Optional[int] = None
    ):
        self._session_factory = session_factory
        self._tasks: Dict[str, SolveTaskState] = {}
        self._lock = asyncio.Lock()
        self._max_parallel = max_parallel or int(os.getenv("SOLVER_MAX_PARALLEL", "3"))
        self._time_budget_s = int(os.getenv("SOLVER_TIME_BUDGET_SECONDS", "5400"))

    @staticmethod
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _coerce_int(value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _coerce_float(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _extract_solve_options(self, solve: Solve) -> Dict[str, Any]:
        matrix = solve.matrix or {}
        return {
            "small_change": self._coerce_bool(matrix.get("small_change")),
            "best_effort": self._coerce_bool(matrix.get("best_effort")),
            "max_iterations": self._coerce_int(matrix.get("max_iterations"), 50),
            "max_cost": self._coerce_float(matrix.get("max_cost"), 10.0),
        }

    async def start_solve(
        self, *, session_id: str, request: StartSolveRequest, user: User
    ) -> StartSolveResponse:
        await self._assert_capacity()

        solve_id = uuid.uuid4().hex
        model_run_plans: List[ModelRunPlan] = []
        issue_url: Optional[str] = None

        db = self._session_factory()
        try:
            chat_session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id, ChatSession.user_id == user.id
                )
                .first()
            )
            if not chat_session:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Session not found for user"
                )

            issue = db.query(Issue).filter(Issue.id == request.issue_id).first()
            if not issue:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Issue not found")
            issue_url = issue.html_url

            ai_models = self._select_models(
                db,
                ai_model_id=request.ai_model_id,
                ai_model_ids=request.ai_model_ids,
            )
            logger.info(
                "Starting solve %s with %d model(s): %s",
                solve_id,
                len(ai_models),
                ", ".join(model.model_id for model in ai_models),
            )

            repo_url = request.repo_url or getattr(issue.repository, "repo_url", None)
            if not repo_url:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Repository URL is required for solver execution",
                )

            experiments = []
            model_run_plans: List[ModelRunPlan] = []
            solve_runs: List[SolveRun] = []
            selected_models = ai_models[:1]

            for current_model in selected_models:
                run_id = uuid.uuid4().hex
                temperature = self._extract_temperature(current_model)
                experiments.append(
                    {
                        "run_id": run_id,
                        "model": current_model.model_id,
                        "temperature": temperature,
                        "mode": "yolo",
                        "ai_model_id": current_model.id,
                    }
                )
                solve_runs.append(
                    SolveRun(
                        id=run_id,
                        solve_id=solve_id,
                        model=current_model.model_id,
                        temperature=temperature,
                        max_edits=5,
                        evolution="baseline",
                        status=SolveStatus.PENDING.value,
                    )
                )
                model_run_plans.append(
                    ModelRunPlan(
                        run_id=run_id,
                        ai_model_id=current_model.id,
                        model_identifier=current_model.model_id,
                        temperature=temperature,
                    )
                )

            max_parallel = 1

            solve = Solve(
                id=solve_id,
                user_id=user.id,
                session_id=chat_session.id,
                repo_url=repo_url,
                issue_number=issue.number,
                base_branch=request.branch_name,
                status=SolveStatus.PENDING.value,
                matrix={
                    "experiments": experiments,
                    "small_change": request.small_change,
                    "best_effort": request.best_effort,
                    "max_iterations": request.max_iterations,
                    "max_cost": request.max_cost,
                },
                limits={
                    "max_parallel": max_parallel,
                    "time_budget_s": self._time_budget_s,
                },
                requested_by=user.github_username or user.email or "unknown",
                max_parallel=max_parallel,
                time_budget_s=self._time_budget_s,
            )

            # Store user options as attributes for easy access
            solve.small_change = request.small_change
            solve.best_effort = request.best_effort
            solve.max_iterations = request.max_iterations
            solve.max_cost = request.max_cost

            db.add(solve)
            for solve_run in solve_runs:
                db.add(solve_run)
            db.commit()
        finally:
            db.close()

        run_ids = [plan.run_id for plan in model_run_plans]
        executor_registry: Dict[str, HeadlessSandboxExecutor] = {}

        task = asyncio.create_task(
            self._execute_runs(
                solve_id=solve_id,
                run_plans=model_run_plans,
                issue_url=issue_url or "",
                repo_url=repo_url,
                branch_name=request.branch_name,
                executor_registry=executor_registry,
            ),
            name=f"solve-{solve_id}",
        )

        task.add_done_callback(
            lambda t, sid=solve_id: asyncio.create_task(self._cleanup_task(sid))
        )

        async with self._lock:
            self._tasks[solve_id] = SolveTaskState(
                solve_id=solve_id,
                run_ids=run_ids,
                executors=executor_registry,
                task=task,
            )

        return StartSolveResponse(
            solve_session_id=solve_id,
            status=SolveStatus.PENDING,
        )

    async def _execute_runs(
        self,
        *,
        solve_id: str,
        run_plans: List[ModelRunPlan],
        issue_url: str,
        repo_url: str,
        branch_name: str,
        executor_registry: Dict[str, HeadlessSandboxExecutor],
    ):
        """Execute each requested run sequentially inside its own sandbox."""

        if not run_plans:
            logger.error("No run plans available for solve %s", solve_id)
            return

        try:
            for plan in run_plans:
                if plan.run_id in executor_registry:
                    logger.warning(
                        "Run %s already has an executor registered. Skipping duplicate.",
                        plan.run_id,
                    )
                    continue

                executor = HeadlessSandboxExecutor()
                executor_registry[plan.run_id] = executor
                logger.info(
                    "Launching run %s for solve %s with model %s",
                    plan.run_id,
                    solve_id,
                    plan.model_identifier,
                )

                try:
                    await self._execute_run(
                        solve_id=solve_id,
                        run_id=plan.run_id,
                        issue_url=issue_url,
                        repo_url=repo_url,
                        branch_name=branch_name,
                        model_name=plan.model_identifier,
                        executor=executor,
                    )
                finally:
                    executor_registry.pop(plan.run_id, None)
        except asyncio.CancelledError:
            logger.info("Solve %s execution loop cancelled", solve_id)
            raise

    async def get_status(
        self, *, session_id: str, solve_id: str, user: User
    ) -> SolveStatusResponse:
        db = self._session_factory()
        try:
            # Look up ChatSession by string session_id
            chat_session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id, ChatSession.user_id == user.id
                )
                .first()
            )
            if not chat_session:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Session not found for user"
                )

            # Query Solve using integer chat_session.id
            solve = (
                db.query(Solve)
                .filter(
                    Solve.id == solve_id,
                    Solve.session_id == chat_session.id,
                    Solve.user_id == user.id,
                )
                .first()
            )
            if not solve:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Solve session not found"
                )

            runs_out = [SolveRunOut.model_validate(run) for run in solve.runs]
            progress = self._build_progress(solve, runs_out)

            champion = (
                SolveRunOut.model_validate(solve.champion_run)
                if solve.champion_run
                else None
            )

            return SolveStatusResponse(
                solve_session_id=solve.id,
                status=SolveStatus(solve.status),
                progress=progress,
                runs=runs_out,
                champion_run=champion,
                error_message=solve.error_message,
            )
        finally:
            db.close()

    async def cancel_solve(
        self, *, session_id: str, solve_id: str, user: User
    ) -> CancelSolveResponse:
        state: Optional[SolveTaskState] = None
        async with self._lock:
            state = self._tasks.get(solve_id)

        if state:
            for executor in list(state.executors.values()):
                await executor.cancel()
            state.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.task

        db = self._session_factory()
        try:
            # Look up ChatSession by string session_id
            chat_session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id, ChatSession.user_id == user.id
                )
                .first()
            )
            if not chat_session:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Session not found for user"
                )

            # Query Solve using integer chat_session.id
            solve = (
                db.query(Solve)
                .filter(
                    Solve.id == solve_id,
                    Solve.session_id == chat_session.id,
                    Solve.user_id == user.id,
                )
                .first()
            )
            if not solve:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Solve session not found"
                )

            timestamp = utc_now()
            if solve.status not in {
                SolveStatus.COMPLETED.value,
                SolveStatus.CANCELLED.value,
                SolveStatus.FAILED.value,
            }:
                solve.status = SolveStatus.CANCELLED.value
                solve.error_message = "Solve cancelled by user"
                solve.completed_at = timestamp

            for run in solve.runs:
                if run.status not in {
                    SolveStatus.COMPLETED.value,
                    SolveStatus.CANCELLED.value,
                    SolveStatus.FAILED.value,
                }:
                    run.status = SolveStatus.CANCELLED.value
                    run.error_message = "Cancelled by user"
                    run.completed_at = timestamp

            db.commit()
        finally:
            db.close()

        await self._cleanup_task(solve_id)
        return CancelSolveResponse(
            solve_session_id=solve_id,
            status=SolveStatus.CANCELLED,
            message="Solve cancelled",
        )

    async def _execute_run(
        self,
        *,
        solve_id: str,
        run_id: str,
        issue_url: str,
        repo_url: str,
        branch_name: str,
        model_name: str,
        executor: HeadlessSandboxExecutor,
    ):
        db = self._session_factory()
        try:
            solve = db.query(Solve).filter(Solve.id == solve_id).first()
            run = db.query(SolveRun).filter(SolveRun.id == run_id).first()
            if not solve or not run:
                logger.warning("Solve or run record missing for %s", solve_id)
                return

            logger.info(
                "Preparing run %s for solve %s (model=%s, issue=%s)",
                run_id,
                solve_id,
                model_name,
                issue_url,
            )

            now = utc_now()
            solve.status = SolveStatus.RUNNING.value
            solve.started_at = solve.started_at or now
            run.status = SolveStatus.RUNNING.value
            run.started_at = now
            db.commit()

            options = self._extract_solve_options(solve)

            request = self._build_headless_request(
                issue_url=issue_url,
                repo_url=repo_url,
                branch_name=branch_name,
                model_name=model_name,
                run=run,
                solve=solve,
                options=options,
            )

            try:
                result = await executor.run(request)
                self._record_success(db, solve, run, result)
            except SandboxExecutionError as exc:
                self._record_failure(
                    db,
                    solve,
                    run,
                    error_message=str(exc),
                    logs=exc.logs,
                )
            except asyncio.CancelledError:
                self._record_cancelled(db, solve, run)
                raise
            except Exception as exc:  # pragma: no cover - defensive programming
                logger.exception("Solver run failed: %s", exc)
                self._record_failure(
                    db,
                    solve,
                    run,
                    error_message=str(exc),
                    logs="",
                )
        finally:
            db.close()

    def _build_headless_request(
        self,
        *,
        issue_url: str,
        repo_url: str,
        branch_name: str,
        model_name: str,
        run: SolveRun,
        solve: Solve,
        options: Dict[str, Any],
    ) -> HeadlessSandboxRequest:
        """Create a sandbox execution request for a solver run."""

        return HeadlessSandboxRequest(
            issue_url=issue_url,
            repo_url=repo_url,
            branch_name=branch_name,
            model_name=model_name,
            temperature=run.temperature,
            small_change=options["small_change"],
            best_effort=options["best_effort"],
            max_iterations=options["max_iterations"],
            max_cost=options["max_cost"],
            solve_id=solve.id,
            solve_run_id=run.id,
            verbose=True,
        )

    def _record_success(
        self, db: Session, solve: Solve, run: SolveRun, result: SandboxRunResult
    ):
        timestamp = result.completed_at
        succeeded = result.exit_code == 0
        run.status = (
            SolveStatus.COMPLETED.value if succeeded else SolveStatus.FAILED.value
        )
        run.completed_at = timestamp
        run.tests_passed = succeeded
        run.latency_ms = result.duration_ms
        run.sandbox_id = result.sandbox_id
        run.pr_url = result.pr_url
        run.error_message = None if succeeded else "Agent execution failed"

        # Store trajectory data with local path and metadata
        trajectory_data = {}
        if result.trajectory_file:
            trajectory_data["remote_path"] = result.trajectory_file
        if result.local_trajectory_path:
            trajectory_data["local_path"] = result.local_trajectory_path
        if result.trajectory_metadata:
            trajectory_data["metadata"] = {
                "exit_status": result.trajectory_metadata.exit_status,
                "submission": result.trajectory_metadata.submission,
                "instance_cost": result.trajectory_metadata.instance_cost,
                "api_calls": result.trajectory_metadata.api_calls,
                "mini_version": result.trajectory_metadata.mini_version,
                "model_name": result.trajectory_metadata.model_name,
                "total_messages": result.trajectory_metadata.total_messages,
            }
        if trajectory_data:
            run.trajectory_data = trajectory_data

        preview_length = 2000
        run.diagnostics = {
            "command": result.command,
            "stdout_tail": (result.stdout or "")[-preview_length:],
            "stderr_tail": (result.stderr or "")[-preview_length:],
            "tfbd_path": result.tfbd_path,
            "script_path": result.script_path,
            "trajectory_file": result.trajectory_file,
            "local_trajectory_path": result.local_trajectory_path,
        }

        if succeeded and not solve.champion_run_id:
            solve.champion_run_id = run.id
            solve.error_message = None

        logger.info(
            "Run %s for solve %s completed (exit_code=%s, success=%s)",
            run.id,
            solve.id,
            result.exit_code,
            succeeded,
        )

        self._finalize_solve_if_complete(db, solve, completed_at=timestamp)
        db.commit()

    def _record_failure(
        self,
        db: Session,
        solve: Solve,
        run: SolveRun,
        *,
        error_message: str,
        logs: str,
    ):
        timestamp = utc_now()
        run.status = SolveStatus.FAILED.value
        run.completed_at = timestamp
        run.error_message = error_message
        run.diagnostics = {"error_logs": logs[-4000:]}

        if not solve.error_message:
            solve.error_message = error_message

        logger.warning(
            "Run %s for solve %s failed: %s", run.id, solve.id, error_message
        )

        self._finalize_solve_if_complete(db, solve, completed_at=timestamp)
        db.commit()

    def _record_cancelled(self, db: Session, solve: Solve, run: SolveRun):
        timestamp = utc_now()
        run.status = SolveStatus.CANCELLED.value
        run.completed_at = timestamp
        run.error_message = "Cancelled by user"

        solve.status = SolveStatus.CANCELLED.value
        solve.error_message = "Cancelled by user"
        solve.completed_at = timestamp

        logger.info("Run %s for solve %s cancelled", run.id, solve.id)

        self._finalize_solve_if_complete(db, solve, completed_at=timestamp)
        db.commit()

    async def _cleanup_task(self, solve_id: str):
        async with self._lock:
            self._tasks.pop(solve_id, None)

    async def _assert_capacity(self):
        async with self._lock:
            if len(self._tasks) >= self._max_parallel:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Maximum number of concurrent solves reached",
                )

    def _finalize_solve_if_complete(
        self, db: Session, solve: Solve, *, completed_at: Optional[datetime] = None
    ):
        """Mark the parent solve complete once all runs are resolved."""

        if solve.status == SolveStatus.CANCELLED.value:
            return

        pending_statuses = {
            SolveStatus.PENDING.value,
            SolveStatus.RUNNING.value,
        }
        pending_runs = (
            db.query(SolveRun)
            .filter(
                SolveRun.solve_id == solve.id,
                SolveRun.status.in_(pending_statuses),
            )
            .count()
        )

        if pending_runs > 0:
            solve.status = SolveStatus.RUNNING.value
            return

        finish_time = completed_at or utc_now()
        solve.completed_at = solve.completed_at or finish_time

        if solve.champion_run_id:
            solve.status = SolveStatus.COMPLETED.value
            solve.error_message = None
        else:
            solve.status = SolveStatus.FAILED.value
            solve.error_message = solve.error_message or "All runs failed"

    def _select_models(
        self,
        db: Session,
        *,
        ai_model_id: Optional[int],
        ai_model_ids: Optional[List[int]],
    ) -> List[AIModel]:
        """Resolve requested models, preserving caller ordering."""

        base_query = db.query(AIModel).filter(AIModel.is_active.is_(True))

        if ai_model_ids:
            models = base_query.filter(AIModel.id.in_(ai_model_ids)).all()
            found_by_id = {model.id: model for model in models}
            ordered_models: List[AIModel] = []
            missing_ids: List[int] = []
            for requested_id in ai_model_ids:
                model = found_by_id.get(requested_id)
                if model:
                    ordered_models.append(model)
                else:
                    missing_ids.append(requested_id)

            if missing_ids:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail=f"AI models not found: {', '.join(map(str, missing_ids))}",
                )

            if not ordered_models:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="No active AI models available for the requested IDs",
                )

            return ordered_models

        if ai_model_id:
            model = (
                base_query.filter(AIModel.id == ai_model_id)
                .order_by(AIModel.id.asc())
                .first()
            )
            if not model:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail="AI model not found or inactive",
                )
            return [model]

        default_model = base_query.order_by(AIModel.id.asc()).first()
        if not default_model:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="No active AI models configured",
            )
        return [default_model]

    @staticmethod
    def _extract_temperature(model: AIModel) -> float:
        try:
            return float((model.config or {}).get("temperature", 0.1))
        except (TypeError, ValueError):
            return 0.1

    @staticmethod
    def _build_progress(solve: Solve, runs: list[SolveRunOut]) -> SolveProgress:
        runs_total = len(runs)
        runs_completed = sum(1 for run in runs if run.status == SolveStatus.COMPLETED)
        runs_failed = sum(1 for run in runs if run.status == SolveStatus.FAILED)
        runs_running = sum(1 for run in runs if run.status == SolveStatus.RUNNING)

        return SolveProgress(
            runs_total=runs_total,
            runs_completed=runs_completed,
            runs_failed=runs_failed,
            runs_running=runs_running,
            last_update=solve.updated_at or utc_now(),
            message=solve.status,
        )
