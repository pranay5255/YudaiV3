"""Realtime tunnel and stream error helpers (Phase 1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import HTTPException


class RealtimeErrorCode(str, Enum):
    TUNNEL_UNAVAILABLE = "TUNNEL_UNAVAILABLE"
    TUNNEL_AUTH_EXPIRED = "TUNNEL_AUTH_EXPIRED"
    TUNNEL_TERMINATED = "TUNNEL_TERMINATED"
    TUNNEL_RESOLVE_FAILED = "TUNNEL_RESOLVE_FAILED"
    # Deprecated: SSE codes superseded by WS unified protocol
    SSE_AUTH_INVALID = "SSE_AUTH_INVALID"
    SSE_STREAM_TIMEOUT = "SSE_STREAM_TIMEOUT"
    SSE_STREAM_TERMINATED = "SSE_STREAM_TERMINATED"
    WS_AUTH_INVALID = "WS_AUTH_INVALID"
    WS_RETRY_EXHAUSTED = "WS_RETRY_EXHAUSTED"
    SINGLE_ACTIVE_EDITOR_CONFLICT = "SINGLE_ACTIVE_EDITOR_CONFLICT"
    WS_PROXY_UPSTREAM_UNAVAILABLE = "WS_PROXY_UPSTREAM_UNAVAILABLE"
    WS_HEARTBEAT_TIMEOUT = "WS_HEARTBEAT_TIMEOUT"
    WS_MESSAGE_PARSE_ERROR = "WS_MESSAGE_PARSE_ERROR"
    PROXY_UPSTREAM_ERROR = "PROXY_UPSTREAM_ERROR"
    MODAL_PROVISION_FAILED = "MODAL_PROVISION_FAILED"


@dataclass(frozen=True)
class RealtimeErrorSpec:
    code: RealtimeErrorCode
    http_status: int
    retryable: bool
    message: str


ERROR_SPECS: Dict[RealtimeErrorCode, RealtimeErrorSpec] = {
    RealtimeErrorCode.TUNNEL_UNAVAILABLE: RealtimeErrorSpec(
        code=RealtimeErrorCode.TUNNEL_UNAVAILABLE,
        http_status=503,
        retryable=False,
        message="Sandbox tunnel is unavailable. Please create a new session.",
    ),
    RealtimeErrorCode.TUNNEL_AUTH_EXPIRED: RealtimeErrorSpec(
        code=RealtimeErrorCode.TUNNEL_AUTH_EXPIRED,
        http_status=401,
        retryable=True,
        message="Session expired. Sign in again to reconnect to sandbox.",
    ),
    RealtimeErrorCode.TUNNEL_TERMINATED: RealtimeErrorSpec(
        code=RealtimeErrorCode.TUNNEL_TERMINATED,
        http_status=410,
        retryable=False,
        message="This session sandbox has already been terminated.",
    ),
    RealtimeErrorCode.TUNNEL_RESOLVE_FAILED: RealtimeErrorSpec(
        code=RealtimeErrorCode.TUNNEL_RESOLVE_FAILED,
        http_status=502,
        retryable=True,
        message="Unable to resolve sandbox tunnel. Retry in a few seconds.",
    ),
    RealtimeErrorCode.SSE_AUTH_INVALID: RealtimeErrorSpec(
        code=RealtimeErrorCode.SSE_AUTH_INVALID,
        http_status=401,
        retryable=True,
        message="Unable to stream updates because session authentication failed.",
    ),
    RealtimeErrorCode.SSE_STREAM_TIMEOUT: RealtimeErrorSpec(
        code=RealtimeErrorCode.SSE_STREAM_TIMEOUT,
        http_status=408,
        retryable=True,
        message="Live stream timed out. Reconnecting...",
    ),
    RealtimeErrorCode.SSE_STREAM_TERMINATED: RealtimeErrorSpec(
        code=RealtimeErrorCode.SSE_STREAM_TERMINATED,
        http_status=410,
        retryable=False,
        message="Stream closed because the sandbox ended.",
    ),
    RealtimeErrorCode.WS_AUTH_INVALID: RealtimeErrorSpec(
        code=RealtimeErrorCode.WS_AUTH_INVALID,
        http_status=401,
        retryable=True,
        message="Chat connection rejected due to invalid session authentication.",
    ),
    RealtimeErrorCode.WS_RETRY_EXHAUSTED: RealtimeErrorSpec(
        code=RealtimeErrorCode.WS_RETRY_EXHAUSTED,
        http_status=503,
        retryable=False,
        message="Chat disconnected after 10 reconnect attempts.",
    ),
    RealtimeErrorCode.SINGLE_ACTIVE_EDITOR_CONFLICT: RealtimeErrorSpec(
        code=RealtimeErrorCode.SINGLE_ACTIVE_EDITOR_CONFLICT,
        http_status=409,
        retryable=False,
        message=(
            "Another active editor session already owns this sandbox identity. "
            "Finish or terminate that session before creating a new one."
        ),
    ),
    RealtimeErrorCode.WS_PROXY_UPSTREAM_UNAVAILABLE: RealtimeErrorSpec(
        code=RealtimeErrorCode.WS_PROXY_UPSTREAM_UNAVAILABLE,
        http_status=502,
        retryable=True,
        message="Sandbox WebSocket upstream is unavailable. Retrying...",
    ),
    RealtimeErrorCode.WS_HEARTBEAT_TIMEOUT: RealtimeErrorSpec(
        code=RealtimeErrorCode.WS_HEARTBEAT_TIMEOUT,
        http_status=408,
        retryable=True,
        message="WebSocket heartbeat timed out. Reconnecting...",
    ),
    RealtimeErrorCode.WS_MESSAGE_PARSE_ERROR: RealtimeErrorSpec(
        code=RealtimeErrorCode.WS_MESSAGE_PARSE_ERROR,
        http_status=400,
        retryable=False,
        message="Failed to parse WebSocket message.",
    ),
    RealtimeErrorCode.PROXY_UPSTREAM_ERROR: RealtimeErrorSpec(
        code=RealtimeErrorCode.PROXY_UPSTREAM_ERROR,
        http_status=502,
        retryable=True,
        message="Upstream sandbox returned an error. Retry in a few seconds.",
    ),
    RealtimeErrorCode.MODAL_PROVISION_FAILED: RealtimeErrorSpec(
        code=RealtimeErrorCode.MODAL_PROVISION_FAILED,
        http_status=503,
        retryable=False,
        message="Failed to provision Modal sandbox compute.",
    ),
}


def error_payload(
    code: RealtimeErrorCode,
    *,
    message: Optional[str] = None,
    detail: Optional[str] = None,
) -> Dict[str, Any]:
    spec = ERROR_SPECS[code]
    payload: Dict[str, Any] = {
        "code": spec.code.value,
        "message": message or spec.message,
        "retryable": spec.retryable,
    }
    if detail:
        payload["detail"] = detail
    return payload


def as_http_exception(
    code: RealtimeErrorCode,
    *,
    message: Optional[str] = None,
    detail: Optional[str] = None,
) -> HTTPException:
    spec = ERROR_SPECS[code]
    return HTTPException(
        status_code=spec.http_status,
        detail=error_payload(code, message=message, detail=detail),
    )
