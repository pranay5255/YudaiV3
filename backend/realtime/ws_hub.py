"""Backward-compat shim — SessionWebSocketHub is now in ws_protocol.py."""

from .ws_protocol import SessionWebSocketHub, get_ws_hub  # noqa: F401
