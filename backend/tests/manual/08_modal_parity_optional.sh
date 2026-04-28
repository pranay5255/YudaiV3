#!/usr/bin/env bash
set -euo pipefail

if [ -z "${MODAL_TOKEN_ID:-}" ] && [ -z "${MODAL_TOKEN_SECRET:-}" ]; then
  echo "Skipping Modal parity smoke: MODAL_TOKEN_ID/MODAL_TOKEN_SECRET are not set."
  exit 0
fi

export YUDAI_TEST_API_ENABLED="${YUDAI_TEST_API_ENABLED:-true}"
export YUDAI_TEST_FAKE_LLM="${YUDAI_TEST_FAKE_LLM:-true}"
export YUDAI_TEST_FAKE_MSWEA="${YUDAI_TEST_FAKE_MSWEA:-true}"
export REALTIME_WS_UNIFIED_ENABLED="${REALTIME_WS_UNIFIED_ENABLED:-true}"
export REALTIME_MODAL_PROVISIONING_ENABLED=true

docker compose -f docker-compose.backend-only.yml --profile modal up -d --build db modal-preflight backend

"$(dirname "$0")/01_seed_test_session.sh"
"$(dirname "$0")/04_ws_workflow_state.sh"
"$(dirname "$0")/06_ws_execution_lifecycle.sh"

