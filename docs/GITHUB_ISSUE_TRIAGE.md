# GitHub Issue Triage

Generated from open issues in `pranay5255/YudaiV3` using the GitHub connector.

Scope: open GitHub issues only, excluding pull requests.

Last updated: 2026-05-11 while implementing #192.

## Summary

#192 is the active AI SDK integration umbrella. It supersedes the prior
runtime/chat/frontend dependency chain and moves the active Agent Workbench chat
path to Vercel AI SDK `streamText`, typed Zod output, and native tool schemas.

The previous high-priority trackers are closed as completed:

- #175: MSWEA Architect -> Tester -> Coder pipeline contracts.
- #179: ChatOps session orchestration alignment.
- #182: Agent Workbench runtime UX and recovery flows.
- #191: workflow state and execution objective regressions.

PR #188 remains the shipped backend foundation for Daifu tool calls and stage
wrappers. #192 now builds on that foundation through the existing Vercel route
shape under `src/api/ai/...`; do not create a parallel root `middleware/` tree.

## Active Backlog

| Issue | Title | Area | Priority | Notes |
| --- | --- | --- | --- | --- |
| `#192` | AI SDK Integration: Replace `llm_service.py` + ChatOps regex pipeline with typed Zod schemas and `streamText` agent | AI middleware/backend/frontend | High | Active umbrella. Use `POST /ai/sessions/{sessionId}/stream`, `src/api/ai/_lib/*`, and Python tool endpoints. |
| `#16` | Add interactive PR changelog review table before merge | GitHub automation + UI | Medium | Defer until PR metadata and execution artifacts are stable. |
| `#143` | Let every agent mode confirmation be handed off to different users. | Product/backend | Low | Needs product design and shared execution identity policy. |
| `#139` | feat: integrate Better Auth with separate auth database | Auth/infra | Needs decision | Choose auth architecture before starting. |
| `#135` | Migrate GitHub App to Org Account & Add Gmail Auth with Auto-Repo Creation | Auth/org setup | Needs decision | Do not run in parallel with #139 until the target auth/org model is chosen. |

## Recommended Execution Order

1. Complete #192 against the current `src/api/ai` route and backend tool
   contracts.
2. Re-run the focused AI middleware, workbench question, objective truncation,
   and backend session-route tests.
3. Defer #16 until generated PR metadata and execution artifacts are stable
   enough for a review table.
4. Decide the auth/org direction before touching #139 or #135.
5. Leave #143 until product ownership and shared execution identity are designed.

## Closed Or Coalesced Issues

| Closed issues | Resolution | Active tracker |
| --- | --- | --- |
| `#175`, `#179`, `#182`, `#191` | Closed as completed on 2026-05-05. | `#192` for the AI SDK migration that consumes and replaces the old dependency chain. |
| `#163`, `#164`, `#165`, `#170`, `#171`, `#172`, `#176`, `#177`, `#178` | Closed as `not_planned`; first-class agent framework is deferred. | `#192` only where typed AI SDK tools replace the old regex/tool-call path. |
| `#173`, `#174` | Closed as `not_planned`; duplicate subagent-class framing replaced by current MSWEA contract hardening. | None. |
| `#166`, `#168`, `#169` | Closed as `not_planned`; sandbox provider work was consolidated into one decision. | `#167` completed. |
| `#167` | Closed as completed; Modal stays canonical until a concrete second provider exists. | None. |
| `#60` | Closed as completed; Daifu prompt treats issue/PR size constraints as Architect-ready issue drafting guidance. | None. |
| `#63` | Closed as completed; `scripts/pr_complexity_report.py` provides the minimal script-only complexity report. | `#16` only if later CI/UI integration is needed. |
| `#180`, `#181`, `#184`, `#185`, `#186` | Closed as `not_planned`; frontend polish grouped into #182, now completed. | None. |

## Current Direction

### AI Chat

The active Agent Workbench chat path is:

```text
AgentWorkbench
  -> useChat / DefaultChatTransport
  -> POST /ai/sessions/{sessionId}/stream
  -> backend /daifu/sessions/{sessionId}/ai-context
  -> AI SDK streamText with OpenRouter-compatible provider
  -> backend tool endpoints as native AI SDK tools
  -> backend /daifu/sessions/{sessionId}/ai-turns
```

Do not route active workbench chat through Python `ChatOps` or
`llm_service.py` regex/directive parsing. Those modules remain available only
for legacy/non-chat callers during the transition.

### Runtime

The production execution path remains the Modal-backed MSWEA orchestrator:

```text
Daifu issue/session flow
  -> Daifu tool wrappers from PR #188
  -> SessionExecutionOrchestrator
  -> Architect mode
  -> Tester mode
  -> Coder mode
  -> PR metadata and frontend-visible execution events
```

Do not implement `@task`, `SubagentExecutor`, a custom `BaseTool` stack, or
duplicate `ArchitectSubagent`/`TesterSubagent`/`CoderSubagent` classes unless
the product direction explicitly reopens the first-class framework later.
