"""Controller-side broker for internal sandbox command execution over WebSocket."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional
from sqlalchemy.orm import Session

from models import ChatSession, Sandbox, SandboxStatus

from .errors import RealtimeErrorCode, as_http_exception
from .lifecycle import RealtimeLifecycleService, get_realtime_lifecycle_service
from .sandbox_transport import run_sandbox_command

SandboxEventCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class SandboxExecBroker:
    """Sends exec.start/stdin/cancel to sandbox internal WS and streams events back."""

    def __init__(self, lifecycle: Optional[RealtimeLifecycleService] = None) -> None:
        self.lifecycle = lifecycle or get_realtime_lifecycle_service()

    def _resolve_runtime(self, db: Session, session: ChatSession) -> tuple[Sandbox, str]:
        runtime = self.lifecycle._get_latest_runtime(db, session_id=session.id)
        if not runtime or not runtime.sandbox_id:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_UNAVAILABLE)

        sandbox = self.lifecycle.get_sandbox_or_404(db, runtime.sandbox_id)
        if sandbox.status == SandboxStatus.TERMINATED.value:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_TERMINATED)
        if not sandbox.tunnel_url:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_UNAVAILABLE)

        return sandbox, sandbox.tunnel_url

    async def run_command(
        self,
        db: Session,
        *,
        session: ChatSession,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 1800,
        on_event: Optional[SandboxEventCallback] = None,
    ) -> Dict[str, Any]:
        sandbox, tunnel_url = self._resolve_runtime(db, session)
        result = await run_sandbox_command(
            tunnel_url=tunnel_url,
            session_public_id=session.session_id,
            command=command,
            cwd=cwd,
            env=env,
            timeout_seconds=timeout_seconds,
            on_event=on_event,
        )
        return {
            "sandbox_id": sandbox.id,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": result.duration_ms,
        }


_exec_broker_singleton: Optional[SandboxExecBroker] = None


def get_sandbox_exec_broker() -> SandboxExecBroker:
    global _exec_broker_singleton
    if _exec_broker_singleton is None:
        _exec_broker_singleton = SandboxExecBroker()
    return _exec_broker_singleton
