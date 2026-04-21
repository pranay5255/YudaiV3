# Real-Time Sessions: Detailed Phase Task List

This task list is based on `REAL_TIME_IMPLEMENTATION_QUESTIONNAIRE.md` answers.

Execution rule:
1. Complete all tasks in a phase.
2. Run phase test checklist (backend + browser).
3. Get sign-off.
4. Only then move to next phase.

---

## Confirmed Scope (from answers)

- Sandbox identity key: `org + repo + environment`.
- Keep one repo, two entrypoints first (controller + sandbox server).
- No backward compatibility required for old `/api/daifu/*` paths.
- Frontend must connect to sandbox via direct tunnel.
- Streaming split: SSE for solver trajectory, WebSocket for chat.
- PostgreSQL on controller host for metadata; sandbox cache in JSON (append-only) at `/home/yudai/.cache/`.
- Sandbox creation at session creation.
- Health check every 10s.
- Auth for tunnel: reuse existing session JWT, TTL 1 hour, reusable.
- CORS origin: `https://yudai.app`.
- No proxy fallback when tunnel fails (hard error).
- Session persistence end condition: both GitHub issue creation and PR creation are completed.
- On end condition: export artifact bundle, persist metadata, then terminate immediately.
- Legacy repo-helper training was planned as a manual admin workflow, but the indexing path has since been removed.

---

## Phase 0: Preflight and Contract Freeze — ✅ COMPLETE

### Tasks
P0-1. ✅ Freeze API contracts for controller and sandbox server (controller routes, sandbox WS exec protocol, sandbox_transport.py).
P0-2. ✅ Sandbox identity canonicalization for `org/repo/environment` — implemented in `config/realtime_identity.py`.
P0-3. ✅ DB migration plan — `Sandbox`, `SessionRuntime`, `SessionArtifact`, `SessionAuditEvent` models added.
P0-4. ✅ Cache JSON schema — `SessionCacheStore` with append-only event log and bundle export.
P0-5. ✅ Auth and token flow — session JWT passthrough via `validate_session_token` + `CONTROLLER_INTERNAL_WS_SECRET` for internal exec WS.
P0-6. ✅ Error taxonomy — `RealtimeErrorCode` enum in `backend/realtime/errors.py` with `as_http_exception` helper.
P0-7. ✅ Audit log schema — `SessionAuditEventName` enum: `sandbox_start`, `solve_start`, `github_issue_create`, `pr_create`, `sandbox_terminate`.
P0-8. ✅ Feature flags — `get_realtime_feature_flags()` / `config/realtime_flags.py` with `modal_provisioning_enabled`, tunnel mode, WS flags.

### Deliverables — All delivered
- Contract: `controller_routes.py`, `sandbox_transport.py`, `ws_protocol.py`
- Migration SQL + model specs: in `models.py`
- Cache schema: `cache_store.py`
- Rollout flags: `config/realtime_flags.py`

---

## Phase 1: Controller + Sandbox Shell (MVP foundation) — ✅ COMPLETE

### Backend Tasks
P1-1. ✅ Controller entrypoint — `backend/run_controller.py` mounts `auth_router`, `github_router`, `session_router`, `solve_router`, `controller_router`.
P1-2. ✅ Sandbox server entrypoint — Modal sandbox runs `uvicorn run_sandbox_server:app` on port 8100 inside the container.
P1-3. ✅ Logic moved into sandbox — solver runs as subprocess inside sandbox via exec broker WS (`sandbox_transport.py`). Session/chat APIs remain on controller.
P1-4. ✅ Controller sandbox lifecycle endpoints — `POST /controller/sandboxes`, `GET /controller/sandboxes/{id}`, `DELETE /controller/sandboxes/{id}`, `POST /controller/sandboxes/{id}/resolve-tunnel`, `POST /controller/sandboxes/{id}/heartbeat`, `POST /controller/sandboxes/cleanup`.
P1-5. ✅ Sandbox manager — `SandboxManager` now lives in canonical `backend/realtime/lifecycle.py` with 10s liveness probe via `start_probe()`/`stop_probe()`.
P1-6. ✅ Session-create flow — `POST /controller/sessions/{id}/runtime` provisions sandbox via `RealtimeLifecycleService.create_runtime_for_session()` and returns `tunnel_url`.
P1-7. ✅ Direct tunnel auth — session JWT validated via `validate_session_token` on WS connect; internal exec WS uses `CONTROLLER_INTERNAL_WS_SECRET`.
P1-8. ✅ CORS policy — configured in `run_controller.py` FastAPI app for `https://yudai.app`.
P1-9. ✅ No-proxy-fallback — `RealtimeErrorCode.TUNNEL_UNAVAILABLE`, `TUNNEL_TERMINATED`, `TUNNEL_RESOLVE_FAILED` raise hard HTTP errors via `as_http_exception`.
P1-10. ✅ Git bootstrap — `SandboxManager.ensure_git_bootstrap()` in `lifecycle.py`: clone once per identity key, `git fetch --all --prune` every 300s (configurable `SANDBOX_GIT_FETCH_INTERVAL_SECONDS`).
P1-11. ✅ Per-user sandbox identity — current MVP provisions per user/session ownership; future shared-sandbox policy remains a separate design issue.
P1-12. ✅ Completion detector — `SessionExecutionOrchestrator._finalize_runtime()` exports artifacts and terminates the sandbox after workflow completion/failure/cancel.
P1-13. ✅ On completion: export artifact bundle via `cache_store.download_sandbox_artifact_bundle()`, persist `SessionArtifact` row, terminate sandbox immediately.

**New infrastructure added (not in original plan):**
- `backend/realtime/sandbox_transport.py` — Shared WebSocket transport layer for internal sandbox exec WS (`/internal/sessions/{id}/ws/exec`).
- `backend/realtime/cache_store.py` — Download artifact tarballs from sandbox to controller persistent storage with streaming base64 protocol.
- `backend/realtime/modal_preflight.py` — Deploy-time preflight: spins up a throw-away sandbox, waits for healthcheck, runs `minisweagent` import smoke test.
- `scripts/modal_preflight_standalone.py` — Standalone Modal preflight runner for CI/deploy scripts.
- `scripts/modal_workflow_standalone.py` — Standalone Modal workflow runner for manual testing.

### Unified Modal Sandbox Architecture (implemented, differs from original plan)

The sandbox image is **unified** — one image runs both:
1. **Sandbox server** (uvicorn on port 8100) as the main process
2. **mini-swe-agent** solve runs as **subprocesses** via exec broker WS

Layers in `_get_unified_sandbox_image()`:
1. `debian-slim 3.11` + `git`, `curl`, `gh`, `gcc`, `libpq`
2. Server Python deps: `fastapi`, `uvicorn`, `httpx`, `sqlalchemy`, etc.
3. Solver Python deps: `mini-swe-agent`
4. Backend source → `/app/backend/`
5. MSWEA mode configs → `/app/mswea_mode_configs/`
6. Workspace directory `/workspace/` (empty at build)

Execution flow:
```
Controller → SandboxExecBroker.run_command()
          → sandbox_transport.run_sandbox_command()
          → WebSocket wss://{tunnel}/internal/sessions/{id}/ws/exec
          → Sandbox subprocess: runs agent script, streams stdout/stderr back
```

### Database Tasks
P1-14. ✅ Tables: `sandboxes`, `session_runtime`, `session_artifacts` — all defined in `backend/models.py`.
P1-15. ✅ Indexes for lifecycle queries on `identity_key`, `status`, `session_id` (in model definitions).
P1-16. ✅ Audit log — `session_audit_events` table with `SessionAuditEvent` model.
P1-17. ⚠️ Migration scripts — DB initialized via `init_db()` in `backend/db/database.py`; Alembic migration files not confirmed present.

### Cache and Artifact Tasks
P1-18. ✅ Cache root — `SessionCacheStore` with configurable `REALTIME_CACHE_ROOT` (defaults to `/home/yudai/.cache/`).
P1-19. ✅ Append-only JSON event write via `cache_store.append_event()`.
P1-20. ✅ Artifact export format — trajectory refs, issue refs, PR refs, runtime metadata, timestamps via `cache_store.export_bundle()`.
P1-21. ✅ `SessionArtifact` row persisted to DB on completion with `artifact_key`, `checksum_sha256`, `bundle_path`, `cache_manifest_path`.

### Frontend Tasks
P1-22. ✅ `src/utils/realtimeRouting.ts` — `buildControllerSessionTargetUrl`, `buildControllerUnifiedWsEndpoint`, `buildUnifiedSessionWebSocketUrl`.
P1-23. ✅ `src/hooks/useSessionWebSocket.ts` — connects to `/controller/sessions/{id}/ws/unified` with session JWT token query param.
P1-24. ✅ WS error handling with `status: 'error'` state; `MAX_RECONNECT_ATTEMPTS = 10`; heartbeat timeout detection.
P1-25. ✅ Old `/api/daifu/*` proxy routes not assumed in controller routing.

### Testing Tasks
P1-26. ✅ Unit tests — `backend/tests/test_realtime_controller_routes.py` (modified).
P1-27. ✅ Integration tests — `backend/tests/test_run_controller_mounts.py` (modified).
P1-28. ✅ Auth session token flow tests — `backend/tests/test_auth_session_token_flow.py` (new).
P1-29. ✅ Modal preflight tests — `backend/tests/test_modal_sandbox_preflight.py` (new).
     ✅ Frontend routing tests — `src/tests/frontend/realtimeRouting.test.ts` (modified).
     ✅ Frontend session store runtime tests — `src/tests/frontend/sessionStore.runtime.test.ts` (new).

### Browser Validation Gate (must pass before Phase 2)
P1-B1. Sign in, choose repo+branch, create session, and verify sandbox is provisioned immediately.
P1-B2. Verify frontend receives `tunnel_url` and all session actions work through direct tunnel.
P1-B3. Simulate tunnel failure and verify hard error message is shown (no hidden fallback).
P1-B4. Create GitHub issue from session, then run solve to PR creation; verify both events are logged.
P1-B5. After PR creation, verify session is terminated immediately and UI shows terminal state.
P1-B6. Verify artifact metadata row exists in PG and cache export is recorded.

### Exit Criteria
- Controller/sandbox split stable in browser for core session flow.
- Lifecycle and termination behavior confirmed.
- DB + cache artifact persistence confirmed.

---

## Phase 2: Legacy Repo-Helper Activation (removed)

### Backend Tasks
P2-1. ⬜ Removed with the legacy indexing path.
P2-2. ⬜ Implement hard-fail startup behavior when model load fails, with explicit error messaging.
P2-3. ⬜ Removed with the legacy indexing path.
P2-4. ⬜ Add basic runtime diagnostics endpoint for model readiness state.

### Training Script Tasks (manual/admin)
P2-5. ⬜ Add admin-only training script in controller codebase (CLI command).
P2-6. ⬜ Script reads session trajectories from exported cache artifacts and builds training dataset.
P2-7. ⬜ Script runs training and writes single shared checkpoint for MVP.
P2-8. ⬜ Script writes run summary (input count, output path, training timestamp, status).
P2-9. ⬜ Add documented runbook for manual trigger, validation, and rollback-by-file-replace.

### Data Tasks
P2-10. ⬜ Define trajectory ingestion format for trainer from `session_artifacts` metadata.
P2-11. ⬜ Add lightweight training-run record table or log file for admin audit (who ran, when, result).

### Testing Tasks
P2-12. ⬜ Unit tests for training dataset builder and schema validation.
P2-13. ⬜ Integration test: train command runs on sample trajectories and produces checkpoint artifact.
P2-14. ⬜ Integration test: sandbox startup fails as expected when checkpoint missing/corrupt.

### Browser Validation Gate (must pass before Phase 3)
P2-B1. Start a new session and verify sandbox boot succeeds without legacy repo-helper loading.
P2-B2. Perform chat and issue workflows and verify no regressions with mandatory model path.
P2-B3. Temporarily break checkpoint path in staging and verify hard-fail UX appears clearly.

### Exit Criteria
- Manual training pipeline is runnable by admin and produces usable checkpoint.
- Sandbox mandatory model load behavior is reliable and observable.

---

## Phase 3: Real-Time Streaming (Unified Controller WebSocket)

### Unified WS Tasks (chat, mode progress, sandbox trajectory)
P3-1. ✅ Route solver/mode trajectory through `/controller/sessions/{id}/ws/unified`.
P3-2. ✅ Use controller-proxied `llm_stream`, `sandbox_stream`, `mode_event`, and `state_event` envelopes; no SSE compatibility path is required.
P3-3. ✅ Use WS heartbeat/reconnect in `useSessionWebSocket.ts`.
P3-4. ⬜ Add controlled reconnect UI for long-running execution streams.
P3-5. ✅ Ensure stream authentication via session token on unified WS connect.
P3-6. ✅ Emit explicit terminal events for completed/failed/cancelled runs.

**Note:** Trajectory data currently streams via WS `TRAJECTORY_UPDATE` messages from solver stdout accumulation in `solve_manager.py`. Phase 3 replaces this with direct SSE from sandbox server.

### WebSocket Tasks (chat)
P3-7. ⬜ Implement WS endpoint for chat in sandbox server (currently chat is REST on controller).
P3-8. ⬜ Implement WS auth handshake using existing session JWT.
P3-9. ⬜ Implement WS message types: plain messages, token chunks, tool events, status events.
P3-10. ✅ Reconnect policy target: retry count 10 — already implemented in `useSessionWebSocket.ts`.
P3-11. ⬜ Implement backpressure policy for MVP (buffer + bounded queue + drop oldest on overflow, with warning events).
P3-12. ⬜ No chat history replay on reconnect (as specified).

### Frontend Tasks
P3-13. ✅ Chat token streaming over unified controller WebSocket for live chat responses.
P3-14. ✅ `TrajectoryViewer` consumes controller-proxied `sandbox_stream` and `mode_event` messages. No frontend direct tunnel or SSE path is required for the current architecture.
P3-15. ⬜ Add reconnect management UI for unified WS states.
P3-16. ⬜ On tunnel drop, show hard error (no polling fallback).
P3-17. ⬜ Keep single active solve trajectory view (no multi-run tabs).

### Testing Tasks
P3-18. ⬜ Unit tests for WS client state machine and reconnect attempts (10 retries).
P3-19. ⬜ Integration tests for unified WS event parsing and lifecycle transitions.
P3-20. ⬜ Load tests for stream stability under long token and message bursts.
P3-21. ⬜ Failure injection tests: dropped tunnel, expired token, sandbox termination mid-stream.

### Browser Validation Gate (must pass before Phase 4)
P3-B1. Chat over WS works end-to-end with visible token/tool/status updates.
P3-B2. Solver trajectory appears in `TrajectoryViewer` via unified controller WebSocket with <=1s perceived update cadence.
P3-B3. Unified WS reconnect behavior works under forced reconnect every 10s.
P3-B4. WS reconnect attempts stop at 10 retries and final hard error is shown.
P3-B5. Tunnel interruption shows explicit hard error and user can re-enter session cleanly.

### Exit Criteria
- Stable real-time chat + trajectory streaming through direct tunnel.
- Error handling and reconnect behavior match MVP requirements.

---

## Phase 4: Advanced Features and Scaffolding

This phase has several unanswered questionnaire items. Implement only scaffolding and non-breaking hooks first.

### Scaffolding Tasks
P4-1. ⬜ Add presence model and API stubs for shared presence indicators (future multi-user).
P4-2. ⬜ Add configurable concurrency strategy interfaces (edit conflict policy not finalized).
P4-3. ⬜ Add abstraction for parallel solve execution strategy (queue policy TBD).
P4-4. ⬜ Add storage strategy interface for embeddings/artifacts (provider TBD).
P4-5. ⬜ Add extension-ready API namespace for future IDE integration.

### Decision-Dependent Tasks (defer until answers provided)
P4-6. ⬜ Finalize conflict resolution mode and implement actual edit coordination.
P4-7. ⬜ Finalize parallel run policy and implement shared vs isolated workdir strategy.
P4-8. ⬜ Finalize embedding persistence target and implement production storage path.
P4-9. ⬜ Finalize fine-tuning hooks scope and implement if in-scope.

### Testing Tasks
P4-10. ⬜ Contract tests for presence and concurrency interfaces (even if stubs).
P4-11. ⬜ Backward-compat tests to ensure Phase 1-3 behavior is unchanged.

### Browser Validation Gate
P4-B1. No user-facing regressions in chat/solve/session lifecycle after scaffolding merge.
P4-B2. Optional presence indicator can be toggled by feature flag without breaking sessions.

### Exit Criteria
- Future-proof extension points merged without destabilizing MVP.
- Deferred items explicitly tracked with owners and deadlines.

---

## Cross-Phase Testing Protocol (Required for Every Phase)

T-1. Local backend tests and lint pass for touched modules.
T-2. Local frontend build/test pass for touched modules.
T-3. Browser smoke on fresh login/session.
T-4. Browser smoke on existing session reload.
T-5. Negative test for auth/token expiry path.
T-6. Negative test for sandbox unavailable path.
T-7. Audit log verification for new events in the phase.
T-8. DB migration apply + rollback rehearsal in non-prod.

---

## Open Items from Questionnaire (Need Answers Before Full Phase 4 and Production Hardening)

- Q67-72 (advanced behavior policy and scope).
- Q73-78 (object storage and lifecycle controls).
- Q79-83 (security hardening requirements).
- Q84-94 (test/load/ops/ownership/timeline/do-not-ship criteria).

Recommended handling:
1. Proceed with Phases 1-3 MVP using current decisions.
2. Resolve open items before implementing non-scaffolding Phase 4 and before production hardening.
