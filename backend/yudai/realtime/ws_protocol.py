"""WebSocket message protocol and hub for unified realtime communication."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket
from pydantic import BaseModel, Field

from yudai.utils import utc_now


class WSMessageType(str, Enum):
    # Client -> Server
    USER_RESPONSE = "user_response"
    EXEC_START = "exec.start"
    EXEC_STDIN = "exec.stdin"
    EXEC_CANCEL = "exec.cancel"

    # Server -> Client
    LLM_STREAM = "llm_stream"
    SANDBOX_STREAM = "sandbox_stream"
    MODE_EVENT = "mode_event"
    STATE_EVENT = "state_event"
    TRAJECTORY_UPDATE = "trajectory_update"
    TOOL_CALL = "tool_call"
    AGENT_QUESTION = "agent_question"
    STATUS = "status"
    HEARTBEAT = "heartbeat"
    ERROR = "error"
    DONE = "done"


class WSEnvelope(BaseModel):
    """Top-level message envelope for all WS communication."""

    type: WSMessageType
    ts: datetime = Field(default_factory=utc_now)
    payload: Dict[str, Any] = Field(default_factory=dict)
    seq: int = 0


# ---------------------------------------------------------------------------
# Typed payloads (server -> client)
# ---------------------------------------------------------------------------


class TrajectoryUpdatePayload(BaseModel):
    messages: List[Dict[str, Any]]
    info: Dict[str, Any] = Field(default_factory=dict)
    message_count: int = 0
    new_message_start_index: int = 0


class ToolCallPayload(BaseModel):
    tool_name: str
    tool_input: Dict[str, Any] = Field(default_factory=dict)
    call_id: Optional[str] = None


class AgentQuestionPayload(BaseModel):
    question_id: str
    question_text: str
    multi_select: bool = False
    options: List[Dict[str, str]] = Field(default_factory=list)


class StatusPayload(BaseModel):
    status: str
    detail: Optional[str] = None


class LLMStreamPayload(BaseModel):
    stream: str = "llm"
    text: str
    final: bool = False


class SandboxStreamPayload(BaseModel):
    stream: str = "sandbox"
    event: str
    data: Optional[str] = None
    exit_code: Optional[int] = None
    pid: Optional[int] = None
    command: Optional[str] = None


class ModeEventPayload(BaseModel):
    mode: str
    state: str
    previous_mode: Optional[str] = None
    detail: Optional[str] = None
    execution_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Typed payloads (client -> server)
# ---------------------------------------------------------------------------


class UserResponsePayload(BaseModel):
    question_id: str
    answer: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_seq_counter: int = 0


def _next_seq() -> int:
    global _seq_counter
    _seq_counter += 1
    return _seq_counter


def build_envelope(
    msg_type: WSMessageType,
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    """Serialize a WSEnvelope to JSON string."""
    envelope = WSEnvelope(
        type=msg_type,
        payload=payload or {},
        seq=_next_seq(),
    )
    return envelope.model_dump_json()


# ---------------------------------------------------------------------------
# Per-session WebSocket hub
# (consolidated from ws_hub.py)
# ---------------------------------------------------------------------------

_ws_hub_logger = logging.getLogger(__name__)


class SessionWebSocketHub:
    """Tracks active frontend sockets by session and broadcasts envelopes."""

    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def register(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            bucket = self._connections.setdefault(session_id, set())
            bucket.add(websocket)

    async def unregister(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            bucket = self._connections.get(session_id)
            if not bucket:
                return
            bucket.discard(websocket)
            if not bucket:
                self._connections.pop(session_id, None)

    async def send_to_session(
        self,
        session_id: str,
        msg_type: WSMessageType,
        payload: Dict[str, Any],
    ) -> int:
        async with self._lock:
            sockets = list(self._connections.get(session_id, set()))

        if not sockets:
            return 0

        message = build_envelope(msg_type, payload)
        delivered = 0
        stale: list[WebSocket] = []
        for socket in sockets:
            try:
                await socket.send_text(message)
                delivered += 1
            except Exception:
                stale.append(socket)

        if stale:
            async with self._lock:
                bucket = self._connections.get(session_id, set())
                for socket in stale:
                    bucket.discard(socket)
                if not bucket:
                    self._connections.pop(session_id, None)

        return delivered


_hub_singleton: Optional[SessionWebSocketHub] = None


def get_ws_hub() -> SessionWebSocketHub:
    global _hub_singleton
    if _hub_singleton is None:
        _hub_singleton = SessionWebSocketHub()
    return _hub_singleton
