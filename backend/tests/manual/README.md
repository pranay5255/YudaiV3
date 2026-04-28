# Backend-Only WebSocket Smoke Tests

These scripts validate the backend API and unified WebSocket path without GitHub OAuth.
They use the disabled-by-default `/test` API to mint a local session token, plus fake LLM
and fake MSWEA modes so the flow can run without external LLM, GitHub, or Modal credentials.

Run the local sandbox profile:

```bash
backend/tests/manual/run_all.sh
```

The runner executes:

1. Compose health and local sandbox startup.
2. Test session/token creation through `/test/auth/session`.
3. Unified WebSocket handshake.
4. Chat streaming over WebSocket.
5. Workflow issue/context commands over WebSocket.
6. Question answer command over WebSocket.
7. Runtime ensure and fake execution lifecycle over controller-to-sandbox WebSocket.
8. Artifact/cache status checks.

Optional Modal parity smoke:

```bash
backend/tests/manual/08_modal_parity_optional.sh
```

