#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/00_compose_health.sh"
"$SCRIPT_DIR/01_seed_test_session.sh"
"$SCRIPT_DIR/02_ws_handshake.sh"
"$SCRIPT_DIR/03_ws_chat_stream.sh"
"$SCRIPT_DIR/04_ws_workflow_state.sh"
"$SCRIPT_DIR/05_ws_question_answer.sh"
"$SCRIPT_DIR/06_ws_execution_lifecycle.sh"
"$SCRIPT_DIR/07_artifact_and_cache.sh"

