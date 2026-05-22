#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.backend-only.yml}"
PLAYWRIGHT_BASE_URL="${PLAYWRIGHT_BASE_URL:-https://yudai.app}"
PLAYWRIGHT_API_BASE_URL="${PLAYWRIGHT_API_BASE_URL:-http://localhost:${PORT:-8000}}"
E2E_SESSION_TOKEN_HOURS="${E2E_SESSION_TOKEN_HOURS:-2}"

repo_owner_from_git() {
  local remote
  remote="$(git -C "$ROOT_DIR" config --get remote.origin.url || true)"
  remote="${remote%.git}"
  case "$remote" in
    git@github.com:*) remote="${remote#git@github.com:}" ;;
    https://github.com/*) remote="${remote#https://github.com/}" ;;
    *) return 1 ;;
  esac
  printf '%s' "${remote%%/*}"
}

repo_name_from_git() {
  local remote
  remote="$(git -C "$ROOT_DIR" config --get remote.origin.url || true)"
  remote="${remote%.git}"
  case "$remote" in
    git@github.com:*) remote="${remote#git@github.com:}" ;;
    https://github.com/*) remote="${remote#https://github.com/}" ;;
    *) return 1 ;;
  esac
  printf '%s' "${remote#*/}"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$1" >&2
    exit 1
  fi
}

require_command docker
require_command node
require_command npm

if ! docker compose -f "$ROOT_DIR/$COMPOSE_FILE" ps --status running --services \
  | grep -qx 'backend'; then
  printf 'The backend service is not running. Start it first:\n' >&2
  printf '  docker compose -f %s up -d db backend\n' "$COMPOSE_FILE" >&2
  exit 1
fi

token_payload="$(
  docker compose -f "$ROOT_DIR/$COMPOSE_FILE" exec -T \
    -e E2E_USERNAME="${E2E_USERNAME:-}" \
    -e E2E_SESSION_TOKEN_HOURS="$E2E_SESSION_TOKEN_HOURS" \
    backend python - <<'PY'
import json
import os
import sys
from contextlib import redirect_stdout

from sqlalchemy import desc

from yudai.auth.github_oauth import create_session_token
from yudai.db.database import SessionLocal
from yudai.models import AuthToken, User
from yudai.utils import ensure_utc, utc_now

username = (os.environ.get("E2E_USERNAME") or "").strip()
expires_in_hours = int(os.environ.get("E2E_SESSION_TOKEN_HOURS") or "2")

db = SessionLocal()
try:
    if username:
        user = db.query(User).filter(User.github_username == username).first()
        if not user:
            raise SystemExit(f"No backend user exists for E2E_USERNAME={username!r}.")
    else:
        user = (
            db.query(User)
            .join(AuthToken, AuthToken.user_id == User.id)
            .filter(AuthToken.is_active.is_(True))
            .order_by(desc(AuthToken.updated_at), desc(AuthToken.created_at))
            .first()
        )
        if not user:
            raise SystemExit(
                "No backend user with an active GitHub OAuth token was found. "
                "Log in to the deployed frontend once, or set E2E_USERNAME to an existing user."
            )

    auth_token = (
        db.query(AuthToken)
        .filter(AuthToken.user_id == user.id, AuthToken.is_active.is_(True))
        .order_by(desc(AuthToken.updated_at), desc(AuthToken.created_at))
        .first()
    )
    if not auth_token:
        raise SystemExit(
            f"Backend user {user.github_username!r} has no active GitHub OAuth token, "
            "so repository listing in the browser cannot work."
        )
    if auth_token.expires_at and ensure_utc(auth_token.expires_at) < utc_now():
        raise SystemExit(
            f"Backend user {user.github_username!r} has an expired GitHub OAuth token. "
            "Log in to the deployed frontend again before running E2E."
        )

    with redirect_stdout(sys.stderr):
        session_token = create_session_token(db, user.id, expires_in_hours=expires_in_hours)
    print(json.dumps({
        "session_token": session_token.session_token,
        "user_id": str(user.id),
        "username": user.github_username,
        "display_name": user.display_name or user.github_username,
        "email": user.email or f"{user.github_username}@example.invalid",
    }))
finally:
    db.close()
PY
)"

json_field() {
  PAYLOAD="$token_payload" FIELD="$1" node -e '
    const payload = JSON.parse(process.env.PAYLOAD);
    process.stdout.write(String(payload[process.env.FIELD] || ""));
  '
}

export PLAYWRIGHT_BASE_URL
export PLAYWRIGHT_API_BASE_URL
export E2E_SESSION_TOKEN
export E2E_USER_ID
export E2E_USERNAME
export E2E_USER_DISPLAY_NAME
export E2E_USER_EMAIL
export E2E_REPO_OWNER
export E2E_REPO_NAME
export E2E_REPO_BRANCH

E2E_SESSION_TOKEN="$(json_field session_token)"
E2E_USER_ID="$(json_field user_id)"
E2E_USERNAME="$(json_field username)"
E2E_USER_DISPLAY_NAME="$(json_field display_name)"
E2E_USER_EMAIL="$(json_field email)"
E2E_REPO_OWNER="${E2E_REPO_OWNER:-$(repo_owner_from_git)}"
E2E_REPO_NAME="${E2E_REPO_NAME:-$(repo_name_from_git)}"
E2E_REPO_BRANCH="${E2E_REPO_BRANCH:-main}"

if [ -z "$E2E_REPO_OWNER" ] || [ -z "$E2E_REPO_NAME" ] || [ -z "$E2E_REPO_BRANCH" ]; then
  printf 'Set E2E_REPO_OWNER, E2E_REPO_NAME, and E2E_REPO_BRANCH before running E2E.\n' >&2
  exit 1
fi

if [ ! -d "$ROOT_DIR/src/node_modules/@playwright/test" ]; then
  (cd "$ROOT_DIR/src" && npm ci)
fi

if [ "${E2E_SKIP_PLAYWRIGHT_INSTALL:-0}" != "1" ]; then
  (cd "$ROOT_DIR/src" && npx playwright install chromium)
fi

printf 'Running real-site E2E against frontend %s and backend API %s\n' \
  "$PLAYWRIGHT_BASE_URL" "$PLAYWRIGHT_API_BASE_URL"
printf 'Using backend user %s and repo %s/%s@%s\n' \
  "$E2E_USERNAME" "$E2E_REPO_OWNER" "$E2E_REPO_NAME" "$E2E_REPO_BRANCH"

(cd "$ROOT_DIR/src" && npm run test:e2e "$@")
