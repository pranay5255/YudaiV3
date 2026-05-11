# YudaiV3 Operations

This is the canonical validation and deployment runbook for the current Vercel
frontend plus Python backend architecture. It replaces the older
`docs/next-steps/testing-deployment-validation.md` file.

## Local Validation

Run frontend checks from `src/`:

```bash
npm run test:auth
npm run test:realtime
npm run test:middleware
npm test
npx tsc --project tsconfig.app.json --noEmit
npx tsc --project tsconfig.node.json --noEmit
npm run typecheck:contract
npm run build
```

Run backend and repository checks from the repo root:

```bash
PYTHONPATH=backend UV_CACHE_DIR=/tmp/uv-cache uv run pytest backend/tests/test_auth_session_token_flow.py backend/tests/test_session_routes_questions.py backend/tests/test_realtime_controller_routes.py backend/tests/test_run_controller_mounts.py
PYTHONPATH=backend UV_CACHE_DIR=/tmp/uv-cache uv run pytest backend/tests
bash -n scripts/deploy.sh
bash -n scripts/e2e/backend_e2e_suite.sh
node --check scripts/e2e/prod_frontend_middleware_smoke.mjs
git diff --check
```

Use focused checks while developing, but run the full backend test suite before
changing runtime, execution, auth, or session contracts.

## Backend Compose Validation

Production-like backend compose uses:

```text
docker-compose.backend-only.yml
backend/docker-compose.defaults.env
backend/.env.prod
backend/Dockerfile
backend/start.sh
backend/yudai/db/init.sql
```

Run after `backend/.env.prod` exists on the target backend host:

```bash
docker compose --env-file backend/.env.prod -f docker-compose.backend-only.yml config --quiet
docker compose --env-file backend/.env.prod -f docker-compose.backend-only.yml up -d db backend
scripts/e2e/backend_e2e_suite.sh
```

Expected backend E2E report:

```text
logs/e2e/backend_e2e_report_*.md
```

## Frontend Production Smoke

Run after the frontend is deployed to Vercel and a disposable production session
token is available:

```bash
FRONTEND_BASE_URL=https://yudai.app \
BACKEND_BASE_URL=https://api.yudai.app \
E2E_SESSION_TOKEN=<disposable-session-token> \
node scripts/e2e/prod_frontend_middleware_smoke.mjs
```

Expected frontend middleware smoke report:

```text
logs/e2e/prod_frontend_middleware_report_*.md
```

The smoke script validates auth-sensitive middleware, Vercel rewrites, backend
proxying, realtime bridge behavior, and the AI stream route.

## Required Environment

Backend:

- `DATABASE_URL`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- GitHub App credentials
- `GITHUB_APP_PRIVATE_KEY_PATH`
- `YUDAI_INTERNAL_MIDDLEWARE_SECRET`
- Modal credentials and sandbox settings
- model provider keys such as `OPENROUTER_API_KEY`
- model name through `OPENROUTER_MODEL` or `MSWEA_MODEL_NAME`

Vercel:

- `YUDAI_BACKEND_BASE_URL`
- `YUDAI_INTERNAL_MIDDLEWARE_SECRET`
- `OPENROUTER_API_KEY` when real model output is required
- `OPENROUTER_MODEL` or `MSWEA_MODEL_NAME`
- optional `VITE_API_BASE_URL`
- optional `VITE_AUTH_API_BASE_URL`
- optional `VITE_AI_API_BASE_URL`

`YUDAI_INTERNAL_MIDDLEWARE_SECRET` must match between Vercel and the backend.

## Common Failure Signals

| Area | Signal | Likely Fix |
| --- | --- | --- |
| Backend env | `docker compose config` fails with missing `backend/.env.prod` | Add the prod env file on the server. It is intentionally not committed. |
| Shared middleware secret | `/realtime/.../events` returns `500` with `YUDAI_INTERNAL_MIDDLEWARE_SECRET is required` | Set the same secret in backend and Vercel env. |
| Secret mismatch | backend WebSocket closes with `invalid_internal_auth` or smoke `RT-001` fails | Confirm Vercel and backend secrets match and the internal user resolves. |
| Vercel runtime WebSocket | Vercel logs show `ReferenceError: WebSocket is not defined` | Use a supported Node WebSocket client or runtime for the middleware bridge. |
| Auth REST | `AUTH-001` or `AUTH-002` fails in production smoke | Check GitHub OAuth env, redirect URI, frontend base URL, and `/auth/api/login`. |
| Auth callback | User returns to `/auth/login?error=missing_auth_data` | Backend callback did not redirect to `/auth/success` with session token data. |
| Vercel rewrites | `/github/*`, `/daifu/*`, `/ai/*`, or `/realtime/*` returns app HTML or 404 | Verify `src/vercel.json` was deployed and the deploy script validated it. |
| AI stream | `AI-001` fails or no `x-vercel-ai-ui-message-stream: v1` header | Check Vercel AI route deployment and backend `/ai-context` and `/ai-turns`. |
| AI fallback | Stream says to configure `OPENROUTER_API_KEY` | Middleware works, but real model output is disabled until model env is set. |
| Disposable token | smoke script fails at `ENV-001` | Provide a disposable `E2E_SESSION_TOKEN`. Do not print production tokens in reports. |
| Modal/runtime | backend E2E fails during runtime creation | Inspect `modal-preflight`, Modal secrets, repo access, sandbox env, and volume permissions. |
| Cleanup | `CLN-001` fails | Delete the sandbox through `/controller/sandboxes/{sandbox_id}` or clean DB state before rerunning. |

## Manual Production Checks

After automated smoke passes:

1. Open `https://yudai.app/auth/login`.
2. Complete GitHub login.
3. Confirm redirect lands in the app, not back on the login page.
4. Start a disposable repository session.
5. Send one chat message and confirm streamed assistant text appears.
6. Answer any pending clarification question and confirm the UI resumes cleanly.
7. Open the Runs panel and confirm execution start/cancel reaches Python
   endpoints.
8. Confirm the backend E2E report has no leftover sandbox cleanup failures.

## Runtime Debug Checklist

For execution failures:

1. Check backend logs around `/daifu/sessions/{session_id}/execution`.
2. Confirm `MODE_ORCHESTRATOR_ENABLED` or equivalent realtime flag is enabled.
3. Confirm the session has repo owner, repo name, branch, and user auth token.
4. Check whether a runtime already exists through
   `/controller/sessions/{session_id}/runtime`.
5. Inspect `agent_executions` rows for mode, status, output summary, and error.
6. Inspect `session_runtime`, `session_artifacts`, and audit events.
7. Inspect Modal sandbox logs and internal exec WebSocket errors.
8. Confirm mode config paths exist inside the sandbox image under
   `/app/mswea_mode_configs`.

For AI stream failures:

1. Confirm `/ai/sessions/{sessionId}/stream` is served by Vercel, not the SPA.
2. Confirm the request includes `Authorization: Bearer <token>`.
3. Confirm backend `/daifu/sessions/{sessionId}/ai-context` succeeds.
4. Confirm model env exists when real output is expected.
5. Confirm backend `/daifu/sessions/{sessionId}/ai-turns` persists after stream.

For realtime UI failures:

1. Check `/realtime/sessions/{sessionId}/events` through Vercel.
2. Check backend `/controller/sessions/{sessionId}/ws/unified`.
3. Confirm internal middleware auth succeeds.
4. Check browser console for EventSource or fetch stream errors.
5. Check backend `mode_event`, `trajectory_update`, `status`, and `error`
   payloads.

## Documentation Maintenance

Keep docs intentionally small:

- Update `docs/ARCHITECTURE.md` for architecture, routes, mode flow, runtime,
  realtime, or UI-system changes.
- Update this file for validation, deployment, environment, or smoke-test
  changes.
- Do not add a new root docs file for temporary planning unless it has a clear
  deletion date or is replacing part of these two docs.
- Keep generated reports under `logs/`, not `docs/`.
