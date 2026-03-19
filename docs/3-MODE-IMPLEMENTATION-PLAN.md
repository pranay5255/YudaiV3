# YudaiV3 3-Mode Agent System Implementation Plan

**Date**: 2026-02-27 (Updated: 2026-03-19)
**Status**: Phase 1 Foundation Complete — Mode Orchestration Pending
**Architecture**: Controller + Unified Modal Sandbox + Sessions API + 3-Mode MSWEA Execution

---

## Executive Summary

This document outlines the implementation plan for YudaiV3's new 3-mode agent system that executes:
1. **Architect Mode**: Creates detailed GitHub issues
2. **Tester Mode**: Writes tests for the issue
3. **Coder Mode**: Implements solution, passes tests, creates PR

The system uses the existing MSWEA solver (mini-swe-agent) with different configs for each mode, executed within a persistent unified Modal sandbox.

---

## Architecture Overview

### Implemented State (as of 2026-03-19)

The sandbox is **unified**: one Modal image runs both the sandbox FastAPI server (uvicorn on port 8100) and mini-swe-agent solver runs as **subprocesses** via an internal WebSocket exec protocol.

```
User (Frontend)
    ↓ (Natural Language + Repo Selection)
Controller (FastAPI — run_controller.py)
    ├── /daifu/*       (session CRUD, chat, issues — session_routes.py)
    ├── /daifu/*       (solve start/status/cancel — solve_routes.py)
    ├── /controller/*  (sandbox lifecycle, runtime — controller_routes.py)
    └── /controller/sessions/{id}/ws/unified  (WS hub for frontend)

    ↓ (Provisions Modal Sandbox at solve start or explicit POST /runtime)
Modal Sandbox (unified image — port 8100 via encrypted tunnel)
    ├── uvicorn run_sandbox_server:app  (main process)
    │     ├── /healthz
    │     └── /internal/sessions/{id}/ws/exec  (internal WS for exec broker)
    └── mini-swe-agent subprocess (spawned per solve via exec broker)

Controller → SandboxExecBroker → sandbox_transport.run_sandbox_command()
          → wss://{tunnel}/internal/sessions/{id}/ws/exec
          → Subprocess stdout/stderr streamed back as WS events
          → Accumulated by TrajectoryStreamAccumulator → broadcast to frontend
```

### Unified Sandbox Image Layers (`_get_unified_sandbox_image()`)

```
1. debian-slim python:3.11
2. apt: git, curl, gh (GitHub CLI), libpq-dev, gcc, gnupg
3. pip: fastapi, uvicorn, httpx, sqlalchemy, pydantic, websockets, python-jose, psycopg2-binary, ...
4. pip: mini-swe-agent
5. copy /app/backend/ (backend source)
6. copy /app/mswea_mode_configs/ (architect/tester/coder yaml configs)
7. mkdir /workspace (empty, cloned at runtime)
```

### Key Files Implemented

| File | Purpose |
|---|---|
| `backend/run_controller.py` | Controller entrypoint (FastAPI) |
| `backend/realtime/lifecycle.py` | `RealtimeLifecycleService` — create/terminate runtime, completion detector |
| `backend/realtime/modal_sandbox.py` | `RealtimeModalSandbox` — unified image + Modal.Sandbox.create() |
| `backend/realtime/sandbox_manager.py` | Liveness probes (10s), git bootstrap (clone+fetch) |
| `backend/realtime/controller_routes.py` | Controller HTTP + WS endpoints |
| `backend/realtime/sandbox_exec_broker.py` | Routes solve commands to sandbox internal WS |
| `backend/realtime/sandbox_transport.py` | Shared WS transport layer for exec protocol |
| `backend/realtime/solve_manager.py` | Orchestrates solve sessions, trajectory streaming, PR creation |
| `backend/realtime/sandbox_artifacts.py` | Downloads artifact tarballs from sandbox |
| `backend/realtime/modal_preflight.py` | Deploy-time preflight (healthcheck + minisweagent smoke test) |
| `src/utils/realtimeRouting.ts` | Frontend URL builders for controller WS |
| `src/hooks/useSessionWebSocket.ts` | WS hook (10 reconnect attempts, heartbeat) |

---

## Session Flow

### Current Flow (Phase 1 — Implemented)

1. **User** authenticates with GitHub (existing).
2. **Frontend** selects repo/branch.
3. **Frontend → Controller**: `POST /daifu/sessions` creates `ChatSession` in DB.
4. **Frontend → Controller**: `POST /controller/sessions/{id}/runtime` provisions sandbox:
   - Creates `Sandbox` + `SessionRuntime` DB records.
   - If `modal_provisioning_enabled`: calls `RealtimeModalSandbox.create()` → Modal tunnel URL returned.
   - Runs `SandboxManager.ensure_git_bootstrap()` (clone repo at identity cache path).
   - Starts liveness probe loop.
   - Records `sandbox_start` audit event.
5. **Controller → Frontend**: Returns `RuntimeResponse` with `tunnel_url`.
6. **Frontend** connects to controller WS at `/controller/sessions/{id}/ws/unified?token={jwt}`.
7. **User → Frontend** sends first message.
8. **Frontend → Controller WS**: `CHAT_MESSAGE` type — handled by `ChatOps.process_chat_message()`.
9. **Frontend → Controller**: `POST /daifu/{session_id}/solve/start` with issue ID.
10. **Controller → Sandbox**: `SandboxExecBroker.run_command()` writes agent script to sandbox, runs via exec WS.
11. **Sandbox subprocess** streams stdout → controller accumulates trajectory → broadcasts `TRAJECTORY_UPDATE` to frontend WS.
12. **On PR creation**: `lifecycle.mark_pr_created()` → completion detector fires → artifact export → sandbox terminate.

### Target Flow (Phases 2-3 — Planned: 3-Mode Pipeline)

> **Not yet implemented.** The mode orchestrator, architect/tester/coder transitions, and MCQ question system are planned below.

```
User sends natural language message
    ↓
Controller triggers ModeOrchestrator.run_full_pipeline(user_prompt)
    ↓
[Architect Mode]
    → exec: python -m minisweagent.solve --config /app/mswea_mode_configs/architect.yaml ...
    → Creates GitHub issue, returns issue_url + issue_number
    → WS: { type: "architect_complete", issue_url, issue_number }
    ↓ auto-triggers
[Tester Mode]
    → exec: python -m minisweagent.solve --config /app/mswea_mode_configs/tester.yaml --issue-number 123
    → Writes tests, commits to branch yudai/issue-123-tests
    → WS: { type: "tester_complete", tests_created, test_branch }
    ↓ auto-triggers
[Coder Mode]
    → exec: python -m minisweagent.solve --config /app/mswea_mode_configs/coder.yaml --issue-number 123 ...
    → Implements solution, runs tests, creates PR
    → WS: { type: "coder_complete", pr_url, pr_number, tests_passed }
    ↓
Session completion → artifact export → sandbox terminate
    → WS: { type: "session_complete", issue_url, pr_url }
```

---

## Implementation Tasks

### ✅ Backend Tasks — Phase 1 (Complete)

#### Database Schema

**Implemented in `backend/models.py`**:
- `Sandbox` table — identity_key, status, tunnel_url, last_heartbeat_at, active_session_id
- `SessionRuntime` table — session_id, sandbox_id, tunnel_url, completion flags
- `SessionArtifact` table — artifact_key, checksum_sha256, bundle_path, exported_at
- `SessionAuditEvent` table — event_name, session_id, sandbox_id, runtime_id, payload

#### Controller Sandbox Provisioning

**Implemented in `backend/realtime/lifecycle.py`**:
```python
async def create_runtime_for_session(db, *, session, user_id, org, repo_owner,
    repo_name, environment, repo_branch, repo_url, github_token, env_inputs) -> RuntimeEnvelope:
    # Builds sandbox identity (org/repo/environment)
    # Re-uses existing non-terminated sandbox or creates new
    # Enforces single active editor
    # If modal_provisioning_enabled: calls RealtimeModalSandbox.create()
    # Starts git bootstrap + liveness probe
    # Records sandbox_start audit event + cache event
```

#### Unified Modal Sandbox

**Implemented in `backend/realtime/modal_sandbox.py`**:
```python
@classmethod
async def create(cls, sandbox_db_id, controller_base_url, github_token=None,
    session_public_id=None, repo_url=None, repo_branch=None, ...) -> RealtimeModalSandbox:
    # Builds env dict (SANDBOX_ID, CONTROLLER_BASE_URL, GITHUB_TOKEN, REPO_URL, ...)
    # modal.Sandbox.create("python", "-m", "uvicorn", "run_sandbox_server:app",
    #                       "--host", "0.0.0.0", "--port", "8100",
    #                       encrypted_ports=[8100])
    # Returns tunnel URL from sandbox.tunnels()[8100].url
```

#### Exec Broker + Transport

**Implemented in `backend/realtime/sandbox_exec_broker.py` + `sandbox_transport.py`**:
```python
# Controller side:
await broker.run_command(db, session=session, command=script, env=env, on_event=cb)
    → resolves tunnel_url from runtime
    → calls run_sandbox_command(tunnel_url, session_public_id, command, ...)

# Transport (sandbox_transport.py):
# Connects to wss://{tunnel}/internal/sessions/{id}/ws/exec
# Sends: { type: "exec.start", payload: { command, cwd, env } }
# Receives: sandbox_stream events (stdout/stderr/exit)
# On cancel: sends exec.cancel
```

#### Solve Manager

**Implemented in `backend/realtime/solve_manager.py`**:
- `DefaultSolverManager.start_solve()` — creates Solve/SolveRun in DB, calls `lifecycle.create_runtime_for_session()`, launches background task
- `_execute_run()` — builds agent script via `AgentScriptParams`, runs via exec broker, accumulates trajectory with `TrajectoryStreamAccumulator`, broadcasts `TRAJECTORY_UPDATE` to WS hub
- After successful run: creates PR via `build_pr_script()`, calls `lifecycle.mark_pr_created()`

#### Completion + Artifact Export

**Implemented in `backend/realtime/lifecycle.py`**:
```python
def _finalize_on_completion(db, runtime, session, sandbox):
    # Triggered when both completion_issue_created AND completion_pr_created = True
    # Collects trajectory refs from SolveRun.trajectory_data
    # Calls cache_store.export_bundle() → writes bundle tar.gz + manifest
    # Persists SessionArtifact row
    # Terminates sandbox in DB + triggers Modal terminate
```

### ⬜ Backend Tasks — Phase 1+ / Mode Orchestrator (Pending)

#### Mode Orchestrator

**File to create**: `backend/solver/mode_orchestrator.py`

The 3-mode pipeline requires:
```python
class ModeOrchestrator:
    async def execute_architect_mode(self, user_prompt: str) -> dict:
        # exec: python -m minisweagent.solve
        #   --config /app/mswea_mode_configs/architect.yaml
        #   --prompt user_prompt
        # Parse result: { issue_url, issue_number }
        # Update DB: session.current_mode = "architect", architect_issue_url

    async def execute_tester_mode(self, issue_number: int) -> dict:
        # exec: python -m minisweagent.solve
        #   --config /app/mswea_mode_configs/tester.yaml
        #   --issue-number 123
        # Update DB: tester_status = "complete"

    async def execute_coder_mode(self, issue_number: int, test_branch: str) -> dict:
        # exec: python -m minisweagent.solve
        #   --config /app/mswea_mode_configs/coder.yaml
        #   --issue-number 123 --test-branch yudai/issue-123-tests
        # Update DB: coder_pr_url, current_mode = "complete"
        # Trigger sandbox termination

    async def run_full_pipeline(self, user_prompt: str):
        architect_result = await self.execute_architect_mode(user_prompt)
        tester_result = await self.execute_tester_mode(architect_result["issue_number"])
        await self.execute_coder_mode(architect_result["issue_number"], tester_result["test_branch"])
```

Note: Each mode calls `broker.run_command()` via `SandboxExecBroker` — same exec infrastructure as the current single-mode solver.

#### Database Schema Additions for 3-Mode

**Add to `ChatSession` table** (not yet added):
```python
current_mode = Column(String, default="pending")  # pending, architect, tester, coder, complete
architect_issue_url = Column(String, nullable=True)
architect_completed_at = Column(DateTime(timezone=True), nullable=True)
tester_status = Column(String, nullable=True)
tester_completed_at = Column(DateTime(timezone=True), nullable=True)
coder_pr_url = Column(String, nullable=True)
coder_completed_at = Column(DateTime(timezone=True), nullable=True)
```

**New `AgentExecution` table** (not yet created):
```python
class AgentExecution(Base):
    __tablename__ = "agent_executions"
    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("chat_sessions.id"), nullable=False)
    mode = Column(String, nullable=False)  # architect, tester, coder
    status = Column(String, default="running")  # running, complete, failed
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    output_summary = Column(JSON, nullable=True)
    error_message = Column(String, nullable=True)
```

#### Message Handler Trigger

**Modify `POST /daifu/sessions/{id}/messages`** to trigger 3-mode pipeline:
```python
if message_count == 1 and session.current_mode == "pending":
    orchestrator = ModeOrchestrator(session_id)
    asyncio.create_task(orchestrator.run_full_pipeline(request.content))
```

#### MSWEA Mode Configs

Mode configs live at `/app/mswea_mode_configs/` inside the sandbox image, copied from `backend/realtime/mswea_mode_configs/` at image build time.

**`architect.yaml`** — analyze user request, research codebase, create GitHub issue with acceptance criteria
**`tester.yaml`** — read issue, write comprehensive unit + integration tests, commit to `yudai/issue-{n}-tests`
**`coder.yaml`** — read issue, merge test branch, implement, run tests until passing, create PR

### ⬜ Frontend Tasks — Mode UI (Pending)

#### TrajectoryViewer Phase Indicators

**File**: `src/components/TrajectoryViewer.tsx`

Add 3-phase progress indicator responding to WS message types:
- `architect_progress` / `architect_complete`
- `tester_progress` / `tester_complete`
- `coder_progress` / `coder_complete`
- `session_complete` → show issue URL + PR URL

#### MCQ/Question UI

**File**: `src/components/UserQuestionPrompt.tsx` (new)

```tsx
interface UserQuestionProps {
  question: string;
  options: Array<{label: string; value: string}>;
  multiSelect: boolean;
  onAnswer: (answer: string | string[]) => void;
}
```
Receives `user_question` WS events, renders radio/checkbox form, posts answer to `/daifu/sessions/{id}/questions/{qid}/answer`.

---

## Configuration Files

### Backend Environment Variables

```env
# Existing vars...

# 3-Mode System
MSWEA_ARCHITECT_MAX_ITERATIONS=10
MSWEA_TESTER_MAX_ITERATIONS=15
MSWEA_CODER_MAX_ITERATIONS=30
MODAL_SANDBOX_TIMEOUT=7200

# Sandbox exec
CONTROLLER_INTERNAL_WS_SECRET=<secret>
CONTROLLER_HEARTBEAT_SECRET=<secret>
SANDBOX_LIVENESS_INTERVAL_SECONDS=10
SANDBOX_GIT_FETCH_INTERVAL_SECONDS=300

# Preflight
MODAL_SANDBOX_PREFLIGHT_ENABLED=true
MODAL_SANDBOX_PREFLIGHT_SANDBOX_TIMEOUT_SECONDS=900
```

---

## Rollout Plan

### Phase 1: Foundation — ✅ COMPLETE (2026-03-19)
- [x] Unified sandbox image (server + solver in one image)
- [x] Modal sandbox provisioning with tunnel URL
- [x] Sandbox exec broker + internal WS transport
- [x] Solve manager running agent as subprocess via exec broker
- [x] Trajectory streaming to frontend WS
- [x] Completion detector (issue + PR) → artifact export → terminate
- [x] Liveness probes + git bootstrap
- [x] Controller HTTP lifecycle endpoints
- [x] Deploy-time preflight checks

### Phase 2: Architect Mode — ⬜ NEXT
- [ ] MSWEA mode config files (architect/tester/coder yamls) in sandbox image
- [ ] `ChatSession` schema additions (current_mode, architect_issue_url, etc.)
- [ ] `AgentExecution` table
- [ ] `ModeOrchestrator` with architect mode execution
- [ ] Issue creation integration + mark_issue_created() call
- [ ] WS message types: architect_progress, architect_complete
- [ ] Frontend phase indicator (first phase only)

### Phase 3: Tester & Coder Modes — ⬜
- [ ] Tester mode execution
- [ ] Test creation and branch management
- [ ] Coder mode execution
- [ ] Full pipeline orchestration: Architect → Tester → Coder
- [ ] Frontend: all 3 phase indicators + final session_complete state

### Phase 4: Conversational System — ⬜
- [ ] Ask question API endpoint
- [ ] Answer question API endpoint
- [ ] `UserQuestion` model + DB table
- [ ] Frontend MCQ UI (`UserQuestionPrompt.tsx`)
- [ ] Resume execution after answer

### Phase 5: Testing & Polish — ⬜
- [ ] Unit tests for ModeOrchestrator
- [ ] Integration tests for Architect → Tester → Coder pipeline
- [ ] E2E tests with real Modal sandbox
- [ ] Error handling for mode failures (retry, skip, escalate)
- [ ] UI polish

---

## Open Questions

1. **MSWEA mode configs**: What CLI flags does mini-swe-agent accept for `--issue-number`, `--test-branch`, `--config`? Confirm interface before implementing ModeOrchestrator.
2. **GitHub Token Security**: Token stored in `GITHUB_TOKEN` sandbox env var — confirm encryption approach for DB storage if needed.
3. **Error Handling**: If Architect mode fails, can user retry? Can they skip Tester and go straight to Coder?
4. **Mode Config Format**: Confirm whether MSWEA mode configs are YAML or JSON and what fields mini-swe-agent actually reads.
5. **Workspace Reuse**: Coder mode needs to merge the test branch from Tester mode — does `/workspace/repo` persist between mode executions in the same sandbox?

---

## Success Criteria

- [x] User can create session with repo URL
- [x] Sandbox is provisioned with repo cloned
- [x] Solve runs agent and streams output to frontend
- [x] Session completes (PR created) and sandbox terminates
- [x] Database tracks execution stages
- [ ] User sends natural language request → Architect mode creates GitHub issue
- [ ] Tester mode creates tests in branch
- [ ] Coder mode implements solution and creates PR
- [ ] Frontend shows 3 phases with progress
- [ ] All modes stream output to frontend

---

## Notes

- Exec infrastructure is **complete** — `SandboxExecBroker` + `sandbox_transport.py` provide the plumbing. Mode orchestration just needs to call `broker.run_command()` with the right script per mode.
- Modal tunnel URL is returned at provisioning; frontend does not need direct sandbox access for exec — controller proxies all commands.
- WS hub (`ws_hub.py`) handles broadcasting to all connected frontend clients for a session — `ModeOrchestrator.send_ws_progress()` just needs to call `ws_hub.send_to_session()`.
- Consider adding pause/resume functionality for debugging mode transitions.
- Consider mode-specific log/artifact export per phase (architect issue JSON, tester coverage report, coder diff).
