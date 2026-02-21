# Tunnel and Stream Error Taxonomy

Hard-error behavior is required when tunnel access fails. No proxy fallback.

## Canonical Error Codes

| Code | HTTP | Retryable | User Message |
|---|---:|---:|---|
| `TUNNEL_UNAVAILABLE` | 503 | No | `Sandbox tunnel is unavailable. Please create a new session.` |
| `TUNNEL_AUTH_EXPIRED` | 401 | Yes | `Session expired. Sign in again to reconnect to sandbox.` |
| `TUNNEL_TERMINATED` | 410 | No | `This session sandbox has already been terminated.` |
| `TUNNEL_RESOLVE_FAILED` | 502 | Yes | `Unable to resolve sandbox tunnel. Retry in a few seconds.` |
| `SSE_AUTH_INVALID` | 401 | Yes | `Unable to stream updates because session authentication failed.` |
| `SSE_STREAM_TIMEOUT` | 408 | Yes | `Live stream timed out. Reconnecting…` |
| `SSE_STREAM_TERMINATED` | 410 | No | `Stream closed because the sandbox ended.` |
| `WS_AUTH_INVALID` | 401 | Yes | `Chat connection rejected due to invalid session authentication.` |
| `WS_RETRY_EXHAUSTED` | 503 | No | `Chat disconnected after 10 reconnect attempts.` |

## SSE Terminal Event Contract

1. `completed`: solver run completed.
2. `failed`: solver run failed and has no retry in progress.
3. `cancelled`: user-initiated cancellation.
4. `sandbox_terminated`: sandbox lifecycle ended.

