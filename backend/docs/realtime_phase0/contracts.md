# Phase 0 Contract Freeze

This contract freezes the initial controller/sandbox interface for Phase 1.

## Controller Endpoints (v1)

1. `POST /controller/sandboxes`
2. `GET /controller/sandboxes/{sandbox_id}`
3. `DELETE /controller/sandboxes/{sandbox_id}`
4. `POST /controller/sandboxes/{sandbox_id}/resolve-tunnel`
5. `POST /controller/sandboxes/{sandbox_id}/heartbeat`
6. `POST /controller/sandboxes/cleanup`
7. `GET /realtime/flags`

Examples are defined in:
`backend/docs/realtime_phase0/contracts-controller.openapi.yaml`.

## Sandbox Session Server Endpoints (v1)

1. `GET /healthz`
2. `POST /sessions/{session_id}/chat`
3. `POST /sessions/{session_id}/issues/create-with-context`
4. `POST /sessions/{session_id}/solve/start`
5. `GET /sessions/{session_id}/solve/status/{solve_id}`
6. `POST /sessions/{session_id}/solve/cancel/{solve_id}`
7. `GET /sessions/{session_id}/solve/stream/{solve_id}/{run_id}?token=...`
8. `GET /sessions/{session_id}/ws/chat` (WebSocket handshake path)

Examples are defined in:
`backend/docs/realtime_phase0/contracts-sandbox.openapi.yaml`.

## Contract-Level Decisions Applied

1. Identity key: `org + repo + environment`.
2. Auth: session JWT passthrough, 1 hour TTL, reusable until expiry.
3. Tunnel resolution may include an additional short-lived signed URL.
4. Frontend direct tunnel only; no controller proxy fallback.
5. Stream split: SSE for solve trajectory, WebSocket for chat.
6. Sandbox completion condition: both GitHub issue and PR creation done.
