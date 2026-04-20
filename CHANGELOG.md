# Changelog

## [Unreleased] — Execution Pipeline Fixes & Mode Orchestrator Stabilization

### Bug Fixes
- **Fixed 500 on `POST /daifu/sessions/{id}/execution`** — `start_execution` in `mode_orchestrator.py` called `get_execution_status(db, session=session)` after `db.commit()`, which expired all ORM attributes. On reload, SQLAlchemy's plain `PG_JSON` column did not reliably detect the in-memory `mode_metadata` mutation, so `active_execution` was absent from the refreshed session — causing `ExecutionResponse` (which overrides `execution_id: str` and `started_at: datetime` as non-optional) to fail Pydantic validation. Fixed by capturing `execution_id`, `execution_plan`, `execution_started_at`, and `session_public_id` as local variables before `db.commit()`, and returning the status dict directly from those locals instead of calling `get_execution_status`.
- **Fixed cascading 409 on execution retry** — The 500 above caused the frontend to retry the `POST /execution`, which hit `ExecutionConflictError` (the asyncio task was already scheduled before the serialization error). Resolved as a side-effect of the 500 fix: the first call now succeeds and no retry is needed.
- **Identified root of WS reconnect storm** — "WebSocket is closed before the connection is established" in browser was a client-side cascade from the 500/409 errors putting the frontend error state into a reconnect loop. The backend was correctly accepting WS connections throughout. Resolved by fixing the upstream 500.

---

## [Unreleased] — Unified Sandbox Architecture (v2)

### Architecture
- **Collapsed dual sandbox into single unified sandbox** — no more nested Modal solver sandbox (`yudai-solver` app removed). Mini-swe-agent runs as subprocess inside the realtime sandbox.
- **Moved solver endpoints to controller host** — `solve_routes.py` now mounted on `run_controller.py`. Frontend no longer needs tunnel URL for solve operations.
- **Replaced SSE with WebSocket for trajectory streaming** — removed `useTrajectoryStream.ts` (EventSource/SSE). Trajectory updates flow through the controller's unified WS hub.
- **Sandbox reuse across solve runs** — cloned repo persists at `/workspace/repo`. Subsequent solves do `git fetch + reset` instead of fresh clone.

### Backend — Image & Provisioning (`modal_sandbox.py`)
- Unified Modal image: debian-slim 3.11 + server deps + `minisweagent` + `gh` CLI + MSWEA mode configs
- Canonical path constants: `SANDBOX_WORKSPACE_PATH = "/workspace/repo"`, `SANDBOX_MSWEA_CONFIG_ROOT = "/app/mswea_mode_configs"`
- Removed `SANDBOX_SETUP_CONTEXT` env var (dead code)
- GitHub CLI installed via official apt repo at image build time

### Backend — Agent Script (`agentScriptGen.py`)
- `clone_repository()` detects existing `.git` and does `git fetch + checkout -f + reset --hard + clean -fdx` for sandbox reuse
- Extracted `_setup_git_credentials()` for `.netrc` setup
- Trajectory path: `/workspace/trajectory.json` (was `/tmp/yudai/last_mini_run.traj.json`)

### Backend — Solve Manager (`solve_manager.py`)
- Replaced `HeadlessSandboxExecutor` with `SandboxExecBroker` WS dispatch
- Controller resolves context (github_token, issue_text) and sends exec commands to sandbox via internal WS
- All workspace path fallbacks use `SANDBOX_WORKSPACE_PATH` constant
- Trajectory streaming via `TrajectoryStreamAccumulator` → `ws_hub.send_to_session()`

### Backend — Mode Orchestrator (`mode_orchestrator.py`)
- MSWEA config root: `/app/mswea_mode_configs` (baked into image, was `/workspace/configs`)
- Inline bash clone logic updated for sandbox reuse (fetch + reset)
- All workspace path fallbacks use `SANDBOX_WORKSPACE_PATH`

### Backend — Solve Routes (`solve_routes.py`)
- Removed SSE streaming endpoint (`stream_trajectory`)
- Mounted on controller host (`run_controller.py`)

### Backend — Sandbox Server (`run_sandbox_server.py`)
- Removed `solve_router` mount (moved to controller)

### Backend — Other
- `sandbox_exec_broker.py` — controller-side WS exec broker for sandbox command dispatch
- `solve_stream_protocol.py` — stdout marker protocol for trajectory/result streaming (new file)
- `lifecycle.py` — minor cleanup
- `realtime_flags.py` — removed SSE feature flag

### Frontend
- Removed `useTrajectoryStream.ts` — SSE hook no longer needed
- `useSessionWebSocket.ts` — sole transport for trajectory updates
- `TrajectoryViewer.tsx` — removed SSE fallback, uses WS only
- `api.ts` — removed SSE stream endpoint
- `realtimeFlags.ts` — removed SSE flag
- `sessionTypes.ts` — removed SSE-related types

### Docs
- `sandbox-architecture-deep-dive.html` — fully rewritten for v2 architecture with code changes tab
- Removed `session-bound-solver-architecture.html` (superseded)

### Deleted
- `backend/realtime/solve_sandbox.py` — nested Modal solver sandbox executor (891 lines)
- `docs/session-bound-solver-architecture.html` — old architecture doc (610 lines)
- `src/hooks/useTrajectoryStream.ts` — SSE trajectory hook (158 lines)
