#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
load_state

request_id="chat-$(date +%s)"
message="$(python3 - <<PY
import json
print(json.dumps({
  "type": "chat_message",
  "request_id": "$request_id",
  "payload": {
    "content": "Summarize the backend websocket architecture for this test session.",
    "repository": {"owner": "octocat", "name": "yudaiv3", "branch": "main"}
  }
}))
PY
)"

ws_send "$request_id" "$message" ack | tee /tmp/yudai-ws-chat.log
grep -q '"type": "llm_stream"' /tmp/yudai-ws-chat.log
grep -q '"type": "ack"' /tmp/yudai-ws-chat.log

