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
- yudai-grep training is manual script in this codebase, admin-only trigger.

---

## Phase 0: Preflight and Contract Freeze

### Tasks
P0-1. Freeze API contracts for controller and sandbox server (OpenAPI and payload examples).  
P0-2. Define sandbox identity canonicalization for `org/repo/environment` and repository+branch normalization rules.  
P0-3. Define DB migration plan using `backend/db/init.sql` + SQLAlchemy model updates in `backend/models.py`.  
P0-4. Define cache JSON schemas for session cache and artifact bundle metadata.  
P0-5. Define auth and token flow sequence diagrams (JWT pass-through for direct tunnel + SSE query token).  
P0-6. Define error taxonomy and user-facing hard-error messages for tunnel and stream failures.  
P0-7. Define audit log schema and event names (sandbox_start, solve_start, github_issue_create, pr_create, sandbox_terminate).  
P0-8. Add feature flags for phase rollout (controller split flag, tunnel mode flag, ws-chat flag, sse-stream flag).

### Deliverables
- Contract doc with endpoint list and examples.
- Migration SQL + model change spec.
- Cache schema doc with sample JSON files.
- Rollout flags documented.

### Browser Validation Gate
- None (design-only phase).

### Exit Criteria
- All contracts approved and no open blockers for Phase 1.

---

## Phase 1: Controller + Sandbox Shell (MVP foundation)

### Backend Tasks
P1-1. Create controller entrypoint (new app module) and keep current repo structure.  
P1-2. Create sandbox session server entrypoint that hosts moved session APIs.  
P1-3. Move/clone required logic from host into sandbox server (`session_routes`, `ChatOps`, `IssueOps`, `llm_service`, context services, solver router integration points).  
P1-4. Implement controller sandbox lifecycle endpoints: create/get/delete/resolve-tunnel/heartbeat/cleanup.  
P1-5. Add sandbox manager service for create/monitor/terminate with 10s liveness probe.  
P1-6. Implement session-create flow to provision sandbox immediately and return `tunnel_url`.  
P1-7. Implement direct tunnel auth using current session JWT (1-hour TTL assumptions preserved by existing token lifecycle).  
P1-8. Implement CORS policy for tunnel-facing server (`https://yudai.app`).  
P1-9. Implement no-proxy-fallback policy: return actionable hard errors on tunnel failures.  
P1-10. Implement git bootstrap policy in sandbox: clone once + periodic fetch.  
P1-11. Enforce single active editor semantics in Phase 1 (no multi-user concurrent edits).  
P1-12. Implement session completion detector (GitHub issue created AND PR created).  
P1-13. On completion, export artifact bundle from sandbox cache, persist metadata in PG, terminate sandbox immediately.

### Database Tasks
P1-14. Add dedicated tables: `sandboxes`, `session_runtime`, `session_artifacts`.  
P1-15. Add indexes for lifecycle queries (`org/repo/environment`, `status`, `updated_at`, `session_id`).  
P1-16. Add audit log table or event rows linked to runtime/sandbox IDs.  
P1-17. Add migration scripts and rollback scripts.

### Cache and Artifact Tasks
P1-18. Create cache root in sandbox: `/home/yudai/.cache/`.  
P1-19. Implement append-only JSON write strategy for session cache artifacts.  
P1-20. Define artifact export format (trajectory refs, issue refs, PR refs, runtime metadata, timestamps, checks).  
P1-21. Persist exported artifact metadata to `session_artifacts`.

### Frontend Tasks
P1-22. Add controller call to get/create runtime and receive `tunnel_url`.  
P1-23. Route session HTTP calls to tunnel target instead of host-proxied routes.  
P1-24. Add hard-error UX states for tunnel unavailable/expired JWT/terminated sandbox.  
P1-25. Remove assumptions that old `/api/daifu/*` host path must remain valid.

### Testing Tasks
P1-26. Unit tests for sandbox identity resolution and state transitions.  
P1-27. Integration tests for lifecycle endpoints and DB persistence.  
P1-28. Integration tests for completion detector and auto-termination sequence.  
P1-29. Security tests for JWT validation and tunnel auth failure paths.

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

## Phase 2: yudai-grep Activation (manual training workflow)

### Backend Tasks
P2-1. Remove optional/fallback import path and make yudai-grep load mandatory at sandbox boot.  
P2-2. Implement hard-fail startup behavior when model load fails, with explicit error messaging.  
P2-3. Wire yudai-grep routing in query paths used by chat/context/solver preparation.  
P2-4. Add basic runtime diagnostics endpoint for model readiness state.

### Training Script Tasks (manual/admin)
P2-5. Add admin-only training script in controller codebase (CLI command).  
P2-6. Script reads session trajectories from exported cache artifacts and builds training dataset.  
P2-7. Script runs training and writes single shared checkpoint for MVP.  
P2-8. Script writes run summary (input count, output path, training timestamp, status).  
P2-9. Add documented runbook for manual trigger, validation, and rollback-by-file-replace.

### Data Tasks
P2-10. Define trajectory ingestion format for trainer from `session_artifacts` metadata.  
P2-11. Add lightweight training-run record table or log file for admin audit (who ran, when, result).

### Testing Tasks
P2-12. Unit tests for training dataset builder and schema validation.  
P2-13. Integration test: train command runs on sample trajectories and produces checkpoint artifact.  
P2-14. Integration test: sandbox startup fails as expected when checkpoint missing/corrupt.

### Browser Validation Gate (must pass before Phase 3)
P2-B1. Start a new session and verify sandbox boot confirms yudai-grep model loaded.  
P2-B2. Perform chat and issue workflows and verify no regressions with mandatory model path.  
P2-B3. Temporarily break checkpoint path in staging and verify hard-fail UX appears clearly.

### Exit Criteria
- Manual training pipeline is runnable by admin and produces usable checkpoint.
- Sandbox mandatory model load behavior is reliable and observable.

---

## Phase 3: Real-Time Streaming (SSE + WebSocket split)

### SSE Tasks (solver trajectory)
P3-1. Move/implement solver SSE stream endpoint inside sandbox server.  
P3-2. Define new SSE event schema (compatibility not required) and document event contract.  
P3-3. Set heartbeat every 3s.  
P3-4. Enforce stream max duration 10s then controlled reconnect behavior.  
P3-5. Ensure stream authentication via JWT query token per your accepted model.  
P3-6. Emit explicit terminal events for completed/failed/cancelled runs.

### WebSocket Tasks (chat)
P3-7. Implement WS endpoint for chat in sandbox server.  
P3-8. Implement WS auth handshake using existing session JWT.  
P3-9. Implement WS message types: plain messages, token chunks, tool events, status events.  
P3-10. Implement reconnect policy target: retry count 10.  
P3-11. Implement backpressure policy for MVP (buffer + bounded queue + drop oldest on overflow, with warning events).  
P3-12. No chat history replay on reconnect (as specified).

### Frontend Tasks
P3-13. Replace REST chat send path with WS chat client and state handlers.  
P3-14. Update `useTrajectoryStream`/`TrajectoryViewer` to consume new SSE schema.  
P3-15. Add reconnect management UI for WS and SSE states.  
P3-16. On tunnel drop, show hard error (no polling fallback).  
P3-17. Keep single active solve trajectory view (no multi-run tabs).

### Testing Tasks
P3-18. Unit tests for WS client state machine and reconnect attempts (10 retries).  
P3-19. Integration tests for SSE event parsing and lifecycle transitions.  
P3-20. Load tests for stream stability under long token and message bursts.  
P3-21. Failure injection tests: dropped tunnel, expired token, sandbox termination mid-stream.

### Browser Validation Gate (must pass before Phase 4)
P3-B1. Chat over WS works end-to-end with visible token/tool/status updates.  
P3-B2. Solver trajectory appears in `TrajectoryViewer` via SSE with <=1s perceived update cadence.  
P3-B3. SSE reconnect behavior works under forced reconnect every 10s.  
P3-B4. WS reconnect attempts stop at 10 retries and final hard error is shown.  
P3-B5. Tunnel interruption shows explicit hard error and user can re-enter session cleanly.

### Exit Criteria
- Stable real-time chat + trajectory streaming through direct tunnel.
- Error handling and reconnect behavior match MVP requirements.

---

## Phase 4: Advanced Features and Scaffolding

This phase has several unanswered questionnaire items. Implement only scaffolding and non-breaking hooks first.

### Scaffolding Tasks
P4-1. Add presence model and API stubs for shared presence indicators (future multi-user).  
P4-2. Add configurable concurrency strategy interfaces (edit conflict policy not finalized).  
P4-3. Add abstraction for parallel solve execution strategy (queue policy TBD).  
P4-4. Add storage strategy interface for embeddings/artifacts (provider TBD).  
P4-5. Add extension-ready API namespace for future IDE integration.

### Decision-Dependent Tasks (defer until answers provided)
P4-6. Finalize conflict resolution mode and implement actual edit coordination.  
P4-7. Finalize parallel run policy and implement shared vs isolated workdir strategy.  
P4-8. Finalize embedding persistence target and implement production storage path.  
P4-9. Finalize fine-tuning hooks scope and implement if in-scope.

### Testing Tasks
P4-10. Contract tests for presence and concurrency interfaces (even if stubs).  
P4-11. Backward-compat tests to ensure Phase 1-3 behavior is unchanged.

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

