# Architecture Drift RCA

Date: 2026-04-20

Scope: root `docs/`, current backend/frontend implementation, and open issues listed in `docs/GITHUB_ISSUE_TRIAGE.md`.

## Verification Summary

### Modal Sandbox Execution

Two Modal checks have now passed with `uv run modal`:

1. `scripts/modal_mode_command_probe.py`
   - Provisions a real Modal sandbox.
   - Waits for `/healthz`.
   - Runs the internal exec smoke test.
   - Builds Architect, Tester, and Coder mode commands through `SessionExecutionOrchestrator._build_mswea_command()`.
   - Verifies each mode uses `mini -c /app/mswea_mode_configs/{mode}/config.yaml -y -m <model> -t <task>`.

2. `scripts/modal_workflow_standalone.py`
   - Provisions a real Modal sandbox.
   - Runs three sequential commands through `/internal/sessions/{id}/ws/exec`.
   - Downloads an artifact bundle from the sandbox.
   - Terminates the Modal sandbox.
   - Verified artifact members:
     - `mode-workflow/workflow-output/architect.txt`
     - `mode-workflow/workflow-output/architect-summary.txt`
     - `mode-workflow/workflow-output/tester.txt`
     - `mode-workflow/workflow-output/tests/test_mock_workflow.py`
     - `mode-workflow/workflow-output/coder.txt`
     - `mode-workflow/workflow-output/workflow-summary.json`

What this proves:

- Modal provisioning works.
- The sandbox FastAPI server starts and exposes `/healthz`.
- The controller-to-sandbox exec WebSocket transport works.
- Multiple commands can run sequentially in one sandbox.
- Artifact download/export from sandbox to controller-local storage works.
- Sandbox termination works.

What this does not prove yet:

- A real `mini-swe-agent` Architect run creates a GitHub issue.
- A real Tester run creates and pushes a test branch.
- A real Coder run creates a PR.
- The authenticated browser flow automatically moves from Daifu issue creation to the 3-mode orchestrator.
- DB state and UI state are correct through a real Architect -> Tester -> Coder production run.

## Actual Implementation Today

### User-Issue Creation Path

`POST /daifu/sessions/{session_id}/issues/create-with-context` creates a local `UserIssue` preview only.

The backend explicitly passes `create_github_issue=False` to `IssueOps.create_issue_with_context()`. This means it does not create the upstream GitHub issue and does not trigger mode orchestration.

`POST /daifu/sessions/{session_id}/issues/{issue_id}/create-github-issue` creates the upstream GitHub issue and marks `completion_issue_created` in lifecycle state, but it still does not start the 3-mode orchestrator.

### Execution Path

`POST /daifu/sessions/{session_id}/execution` is the only path that starts `SessionExecutionOrchestrator.start_execution()`.

The orchestrator does run remaining modes sequentially:

1. Architect
2. Tester
3. Coder

It provisions/reuses runtime, runs each mode through `SandboxExecBroker`, writes per-mode summaries, updates `ChatSession` mode fields, and finalizes artifacts at the end.

### Frontend Path

`SolveIssues` starts execution for an existing GitHub issue using the real GitHub issue number.

`Chat` has a preview modal flow:

1. Generate local issue preview.
2. Optionally create upstream GitHub issue.
3. Optionally start execution.

The `Chat` solve button currently passes `issuePreview.userIssue.issue_id` into objective text as `Resolve GitHub issue #${issueId}`. That value is the local `UserIssue.issue_id`, not necessarily the upstream GitHub issue number. This can mislead the Architect/Coder pipeline.

## Root Cause

The repo contains two partially overlapping execution models:

1. Older issue/solve model:
   - Local `UserIssue` preview.
   - Optional GitHub issue creation.
   - Old `Solve` / `SolveRun` / trajectory artifact concepts.

2. New 3-mode model:
   - `SessionExecutionOrchestrator`.
   - `AgentExecution`.
   - Mode configs copied into the Modal image.
   - Architect -> Tester -> Coder pipeline through sandbox exec.

The docs were updated in slices, not as one canonical contract. Some docs still describe direct tunnel/SSE or old solve-manager behavior; others describe the newer controller WebSocket and unified sandbox model. The implementation is also transitional: the 3-mode orchestrator exists, but the product trigger semantics and mode config contracts are not finished.

## Drift Findings

### 1. Issue Creation Does Not Trigger The 3-Mode Orchestrator

Spec expectation:

- User/Daifu creates a GitHub issue.
- That issue then flows through Architect -> Tester -> Coder.

Actual:

- Local preview issue creation does not create a GitHub issue.
- Confirmed GitHub issue creation marks lifecycle issue-created, but does not start execution.
- Execution starts only through `/daifu/sessions/{session_id}/execution`.

Impact:

- The desired "Daifu creates issue, then the orchestrator takes over" workflow is not implemented.
- Users can create issues without any mode execution.
- The lifecycle can mark issue-created before the orchestrator runs Architect, causing duplicate or contradictory issue semantics.

Issue mapping:

- Existing: `#173`, `#174`, `#175`, `#179`
- New issue recommended: "Auto-start or explicitly hand off 3-mode execution after GitHub issue creation".

### 2. Architect Mode Semantics Are Ambiguous

Spec says Architect creates the GitHub issue.

Frontend issue-preview flow already lets the user create a GitHub issue before execution.

This creates an unresolved product/architecture choice:

- Option A: User creates a GitHub issue first, then pipeline should skip Architect and start Tester.
- Option B: User only creates a local preview, then Architect creates the real GitHub issue.
- Option C: Architect reviews/enriches an existing GitHub issue instead of creating a new one.

Actual implementation mixes A and B.

Issue mapping:

- Existing: `#173`, `#175`
- New issue recommended: "Define Architect mode input contract: create issue vs consume existing issue".

### 3. Live Mode Configs Are Not Real Role-Specific Configs Yet

Live configs used by Modal:

- `backend/realtime/mswea_mode_configs/architect/config.yaml`
- `backend/realtime/mswea_mode_configs/tester/config.yaml`
- `backend/realtime/mswea_mode_configs/coder/config.yaml`

These are still close to generic mini-swe-agent templates. Tester says to create a reproduction script, edit source, and resolve the issue. That violates the intended Tester role, where it should only write tests and should not implement. Coder also uses the generic "solve this issue" workflow, not a TDD handoff contract.

Unused richer configs exist:

- `backend/configs/tester.yaml`
- `backend/configs/coder.yaml`

Those are not copied into the Modal image and are not referenced by `MSWEA_CONFIG_PATHS`.

Impact:

- Real mode execution is likely to behave incorrectly even though command transport works.
- Tester may modify source code.
- Coder may not consume Tester output as a hard contract.

Issue mapping:

- Existing: `#173`, `#174`, `#175`
- New issue recommended: "Replace live Modal mode configs with strict Architect/Tester/Coder contracts and delete unused config copies".

### 4. MSWEA Output Parsing Is Too Fragile

The orchestrator parses issue/PR metadata by regexing stdout/stderr and by scanning for arbitrary JSON lines with keys such as `issue_url`, `issue_number`, `pr_url`, `pr_number`, and `test_branch`.

There is no enforced sentinel, artifact contract, or schema validation.

Impact:

- A successful `mini` run can still fail orchestration if it does not print the expected shape.
- A random log line can be misparsed.
- Mode summaries are not a reliable machine contract.

Issue mapping:

- Existing: `#162`
- New issue recommended: "Define structured MSWEA mode result contract and validate mode summaries".

### 5. Docs Still Mention The Wrong Mini CLI Contract

`docs/3-MODE-IMPLEMENTATION-PLAN.md` still contains examples like:

- `python -m minisweagent.solve --config ...`
- `--issue-number`
- `--test-branch`

Actual implementation uses:

- `mini -c <config> -y -m <model> -t <task>`

Impact:

- The docs describe a CLI that is not what the code executes.
- Future agents will implement against stale flags.

Issue mapping:

- Existing: `#173` through `#175`
- New issue recommended: "Canonicalize mini-swe-agent CLI docs and tests".

### 6. Completion Detector Docs Overstate Automatic Termination

Docs say completion detection triggers when both issue and PR are created, then exports artifacts and terminates immediately.

Actual:

- `mark_issue_created()` sets `completion_issue_created`.
- `mark_pr_created()` sets `completion_pr_created`.
- `_finalize_on_completion()` only sets metadata and is not called by either method.
- Artifact export and termination happen through `finalize_session_execution()`, currently called by `SessionExecutionOrchestrator` at the end of the pipeline.

Impact:

- The issue+PR flags alone do not guarantee automatic export/termination.
- Non-orchestrator flows can drift from documented lifecycle behavior.
- `_finalize_on_completion()` is effectively dead code in its current form.

Issue mapping:

- Existing: `#166`, `#175`
- New issue recommended: "Make lifecycle completion finalization single-source and remove dead `_finalize_on_completion`".

### 7. Streaming Architecture Docs Conflict

`REAL_TIME_IMPLEMENTATION_QUESTIONNAIRE.md` and `REAL_TIME_PHASE_TASK_LIST.md` describe an SSE trajectory + WS chat split and direct frontend tunnel access.

`sandbox-architecture-deep-dive.html` describes the newer architecture: controller unified WebSocket replaces SSE and direct frontend tunnel resolution.

Actual:

- Frontend uses `/controller/sessions/{id}/ws/unified`.
- Chat streaming now uses the same unified WebSocket.
- Trajectory and sandbox events also use the controller WebSocket.

Impact:

- There is no single canonical real-time spec.
- Future work could accidentally reintroduce SSE/direct tunnel complexity.

Issue mapping:

- Existing: `#182`
- New issue recommended: "Canonicalize real-time streaming docs around unified controller WebSocket".

### 8. Sandbox Identity Policy Has Drifted

Docs say sandbox identity is `org + repo + environment`.

Recent implementation scopes identity by user to avoid cross-user reuse:

- `org={org or default_org}-user-{user_id}`

Impact:

- This fixes immediate cross-user collision risk.
- It contradicts the shared-sandbox/invited-user direction in the questionnaire.
- Future collaboration features need an explicit policy.

Issue mapping:

- Existing: `#143`, `#167`, `#166`
- New issue recommended: "Define sandbox identity policy for MVP single-user vs future shared sessions".

### 9. Sandbox Provider Abstractions Are Still Missing

The current code still directly uses `RealtimeModalSandbox`, `SandboxExecBroker`, `sandbox_transport`, and lifecycle internals.

Open issues `#167`, `#166`, `#168`, and `#169` are still valid. They should now be treated as the next foundation for formalizing Modal/local providers, as the user requested.

Recommendation:

- Keep these issues, but coalesce their acceptance criteria into a single provider-contract epic.
- Do not start `#168` before the base ABC in `#167` is merged.

### 10. Frontend Execution UX Is Split Between Chat And SolveIssues

`SolveIssues` starts execution from an existing GitHub issue and uses the real issue number.

`Chat` starts execution from a preview modal and uses the local `UserIssue.issue_id` in objective text.

Impact:

- Two start paths can produce different objective contracts.
- Chat-initiated execution can hand the agent a fake GitHub issue number.
- The UI does not clearly represent which mode is active or whether the issue is local preview vs upstream GitHub issue.

Issue mapping:

- Existing: `#182`, `#185`
- New issue recommended: "Unify Chat issue modal and Execution tab start contract".

## Dead Code And Cleanup Targets

Ruthless cleanup candidates, with 2026-04-20 status:

1. `backend/realtime/sandbox_artifacts.py`
   - Three-line backward-compat shim to `cache_store.py`.
   - Status: deleted; tests now use canonical `cache_store.py`.

2. `backend/realtime/sandbox_exec_broker.py`
   - Three-line backward-compat shim to `lifecycle.py`.
   - Status: deleted; callers use canonical `lifecycle.py`.

3. `backend/realtime/sandbox_manager.py`
   - Three-line backward-compat shim to `lifecycle.py`.
   - Status: deleted; future provider work should add a real module intentionally if needed.

4. `backend/realtime/ws_hub.py`
   - Three-line backward-compat shim to `ws_protocol.py`.
   - Status: deleted; imports now use `ws_protocol.py`.

5. `backend/realtime/solve_stream_protocol.py`
   - Backward-compat shim for constants now in `agentScriptGen.py`.
   - Status: deleted; old solve stream constants stay in `agentScriptGen.py`.

6. `backend/realtime/mode_orchestrator.py::run_mode_pipeline_background`
   - No runtime caller found.
   - Delete or wire intentionally.

7. `backend/realtime/lifecycle.py::_finalize_on_completion`
   - Not called.
   - Delete or make it the actual finalization path.

8. `backend/configs/tester.yaml` and `backend/configs/coder.yaml`
   - Richer than live configs but unused.
   - Status: deleted after their useful constraints were moved into live mode configs.

9. `src/data/last_mini_run.traj.json`
   - Static old trajectory sample imported by `TrajectoryViewer`.
   - Status: deleted from production UI.

10. `backend/context/yudai-grep/build/lib/*`
    - Generated build output appears tracked.
    - Delete from source control unless it is intentionally vendored.

11. `backend/MSWEA_PLANNING_CONTEXT.txt`
   - Stale planning context that references old paths and old solve flow.
   - Status: deleted; this RCA is the replacement.

12. `backend/daifuUserAgent/githubAPIFULL.md`
   - Generated GitHub API dump, not architecture source.
   - Status: deleted.

13. `src/node_modules/`
    - Not tracked, but present locally and being hit by broad scans.
    - Remove locally and tighten Tailwind content globs.

## Open Issue Triage Correlation

Current open issues fetched by `gh api` match `docs/GITHUB_ISSUE_TRIAGE.md`.

### Should Close Or Reclassify

- `#138`: likely fixed by current Modal image, because `pgvector` is now installed in `SANDBOX_SERVER_PIP_PACKAGES` and Modal preflight verifies import/runtime smoke. Keep open only until a CI/prod Modal preflight confirms after merge.
- `#182`: partially completed for chat token streaming. Keep open, but narrow it to remaining loading feedback, mode progress, and trajectory UI.

### Keep As-Is

- `#60`, `#63`, `#16`: still separate GitHub automation work.
- `#139` and `#135`: still architecture decisions; do not mix with 3-mode orchestration.
- `#180`, `#181`, `#183`, `#184`, `#185`, `#186`: frontend UX batch remains valid.
- `#143`: still valid, but blocked on shared-sandbox identity policy.

### Coalesce Into A Sandbox Provider Epic

- `#167`: Sandbox ABC and SandboxProvider ABC
- `#166`: Wire provider into lifecycle/broker/transport
- `#168`: Modal provider implementation
- `#169`: Local provider implementation
- `#170`: SandboxMiddleware

These should become one staged epic with strict acceptance tests.

### Reframe The Agent Framework Epic Around Current Reality

- `#173`, `#174`, `#175` should not create a separate duplicate subagent system if the immediate runtime is mini-swe-agent mode configs.
- Reframe them as:
  - Architect mode contract and config
  - Tester mode contract and config
  - Coder mode contract and config
  - Structured mode result artifacts
  - End-to-end orchestrator tests

`#171`, `#172`, `#176`, `#177`, `#178`, and `#179` are still useful for the later first-class Yudai agent framework, but they should not block the immediate MSWEA 3-mode pipeline.

### New Issues Recommended

1. Auto-start or explicitly hand off 3-mode execution after GitHub issue creation.
2. Define Architect mode input semantics: create issue vs consume existing issue.
3. Replace live Modal mode configs with strict Architect/Tester/Coder contracts.
4. Define and validate structured MSWEA result artifacts.
5. Make lifecycle completion/export/termination single-source and remove dead `_finalize_on_completion`.
6. Canonicalize real-time docs around unified controller WebSocket.
7. Define sandbox identity policy for single-user MVP and future shared sessions.
8. Unify Chat issue modal and Execution tab start contracts.
9. Dead-code cleanup for compatibility shims, stale configs, generated docs, and static trajectory data.
10. Add authenticated E2E that uses a fake/probe `mini` in Modal and verifies DB state across Architect -> Tester -> Coder.

## Recommended Next Build Order

1. Trigger semantics:
   - Status: decided for MVP. GitHub issue creation seeds `architect_issue_number/url` and auto-starts the fixed pipeline when the mode orchestrator flag is enabled.
   - Architect enriches the existing GitHub issue context; it does not create the issue.

2. Fix frontend/backend start contract:
   - Status: partially fixed. Chat issue creation now receives execution metadata and switches to Trajectory when auto-start succeeds.
   - Remaining: factor Chat modal and Execution tab onto one shared frontend start helper.

3. Replace live mode configs:
   - Status: fixed for current runtime. Live Architect/Tester/Coder configs now enforce the mode contracts and shared `.yudai/context.md`.

4. Add structured output contract:
   - Each mode writes `.yudai/executions/{pipeline}/{mode}/result.json`.
   - Orchestrator validates JSON schema instead of regexing logs.

5. Add fake-mini E2E:
   - Run the full `/execution` API against Modal with `YUDAI_MSWEA_COMMAND_PROBE` or a fake `mini`.
   - Verify DB fields: `architect_issue_number`, `tester_completed_at`, `coder_pr_number`, `workflow_completed_at`, `SessionArtifact`.

6. Then formalize provider base classes:
   - `Sandbox`
   - `SandboxProvider`
   - `ModalSandboxProvider`
   - `LocalSandboxProvider`

7. Clean dead code once tests protect the new path.
