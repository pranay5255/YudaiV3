# Rollout Flags (Phase 0)

## Backend Flags

Defined in `backend/config/realtime_flags.py`.

1. `REALTIME_CONTROLLER_SPLIT_ENABLED` (default: `false`)
2. `REALTIME_TUNNEL_MODE_ENABLED` (default: `false`)
3. `REALTIME_WS_CHAT_ENABLED` (default: `false`)
4. `REALTIME_SSE_STREAM_ENABLED` (default: `false`)
5. `REALTIME_CONTRACT_VERSION` (default: `realtime-v1-phase0`)

Exposed via endpoint:
`GET /realtime/flags`

## Frontend Flags

Defined in `src/config/realtimeFlags.ts`.

1. `VITE_REALTIME_CONTROLLER_SPLIT_ENABLED`
2. `VITE_REALTIME_TUNNEL_MODE_ENABLED`
3. `VITE_REALTIME_WS_CHAT_ENABLED`
4. `VITE_REALTIME_SSE_STREAM_ENABLED`
5. `VITE_REALTIME_CONTRACT_VERSION`

## Env Templates Updated

1. `.env.dev`
2. `.env.prod`

