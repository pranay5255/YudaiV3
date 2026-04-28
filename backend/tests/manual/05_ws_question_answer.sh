#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
load_state

conversation_response="$(curl -fsS -X POST "$BACKEND_URL/daifu/sessions/$SESSION_ID/conversation" \
  -H "Authorization: Bearer $SESSION_TOKEN" \
  -H 'Content-Type: application/json' \
  --data '{"message":"Please improve auth testing in the backend."}')"

QUESTION_ID="$(printf '%s' "$conversation_response" | python3 -c 'import json,sys; print(json.load(sys.stdin)["follow_up_question"]["question_id"])')"
request_id="question-$(date +%s)"
message="$(python3 - <<PY
import json
print(json.dumps({
  "type": "question.answer",
  "request_id": "$request_id",
  "payload": {
    "question_id": "$QUESTION_ID",
    "selected_option_ids": ["tests"],
    "answer_text": "Prioritize backend-only regression tests.",
    "resume_execution": False
  }
}))
PY
)"

ws_send "$request_id" "$message" ack | tee /tmp/yudai-ws-question.log
grep -q "$QUESTION_ID" /tmp/yudai-ws-question.log

