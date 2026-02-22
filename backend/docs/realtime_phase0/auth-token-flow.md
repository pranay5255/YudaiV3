# Auth and Token Flow (Phase 0)

## Fixed Decisions

1. Tunnel auth reuses existing session JWT.
2. JWT tunnel TTL is 1 hour.
3. JWT is reusable until expiration.
4. Controller may return signed short-lived tunnel URL in addition to JWT auth.
5. SSE query token is accepted for EventSource compatibility.

## Browser -> Controller -> Sandbox (direct tunnel)

```mermaid
sequenceDiagram
    participant B as Browser
    participant C as Controller
    participant S as Sandbox Server

    B->>C: POST /controller/sandboxes (Authorization: Bearer session_jwt)
    C->>C: validate session_jwt
    C->>C: create sandbox + store runtime metadata
    C-->>B: 201 {sandbox_id, signed_tunnel_url, token_ttl_seconds=3600}
    B->>S: HTTPS request to signed tunnel (Authorization: Bearer session_jwt)
    S->>S: validate session_jwt
    S-->>B: request response
```

## SSE Stream Auth (query token)

```mermaid
sequenceDiagram
    participant B as Browser(EventSource)
    participant S as Sandbox SSE Endpoint

    B->>S: GET /sessions/{id}/solve/stream/{solve_id}/{run_id}?token=session_jwt
    S->>S: validate token + expiry
    S-->>B: event: trajectory_update
    S-->>B: event: heartbeat
    S-->>B: event: done
```
