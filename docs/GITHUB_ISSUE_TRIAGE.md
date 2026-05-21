# GitHub Issue Triage

Generated from open issues in `pranay5255/YudaiV3` using `gh api`.

Scope: open GitHub issues only, excluding pull requests unless explicitly noted.

Last updated: 2026-05-21 while creating the organization, runtime profile, and
Agent Evolution backlog.

## Summary

The product direction is now organization-first:

```text
organization -> repositories -> runtime profiles -> user sessions -> Modal executions
```

The core objective is not just running mini-swe-agent in Modal. The app should
help each organization evolve repo-specific agent harnesses over time. Session
history, sandbox traces, GitHub issues, PRs, CI failures, and repo manifests
become evidence for suggested changes to tools, env vars, secrets, agent configs,
and validation harnesses. Admins review, validate, and publish those changes as
immutable runtime profile versions.

`#194` is the new top-priority umbrella spec for the organization profile and
RBAC model. It should be completed before implementation work fans out.

`#192` remains the active AI SDK integration tracker for the current Agent
Workbench chat path. It should continue to constrain chat/tool integration:
`src/api/ai/...`, typed Zod schemas, and Python backend tool endpoints remain
the active architecture.

Draft PR `#193` adds session execution approval cards. It is not listed in the
issue table because it is a pull request, but it is important context for the
current runtime surface: AgentWorkbench is moving toward backend-controlled
stage approval and trace monitoring instead of direct manual stage starts.

## Layered Closure Strategy

Close the backlog in layers so each merged change gives the next layer a stable
contract instead of mixing product governance, auth, runtime persistence, and
agent evolution in one PR.

| Layer | Focus | Issues / PRs | Exit criteria |
| --- | --- | --- | --- |
| Layer 0 | Current PR cleanup | PR `#193` | Session execution approvals, event replay, stop, and run monitoring are green in CI. No org/admin governance is added here. |
| Layer 1 | Product and auth shape | `#194`, `#205` | Organization profile, roles, onboarding, Google login, and GitHub capability boundaries are specified. |
| Layer 2 | Backend data foundation | `#195`, `#197`, `#196` | Orgs, memberships, repositories, immutable runtime profile versions, and session/execution pins exist. |
| Layer 3 | Runtime control plane | `#198`, `#143`, `#201`, `#200`, `#199` | Admin/member dashboard, approval requests, secrets/env bindings, tool manifests, validation, and profile editing are implemented. |
| Layer 4 | Agent Evolution | `#202`, `#203`, `#204` | Evidence-backed suggestions are mined from sessions/GitHub artifacts and routed through admin review and publish. |
| Layer 5 | Later external surfaces | `#16` | PR changelog/review surfaces consume stable metadata from earlier layers. |

PR `#193` should be merged only as the Layer 0 bridge: it introduces the
question-card approval primitive for session execution. It does not close
`#194`, `#143`, `#195`, or `#205`; those issues reuse the primitive after the
organization and runtime-profile models exist.

## Active Backlog

| Issue | Title | Area | Priority | Notes |
| --- | --- | --- | --- | --- |
| `#194` | Define organization profile and RBAC model for Agent Workbench | Product/backend/frontend | P0 | New umbrella spec. Defines organization-first app model, roles, access matrix, admin dashboard, and member-limited surface. |
| `#195` | Add organization, membership, and repository ownership data model | Backend/data | P0 | First implementation dependency for org-scoped sessions, repositories, runtime profiles, and access checks. |
| `#205` | Define Google login and organization onboarding under the new org profile model | Auth/product | P0 | Reconciles `#135` and `#139` with organization-first onboarding and separates human identity from repo capability. |
| `#197` | Design and implement immutable runtime profile versions | Backend/runtime/data | P1 | Defines the core runtime profile object: agent configs, tools, env bindings, build metadata, and validation status. |
| `#196` | Pin sessions and executions to organization repositories and runtime profile versions | Backend/runtime | P1 | Makes sessions and executions reproducible by storing org, repo, profile version, branch, and commit context. |
| `#198` | Add AgentWorkbench organization dashboard for admins and members | Frontend/product | P1 | Adds the visible organization control plane inside the main app. Admins manage org surfaces; members get limited access. |
| `#143` | Admin approval workflow for runtime profile, harness, config, tool, and artifact changes | Product/backend/frontend | P1 | Replaces the old cross-user handoff framing. Users request profile/harness/tool/artifact approvals; admins review, validate, approve, publish, or reject. |
| `#200` | Add sandbox tool manifest and profile validation pipeline | Runtime/Modal | P1 | Models apt/pip/npm/bash tools and validates profile candidates before publish. |
| `#201` | Add org-scoped secrets and environment bindings for runtime profiles | Backend/security/frontend | P1 | Adds admin-managed env/secret bindings resolved into Modal sandbox start env. Values must remain write-only. |
| `#202` | Define Agent Evolution suggestion and evidence model | Product/backend | P1 | Specifies how session/GitHub evidence becomes admin-reviewable profile suggestions. |
| `#199` | Add runtime profile editor for agent config overlays in AgentWorkbench | Frontend/backend | P2 | UI for editing Architect, Tester, Coder, Browser, and Probe config overlays as draft profile changes. |
| `#203` | Mine session history and GitHub artifacts for runtime profile improvement suggestions | Backend/evolution | P2 | Implements analyzers for missing tools, package managers, timeouts, CI failures, repeated setup commands, and repo drift. |
| `#204` | Add Agent Evolution inbox and profile publish flow to AgentWorkbench | Frontend/backend | P2 | Admin UI for reviewing evidence, accepting/rejecting suggestions, validating drafts, publishing, and rollback. |
| `#192` | AI SDK Integration: Replace `llm_service.py` + ChatOps regex pipeline with typed Zod schemas and `streamText` agent | AI middleware/backend/frontend | Active | Existing AI SDK umbrella. Keep active AgentWorkbench chat on `POST /ai/sessions/{sessionId}/stream`. |
| `#16` | Add interactive PR changelog review table before merge | GitHub automation + UI | Later | Defer until PR metadata, execution artifacts, and runtime profile versioning are stable. |
| `#139` | feat: integrate Better Auth with separate auth database | Auth/infra | Needs decision | Should be interpreted through `#205` before implementation starts. |
| `#135` | Migrate GitHub App to Org Account & Add Gmail Auth with Auto-Repo Creation | Auth/org setup | Needs decision | Should be interpreted through `#205` before implementation starts. |

## Recommended Execution Order

1. Complete `#194` as the source-of-truth product and authorization spec.
2. Complete `#205` enough to decide Google/GitHub identity and organization
   onboarding boundaries.
3. Implement `#195` so organizations, members, and org repositories exist in
   the backend model.
4. Implement `#197` and `#196` together or in close sequence so runtime profile
   versions are immutable and sessions/executions are pinned to them.
5. Implement the admin/member dashboard in `#198`, then the approval request
   workflow in `#143`.
6. Implement secrets/env bindings in `#201`, then tool manifests and validation
   in `#200`, both routed through admin approval.
7. Implement `#202` as the Agent Evolution spec, then `#203` analyzers, then
   `#204` inbox/publish UI.
8. Keep `#192` active for chat/tool stream correctness during these changes.
9. Defer `#16` until PR metadata, execution artifacts, and runtime profile
   versioning are stable.

Next issue to tackle one by one: `#194`.

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
| `#180`, `#181`, `#184`, `#185`, `#186` | Closed as `not_planned`; frontend polish grouped into `#182`, now completed. | None. |

## Current Direction

### Organization Surface

AgentWorkbench should become the main organization control plane:

```text
Top-level org context
  -> organization dashboard
  -> repositories
  -> runtime profiles
  -> secrets and env bindings
  -> tool builds and validation
  -> sessions and executions
  -> audit log
```

Admins manage users, repos, profiles, tools, keys, env vars, and profile publish
flow. Members get limited repo/profile/session access. Runtime profile changes
must be draft, validated, and published before future sessions can use them.

`#143` owns the approval workflow between these surfaces. Members can submit
requests for profile configs, harness scripts, tools, env bindings, secret
bindings, runtime reprovisioning, and generated artifacts. Admins review those
requests with evidence, validation status, risk, and audit history before
approving, rejecting, requesting changes, validating, or publishing.

### Agent Evolution

The app should mine previous sessions and GitHub artifacts to suggest runtime
profile improvements:

```text
session history + sandbox traces + GitHub artifacts + repo manifests
  -> evidence records
  -> evolution suggestions
  -> admin review
  -> validation sandbox
  -> immutable runtime profile version
  -> better future sessions
```

Suggestions must not apply automatically. Admin approval and publish are required.

### AI Chat

The active Agent Workbench chat path remains:

```text
AgentWorkbench
  -> useChat / DefaultChatTransport
  -> POST /ai/sessions/{sessionId}/stream
  -> backend /daifu/sessions/{sessionId}/ai-context
  -> AI SDK streamText with OpenRouter-compatible provider
  -> backend tool endpoints as native AI SDK tools
  -> backend /daifu/sessions/{sessionId}/ai-turns
```

Do not route active workbench chat through Python `ChatOps` or `llm_service.py`
regex/directive parsing. Those modules remain available only for legacy/non-chat
callers during the transition.

### Runtime

The production execution path remains the Modal-backed MSWEA orchestrator:

```text
Daifu issue/session flow
  -> Daifu tool wrappers
  -> SessionExecutionOrchestrator
  -> Architect mode
  -> Tester mode
  -> Coder mode
  -> PR metadata and frontend-visible execution events
```

Do not implement `@task`, `SubagentExecutor`, a custom `BaseTool` stack, or
duplicate `ArchitectSubagent`/`TesterSubagent`/`CoderSubagent` classes unless
the product direction explicitly reopens the first-class framework later.
