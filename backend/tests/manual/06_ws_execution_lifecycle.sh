#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
load_state

runtime_request_id="runtime-$(date +%s)"
runtime_message="$(python3 - <<PY
import json
print(json.dumps({
  "type": "runtime.ensure",
  "request_id": "$runtime_request_id",
  "payload": {
    "org": "yudai",
    "repo_owner": "octocat",
    "repo_name": "yudaiv3",
    "environment": "main",
    "repo_branch": "main",
    "repo_url": "https://github.com/octocat/yudaiv3.git"
  }
}))
PY
)"
ws_send "$runtime_request_id" "$runtime_message" ack

exec_request_id="exec-$(date +%s)"
exec_message="$(python3 - <<PY
import json
print(json.dumps({
  "type": "execution.start",
  "request_id": "$exec_request_id",
  "payload": {
    "objective": "Run fake Architect, Tester, and Coder for backend websocket smoke."
  }
}))
PY
)"

python3 "$SCRIPT_DIR/ws_client.py" \
  --base-url "$BACKEND_URL" \
  --session-id "$SESSION_ID" \
  --token "$SESSION_TOKEN" \
  --send "$exec_message" \
  --request-id "$exec_request_id" \
  --expect-type ack \
  --timeout 90 \
  --max-events 120 | tee /tmp/yudai-ws-exec.log

grep -q '"type": "ack"' /tmp/yudai-ws-exec.log
grep -q '"type": "sandbox_stream"' /tmp/yudai-ws-exec.log

status_request_id="exec-status-$(date +%s)"
status_message="$(python3 - <<PY
import json
print(json.dumps({"type": "execution.status", "request_id": "$status_request_id", "payload": {}}))
PY
)"
ws_send "$status_request_id" "$status_message" ack
