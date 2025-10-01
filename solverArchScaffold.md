# Solver Architecture Scaffold

> Minute-by-minute breakdown of the implementation path for adding the parallel solver service backed by e2b sandboxes and the mini-swe-agent. Use this as the working specification while refactoring the backend and UI layers.

## 0. Prerequisites & Baseline Validation (Day 0)
- [ ] Confirm FastAPI backend (`backend/run_server.py`) can reach Redis/Postgres (used later for queue + job records). Add local `.env` entries if missing.  
- [ ] Ensure `backend/requirements.txt` is synced with `pyproject.toml`; run `pip install -r backend/requirements.txt` to verify no drift.  
- [ ] Validate chat session flow via `backend/daifuUserAgent/session_routes.py` and `session_service.py` so you know where to plug solver updates.  
- [ ] Inventory GitHub credentials already handled in `backend/github` to avoid duplicate config.

## 1. Dependency Updates (Day 1 Morning)
1. **Python Backend (`backend/requirements.txt` + `pyproject.toml`)**  
   - Add `e2b` (official SDK), `mini-swe-agent`, `redis` (if queue uses Redis), `rq` or `celery` depending on chosen worker, and `tenacity` for retries.  
   - Pin versions for reproducibility (e.g. `e2b==0.x.y`, `mini-swe-agent==<current>`, `tenacity==8.2.3`).  
   - Re-run `pip-compile` if you use it; update lock files.
2. **Backend Config (`backend/config/settings.py` or equivalent)**  
   - Add typed settings for `E2B_API_KEY`, `E2B_TEMPLATE_ID`, concurrency caps, Redis URL, BYOC control plane URL.  
   - Extend `config/__init__.py` exports if needed so FastAPI can inject the settings.  
3. **Frontend (`package.json`)**  
   - If the UI triggers solver jobs, add any needed client libs (e.g., `socket.io-client` for live updates).  
   - Regenerate `package-lock.json`/`pnpm-lock.yaml` accordingly.

## 2. Data Model Extensions (Day 1 Afternoon)
- **Database (`backend/models.py`)**  
  - Add `SolverJob` ORM model with fields: `id`, `session_id`, `issue_id`, `status`, `sandbox_id`, `agent_run_id`, `logs_url`, `diff_snapshot_url`, `started_at`, `finished_at`, `error_message`.  
  - Create alembic migration (if using) or raw SQL migration to add table + indexes on `session_id` and `issue_id`.  
- **Pydantic Schemas (`models.py` or dedicated schema file)**  
  - Define `SolverJobRequest`, `SolverJobResponse`, `SolverJobStatusUpdate`.  
  - Wire them into `SessionContextResponse`/`ChatMessageResponse` if the chat stream should surface solver status.

## 3. Queue & Orchestrator Skeleton (Day 2 Morning)
1. **Job Queue**  
   - Decide on queue tech (Redis Queue or Celery).  
   - Create `backend/daifuUserAgent/solver_queue.py` with helper `enqueue_solver_job(issue_payload)`; import settings + job schema.  
   - Register queue worker entry point (e.g., `backend/daifuUserAgent/solver_worker.py`).
2. **Orchestrator Service**  
   - New file `backend/daifuUserAgent/solver_service.py` encapsulating lifecycle: `create_job`, `launch_sandbox`, `run_agent`, `stream_results`, `cleanup`.  
   - Inject dependencies: DB session, queue client, GitHubOps (for repo metadata), SessionService (for cross-linking).  
   - Add logging with job IDs for traceability.
3. **API Surface**  
   - Extend `session_routes.py` or add `/solver` router exposing `POST /sessions/{id}/issues/{issue_id}/solve` to enqueue work and `GET /solver/jobs/{job_id}` for polling.  
   - Use dependency injection to grab DB + `SolverService`.

## 4. e2b Sandbox Integration (Day 2 Afternoon)
1. **Template Authoring**  
   - Create `backend/solver_templates/template.toml` (or YAML) per e2b docs.  
   - Add `prepare_repo.sh` to clone `repo_owner/repo_name` using GitHub token from env; script writes repo to `/workspace/<job_id>`.  
   - Add `install_deps.sh` to run `pip install -r requirements.txt` or `npm install` inside sandbox.
2. **Metadata Wiring**  
   - In `solver_service.launch_sandbox`, call `sandbox.add_metadata` with `session_id`, `chat_id`, `issue_id`, `job_id`, `user_id`.  
   - Store sandbox handle/IDs back on `SolverJob` record.
3. **Parallelism**  
   - Configure orchestrator to request sandbox with concurrency hints (max CPU/memory).  
   - Maintain job concurrency counters in Redis to avoid over-provisioning.

## 5. mini-swe-agent Execution Flow (Day 3 Morning)
1. **Wrapper Script**  
   - Commit `backend/solver_templates/run_solver.py`; script reads env: `ISSUE_JSON`, `REPO_PATH`, `SESSION_METADATA`.  
   - Calls `mini_swe_agent.solve_issue(...)` with plan+execute loops.  
   - Writes outputs to `/workspace/output/{job_id}/diff.patch`, `/workspace/output/{job_id}/plan.json`, `/workspace/output/{job_id}/logs.txt`.
2. **Orchestrator Invocation**  
   - From `solver_service.run_agent`, execute `sandbox.process.run("python run_solver.py")`.  
   - Stream stdout/stderr into backend logger; push incremental updates to chat via `ChatOps.post_system_message`.
3. **Result Collection**  
   - Fetch artifact files via e2b file API; store in S3/object store.  
   - Update `SolverJob` record with artifact URLs and final status.

## 6. Chat & Issue Integration (Day 3 Afternoon)
- Update `ChatOps.py` to add helper `append_solver_status(session_id, job_id, status, summary)` that creates assistant messages when solver hits milestones.  
- In `IssueOps.py`, after job completion, attach resulting diff summary or commit suggestion back to issue context.  
- Modify `src/components/Chat.tsx` to subscribe to solver job events (WebSocket or polling) and render status timeline (Queued → Running → Awaiting Review → Completed/Failed).  
- Extend `src/types.ts` with `SolverJob` interface mirroring backend JSON.

## 7. Observability & Telemetry (Day 4)
- Add structured logs in `solver_service` with JSON payloads containing job metadata.  
- Configure metrics collection (Prometheus or OpenTelemetry) to track job durations, sandbox failures, agent errors.  
- Implement alert hooks for consecutive job failures.

## 8. Testing Strategy (Day 5)
1. **Unit Tests**  
   - `tests/test_solver_service.py`: mock e2b client + mini-swe agent to assert lifecycle transitions.  
   - `tests/test_solver_queue.py`: verify enqueue/dequeue and retry semantics.  
2. **Integration Tests**  
   - Spin a fake sandbox client to ensure orchestrator writes correct metadata and stores artifacts.  
   - End-to-end test hitting `/solve` route with sample issue; assert chat receives status updates.

## 9. Deployment & BYOC Prep (Day 6)
- Document BYOC settings in `docs/solver/byoc.md`: network policies, node sizing, secret injection.  
- Update deployment manifests (Dockerfile, Helm charts) to include new env vars + background worker container.  
- Ensure CI pipeline builds mini-swe wrapper and runs backend tests.

## 10. Rollout Checklist & Future Work (Day 7)
- Create runbook in `docs/solver/runbook.md`.  
- Plan phased rollout: canary on staging sessions, collect metrics, enable for broader user base.  
- Backlog items: intelligent issue triage, auto-commit capabilities, support for additional agents, UI diff viewer.

## Key Files & Touchpoints Summary
- Backend Modules: `backend/daifuUserAgent/solver_service.py`, `solver_queue.py`, `ChatOps.py`, `IssueOps.py`, `session_service.py`, `llm_service.py`.  
- Config & Models: `backend/config/settings.py`, `backend/models.py`, migrations, `.env`.  
- Templates & Scripts: `backend/solver_templates/template.toml`, `prepare_repo.sh`, `install_deps.sh`, `run_solver.py`.  
- Frontend: `src/components/Chat.tsx`, `src/types.ts`, global store/hooks for job status.  
- Docs: `docs/solverArchScaffold.md` (this file), `docs/solver/byoc.md`, `docs/solver/runbook.md`.

> Keep this checklist in version control and update the checkboxes during implementation sprints; treat each section as a discrete deliverable.
