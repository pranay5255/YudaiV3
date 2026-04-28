#!/usr/bin/env bash
set -euo pipefail

export YUDAI_TEST_API_ENABLED="${YUDAI_TEST_API_ENABLED:-true}"
export YUDAI_TEST_FAKE_LLM="${YUDAI_TEST_FAKE_LLM:-true}"
export YUDAI_TEST_FAKE_MSWEA="${YUDAI_TEST_FAKE_MSWEA:-true}"
export REALTIME_WS_UNIFIED_ENABLED="${REALTIME_WS_UNIFIED_ENABLED:-true}"
export REALTIME_MODAL_PROVISIONING_ENABLED="${REALTIME_MODAL_PROVISIONING_ENABLED:-false}"
export SANDBOX_TUNNEL_TEMPLATE="${SANDBOX_TUNNEL_TEMPLATE:-http://sandbox-dev:8100}"
export CONTROLLER_INTERNAL_WS_SECRET="${CONTROLLER_INTERNAL_WS_SECRET:-local-dev-secret}"
export CONTROLLER_HEARTBEAT_SECRET="${CONTROLLER_HEARTBEAT_SECRET:-local-heartbeat-secret}"

docker compose -f docker-compose.backend-only.yml --profile local-sandbox up -d --build db backend sandbox-dev

for _ in $(seq 1 60); do
  if curl -fsS "${BACKEND_URL:-http://localhost:8000}/health" >/dev/null; then
    break
  fi
  sleep 2
done

curl -fsS "${BACKEND_URL:-http://localhost:8000}/health"
curl -fsS "${BACKEND_URL:-http://localhost:8000}/realtime/flags"
