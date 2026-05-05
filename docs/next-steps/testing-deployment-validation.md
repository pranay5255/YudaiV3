# Next Step: Testing And Deployment Validation

This file is the next-step runbook for validating the React + Vercel SSE middleware + Python backend architecture.

Current local status from this branch:

- Frontend unit/integration tests pass: `34 passed`.
- Backend tests pass: `111 passed`.
- Frontend build passes.
- Browser app TypeScript, Vercel middleware TypeScript, contract typecheck, lint, shell syntax, and smoke script syntax all pass.
- Production smoke has not been run locally because it requires deployed Vercel/backend env and a disposable production session token.

## Local Test Commands

Run from `src/`:

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

Run from repo root:

```bash
PYTHONPATH=backend UV_CACHE_DIR=/tmp/uv-cache uv run pytest backend/tests/test_auth_session_token_flow.py backend/tests/test_session_routes_questions.py backend/tests/test_realtime_controller_routes.py backend/tests/test_run_controller_mounts.py
PYTHONPATH=backend UV_CACHE_DIR=/tmp/uv-cache uv run pytest backend/tests
bash -n scripts/deploy.sh
bash -n scripts/e2e/backend_e2e_suite.sh
node --check scripts/e2e/prod_frontend_middleware_smoke.mjs
git diff --check
```

## Production Run Order

Run these on the prod backend server after `backend/.env.prod` exists:

```bash
docker compose --env-file backend/.env.prod -f docker-compose.backend-only.yml config --quiet
docker compose --env-file backend/.env.prod -f docker-compose.backend-only.yml up -d db backend
scripts/e2e/backend_e2e_suite.sh
```

Run this after the frontend is deployed to Vercel and a disposable production session token is available:

```bash
FRONTEND_BASE_URL=https://yudai.app \
BACKEND_BASE_URL=https://api.yudai.app \
E2E_SESSION_TOKEN=<disposable-session-token> \
node scripts/e2e/prod_frontend_middleware_smoke.mjs
```

Expected report locations:

- Backend compose E2E: `logs/e2e/backend_e2e_report_*.md`
- Frontend middleware smoke: `logs/e2e/prod_frontend_middleware_report_*.md`

## Errors That Need Your Attention

| Area | Signal | Likely Fix |
|---|---|---|
| Backend env | `docker compose config` fails with missing `backend/.env.prod` | Ensure the prod server has `backend/.env.prod`; this file is intentionally not committed. |
| Shared middleware secret | `/realtime/.../events` returns `500` with `YUDAI_INTERNAL_MIDDLEWARE_SECRET is required` | Set the same `YUDAI_INTERNAL_MIDDLEWARE_SECRET` in backend `.env.prod` and Vercel env. |
| Secret mismatch | Backend WebSocket closes with `invalid_internal_auth` or smoke `RT-001` fails | The Vercel secret and backend secret do not match, or `internal_user_id` does not resolve to a backend user. |
| Vercel runtime WebSocket | Vercel function logs show `ReferenceError: WebSocket is not defined` | Add a supported Node WebSocket client for the middleware bridge, or force a Vercel runtime that provides `WebSocket`. |
| Auth REST | `AUTH-001` or `AUTH-002` fails in production smoke | Check `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`, `GITHUB_REDIRECT_URI`, `FRONTEND_BASE_URL`, and `/auth/api/login`. |
| Frontend auth callback | User returns to `/auth/login?error=missing_auth_data` | Python callback is not redirecting to `/auth/success` with `session_token`, `user_id`, and `username`. |
| Vercel rewrites | `/github/*`, `/daifu/*`, `/ai/*`, or `/realtime/*` returns app HTML or 404 | Verify `src/vercel.json` was deployed and not overwritten; `scripts/deploy.sh` now validates this. |
| AI stream | `AI-001` fails or no `x-vercel-ai-ui-message-stream: v1` header | Check Vercel AI route deployment, backend `/ai-context`, backend `/ai-turns`, and `OPENROUTER_API_KEY` if real model output is required. |
| AI fallback | Stream says `AI middleware is connected. Configure OPENROUTER_API_KEY...` | Middleware route works, but real model generation is disabled until `OPENROUTER_API_KEY` is set. |
| Disposable token | `prod_frontend_middleware_smoke.mjs` fails at `ENV-001` | Provide `E2E_SESSION_TOKEN`. Current backend E2E intentionally does not print tokens; choose a safe handoff method on prod. |
| Modal/runtime | Backend E2E fails during session/runtime creation or `SES-*` checks | Inspect `modal-preflight`, Modal secrets, repo access, `SANDBOX_*` envs, and Docker volume permissions. |
| Cleanup | `CLN-001` fails | Manually delete the sandbox through `/controller/sandboxes/{sandbox_id}` or DB cleanup before rerunning. |

## What Works Before Production Smoke

- `LoginPage` starts GitHub REST auth.
- Auth callback state resets app to the chat tab.
- Protected app shell renders `AgentWorkbench`.
- Active chat uses the AI SDK stream endpoint and sends bearer auth only in headers.
- Browser realtime uses same-origin SSE instead of direct backend WebSocket.
- Node middleware validates the user before proxying or opening backend WebSocket.
- Python backend accepts internal middleware identity and rejects invalid internal auth.
- Backend AI context and AI turn persistence endpoints enforce session ownership.

## Manual Final Checks

After automated production smoke passes, manually verify:

- Open `https://yudai.app/auth/login`.
- Click GitHub login and complete OAuth.
- Confirm redirect lands in the app, not back on the login page.
- Start a disposable repository session.
- Send one chat message and confirm streamed assistant text appears.
- Open the Runs panel and confirm execution start/cancel still reaches Python endpoints.
- Confirm the backend E2E report has no leftover sandbox cleanup failures.
