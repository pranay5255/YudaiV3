# Realtime Contract (Controller-Broker v2)

This contract defines the controller-brokered realtime architecture.
Browser clients talk to the Node middleware for non-auth app traffic; the
middleware validates auth through REST before opening backend realtime links.

## Controller Endpoints

1. `POST /controller/sandboxes`
2. `GET /controller/sandboxes/{sandbox_id}`
3. `DELETE /controller/sandboxes/{sandbox_id}`
4. `POST /controller/sandboxes/{sandbox_id}/resolve-tunnel` (controller/internal diagnostics only)
5. `POST /controller/sandboxes/{sandbox_id}/heartbeat`
6. `POST /controller/sandboxes/cleanup`
7. `POST /controller/sessions/{session_id}/runtime`
8. `GET /controller/sessions/{session_id}/runtime`
9. `WS /controller/sessions/{session_id}/ws/unified` (internal Node middleware only)
10. `GET /realtime/flags`

Examples are defined in:
`backend/docs/realtime_phase0/contracts-controller.openapi.yaml`.

## Sessions API (Middleware Surface)

End-user session APIs are reached through Node middleware and forwarded to the
controller under `/daifu/*`, including:

1. `POST /daifu/sessions/{session_id}/ai-context`
2. `POST /daifu/sessions/{session_id}/ai-turns`
3. `POST /daifu/sessions/{session_id}/execution`

The server enforces fixed mode transitions:
`architect -> tester -> coder`.

## Sandbox Endpoints (Internal Only)

1. `GET /healthz`
2. `WS /internal/sessions/{session_id}/ws/exec`
   - accepts `exec.start`, `exec.stdin`, `exec.cancel`
   - emits stdout/stderr/exit events

Examples are defined in:
`backend/docs/realtime_phase0/contracts-sandbox.openapi.yaml`.

## Contract-Level Decisions

1. No browser traffic to sandbox tunnel/proxy routes.
2. Browser realtime uses Node SSE; controller unified WS is internal to Node.
3. Sandbox WS is authenticated with controller-only internal secret.
4. Session mode state is persisted server-side and cannot be user-forced.
