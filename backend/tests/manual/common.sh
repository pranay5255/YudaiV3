#!/usr/bin/env bash
set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
MANUAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_FILE="${STATE_FILE:-${MANUAL_DIR}/.manual_state.env}"

json_get() {
  local key="$1"
  python3 -c 'import json,sys; print(json.load(sys.stdin)[sys.argv[1]])' "$key"
}

load_state() {
  if [ ! -f "$STATE_FILE" ]; then
    echo "Missing state file: $STATE_FILE. Run 01_seed_test_session.sh first." >&2
    exit 1
  fi
  # shellcheck disable=SC1090
  source "$STATE_FILE"
}

ws_send() {
  local request_id="$1"
  local message_json="$2"
  local expect_type="${3:-ack}"
  python3 "$MANUAL_DIR/ws_client.py" \
    --base-url "$BACKEND_URL" \
    --session-id "$SESSION_ID" \
    --token "$SESSION_TOKEN" \
    --send "$message_json" \
    --request-id "$request_id" \
    --expect-type "$expect_type"
}
