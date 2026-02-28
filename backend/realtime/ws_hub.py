"""In-memory WebSocket hub for controller-side per-session broadcasting."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Set

from fastapi import WebSocket

from .ws_protocol import WSMessageType, build_envelope

logger = logging.getLogger(__name__)


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


_hub_singleton: SessionWebSocketHub | None = None


def get_ws_hub() -> SessionWebSocketHub:
    global _hub_singleton
    if _hub_singleton is None:
        _hub_singleton = SessionWebSocketHub()
    return _hub_singleton
