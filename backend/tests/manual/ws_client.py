#!/usr/bin/env python3
"""Small websocket client for backend-only manual smoke tests."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from urllib.parse import quote

import websockets


def _ws_url(base_url: str, session_id: str, token: str) -> str:
    base = base_url.rstrip("/")
    if base.startswith("https://"):
        base = "wss://" + base[len("https://") :]
    elif base.startswith("http://"):
        base = "ws://" + base[len("http://") :]
    return (
        f"{base}/controller/sessions/{quote(session_id)}/ws/unified"
        f"?token={quote(token)}"
    )


async def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--send", help="JSON websocket message to send")
    parser.add_argument("--expect-type")
    parser.add_argument("--expect-status")
    parser.add_argument("--request-id")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-events", type=int, default=80)
    args = parser.parse_args()

    url = _ws_url(args.base_url, args.session_id, args.token)
    async with websockets.connect(url, max_size=None, open_timeout=10) as ws:
        if args.send:
            await ws.send(args.send)

        seen = []
        for _ in range(args.max_events):
            raw = await asyncio.wait_for(ws.recv(), timeout=args.timeout)
            event = json.loads(raw)
            seen.append(event)
            print(json.dumps(event, sort_keys=True))

            if args.request_id and event.get("request_id") != args.request_id:
                continue
            if args.expect_type and event.get("type") != args.expect_type:
                continue
            if args.expect_status:
                payload = event.get("payload") or {}
                status_value = payload.get("status")
                if status_value != args.expect_status:
                    continue
            return 0

    print("expected event not observed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))

