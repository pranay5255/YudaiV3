#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
load_state

issue_request_id="issue-$(date +%s)"
issue_message="$(python3 - <<PY
import json
print(json.dumps({
  "type": "workflow.issue.select",
  "request_id": "$issue_request_id",
  "payload": {
    "number": 77,
    "title": "Backend websocket manual smoke test",
    "state": "open",
    "html_url": "https://github.com/octocat/yudaiv3/issues/77",
    "body": "Verify websocket-first backend flow.",
    "labels": ["backend", "websocket"]
  }
}))
PY
)"
ws_send "$issue_request_id" "$issue_message" ack

context_request_id="context-$(date +%s)"
context_message="$(python3 - <<PY
import json
print(json.dumps({
  "type": "workflow.context.update",
  "request_id": "$context_request_id",
  "payload": {
    "affected_systems": ["backend/yudai", "backend/solver", "docker-compose"],
    "constraints": "Run without GitHub OAuth.",
    "acceptance_criteria": "WebSocket commands ack and stream events."
  }
}))
PY
)"
ws_send "$context_request_id" "$context_message" ack

get_request_id="workflow-$(date +%s)"
get_message="$(python3 - <<PY
import json
print(json.dumps({"type": "workflow.get", "request_id": "$get_request_id", "payload": {}}))
PY
)"
ws_send "$get_request_id" "$get_message" ack | tee /tmp/yudai-ws-workflow.log
grep -q 'Backend websocket manual smoke test' /tmp/yudai-ws-workflow.log
