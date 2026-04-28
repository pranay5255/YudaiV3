# GitHub Issue Triage

Generated from open issues in `pranay5255/YudaiV3` using `gh api`.

Scope: open GitHub issues only, excluding pull requests.

Last updated: 2026-04-28 after completing the first low-hanging backlog pass.

## Summary

The active backlog has been reduced to a smaller set of umbrella issues. Stale first-class agent-framework issues around `@task`, `SubagentExecutor`, custom tool decorators, and duplicate subagent classes were closed as `not_planned`. The current backend direction is to harden the existing Daifu + MSWEA orchestrator path instead of building a parallel framework.

PR #188 remains the shipped backend step for Daifu tool calls: it added issue-publishing and fixed Architect, Tester, and Coder stage wrappers. Follow-up runtime work now lives in #175 and #179. The first low-hanging pass also completed the sandbox-provider decision (#167), Daifu issue/PR sizing guidance (#60), and the minimal PR complexity script (#63).

## Active Backlog

| Issue | Title | Area | Priority | Notes |
| --- | --- | --- | --- | --- |
| `#175` | Harden current MSWEA Architect -> Tester -> Coder pipeline contracts | Backend/runtime | High | Canonical tracker for mode contracts, structured outputs, tester branch handoff, coder validation, and PR metadata. Supersedes old `#173` and `#174`. |
| `#179` | Refactor ChatOps onto current Daifu session orchestration | Backend/session | High | Keep ChatOps aligned with current Daifu tool services, session routes, and MSWEA handoff. Do not add the deferred first-class framework here. |
| `#182` | Polish Agent Workbench runtime UX and recovery flows | Frontend UX | High | Umbrella for progress, cancel/retry, errors, notifications, empty states, repository selection, and persisted preferences. Supersedes old `#180`, `#181`, `#184`, `#185`, and `#186`. |
| `#16` | Add interactive PR changelog review table before merge | GitHub automation + UI | Medium | Larger PR-review workflow item; defer until PR metadata and execution artifacts are stable. |
| `#143` | Let every agent mode confirmation be handed off to different users. | Product/backend | Low | Needs product design and shared-sandbox identity policy before implementation. |
| `#139` | feat: integrate Better Auth with separate auth database | Auth/infra | Needs decision | Choose auth architecture before starting. |
| `#135` | Migrate GitHub App to Org Account & Add Gmail Auth with Auto-Repo Creation | Auth/org setup | Needs decision | Do not run in parallel with #139 until the target auth/org model is chosen. |

## Recommended Execution Order

1. Harden the current MSWEA runtime path in `#175`.
2. Align ChatOps and session handoff with that runtime in `#179`.
3. Polish frontend runtime/recovery UX in `#182` once backend events and failure states are stable.
4. Defer `#16` until PR metadata and execution artifacts are stable enough for a useful review table.
5. Decide the auth/org direction before touching `#139` or `#135`.
6. Leave `#143` until product ownership and shared execution identity are designed.

## Closed Or Coalesced Issues

| Closed issues | Resolution | Active tracker |
| --- | --- | --- |
| `#163`, `#164`, `#165`, `#170`, `#171`, `#172`, `#176`, `#177`, `#178` | Closed as `not_planned`; first-class agent framework is deferred. | `#175`, `#179` |
| `#173`, `#174` | Closed as `not_planned`; duplicate subagent-class framing replaced by current MSWEA contract hardening. | `#175` |
| `#166`, `#168`, `#169` | Closed as `not_planned`; sandbox provider work was consolidated into one decision. | `#167` completed |
| `#167` | Closed as completed; `docs/SANDBOX_PROVIDER_DECISION.md` records that Modal stays canonical until a concrete second provider exists. | None |
| `#60` | Closed as completed; Daifu prompt now treats issue/PR size constraints as Architect-ready issue drafting guidance. | None |
| `#63` | Closed as completed; `scripts/pr_complexity_report.py` provides the minimal script-only complexity report. | `#16` only if later CI/UI integration is needed |
| `#180`, `#181`, `#184`, `#185`, `#186` | Closed as `not_planned`; frontend polish grouped into one workbench UX umbrella. | `#182` |

## Current Direction

### Runtime

The production path is the Modal-backed MSWEA orchestrator:

```text
Daifu issue/session flow
  -> current Daifu tool wrappers from PR #188
  -> SessionExecutionOrchestrator
  -> Architect mode
  -> Tester mode
  -> Coder mode
  -> PR metadata and frontend-visible execution events
```

Do not implement `@task`, `SubagentExecutor`, a custom `BaseTool` stack, or duplicate `ArchitectSubagent`/`TesterSubagent`/`CoderSubagent` classes unless the product direction explicitly reopens the first-class framework later.

### Frontend

The active UI tracker is `#182`. Treat the older standalone UX issues as folded into that umbrella, and re-audit work against the shipped Agent Workbench shell before coding.

### Sandbox

`docs/SANDBOX_PROVIDER_DECISION.md` records the current decision: keep Modal explicit and do not add a sandbox-provider abstraction until a second provider requirement is concrete.

## Suggested Worktree Strategy

Use separate worktrees for independent streams:

```bash
cd /home/pranay5255/YudaiV3
git fetch origin

git worktree add -b feat/mswea-contract-hardening ../YudaiV3-mswea-contract origin/main
git worktree add -b feat/frontend-workbench-polish ../YudaiV3-frontend-polish origin/main
git worktree add -b feat/auth-epic ../YudaiV3-auth origin/main
```

Recommended branch grouping:

| Branch | Issues |
| --- | --- |
| `feat/mswea-contract-hardening` | `#175`, then `#179` if ChatOps/session handoff is included |
| `feat/frontend-workbench-polish` | `#182` |
| `feat/pr-changelog-review` | `#16`, after PR metadata/artifacts stabilize |
| `feat/auth-epic` | `#139` or `#135`, after architecture decision |
