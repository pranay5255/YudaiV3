"""WebSocket message protocol for unified realtime communication."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from utils import utc_now


class WSMessageType(str, Enum):
    # Client -> Server
    CHAT_MESSAGE = "chat_message"
    USER_RESPONSE = "user_response"

    # Server -> Client
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
    options: List[str] = Field(default_factory=list)


class StatusPayload(BaseModel):
    status: str
    detail: Optional[str] = None


# ---------------------------------------------------------------------------
# Typed payloads (client -> server)
# ---------------------------------------------------------------------------


class ChatMessagePayload(BaseModel):
    content: str


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
