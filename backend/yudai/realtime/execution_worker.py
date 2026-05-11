"""Backend worker for queued session and sandbox executions."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import uuid
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from yudai.db.database import SessionLocal, init_db
from yudai.models import AgentExecution, AgentExecutionLease, ChatSession, SessionModeStatus
from yudai.utils import utc_now

from .mode_orchestrator import (
    BROWSER_CHECK_MODE,
    get_session_execution_orchestrator,
)

logger = logging.getLogger(__name__)


class ExecutionWorker:
    def __init__(self, *, poll_interval_seconds: float = 2.0) -> None:
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = asyncio.Event()
        self.worker_id = os.getenv("HOSTNAME") or f"backend-worker-{os.getpid()}"
        self.lease_seconds = int(os.getenv("EXECUTION_WORKER_LEASE_SECONDS", "120"))
        self.heartbeat_seconds = max(5, int(os.getenv("EXECUTION_WORKER_HEARTBEAT_SECONDS", "15")))

    def stop(self) -> None:
        self._stop_event.set()

    async def run_forever(self) -> None:
        while not self._stop_event.is_set():
            claimed_id = await self.run_once()
            if not claimed_id:
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.poll_interval_seconds,
                    )
                except asyncio.TimeoutError:
                    pass

    async def run_once(self) -> Optional[str]:
        db = SessionLocal()
        try:
            execution = self.claim_next(db)
            if not execution:
                return None
            execution_id = execution.id
            session = execution.session
            if not session:
                self._fail_claimed_execution(db, execution, "Execution has no session")
                return execution_id

            metadata = dict(execution.execution_metadata or {})
            user_id = int(metadata.get("user_id") or session.user_id)
            objective = str(
                metadata.get("objective_with_context")
                or metadata.get("objective")
                or "Continue the current workflow."
            )
            max_modes = metadata.get("max_modes")
            max_modes_int = int(max_modes) if max_modes is not None else None
            sidecar = bool(metadata.get("sidecar")) or execution.mode == BROWSER_CHECK_MODE
            session_public_id = session.session_id
            lease_id = str(metadata.get("lease_id") or "")
        finally:
            db.close()

        orchestrator = get_session_execution_orchestrator()
        heartbeat_task = (
            asyncio.create_task(self._heartbeat_lease(lease_id), name=f"execution-lease-{lease_id}")
            if lease_id
            else None
        )
        try:
            if sidecar:
                await orchestrator.run_browser_check(
                    session_public_id=session_public_id,
                    user_id=user_id,
                    execution_id=execution_id,
                    objective=objective,
                )
            else:
                await orchestrator.run_full_pipeline(
                    session_public_id=session_public_id,
                    user_id=user_id,
                    execution_id=execution_id,
                    objective=objective,
                    max_modes=max_modes_int,
                )
        except asyncio.CancelledError:
            logger.info("execution %s was cancelled while running", execution_id)
        except Exception:
            logger.exception("execution %s failed outside orchestrator handling", execution_id)
        finally:
            if heartbeat_task is not None:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            if lease_id:
                self.release_lease(lease_id, reason="worker_finished")
        return execution_id

    def claim_next(self, db: Session) -> Optional[AgentExecution]:
        self._requeue_expired_leases(db)
        query = (
            db.query(AgentExecution)
            .filter(AgentExecution.status == SessionModeStatus.QUEUED.value)
            .order_by(AgentExecution.created_at.asc(), AgentExecution.id.asc())
        )
        if db.bind is not None and db.bind.dialect.name != "sqlite":
            query = query.with_for_update(skip_locked=True)
        execution = query.first()
        if execution is None:
            return None

        now = utc_now()
        previous_attempt = (
            db.query(AgentExecutionLease)
            .filter(AgentExecutionLease.execution_id == execution.id)
            .count()
        )
        lease = AgentExecutionLease(
            lease_id=f"lease_{uuid.uuid4().hex[:24]}",
            execution_id=execution.id,
            worker_id=self.worker_id,
            lease_token=uuid.uuid4().hex,
            attempt=previous_attempt + 1,
            acquired_at=now,
            heartbeat_at=now,
            expires_at=now + timedelta(seconds=self.lease_seconds),
        )
        db.add(lease)

        execution.status = SessionModeStatus.RUNNING.value
        metadata = dict(execution.execution_metadata or {})
        metadata["claimed_at"] = now.isoformat()
        metadata["claimed_by"] = self.worker_id
        metadata["lease_id"] = lease.lease_id
        metadata["lease_attempt"] = lease.attempt
        execution.execution_metadata = metadata
        flag_modified(execution, "execution_metadata")

        session = execution.session
        if isinstance(session, ChatSession):
            active_execution = dict((session.mode_metadata or {}).get("active_execution") or {})
            if active_execution.get("execution_id") == execution.id:
                active_execution["status"] = SessionModeStatus.RUNNING.value
                active_execution["detail"] = "Execution worker claimed queued run"
                session.mode_metadata = {
                    **(session.mode_metadata or {}),
                    "active_execution": active_execution,
                }
                flag_modified(session, "mode_metadata")
            session.mode_status = SessionModeStatus.RUNNING.value
            session.mode_updated_at = utc_now()
            session.last_activity = utc_now()

        db.commit()
        db.refresh(execution)
        return execution

    def _requeue_expired_leases(self, db: Session) -> None:
        now = utc_now()
        expired_leases = (
            db.query(AgentExecutionLease)
            .filter(
                AgentExecutionLease.released_at.is_(None),
                AgentExecutionLease.expires_at < now,
            )
            .all()
        )
        for lease in expired_leases:
            execution = (
                db.query(AgentExecution)
                .filter(AgentExecution.id == lease.execution_id)
                .first()
            )
            lease.released_at = now
            lease.release_reason = "expired"
            if execution and execution.status in {
                SessionModeStatus.RUNNING.value,
                SessionModeStatus.DECIDING.value,
                SessionModeStatus.STALLED.value,
            }:
                execution.status = SessionModeStatus.QUEUED.value
                metadata = dict(execution.execution_metadata or {})
                metadata["stalled_at"] = now.isoformat()
                metadata["stalled_lease_id"] = lease.lease_id
                execution.execution_metadata = metadata
                flag_modified(execution, "execution_metadata")

                session = execution.session
                if isinstance(session, ChatSession):
                    active_execution = dict((session.mode_metadata or {}).get("active_execution") or {})
                    if active_execution.get("execution_id") == execution.id:
                        active_execution["status"] = SessionModeStatus.QUEUED.value
                        active_execution["detail"] = "Execution worker lease expired; run requeued"
                        session.mode_metadata = {
                            **(session.mode_metadata or {}),
                            "active_execution": active_execution,
                        }
                        flag_modified(session, "mode_metadata")
                    session.mode_status = SessionModeStatus.QUEUED.value
                    session.mode_updated_at = now
        if expired_leases:
            db.commit()

    async def _heartbeat_lease(self, lease_id: str) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            db = SessionLocal()
            try:
                lease = (
                    db.query(AgentExecutionLease)
                    .filter(
                        AgentExecutionLease.lease_id == lease_id,
                        AgentExecutionLease.released_at.is_(None),
                    )
                    .first()
                )
                if lease is None:
                    return
                now = utc_now()
                lease.heartbeat_at = now
                lease.expires_at = now + timedelta(seconds=self.lease_seconds)
                db.commit()
            finally:
                db.close()

    def release_lease(self, lease_id: str, *, reason: str) -> None:
        db = SessionLocal()
        try:
            lease = (
                db.query(AgentExecutionLease)
                .filter(
                    AgentExecutionLease.lease_id == lease_id,
                    AgentExecutionLease.released_at.is_(None),
                )
                .first()
            )
            if lease is None:
                return
            lease.released_at = utc_now()
            lease.release_reason = reason
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _fail_claimed_execution(db: Session, execution: AgentExecution, message: str) -> None:
        execution.status = SessionModeStatus.FAILED.value
        execution.error_message = message
        execution.completed_at = utc_now()
        db.commit()


async def _main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    init_db()
    worker = ExecutionWorker(
        poll_interval_seconds=float(os.getenv("EXECUTION_WORKER_POLL_SECONDS", "2"))
    )
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, worker.stop)
        except NotImplementedError:  # pragma: no cover - platform-specific
            pass
    logger.info("execution worker started")
    await worker.run_forever()
    logger.info("execution worker stopped")


if __name__ == "__main__":
    asyncio.run(_main())
