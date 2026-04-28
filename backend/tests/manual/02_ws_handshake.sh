#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "$SCRIPT_DIR/common.sh"
load_state

python3 "$SCRIPT_DIR/ws_client.py" \
  --base-url "$BACKEND_URL" \
  --session-id "$SESSION_ID" \
  --token "$SESSION_TOKEN" \
  --expect-type status \
  --expect-status connected

