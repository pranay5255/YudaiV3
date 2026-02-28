# Rollout Flags (Controller-Broker Contract)

## Backend Flags

Defined in `backend/config/realtime_flags.py`.

1. `REALTIME_CONTROLLER_SPLIT_ENABLED` (default: `false`)
2. `REALTIME_CONTROLLER_BROKER_ENABLED` (default: `true`)
3. `REALTIME_SANDBOX_INTERNAL_EXEC_ENABLED` (default: `true`)
4. `REALTIME_MODE_ORCHESTRATOR_ENABLED` (default: `true`)
5. `REALTIME_WS_CHAT_ENABLED` (default: `false`)
6. `REALTIME_SSE_STREAM_ENABLED` (default: `false`)
7. `REALTIME_MODAL_PROVISIONING_ENABLED` (default: `false`)
8. `REALTIME_WS_UNIFIED_ENABLED` (default: `false`)
9. `REALTIME_CONTRACT_VERSION` (default: `realtime-v2-controller-broker`)

Exposed via endpoint:
`GET /realtime/flags`

## Frontend Flags

Defined in `src/config/realtimeFlags.ts`.

1. `VITE_REALTIME_CONTROLLER_SPLIT_ENABLED`
2. `VITE_REALTIME_CONTROLLER_BROKER_ENABLED`
3. `VITE_REALTIME_SANDBOX_INTERNAL_EXEC_ENABLED`
4. `VITE_REALTIME_MODE_ORCHESTRATOR_ENABLED`
5. `VITE_REALTIME_WS_CHAT_ENABLED`
6. `VITE_REALTIME_SSE_STREAM_ENABLED`
7. `VITE_REALTIME_WS_UNIFIED_ENABLED`
8. `VITE_REALTIME_CONTRACT_VERSION`

## Deprecated Flags

These are no longer part of the active contract and should not be used for new deployments.

1. `REALTIME_TUNNEL_MODE_ENABLED`
2. `REALTIME_CONTROLLER_PROXY_ENABLED`
3. `VITE_REALTIME_TUNNEL_MODE_ENABLED`
4. `VITE_REALTIME_CONTROLLER_PROXY_ENABLED`
