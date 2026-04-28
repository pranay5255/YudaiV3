#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
load_state

for _ in $(seq 1 60); do
  response="$(curl -fsS "$BACKEND_URL/daifu/sessions/$SESSION_ID/execution" \
    -H "Authorization: Bearer $SESSION_TOKEN")"
  status_value="$(printf '%s' "$response" | json_get status)"
  printf 'execution status: %s\n' "$status_value"
  if [ "$status_value" = "complete" ] || [ "$status_value" = "failed" ]; then
    break
  fi
  sleep 2
done

printf '%s\n' "$response" | grep -q '"artifact"'

workflow_request_id="workflow-artifact-$(date +%s)"
workflow_message="$(python3 - <<PY
import json
print(json.dumps({"type": "workflow.get", "request_id": "$workflow_request_id", "payload": {}}))
PY
)"
ws_send "$workflow_request_id" "$workflow_message" ack | tee /tmp/yudai-ws-artifact.log
grep -q '"artifact"' /tmp/yudai-ws-artifact.log
