# Daifu + MSWEA 3-Mode Implementation Plan

Last updated: 2026-04-28

Status: canonical plan for the current Daifu, context-probe, and Architect -> Tester -> Coder runtime.

This document replaces the older standalone 3-mode plan and the hybrid Daifu/Architect probe plan. The active direction is the current Modal-backed MSWEA orchestrator plus Daifu session tooling, not a parallel first-class agent framework.

## Summary

YudaiV3 now has three related runtime paths:

1. Daifu chat and issue drafting: conversational repository assistant that asks questions, requests code probes, drafts Architect-ready GitHub issues, and can publish an existing drafted issue.
2. Context probes: lightweight read-only MSWEA probe runs that explore code and feed results back into Daifu.
3. Fixed 3-mode execution: Architect -> Tester -> Coder modes run through `SessionExecutionOrchestrator` in the shared Modal sandbox.

The next implementation focus is not new agent packages or `@task` delegation. It is to harden the current runtime contracts, make the issue-to-execution handoff reliable, and polish frontend recovery/progress UX.

## Current Architecture

```text
Frontend Agent Workbench
  -> Daifu session/chat APIs
  -> Daifu structured response contract
       - questions
       - probes
       - issue actions
       - create_github_issue tool call
  -> Controller WebSocket hub
  -> Modal-backed runtime lifecycle
  -> SandboxExecBroker
  -> mini-swe-agent mode configs
       - probe
       - architect
       - tester
       - coder
```

Important backend surfaces:

| Area | Current surface |
| --- | --- |
| Chat and issue drafting | `backend/yudai/daifuUserAgent/llm_service.py`, `ChatOps.py`, `IssueOps.py` |
| Session routes and workflow confirmation | `backend/yudai/daifuUserAgent/session_routes.py` |
| Daifu tool wrappers | `backend/yudai/daifuUserAgent/mode_tools.py` |
| Probe execution | `backend/yudai/daifuUserAgent/context_probe.py`, `backend/yudai/realtime/mswea_mode_configs/probe/config.yaml` |
| 3-mode orchestration | `backend/yudai/realtime/mode_orchestrator.py` |
| Runtime lifecycle and sandbox exec | `backend/yudai/realtime/lifecycle.py`, `sandbox_transport.py`, `modal_sandbox.py` |
| Frontend runtime state | `src/components/AgentWorkbench.tsx`, `src/hooks/useSessionWebSocket.ts`, `src/stores/sessionStore.ts` |

## Implemented Behavior

### Daifu chat contract

Daifu responses use a structured `<daifu_response>` JSON contract. The model can return:

- `text`: concise user-facing response.
- `questions`: up to 2 clarification questions for the Q&A UI.
- `probes`: up to 3 natural-language code exploration requests.
- `actions`: issue-draft buttons for the frontend.
- `tool_calls`: normally only `create_github_issue` with a known session `issue_id`.

Daifu issue drafts should be Architect-ready. They should include objective, repository evidence, scope and out-of-scope, implementation plan, likely files, acceptance criteria, and tests. Drafts should aim for one focused PR per issue, prefer roughly 150 LOC or smaller changes, and split likely >200 LOC or cross-subsystem work into multiple issues.

### Context probes

Daifu can ask for code exploration without writing shell commands. It emits natural-language probe requests, and `ContextProbeService` runs lightweight MSWEA probe agents inside the sandbox.

Probe behavior:

- Read-only repository exploration.
- Uses `backend/yudai/realtime/mswea_mode_configs/probe/config.yaml`.
- Writes findings under `.yudai/probes/`.
- Returns bounded markdown context for injection into the next Daifu prompt.
- Degrades gracefully when there is no active sandbox or a probe times out.

### GitHub issue publication and execution confirmation

Daifu can publish an existing drafted issue through the current backend issue tool. After GitHub issue creation, the backend asks the user before starting the fixed Architect -> Tester -> Coder workflow.

This keeps the action boundary explicit:

```text
Draft issue
  -> publish GitHub issue
  -> ask user to start workflow
  -> run Architect -> Tester -> Coder
```

### Fixed 3-mode pipeline

`SessionExecutionOrchestrator` runs legal next stages through the existing Modal runtime:

```text
Architect
  -> enrich existing GitHub issue and shared context
Tester
  -> generate or validate tests and handoff metadata
Coder
  -> implement, run tests, and emit PR metadata
```

Stage tools are exposed through `DaifuModeToolService` and preserve the fixed order. The orchestrator emits WebSocket mode/tool events and stores execution state in the existing session metadata and execution rows.

## Active Plan

### 1. Harden 3-mode contracts (`#175`)

The highest-priority backend work is to make each mode's role and handoff explicit.

Implementation targets:

- Architect consumes an existing GitHub issue, inspects the repo, and writes durable shared context.
- Tester stays limited to tests, fixtures, test branch metadata, and test evidence.
- Coder consumes Architect and Tester outputs, implements the change, validates tests, and emits PR metadata.
- Mode results should be structured artifacts where possible, not only stdout parsing.
- The orchestrator should store issue metadata, tester evidence, coder validation, and PR metadata in predictable places.

Acceptance criteria:

- Mode configs document clear boundaries.
- Tests cover structured output parsing and failure handling.
- A real GitHub issue can flow through Architect -> Tester -> Coder -> PR.
- Recoverable mode failures leave useful session state for the frontend.

### 2. Align ChatOps handoff (`#179`)

ChatOps should stay on the current Daifu/session/orchestrator contracts. Do not add `SubagentExecutor`, `@task`, custom `BaseTool`, or duplicate subagent packages in this work.

Implementation targets:

- Preserve existing chat/session API behavior.
- Keep Daifu issue creation and workflow confirmation on current session routes.
- Persist probe results, execution summaries, issue references, and PR references consistently.
- Avoid stale frontend data concepts or retired indexing paths.
- Keep frontend-visible WebSocket progress at least as good as today.

Acceptance criteria:

- Existing chat send and message persistence still work.
- GitHub issue creation remains available through the current issue-creation contract.
- Execution handoff produces mode/tool events visible to the workbench.
- Recoverable errors are stored and surfaced instead of killing the session.

### 3. Polish runtime UX (`#182`)

Frontend work should follow backend event and error contracts rather than inventing independent state.

Implementation targets:

- Clear execution progress and cancellation states.
- Actionable retry/recovery paths for repository, session, chat, and execution failures.
- Unified notification behavior.
- Useful empty states.
- Responsive repository selection.
- Persist only durable layout/workspace preferences.

Acceptance criteria:

- No dead-end error states.
- Execution and question/probe states are understandable on mobile and desktop.
- PR links and final execution outputs remain easy to inspect.

### 4. Defer non-current architecture

The following are intentionally out of scope for the current plan:

- First-class `yudai.agents` framework.
- `SubagentExecutor`.
- `@task` dynamic delegation.
- Custom `BaseTool` and builtin tool stack.
- Sandbox provider abstraction before a real second provider exists.

Current sandbox provider decision: Modal remains explicit and canonical until a concrete second provider requirement exists.

## Execution Flow Details

### Daifu issue drafting

```text
User message
  -> Daifu prompt with repo/session/probe context
  -> structured response
       - questions if scope is ambiguous
       - probes if code context is missing
       - actions for issue drafts
       - create_github_issue only after confirmation
```

Daifu should not publish issues before user confirmation. When the task is too large, Daifu should draft multiple focused issues instead of one oversized issue.

### Probe gathering

```text
Daifu emits probes
  -> ContextProbeService builds probe tasks
  -> SandboxExecBroker runs mini-swe-agent with probe config
  -> probe markdown is captured
  -> probe results are cached in session metadata
  -> next Daifu turn receives CODE_EXPLORATION_CONTEXT
```

Probe output is support context only. It should not mutate source files, tests, issues, or PRs.

### Workflow execution

```text
GitHub issue exists
  -> backend asks user to start workflow
  -> DaifuModeToolService starts legal next stage
  -> SessionExecutionOrchestrator schedules stage or sequence
  -> mode command runs in the shared Modal sandbox
  -> stdout/stderr and mode events stream to frontend
  -> final metadata updates session/lifecycle state
```

Architect should not create a second GitHub issue. Tester should not implement product code. Coder should not ignore Tester handoff evidence.

## Testing Plan

Backend tests should cover:

- Daifu structured response parsing.
- Prompt guidance for Architect-ready issue drafting and split rules.
- Probe command construction and context formatting.
- Create GitHub issue tool behavior and ownership validation.
- Stage tool scheduling and legal mode order.
- Structured parsing of mode results.
- Failure paths that leave useful session state.

Frontend tests should cover:

- WebSocket mode/tool/probe status handling.
- Question prompt behavior.
- Execution progress and cancellation state.
- Recoverable error actions.
- Mobile-safe repository and execution UI.

Manual validation should include:

1. Start a session with a real repository.
2. Ask Daifu to draft a scoped issue.
3. Confirm issue publication.
4. Start the workflow from the confirmation prompt.
5. Verify Architect, Tester, and Coder events stream in order.
6. Verify final issue/PR metadata appears in session context and frontend UI.

## Current Backlog Map

| Issue | Role in this plan |
| --- | --- |
| `#175` | Primary backend runtime hardening for Architect -> Tester -> Coder. |
| `#179` | ChatOps/session handoff onto current Daifu and orchestrator contracts. |
| `#182` | Frontend runtime UX and recovery polish. |
| `#16` | Future PR changelog/review table after PR metadata stabilizes. |

Completed supporting items:

- `#60`: Daifu prompt now treats issue/PR size constraints as issue-drafting guidance.
- `#63`: Minimal script-only PR complexity report exists at `scripts/pr_complexity_report.py`.
- `#167`: Sandbox provider decision recorded; no abstraction now.

## File Summary

| File | Current role |
| --- | --- |
| `backend/yudai/daifuUserAgent/llm_service.py` | Daifu prompt and structured response parsing. |
| `backend/yudai/daifuUserAgent/context_probe.py` | Lightweight code exploration service. |
| `backend/yudai/daifuUserAgent/mode_tools.py` | Daifu-facing wrappers for issue and mode tools. |
| `backend/yudai/daifuUserAgent/session_routes.py` | Session APIs, issue publication, questions, execution handoff. |
| `backend/yudai/realtime/mode_orchestrator.py` | Fixed 3-mode stage orchestration. |
| `backend/yudai/realtime/mswea_mode_configs/*/config.yaml` | Probe, Architect, Tester, and Coder mode instructions. |
| `src/hooks/useSessionWebSocket.ts` | Frontend consumption of runtime events. |
| `src/components/AgentWorkbench.tsx` | Primary active frontend shell. |

## Success Criteria

- Daifu drafts smaller, repo-grounded, Architect-ready issues.
- Probe results make Daifu responses more code-grounded without exposing shell commands.
- GitHub issue publication always has explicit user confirmation.
- Architect -> Tester -> Coder runs in order against one shared runtime.
- Each mode has a clear role boundary and structured handoff.
- The frontend shows progress, questions, recoverable errors, final issue links, and PR links clearly.
