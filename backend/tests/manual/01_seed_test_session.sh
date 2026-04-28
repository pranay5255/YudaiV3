#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"

payload='{"username":"backend-ws","repo_owner":"octocat","repo_name":"yudaiv3","repo_branch":"main"}'
response="$(curl -fsS -X POST "$BACKEND_URL/test/auth/session" \
  -H 'Content-Type: application/json' \
  --data "$payload")"

SESSION_TOKEN="$(printf '%s' "$response" | json_get session_token)"
SESSION_ID="$(printf '%s' "$response" | json_get session_id)"

cat > "$STATE_FILE" <<STATE
export BACKEND_URL="$BACKEND_URL"
export SESSION_TOKEN="$SESSION_TOKEN"
export SESSION_ID="$SESSION_ID"
STATE

printf '%s\n' "$response"
printf 'Wrote %s\n' "$STATE_FILE"

