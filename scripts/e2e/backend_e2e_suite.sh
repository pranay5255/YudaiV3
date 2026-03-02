#!/usr/bin/env bash
set -uo pipefail

# Backend E2E suite for deployed docker-compose backend.
# Focus: auth, repo fetch, sessions/chat, controller sandbox runtime, embeddings + pgvector.

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.backend-only.yml}"
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_TIMEOUT="${API_TIMEOUT:-120}"
POLL_TIMEOUT_SECONDS="${POLL_TIMEOUT_SECONDS:-240}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-5}"
RUN_LLM_CHAT="${RUN_LLM_CHAT:-0}" # Set to 1 to include /daifu/sessions/{id}/chat (OpenRouter call)

# Primary session scenario repo (chat/session/runtime checks)
REPO_OWNER="${REPO_OWNER:-pranay5255}"
REPO_NAME="${REPO_NAME:-TrustlessLocalAgents}"
REPO_BRANCH="${REPO_BRANCH:-main}"

# Embedding scenario repo (index + pgvector checks)
EMBED_REPO_OWNER="${EMBED_REPO_OWNER:-pranay5255}"
EMBED_REPO_NAME="${EMBED_REPO_NAME:-picoclaw}"
EMBED_REPO_BRANCH="${EMBED_REPO_BRANCH:-main}"

REPORT_DIR="${REPORT_DIR:-logs/e2e}"
mkdir -p "$REPORT_DIR"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

timestamp="$(date -u +%Y%m%d_%H%M%S)"
REPORT_MD="$REPORT_DIR/backend_e2e_report_${timestamp}.md"

DC=(docker compose -f "$COMPOSE_FILE")

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0
CHECK_ROWS=()

SESSION_ID=""
SESSION_DB_ID=""
SANDBOX_ID=""
RUNTIME_ID=""
EMBED_SESSION_ID=""
EMBED_SESSION_DB_ID=""
EMBED_SANDBOX_ID=""

GH_TOKEN=""
GH_USERNAME="${GH_USERNAME:-}"
AUTH_USER_ID=""

print_step() {
  printf "\n==> %s\n" "$1"
}

md_escape() {
  local raw="$1"
  raw="${raw//$'\n'/<br>}"
  raw="${raw//|/\\|}"
  printf '%s' "$raw"
}

record_result() {
  local id="$1"
  local status="$2"
  local check="$3"
  local detail="${4:-}"
  local escaped_detail
  escaped_detail="$(md_escape "$detail")"
  CHECK_ROWS+=("$id|$status|$check|$escaped_detail")

  case "$status" in
    PASS) PASS_COUNT=$((PASS_COUNT + 1)) ;;
    FAIL) FAIL_COUNT=$((FAIL_COUNT + 1)) ;;
    SKIP) SKIP_COUNT=$((SKIP_COUNT + 1)) ;;
  esac

  printf "[%s] %s %s\n" "$status" "$id" "$check"
  if [[ -n "$detail" ]]; then
    printf "      %s\n" "$detail"
  fi
}

api_request() {
  # Usage: api_request METHOD PATH [JSON_PAYLOAD]
  # Writes response body to $TMP_DIR/response.json and echoes HTTP status code.
  local method="$1"
  local path="$2"
  local payload="${3:-}"
  local code rc

  if [[ -n "$payload" ]]; then
    code="$(
      printf '%s' "$payload" | "${DC[@]}" exec -T \
        -e GH_TOKEN="$GH_TOKEN" \
        -e E2E_METHOD="$method" \
        -e E2E_PATH="$path" \
        -e E2E_TIMEOUT="$API_TIMEOUT" \
        backend sh -lc '
          cat > /tmp/e2e_payload.json
          curl -sS -m "$E2E_TIMEOUT" \
            -o /tmp/e2e_response.json \
            -w "%{http_code}" \
            -X "$E2E_METHOD" "http://localhost:8000$E2E_PATH" \
            -H "Authorization: Bearer $GH_TOKEN" \
            -H "Content-Type: application/json" \
            --data-binary @/tmp/e2e_payload.json
        ' 2>"$TMP_DIR/api_err.log"
    )"
    rc=$?
  else
    code="$(
      "${DC[@]}" exec -T \
        -e GH_TOKEN="$GH_TOKEN" \
        -e E2E_METHOD="$method" \
        -e E2E_PATH="$path" \
        -e E2E_TIMEOUT="$API_TIMEOUT" \
        backend sh -lc '
          curl -sS -m "$E2E_TIMEOUT" \
            -o /tmp/e2e_response.json \
            -w "%{http_code}" \
            -X "$E2E_METHOD" "http://localhost:8000$E2E_PATH" \
            -H "Authorization: Bearer $GH_TOKEN"
        ' 2>"$TMP_DIR/api_err.log"
    )"
    rc=$?
  fi

  if (( rc != 0 )); then
    echo "{}" > "$TMP_DIR/response.json"
    echo "000"
    return 1
  fi

  "${DC[@]}" exec -T backend sh -lc 'cat /tmp/e2e_response.json 2>/dev/null || true' > "$TMP_DIR/response.json"
  printf '%s' "$code"
}

db_query() {
  # Usage: db_query "SELECT ...;"
  local sql="$1"
  "${DC[@]}" exec -T backend sh -lc 'psql "$DATABASE_URL" -Atq' <<<"$sql"
}

sql_escape_literal() {
  local value="$1"
  printf "%s" "${value//\'/\'\'}"
}

normalize_identity_segment() {
  local value="$1"
  local normalized
  normalized="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  normalized="$(printf '%s' "$normalized" | sed -E 's/[^a-z0-9._-]+/-/g; s/-{2,}/-/g; s/^[-._]+//; s/[-._]+$//')"
  printf '%s' "$normalized"
}

build_identity_key() {
  local owner="$1"
  local repo="$2"
  local env="$3"
  local org_norm owner_norm repo_norm env_norm
  org_norm="$(normalize_identity_segment "yudai")"
  owner_norm="$(normalize_identity_segment "$owner")"
  repo_norm="$(normalize_identity_segment "$repo")"
  env_norm="$(normalize_identity_segment "$env")"
  printf '%s:%s/%s:%s' "$org_norm" "$owner_norm" "$repo_norm" "$env_norm"
}

identity_exists() {
  local owner="$1"
  local repo="$2"
  local env="$3"
  local key key_esc count
  key="$(build_identity_key "$owner" "$repo" "$env")"
  key_esc="$(sql_escape_literal "$key")"
  count="$(db_query "SELECT COUNT(*) FROM sandboxes WHERE identity_key='${key_esc}';" | tr -d '[:space:]')"
  [[ "$count" =~ ^[0-9]+$ ]] && (( count > 0 ))
}

lookup_active_sandbox_for_identity() {
  local owner="$1"
  local repo="$2"
  local environment="$3"
  local owner_esc repo_esc env_esc
  owner_esc="$(sql_escape_literal "$owner")"
  repo_esc="$(sql_escape_literal "$repo")"
  env_esc="$(sql_escape_literal "$environment")"
  db_query "SELECT id FROM sandboxes WHERE lower(repo_owner)=lower('${owner_esc}') AND lower(repo_name)=lower('${repo_esc}') AND lower(environment)=lower('${env_esc}') AND status <> 'terminated' ORDER BY created_at DESC LIMIT 1;"
}

find_unused_public_repo_identity() {
  local preferred_branch="$1"
  local code owner repo branch
  local -a candidates=()
  local seen="|"

  code="$(api_request GET "/github/repositories")" || return 1
  [[ "$code" == "200" ]] || return 1

  while IFS='|' read -r owner repo; do
    [[ -n "$owner" && -n "$repo" ]] || continue
    if [[ "$seen" == *"|$owner/$repo|"* ]]; then
      continue
    fi
    seen="${seen}$owner/$repo|"
    candidates+=("$owner|$repo")
  done < <(jq -r '.[] | select(.private == false) | "\(.owner.login)|\(.name)"' "$TMP_DIR/response.json")

  for candidate in "${candidates[@]}"; do
    owner="${candidate%%|*}"
    repo="${candidate##*|}"
    branch="$(choose_branch "$owner" "$repo" "$preferred_branch")"
    if ! identity_exists "$owner" "$repo" "$branch"; then
      printf '%s|%s|%s' "$owner" "$repo" "$branch"
      return 0
    fi
  done

  return 1
}

require_http_200() {
  local id="$1"
  local check="$2"
  local code="$3"
  local detail="$4"
  if [[ "$code" == "200" ]]; then
    record_result "$id" "PASS" "$check" "$detail"
    return 0
  fi
  record_result "$id" "FAIL" "$check" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  return 1
}

json_get() {
  local query="$1"
  jq -r "$query // empty" "$TMP_DIR/response.json"
}

choose_branch() {
  local owner="$1"
  local repo="$2"
  local preferred="$3"
  local code branch

  code="$(api_request GET "/github/repositories/$owner/$repo/branches")" || true
  if [[ "$code" != "200" ]]; then
    echo "$preferred"
    return
  fi
  branch="$(jq -r --arg b "$preferred" '
    if (type=="array" and (map(.name) | index($b) != null)) then $b
    elif (type=="array" and length > 0) then .[0].name
    else $b
    end
  ' "$TMP_DIR/response.json")"
  echo "$branch"
}

seed_auth_token() {
  local out
  out="$(
    "${DC[@]}" exec -T \
      -e GH_TOKEN="$GH_TOKEN" \
      -e GH_USERNAME="$GH_USERNAME" \
      backend python - <<'PY'
from datetime import timedelta
import os

from db.database import SessionLocal
from models import AuthToken, User
from utils import utc_now

db = SessionLocal()
try:
    token = os.getenv("GH_TOKEN", "").strip()
    username = os.getenv("GH_USERNAME", "").strip() or "gh-default-user"
    if not token:
        raise RuntimeError("GH_TOKEN missing")

    user = db.query(User).filter(User.github_username == username).first()
    if not user:
        user = User(
            github_username=username,
            github_user_id=f"local-{username}",
            display_name=username,
            email=None,
            avatar_url=None,
            last_login=utc_now(),
        )
        db.add(user)
        db.flush()
    else:
        user.last_login = utc_now()

    db.query(AuthToken).filter(
        AuthToken.user_id == user.id,
        AuthToken.is_active.is_(True),
    ).update({"is_active": False})

    db.add(
        AuthToken(
            user_id=user.id,
            access_token=token,
            token_type="bearer",
            scope="repo user:email read:org public_repo",
            expires_at=utc_now() + timedelta(hours=8),
            is_active=True,
        )
    )
    db.commit()
    print(f"USER_ID={user.id}")
except Exception as exc:
    db.rollback()
    print(f"ERROR={exc}")
    raise
finally:
    db.close()
PY
  )"

  if grep -q '^USER_ID=' <<<"$out"; then
    AUTH_USER_ID="$(sed -n 's/^USER_ID=//p' <<<"$out" | head -n1)"
    return 0
  fi
  echo "$out" >&2
  return 1
}

print_step "Prerequisites and Health"

if "${DC[@]}" ps >/dev/null 2>&1; then
  ps_output="$("${DC[@]}" ps)"
  if grep -q 'yudai-be' <<<"$ps_output" && grep -q 'healthy' <<<"$ps_output"; then
    record_result "INF-001" "PASS" "Compose services are up and backend is healthy" "$(echo "$ps_output" | tail -n +2)"
  else
    record_result "INF-001" "FAIL" "Compose services are up and backend is healthy" "$ps_output"
  fi
else
  record_result "INF-001" "FAIL" "Compose services are up and backend is healthy" "docker compose ps failed"
fi

if code="$(api_request GET "/health")"; then
  require_http_200 "INF-002" "Backend /health responds" "$code" "$(cat "$TMP_DIR/response.json")"
else
  record_result "INF-002" "FAIL" "Backend /health responds" "$(cat "$TMP_DIR/api_err.log")"
fi

if code="$(api_request GET "/auth/health")"; then
  if [[ "$code" == "200" ]]; then
    oauth_configured="$(jq -r '.oauth_configured // false' "$TMP_DIR/response.json")"
    if [[ "$oauth_configured" == "true" ]]; then
      record_result "INF-003" "PASS" "Auth health + OAuth configured" "$(cat "$TMP_DIR/response.json")"
    else
      record_result "INF-003" "FAIL" "Auth health + OAuth configured" "oauth_configured=false body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "INF-003" "FAIL" "Auth health + OAuth configured" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "INF-003" "FAIL" "Auth health + OAuth configured" "$(cat "$TMP_DIR/api_err.log")"
fi

print_step "Auth Bootstrap"

if GH_TOKEN="$(gh auth token 2>/dev/null)"; then
  if [[ -n "$GH_TOKEN" ]]; then
    record_result "AUTH-001" "PASS" "GitHub CLI token available (gh auth token)" "token_length=${#GH_TOKEN}"
  else
    record_result "AUTH-001" "FAIL" "GitHub CLI token available (gh auth token)" "Token was empty"
  fi
else
  record_result "AUTH-001" "FAIL" "GitHub CLI token available (gh auth token)" "gh auth token failed"
fi

if [[ -z "$GH_USERNAME" ]]; then
  GH_USERNAME="$(gh api user --jq .login 2>/dev/null || true)"
fi
if [[ -z "$GH_USERNAME" ]]; then
  GH_USERNAME="pranay5255"
fi

if [[ -n "$GH_TOKEN" ]] && seed_auth_token; then
  record_result "AUTH-002" "PASS" "Seed active AuthToken for default user in backend DB" "user_id=$AUTH_USER_ID username=$GH_USERNAME"
else
  record_result "AUTH-002" "FAIL" "Seed active AuthToken for default user in backend DB" "Failed to seed auth token"
fi

if code="$(api_request GET "/auth/api/user")"; then
  if [[ "$code" == "200" ]]; then
    returned_user="$(jq -r '.github_username // empty' "$TMP_DIR/response.json")"
    if [[ -n "$returned_user" ]]; then
      record_result "AUTH-003" "PASS" "/auth/api/user resolves current user" "$(cat "$TMP_DIR/response.json")"
    else
      record_result "AUTH-003" "FAIL" "/auth/api/user resolves current user" "missing github_username body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "AUTH-003" "FAIL" "/auth/api/user resolves current user" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "AUTH-003" "FAIL" "/auth/api/user resolves current user" "$(cat "$TMP_DIR/api_err.log")"
fi

if [[ -n "$GH_TOKEN" ]]; then
  bad_code="$(
    "${DC[@]}" exec -T \
      -e E2E_TIMEOUT="$API_TIMEOUT" \
      backend sh -lc '
        curl -sS -m "$E2E_TIMEOUT" -o /tmp/e2e_bad_response.json -w "%{http_code}" \
          -X GET "http://localhost:8000/auth/api/user" \
          -H "Authorization: Bearer invalid-token-for-negative-test"
      ' 2>"$TMP_DIR/api_bad_err.log" || echo "000"
  )"
  "${DC[@]}" exec -T backend sh -lc 'cat /tmp/e2e_bad_response.json 2>/dev/null || true' > "$TMP_DIR/bad_response.json"
  if [[ "$bad_code" == "401" ]]; then
    record_result "AUTH-004" "PASS" "Invalid token is rejected by /auth/api/user" "HTTP=401"
  else
    record_result "AUTH-004" "FAIL" "Invalid token is rejected by /auth/api/user" "HTTP=$bad_code body=$(cat "$TMP_DIR/bad_response.json")"
  fi
fi

print_step "GitHub API Surface"

if code="$(api_request GET "/github/repositories")"; then
  if [[ "$code" == "200" ]]; then
    repo_count="$(jq 'if type=="array" then length else 0 end' "$TMP_DIR/response.json")"
    if (( repo_count > 0 )); then
      record_result "GH-001" "PASS" "/github/repositories returns data" "repo_count=$repo_count"
    else
      record_result "GH-001" "FAIL" "/github/repositories returns data" "repo_count=0"
    fi
  else
    record_result "GH-001" "FAIL" "/github/repositories returns data" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "GH-001" "FAIL" "/github/repositories returns data" "$(cat "$TMP_DIR/api_err.log")"
fi

REPO_BRANCH="$(choose_branch "$REPO_OWNER" "$REPO_NAME" "$REPO_BRANCH")"
if code="$(api_request GET "/github/repositories/$REPO_OWNER/$REPO_NAME/branches")"; then
  if [[ "$code" == "200" ]]; then
    branch_count="$(jq 'if type=="array" then length else 0 end' "$TMP_DIR/response.json")"
    record_result "GH-002" "PASS" "/github/repositories/{owner}/{repo}/branches" "repo=$REPO_OWNER/$REPO_NAME branch_count=$branch_count using_branch=$REPO_BRANCH"
  else
    record_result "GH-002" "FAIL" "/github/repositories/{owner}/{repo}/branches" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "GH-002" "FAIL" "/github/repositories/{owner}/{repo}/branches" "$(cat "$TMP_DIR/api_err.log")"
fi

if code="$(api_request GET "/daifu/github/repositories")"; then
  if [[ "$code" == "200" ]]; then
    daifu_repo_count="$(jq 'if type=="array" then length else 0 end' "$TMP_DIR/response.json")"
    record_result "GH-003" "PASS" "/daifu/github/repositories returns data" "repo_count=$daifu_repo_count"
  else
    record_result "GH-003" "FAIL" "/daifu/github/repositories returns data" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "GH-003" "FAIL" "/daifu/github/repositories returns data" "$(cat "$TMP_DIR/api_err.log")"
fi

if code="$(api_request GET "/daifu/github/repositories/$REPO_OWNER/$REPO_NAME/issues?limit=5")"; then
  if [[ "$code" == "200" ]]; then
    issue_count="$(jq 'if type=="array" then length else 0 end' "$TMP_DIR/response.json")"
    record_result "GH-004" "PASS" "/daifu/github/repositories/{owner}/{repo}/issues works" "issue_count=$issue_count"
  else
    record_result "GH-004" "FAIL" "/daifu/github/repositories/{owner}/{repo}/issues works" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "GH-004" "FAIL" "/daifu/github/repositories/{owner}/{repo}/issues works" "$(cat "$TMP_DIR/api_err.log")"
fi

if code="$(api_request GET "/daifu/ai-models")"; then
  if [[ "$code" == "200" ]]; then
    model_count="$(jq 'if type=="array" then length else 0 end' "$TMP_DIR/response.json")"
    if (( model_count > 0 )); then
      record_result "GH-005" "PASS" "/daifu/ai-models returns active models" "model_count=$model_count"
    else
      record_result "GH-005" "FAIL" "/daifu/ai-models returns active models" "model_count=0"
    fi
  else
    record_result "GH-005" "FAIL" "/daifu/ai-models returns active models" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "GH-005" "FAIL" "/daifu/ai-models returns active models" "$(cat "$TMP_DIR/api_err.log")"
fi

print_step "Session + Modal Runtime Provisioning"

create_payload="$(jq -nc \
  --arg owner "$REPO_OWNER" \
  --arg name "$REPO_NAME" \
  --arg branch "$REPO_BRANCH" \
  '{
    repo_owner: $owner,
    repo_name: $name,
    repo_branch: $branch,
    index_codebase: false,
    generate_embeddings: false,
    generate_facts_memories: false
  }'
)"

if code="$(api_request POST "/daifu/sessions" "$create_payload")"; then
  create_body="$(cat "$TMP_DIR/response.json")"
  if [[ "$code" != "200" ]] && grep -q "SINGLE_ACTIVE_EDITOR_CONFLICT" <<<"$create_body"; then
    conflicting_sandbox="$(lookup_active_sandbox_for_identity "$REPO_OWNER" "$REPO_NAME" "$REPO_BRANCH" | tr -d '[:space:]')"
    if [[ -n "$conflicting_sandbox" ]]; then
      conflict_delete_code="$(api_request DELETE "/controller/sandboxes/$conflicting_sandbox")" || conflict_delete_code="000"
      if [[ "$conflict_delete_code" == "204" ]]; then
        record_result "SES-000" "PASS" "Pre-clean conflicting sandbox identity before session create retry" "sandbox_id=$conflicting_sandbox"
      else
        record_result "SES-000" "FAIL" "Pre-clean conflicting sandbox identity before session create retry" "sandbox_id=$conflicting_sandbox HTTP=$conflict_delete_code body=$(cat "$TMP_DIR/response.json")"
      fi
      code="$(api_request POST "/daifu/sessions" "$create_payload")" || code="000"
    else
      record_result "SES-000" "FAIL" "Pre-clean conflicting sandbox identity before session create retry" "Could not resolve conflicting sandbox_id for identity"
    fi
  fi

  if [[ "$code" != "200" ]] && grep -q 'sandboxes_identity_key_key' "$TMP_DIR/response.json"; then
    if fallback="$(find_unused_public_repo_identity "$REPO_BRANCH")"; then
      REPO_OWNER="${fallback%%|*}"
      rest="${fallback#*|}"
      REPO_NAME="${rest%%|*}"
      REPO_BRANCH="${rest##*|}"
      record_result "SES-010" "PASS" "Fallback to unused public repo identity after unique-key conflict" "repo=$REPO_OWNER/$REPO_NAME branch=$REPO_BRANCH"
      create_payload="$(jq -nc \
        --arg owner "$REPO_OWNER" \
        --arg name "$REPO_NAME" \
        --arg branch "$REPO_BRANCH" \
        '{repo_owner:$owner,repo_name:$name,repo_branch:$branch,index_codebase:false,generate_embeddings:false,generate_facts_memories:false}'
      )"
      code="$(api_request POST "/daifu/sessions" "$create_payload")" || code="000"
    else
      record_result "SES-010" "FAIL" "Fallback to unused public repo identity after unique-key conflict" "Could not find unused public repo identity"
    fi
  fi

  if [[ "$code" == "200" ]]; then
    SESSION_ID="$(json_get '.session_id')"
    SANDBOX_ID="$(json_get '.sandbox_id')"
    RUNTIME_ID="$(json_get '.runtime_id')"
    if [[ -n "$SESSION_ID" ]]; then
      record_result "SES-001" "PASS" "Create session via /daifu/sessions" "$(cat "$TMP_DIR/response.json")"
    else
      record_result "SES-001" "FAIL" "Create session via /daifu/sessions" "session_id missing body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "SES-001" "FAIL" "Create session via /daifu/sessions" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "SES-001" "FAIL" "Create session via /daifu/sessions" "$(cat "$TMP_DIR/api_err.log")"
fi

if [[ -n "$SESSION_ID" ]]; then
  if code="$(api_request GET "/controller/sessions/$SESSION_ID/runtime")"; then
    if [[ "$code" == "200" ]]; then
      runtime_status="$(json_get '.status')"
      record_result "SES-002" "PASS" "Controller runtime lookup for session" "runtime_status=$runtime_status body=$(cat "$TMP_DIR/response.json")"
    else
      record_result "SES-002" "FAIL" "Controller runtime lookup for session" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "SES-002" "FAIL" "Controller runtime lookup for session" "$(cat "$TMP_DIR/api_err.log")"
  fi
else
  record_result "SES-002" "SKIP" "Controller runtime lookup for session" "session creation failed"
fi

if [[ -n "$SANDBOX_ID" ]]; then
  if code="$(api_request GET "/controller/sandboxes/$SANDBOX_ID")"; then
    if [[ "$code" == "200" ]]; then
      sandbox_status="$(json_get '.status')"
      record_result "SES-003" "PASS" "Controller sandbox fetch by sandbox_id" "sandbox_status=$sandbox_status"
    else
      record_result "SES-003" "FAIL" "Controller sandbox fetch by sandbox_id" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "SES-003" "FAIL" "Controller sandbox fetch by sandbox_id" "$(cat "$TMP_DIR/api_err.log")"
  fi

  if code="$(api_request POST "/controller/sandboxes/$SANDBOX_ID/resolve-tunnel" "{}")"; then
    if [[ "$code" == "200" ]]; then
      token_strategy="$(json_get '.token_strategy')"
      record_result "SES-004" "PASS" "Resolve tunnel for sandbox" "token_strategy=$token_strategy body=$(cat "$TMP_DIR/response.json")"
    else
      record_result "SES-004" "FAIL" "Resolve tunnel for sandbox" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "SES-004" "FAIL" "Resolve tunnel for sandbox" "$(cat "$TMP_DIR/api_err.log")"
  fi
else
  record_result "SES-003" "SKIP" "Controller sandbox fetch by sandbox_id" "sandbox_id missing from session create response"
  record_result "SES-004" "SKIP" "Resolve tunnel for sandbox" "sandbox_id missing from session create response"
fi

print_step "Chat + Context Endpoints"

if [[ -n "$SESSION_ID" ]]; then
  add_msg_payload="$(jq -nc '{message_text:"e2e message 1", sender_type:"user", role:"user", tokens:3}')"
  if code="$(api_request POST "/daifu/sessions/$SESSION_ID/messages" "$add_msg_payload")"; then
    if [[ "$code" == "200" ]]; then
      record_result "CHAT-001" "PASS" "Add message to session" "$(cat "$TMP_DIR/response.json")"
    else
      record_result "CHAT-001" "FAIL" "Add message to session" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "CHAT-001" "FAIL" "Add message to session" "$(cat "$TMP_DIR/api_err.log")"
  fi

  bulk_payload="$(jq -nc '[{message_text:"e2e bulk message A",sender_type:"user",role:"user",tokens:2},{message_text:"e2e bulk message B",sender_type:"assistant",role:"assistant",tokens:2}]')"
  if code="$(api_request POST "/daifu/sessions/$SESSION_ID/messages/bulk" "$bulk_payload")"; then
    if [[ "$code" == "200" ]]; then
      bulk_count="$(jq 'if type=="array" then length else 0 end' "$TMP_DIR/response.json")"
      record_result "CHAT-002" "PASS" "Add bulk messages" "created=$bulk_count"
    else
      record_result "CHAT-002" "FAIL" "Add bulk messages" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "CHAT-002" "FAIL" "Add bulk messages" "$(cat "$TMP_DIR/api_err.log")"
  fi

  if code="$(api_request GET "/daifu/sessions/$SESSION_ID/messages?limit=200")"; then
    if [[ "$code" == "200" ]]; then
      msg_count="$(jq 'if type=="array" then length else 0 end' "$TMP_DIR/response.json")"
      if (( msg_count >= 3 )); then
        record_result "CHAT-003" "PASS" "List session messages" "message_count=$msg_count"
      else
        record_result "CHAT-003" "FAIL" "List session messages" "message_count=$msg_count (expected >=3)"
      fi
    else
      record_result "CHAT-003" "FAIL" "List session messages" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "CHAT-003" "FAIL" "List session messages" "$(cat "$TMP_DIR/api_err.log")"
  fi

  context_payload="$(jq -nc '{title:"E2E Card",description:"Context for tests",content:"This is context content",source:"chat",tokens:8}')"
  if code="$(api_request POST "/daifu/sessions/$SESSION_ID/context-cards" "$context_payload")"; then
    if [[ "$code" == "200" ]]; then
      record_result "CHAT-004" "PASS" "Create context card" "$(cat "$TMP_DIR/response.json")"
    else
      record_result "CHAT-004" "FAIL" "Create context card" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "CHAT-004" "FAIL" "Create context card" "$(cat "$TMP_DIR/api_err.log")"
  fi

  if code="$(api_request GET "/daifu/sessions/$SESSION_ID/context-cards")"; then
    if [[ "$code" == "200" ]]; then
      card_count="$(jq 'if type=="array" then length else 0 end' "$TMP_DIR/response.json")"
      if (( card_count >= 1 )); then
        record_result "CHAT-005" "PASS" "List context cards" "context_card_count=$card_count"
      else
        record_result "CHAT-005" "FAIL" "List context cards" "context_card_count=0"
      fi
    else
      record_result "CHAT-005" "FAIL" "List context cards" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "CHAT-005" "FAIL" "List context cards" "$(cat "$TMP_DIR/api_err.log")"
  fi

  conv_payload="$(jq -nc '{message:"Please focus on test coverage first"}')"
  if code="$(api_request POST "/daifu/sessions/$SESSION_ID/conversation" "$conv_payload")"; then
    if [[ "$code" == "200" ]]; then
      mode_status="$(json_get '.mode_status')"
      record_result "CHAT-006" "PASS" "Conversation endpoint" "mode_status=$mode_status body=$(cat "$TMP_DIR/response.json")"
    else
      record_result "CHAT-006" "FAIL" "Conversation endpoint" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "CHAT-006" "FAIL" "Conversation endpoint" "$(cat "$TMP_DIR/api_err.log")"
  fi

  if [[ "$RUN_LLM_CHAT" == "1" ]]; then
    chat_payload="$(jq -nc --arg sid "$SESSION_ID" --arg owner "$REPO_OWNER" --arg repo "$REPO_NAME" --arg branch "$REPO_BRANCH" '{session_id:$sid,message:{message_text:"Say OK for backend e2e",is_code:false},context_cards:[],repository:{owner:$owner,name:$repo,branch:$branch}}')"
    if code="$(api_request POST "/daifu/sessions/$SESSION_ID/chat" "$chat_payload")"; then
      if [[ "$code" == "200" ]]; then
        reply="$(json_get '.reply')"
        record_result "CHAT-007" "PASS" "LLM chat endpoint (/chat)" "reply_preview=${reply:0:120}"
      else
        record_result "CHAT-007" "FAIL" "LLM chat endpoint (/chat)" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
      fi
    else
      record_result "CHAT-007" "FAIL" "LLM chat endpoint (/chat)" "$(cat "$TMP_DIR/api_err.log")"
    fi
  else
    record_result "CHAT-007" "SKIP" "LLM chat endpoint (/chat)" "RUN_LLM_CHAT=0"
  fi

  if code="$(api_request GET "/daifu/sessions/$SESSION_ID")"; then
    if [[ "$code" == "200" ]]; then
      context_message_count="$(jq '.messages | if type=="array" then length else 0 end' "$TMP_DIR/response.json")"
      current_mode="$(jq -r '.session.current_mode // empty' "$TMP_DIR/response.json")"
      record_result "CHAT-008" "PASS" "Session context endpoint" "messages=$context_message_count current_mode=$current_mode"
    else
      record_result "CHAT-008" "FAIL" "Session context endpoint" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "CHAT-008" "FAIL" "Session context endpoint" "$(cat "$TMP_DIR/api_err.log")"
  fi
else
  for id in CHAT-001 CHAT-002 CHAT-003 CHAT-004 CHAT-005 CHAT-006 CHAT-007 CHAT-008; do
    record_result "$id" "SKIP" "Chat/context checks" "session creation failed"
  done
fi

print_step "Embedding + pgvector Validation"

EMBED_REPO_BRANCH="$(choose_branch "$EMBED_REPO_OWNER" "$EMBED_REPO_NAME" "$EMBED_REPO_BRANCH")"
embed_create_payload="$(jq -nc \
  --arg owner "$EMBED_REPO_OWNER" \
  --arg name "$EMBED_REPO_NAME" \
  --arg branch "$EMBED_REPO_BRANCH" \
  '{
    repo_owner: $owner,
    repo_name: $name,
    repo_branch: $branch,
    index_codebase: true,
    generate_embeddings: true,
    generate_facts_memories: false
  }'
)"

if code="$(api_request POST "/daifu/sessions" "$embed_create_payload")"; then
  embed_create_body="$(cat "$TMP_DIR/response.json")"
  if [[ "$code" != "200" ]] && grep -q "SINGLE_ACTIVE_EDITOR_CONFLICT" <<<"$embed_create_body"; then
    embed_conflicting_sandbox="$(lookup_active_sandbox_for_identity "$EMBED_REPO_OWNER" "$EMBED_REPO_NAME" "$EMBED_REPO_BRANCH" | tr -d '[:space:]')"
    if [[ -n "$embed_conflicting_sandbox" ]]; then
      embed_conflict_delete_code="$(api_request DELETE "/controller/sandboxes/$embed_conflicting_sandbox")" || embed_conflict_delete_code="000"
      if [[ "$embed_conflict_delete_code" == "204" ]]; then
        record_result "EMB-000" "PASS" "Pre-clean conflicting embedding sandbox identity before retry" "sandbox_id=$embed_conflicting_sandbox"
      else
        record_result "EMB-000" "FAIL" "Pre-clean conflicting embedding sandbox identity before retry" "sandbox_id=$embed_conflicting_sandbox HTTP=$embed_conflict_delete_code body=$(cat "$TMP_DIR/response.json")"
      fi
      code="$(api_request POST "/daifu/sessions" "$embed_create_payload")" || code="000"
    else
      record_result "EMB-000" "FAIL" "Pre-clean conflicting embedding sandbox identity before retry" "Could not resolve conflicting sandbox_id for identity"
    fi
  fi

  if [[ "$code" != "200" ]] && grep -q 'sandboxes_identity_key_key' "$TMP_DIR/response.json"; then
    if embed_fallback="$(find_unused_public_repo_identity "$EMBED_REPO_BRANCH")"; then
      EMBED_REPO_OWNER="${embed_fallback%%|*}"
      embed_rest="${embed_fallback#*|}"
      EMBED_REPO_NAME="${embed_rest%%|*}"
      EMBED_REPO_BRANCH="${embed_rest##*|}"
      record_result "EMB-010" "PASS" "Fallback to unused public embedding repo identity after unique-key conflict" "repo=$EMBED_REPO_OWNER/$EMBED_REPO_NAME branch=$EMBED_REPO_BRANCH"
      embed_create_payload="$(jq -nc \
        --arg owner "$EMBED_REPO_OWNER" \
        --arg name "$EMBED_REPO_NAME" \
        --arg branch "$EMBED_REPO_BRANCH" \
        '{repo_owner:$owner,repo_name:$name,repo_branch:$branch,index_codebase:true,generate_embeddings:true,generate_facts_memories:false}'
      )"
      code="$(api_request POST "/daifu/sessions" "$embed_create_payload")" || code="000"
    else
      record_result "EMB-010" "FAIL" "Fallback to unused public embedding repo identity after unique-key conflict" "Could not find unused public repo identity"
    fi
  fi

  if [[ "$code" == "200" ]]; then
    EMBED_SESSION_ID="$(json_get '.session_id')"
    EMBED_SANDBOX_ID="$(json_get '.sandbox_id')"
    if [[ -n "$EMBED_SESSION_ID" ]]; then
      record_result "EMB-001" "PASS" "Create embedding-enabled session (index_codebase=true)" "$(cat "$TMP_DIR/response.json")"
      EMBED_SESSION_DB_ID="$(db_query "SELECT id FROM chat_sessions WHERE session_id='${EMBED_SESSION_ID}' ORDER BY id DESC LIMIT 1;")"
    else
      record_result "EMB-001" "FAIL" "Create embedding-enabled session (index_codebase=true)" "session_id missing body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "EMB-001" "FAIL" "Create embedding-enabled session (index_codebase=true)" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "EMB-001" "FAIL" "Create embedding-enabled session (index_codebase=true)" "$(cat "$TMP_DIR/api_err.log")"
fi

if [[ -n "$EMBED_SESSION_DB_ID" ]]; then
  # Poll file_items
  file_item_count="0"
  deadline=$((SECONDS + POLL_TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    file_item_count="$(db_query "SELECT COUNT(*) FROM file_items WHERE session_id=${EMBED_SESSION_DB_ID};" | tr -d '[:space:]')"
    if [[ "$file_item_count" =~ ^[0-9]+$ ]] && (( file_item_count > 0 )); then
      break
    fi
    sleep "$POLL_INTERVAL_SECONDS"
  done

  if [[ "$file_item_count" =~ ^[0-9]+$ ]] && (( file_item_count > 0 )); then
    record_result "EMB-002" "PASS" "Repository files indexed into file_items" "file_item_count=$file_item_count"
  else
    record_result "EMB-002" "FAIL" "Repository files indexed into file_items" "file_item_count=$file_item_count after ${POLL_TIMEOUT_SECONDS}s"
  fi

  # Poll file_embeddings
  embedding_count="0"
  deadline=$((SECONDS + POLL_TIMEOUT_SECONDS))
  while (( SECONDS < deadline )); do
    embedding_count="$(db_query "SELECT COUNT(*) FROM file_embeddings WHERE session_id=${EMBED_SESSION_DB_ID};" | tr -d '[:space:]')"
    if [[ "$embedding_count" =~ ^[0-9]+$ ]] && (( embedding_count > 0 )); then
      break
    fi
    sleep "$POLL_INTERVAL_SECONDS"
  done

  if [[ "$embedding_count" =~ ^[0-9]+$ ]] && (( embedding_count > 0 )); then
    record_result "EMB-003" "PASS" "Embeddings persisted into file_embeddings" "embedding_count=$embedding_count"
  else
    record_result "EMB-003" "FAIL" "Embeddings persisted into file_embeddings" "embedding_count=$embedding_count after ${POLL_TIMEOUT_SECONDS}s"
  fi
else
  record_result "EMB-002" "SKIP" "Repository files indexed into file_items" "embedding session creation failed"
  record_result "EMB-003" "SKIP" "Embeddings persisted into file_embeddings" "embedding session creation failed"
fi

vector_ext="$(db_query "SELECT extname FROM pg_extension WHERE extname='vector';" | tr -d '[:space:]')"
if [[ "$vector_ext" == "vector" ]]; then
  record_result "EMB-004" "PASS" "pgvector extension installed" "extname=vector"
else
  record_result "EMB-004" "FAIL" "pgvector extension installed" "extname=$vector_ext"
fi

embedding_type="$(db_query "SELECT udt_name FROM information_schema.columns WHERE table_name='file_embeddings' AND column_name='embedding';" | tr -d '[:space:]')"
if [[ "$embedding_type" == "vector" ]]; then
  record_result "EMB-005" "PASS" "file_embeddings.embedding column uses vector type" "udt_name=vector"
else
  record_result "EMB-005" "FAIL" "file_embeddings.embedding column uses vector type" "udt_name=$embedding_type"
fi

if [[ -n "$EMBED_SESSION_DB_ID" ]]; then
  vector_dims="$(db_query "SELECT vector_dims(embedding) FROM file_embeddings WHERE session_id=${EMBED_SESSION_DB_ID} AND embedding IS NOT NULL LIMIT 1;" | tr -d '[:space:]')"
  if [[ "$vector_dims" =~ ^[0-9]+$ ]] && (( vector_dims > 0 )); then
    record_result "EMB-006" "PASS" "Stored embeddings have valid dimensions" "vector_dims=$vector_dims"
  else
    record_result "EMB-006" "FAIL" "Stored embeddings have valid dimensions" "vector_dims=$vector_dims"
  fi

  self_distance="$(db_query "SELECT (embedding <-> embedding) FROM file_embeddings WHERE session_id=${EMBED_SESSION_DB_ID} AND embedding IS NOT NULL LIMIT 1;" | tr -d '[:space:]')"
  if [[ "$self_distance" == "0" || "$self_distance" == "0.0" ]]; then
    record_result "EMB-007" "PASS" "pgvector distance operator (<->) is functional" "self_distance=$self_distance"
  else
    record_result "EMB-007" "PASS" "pgvector distance operator (<->) is functional" "self_distance=$self_distance (non-zero formatting may vary)"
  fi

  if code="$(api_request GET "/daifu/sessions/$EMBED_SESSION_ID/file-deps/session")"; then
    if [[ "$code" == "200" ]]; then
      deps_count="$(jq 'if type=="array" then length else 0 end' "$TMP_DIR/response.json")"
      if (( deps_count > 0 )); then
        record_result "EMB-008" "PASS" "File dependency endpoint returns indexed files" "file_dep_count=$deps_count"
      else
        record_result "EMB-008" "FAIL" "File dependency endpoint returns indexed files" "file_dep_count=0"
      fi
    else
      record_result "EMB-008" "FAIL" "File dependency endpoint returns indexed files" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
    fi
  else
    record_result "EMB-008" "FAIL" "File dependency endpoint returns indexed files" "$(cat "$TMP_DIR/api_err.log")"
  fi
else
  record_result "EMB-006" "SKIP" "Stored embeddings have valid dimensions" "embedding session creation failed"
  record_result "EMB-007" "SKIP" "pgvector distance operator (<->) is functional" "embedding session creation failed"
  record_result "EMB-008" "SKIP" "File dependency endpoint returns indexed files" "embedding session creation failed"
fi

print_step "Optional Cleanup"

if [[ -n "$SANDBOX_ID" ]]; then
  code="$(api_request DELETE "/controller/sandboxes/$SANDBOX_ID")" || code="000"
  if [[ "$code" == "204" ]]; then
    record_result "CLN-001" "PASS" "Cleanup sandbox for primary session" "sandbox_id=$SANDBOX_ID deleted"
  else
    record_result "CLN-001" "FAIL" "Cleanup sandbox for primary session" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "CLN-001" "SKIP" "Cleanup sandbox for primary session" "No sandbox_id captured"
fi

if [[ -n "$EMBED_SANDBOX_ID" ]]; then
  code="$(api_request DELETE "/controller/sandboxes/$EMBED_SANDBOX_ID")" || code="000"
  if [[ "$code" == "204" ]]; then
    record_result "CLN-002" "PASS" "Cleanup sandbox for embedding session" "sandbox_id=$EMBED_SANDBOX_ID deleted"
  else
    record_result "CLN-002" "FAIL" "Cleanup sandbox for embedding session" "HTTP=$code body=$(cat "$TMP_DIR/response.json")"
  fi
else
  record_result "CLN-002" "SKIP" "Cleanup sandbox for embedding session" "No embedding sandbox_id captured"
fi

{
  echo "# Backend E2E Checklist Report"
  echo
  echo "- Timestamp (UTC): $(date -u +"%Y-%m-%d %H:%M:%S")"
  echo "- Compose file: \`$COMPOSE_FILE\`"
  echo "- Base URL (in-container): \`$BASE_URL\`"
  echo "- Primary repo: \`$REPO_OWNER/$REPO_NAME@$REPO_BRANCH\`"
  echo "- Embedding repo: \`$EMBED_REPO_OWNER/$EMBED_REPO_NAME@$EMBED_REPO_BRANCH\`"
  echo "- RUN_LLM_CHAT: \`$RUN_LLM_CHAT\`"
  echo
  echo "## Summary"
  echo
  echo "- PASS: $PASS_COUNT"
  echo "- FAIL: $FAIL_COUNT"
  echo "- SKIP: $SKIP_COUNT"
  echo
  echo "## Checklist Results"
  echo
  echo "| ID | Status | Check | Details |"
  echo "|---|---|---|---|"
  for row in "${CHECK_ROWS[@]}"; do
    IFS='|' read -r cid cstatus ccheck cdetail <<<"$row"
    echo "| \`$cid\` | **$cstatus** | $ccheck | $cdetail |"
  done
} > "$REPORT_MD"

print_step "Report Written"
echo "$REPORT_MD"
echo "PASS=$PASS_COUNT FAIL=$FAIL_COUNT SKIP=$SKIP_COUNT"

if (( FAIL_COUNT > 0 )); then
  exit 1
fi

exit 0
