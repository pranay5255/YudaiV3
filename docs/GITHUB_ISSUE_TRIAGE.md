# GitHub Issue Triage

Generated from open issues in `pranay5255/YudaiV3` using `gh api`.

Scope: open GitHub issues only, excluding pull requests.

Commit reconciliation: updated on 2026-04-21 from the last 100 commits on this branch, covering the agent-framework foundation merge, non-indexed session cleanup, frontend workbench rebuild, and current merge commits through `9337a77`.

## Legend

| Field | Meaning |
| --- | --- |
| Effort | `XS` < 2h, `S` 0.5-1d, `M` 1-2d, `L` 3-5d, `XL` 1w+ |
| Input | `Low` can implement from issue, `Med` needs UX/API choice, `High` needs product, credential, or account decision |
| Locality | Whether changes are local to a few files/folders or cross-cutting |

## Recommended Execution Order

1. Verify and close completed drift: `#138` should be closed after one final preflight/import check if desired.
2. Re-audit frontend UX issues against the shipped Agent Workbench before implementing old issue copy: `#180`, `#181`, `#184`, `#186`, `#185`. Skip `#183`, which is now closed as not planned because the retired organization UI is no longer part of the product.
3. Harden the current 3-mode MSWEA path instead of creating a parallel framework: reframe `#173`, `#174`, and `#175` around the existing orchestrator, live mode configs, structured mode outputs, and a real GitHub issue -> tester branch -> coder PR run.
4. Fix the product handoff from Daifu issue creation to execution: add the missing issue for "create/confirm GitHub issue, then explicitly start or auto-start 3-mode execution"; connect it to `#179` only if ChatOps becomes the integration boundary.
5. Finish contract/codegen hardening: narrow `#162` to schema drift prevention, generated-client discipline, and CI checks now that config models, OpenAPI export, and TypeScript types exist.
6. Re-evaluate the sandbox-provider epic before building abstractions: `#166` is obsolete as written, and `#167`-`#170` should only proceed if a second provider is still a product requirement.
7. Keep deferred agent-framework work behind the current MSWEA pipeline: `#171`, `#177`, `#178`, `#172`, `#176`, and final `#179`.
8. GitHub automation: `#60`, `#63`, then `#16`.
9. Auth/org epic: decide `#139` vs `#135` architecture first; do not start both independently.
10. Needs product design first: `#143`.

## 2026-04-21 Last-100-Commit Development Ledger

| Area | Shipped work | Primary files / commits | Triage impact |
| --- | --- | --- | --- |
| Backend package consolidation | Moved the active backend surface under `backend/yudai`, including auth, DB, GitHub routes, Daifu session/chat services, realtime controller code, models, utilities, and runtime entrypoints. | `0170d10` foundation merge; `backend/yudai/**`; deleted many legacy top-level `backend/*` modules | Future issue paths should target `backend/yudai/*`. Avoid triage text that sends work to deleted top-level modules. |
| Typed config and API contract foundation | Added backend config models, typed API exports, OpenAPI export tooling, generated TypeScript contract types, a frontend contract alias layer, and a contract-backed agent API client. | `backend/yudai/config/*`, `backend/yudai/types/__init__.py`, `backend/yudai/tools/export_openapi.py`, `src/types/generated.ts`, `src/types/apiContract.ts`, `src/services/agentApi.ts`, `src/tsconfig.contract.json` | `#162` is partially shipped. Keep it open only for contract completeness, generation discipline, and CI drift checks. |
| Realtime and MSWEA execution substrate | Added/consolidated lifecycle management, controller routes, sandbox transport, cache/artifact export, Modal preflight, mode orchestration, live Architect/Tester/Coder/Probe configs, and standalone Modal workflow probes. | `backend/yudai/realtime/lifecycle.py`, `mode_orchestrator.py`, `sandbox_transport.py`, `cache_store.py`, `modal_preflight.py`, `mswea_mode_configs/*`, `scripts/modal_*` | `#173`-`#175` now have a real implementation substrate. Remaining work is role contract strictness, structured outputs, production GitHub run proof, and UI/DB state verification. |
| Daifu context probe path | Added a lightweight Probe mode plan and implementation pieces for Daifu to request natural-language code exploration through sandboxed Architect-style probes. | `backend/yudai/daifuUserAgent/context_probe.py`, `backend/yudai/realtime/mswea_mode_configs/probe/config.yaml`, `docs/HYBRID_DAIFU_ARCHITECT_PLAN.md`, probe/LLM tests | Create or map a follow-up issue if probe results need first-class UI/state handling. Do not confuse Probe mode with the main Architect mode. |
| Non-indexed sessions and indexing removal | Removed legacy indexing, embedding, vector-schema, file-dependency, and bundled `yudai-grep` code paths; updated backend/session tests and UI state accordingly. | `36cf803` -> `27d30db`; deleted `backend/context/yudai-grep/**`, `backend/context/facts_and_memories.py`, `backend/download_model.py`, `backend/utils/chunking.py`; updated requirements and tests | `#138` is effectively solved. Any remaining context work should be repo-probe/session-context work, not embedding/index repair. |
| Frontend Agent Workbench rebuild | Added the Agent Workbench shell, routed the app into it, refreshed global design tokens, added alpha-aware Tailwind tokens, rebuilt login and auth callback/success screens, and cleaned protected-route loading/debug behavior. | `23d2009` -> `f05ec21`; `src/components/AgentWorkbench.tsx`, `LoginPage.tsx`, `AuthCallback.tsx`, `AuthSuccess.tsx`, `ProtectedRoute.tsx`, `src/App.tsx`, `src/index.css`, `src/tailwind.config.js` | Re-audit `#180`, `#181`, `#184`, `#186`, and `#185` against the new shell before doing isolated legacy-component work. `#183` is closed as not planned. |
| Frontend session/runtime streaming | Tightened WebSocket tool-call typing, session store/runtime behavior, realtime routing, execution screens, trajectory streaming, and related frontend tests. | `src/hooks/useSessionWebSocket.ts`, `src/stores/sessionStore.ts`, `src/utils/realtimeRouting.ts`, `src/components/SolveIssues.tsx`, `src/components/TrajectoryViewer.tsx`, `src/tests/frontend/*` | `#182` is partially solved. Keep only remaining loading/progress summaries, cancel/retry affordances, and failure recovery polish. |
| Tests, CI, deployment, and docs | Added/updated backend tests for auth/session/context/probe/mode/realtime flows, frontend tests for auth/session/runtime, CI path aliases, Docker/compose/deploy scripts, and architecture docs. | `backend/tests/*`, `src/tests/frontend/*`, `.github/workflows/ci.yml`, `backend/Dockerfile`, `docker-compose.backend-only.yml`, `scripts/deploy.sh`, `docs/*` | Future triage should treat command-level Modal smoke tests as available evidence, but still require one real browser + GitHub + Modal pipeline run before closing the 3-mode workflow. |

## 2026-04-21 Development Reconciliation Flags

| Issue | Status after last 100 commits | Action |
| --- | --- | --- |
| `#138` | Solved / close candidate | Embedding/indexing dependencies and old source modules were removed. Close after verifying current Modal/runtime imports, not by restoring indexing. |
| `#162` | Partially shipped | Config dataclasses, generated types, API aliases, and client scaffolding exist. Re-scope to generated contract freshness, CI enforcement, and missing schema coverage. |
| `#173` | Partially shipped, needs contract decision | Architect mode config and orchestrator path exist. Decide whether Architect creates the GitHub issue, enriches an existing issue, or is skipped after manual issue creation. |
| `#174` | Partially shipped, needs stricter role boundary | Tester mode config/path exists. Tighten the contract so Tester writes only tests/fixtures, records a test branch, and does not implement product code. |
| `#175` | Partially shipped, needs handoff validation | Coder mode config/path exists. Require structured input from Tester, schema-validated PR metadata, test evidence, and a real PR-creation run. |
| `#182` | Partially shipped / scope reduced | Unified WebSocket streaming and frontend runtime state are in place. Keep UX work for progress summaries, cancel/retry, grouped errors, and user-readable recovery. |
| `#166` | Obsolete as written | Legacy `sandbox_exec_broker`, `sandbox_manager`, and old solve-manager surfaces were deleted. Rename around canonical `lifecycle.py`, `sandbox_transport.py`, and provider strategy, or close. |
| `#167`-`#170` | Defer / validate need | Provider abstractions should follow a real second-provider requirement. Do not block current Modal pipeline stabilization on abstraction work. |
| `#171`, `#172`, `#176`, `#177`, `#178`, `#179` | Deferred framework work | Keep behind the current MSWEA orchestrator. Re-open sequencing only after the live 3-mode path has a reliable contract and e2e proof. |
| `#180`, `#181`, `#184`, `#186`, `#185` | Needs frontend re-triage | The workbench/auth shell changed substantially. Re-test the current UI before implementing the older issue descriptions literally. |
| `#183` | Closed / not planned | Retired organization UI is no longer part of the product surface. Do not implement the old search/group/filter scope. |
| `#139`, `#135` | Still needs architecture decision | Auth screens improved, but the backend/org/account architecture choice is unchanged. |

## 2026-04-20 Drift Resolution Flags

| Issue | Flag | Action |
| --- | --- | --- |
| `#138` | Superseded by cleanup | The obsolete indexing dependency path has been removed; keep open only if a fresh Modal preflight exposes a current runtime import failure. |
| `#182` | Partially solved, scope reduced | Frontend chat token streaming works; sandbox stdout/stderr is now proxied through the unified controller WebSocket and grouped in `TrajectoryViewer`. Keep open for UX polish: loading states, mode progress summaries, cancel/retry affordances. |
| `#173` | Reframe | Do not build a duplicate `ArchitectSubagent` now. Treat this as Architect MSWEA config/contract: consume an existing GitHub issue, ask clarifying questions when needed, search repo context, and append `.yudai/context.md`. |
| `#174` | Reframe | Do not build a duplicate `TesterSubagent` now. Treat this as Tester MSWEA config/contract: only write tests/test fixtures, commit a tester branch, and append `.yudai/context.md`. |
| `#175` | Reframe | Do not build a duplicate `CoderSubagent` now. Treat this as Coder MSWEA config/contract plus PR creation: consume tester branch/context, implement, test, push, and emit PR metadata. |
| `#166` | Coalesce/rename | `sandbox_exec_broker`, `sandbox_manager`, and artifact shims were dead compatibility surfaces. Future work should wire the provider into canonical `lifecycle.py`, `sandbox_transport.py`, and `cache_store.py` only. |
| `#167`, `#168`, `#169`, `#170` | Keep as staged provider epic | Still valid after dead-code cleanup. Implement ABCs only after the current Modal runtime path is protected by tests. |
| `#171`, `#172`, `#176`, `#177`, `#178`, `#179` | Defer | Keep for a later first-class Yudai agent framework. They should not block the immediate mini-swe-agent 3-mode pipeline. |
| New issue needed | Add | "Auto-start 3-mode execution after GitHub issue creation and verify DB state through Architect -> Tester -> Coder." |
| New issue needed | Add | "Add structured MSWEA result artifacts and parse them instead of relying only on stdout JSON." |
| New issue needed | Add | "Canonicalize realtime docs around unified controller WebSocket and remove stale SSE/direct tunnel references." |

## Issue Categorization

| Issue | Title | Area | Effort | Time | Input | Locality / Dependency |
| --- | --- | --- | --- | --- | --- | --- |
| `#138` | Modal sandbox dependency drift | Backend/Infra | XS | <2h | Low | Close candidate: verify current Modal imports only; do not restore indexing |
| `#180` | Persist sidebar collapsed/expanded state across sessions | Frontend | S | 0.5-1d | Low | Re-audit against `AgentWorkbench` shell and current store behavior |
| `#181` | Add contextual quick-start suggestions in empty states | Frontend | S | 0.5-1d | Med | Re-audit: likely `AgentWorkbench`, `Chat`, repo metadata hook |
| `#184` | Improve toast notification UX | Frontend | S/M | 1-2d | Low | Re-audit after workbench/auth rebuild; avoid legacy toast-only scope if shell changed |
| `#186` | Replace repository selection Toast with slide-over panel | Frontend | M | 1-2d | Med | Re-audit against current repository selection and workbench navigation |
| `#185` | Add actionable recovery buttons to error states | Frontend + maybe Backend | M | 1-2d | Med | Cross: workbench error states, API error shapes, retry/cancel hooks |
| `#182` | Improve loading feedback with streaming tokens and step progress | Frontend + Backend | M/L | 2-4d | Med | Remaining scope only: progress summaries, cancel/retry affordances, recovery polish |
| `#60` | Implement constraints for GitHub issue and PR creation | Backend | M | 1-2d | Med | Local-ish: `backend/yudai/daifuUserAgent/IssueOps.py`, `githubOps.py`, `ChatOps.py` |
| `#63` | Implement PR complexity code categorisation | CI + Backend | M | 1-2d | Low/Med | Cross: `.github/workflows`, classifier/report script |
| `#16` | CHANGELOG after PR creation and before PR merge | Frontend + Backend + Remotion | L | 3-5d | Med/High | Cross: PR flow, changelog table, video explainer |
| `#143` | Let every agent mode confirmation be handed off to different users | Product + Backend | XL | 1w+ | High | Architecture issue; needs design before coding |

## Agent Framework / MSWEA Epic

| Issue | Title | Area | Effort | Time | Input | Locality / Dependency |
| --- | --- | --- | --- | --- | --- | --- |
| `#162` | Harden typed config/API models/TypeScript codegen pipeline | Backend + Frontend | M | 1-2d | Med | Partially shipped; finish CI drift checks and schema coverage |
| `#163` | Add ToolErrorHandlingMiddleware for graceful tool failures | Backend | M | 1-2d | Low | Deferred until first-class agent middleware exists |
| `#164` | Add LoopDetectionMiddleware for agent safety | Backend | M | 1-2d | Low | Deferred until first-class agent middleware exists |
| `#165` | Add TypedThreadState schema for agent state | Backend | S/M | 1-2d | Low | Deferred; do not block current MSWEA execution |
| `#167` | Create Sandbox ABC and SandboxProvider ABC abstractions | Backend | M | 1-2d | Low | Validate need first; current path is canonical Modal lifecycle/transport |
| `#166` | Rename/close old SandboxProvider wiring issue | Backend | S/M | 0.5-1d | Med | Obsolete wording references deleted broker/manager surfaces |
| `#168` | Implement ModalSandboxProvider as a pluggable SandboxProvider | Backend | M/L | 2-4d | Med | Only after `#167` is justified; current Modal runtime already works through lifecycle |
| `#169` | Implement LocalSandboxProvider for local development mode | Backend | M | 1-2d | Low | Only after product/dev workflow confirms local provider requirement |
| `#170` | Add SandboxMiddleware to inject sandbox state into ThreadState | Backend | M | 1-2d | Low | Deferred with first-class agent framework work |
| `#171` | Create yudai agents package with MiddlewareChain and lead_agent factory | Backend | L | 3-5d | Med | Deferred; do not duplicate `SessionExecutionOrchestrator` yet |
| `#177` | Create BaseTool ABC and `@tool` decorator for YudaiV3 | Backend | M | 1-2d | Low | Deferred; `backend/yudai/tools` currently holds export tooling only |
| `#178` | Implement builtin tools | Backend | M/L | 2-4d | Low | Deferred until tool abstraction exists |
| `#172` | Create SubagentExecutor for composable subagent execution | Backend | L | 3-5d | Med | Deferred; current work should harden mode configs/orchestrator |
| `#173` | Harden Architect mode config and contract | Backend | M | 1-2d | Med | Local: `backend/yudai/realtime/mode_orchestrator.py`, `mswea_mode_configs/architect/config.yaml`; decide create-vs-consume issue |
| `#174` | Harden Tester mode config and branch/test contract | Backend | M | 1-2d | Low/Med | Local: tester config/orchestrator; enforce tests-only behavior and branch metadata |
| `#175` | Harden Coder mode handoff, PR metadata, and pipeline proof | Backend | L | 3-5d | Med | Local-ish: orchestrator, coder config, lifecycle completion, artifact export |
| `#176` | Create `@task` tool for dynamic subagent delegation | Backend | M/L | 2-4d | Med | Deferred until after stable 3-mode production path |
| `#179` | Integrate ChatOps/issue flow with current execution orchestrator | Backend | L/XL | 3-7d | High | Cross: `backend/yudai/daifuUserAgent/ChatOps.py`, `session_service.py`, `backend/yudai/realtime/mode_orchestrator.py` |

## Auth / Org Epic

| Issue | Title | Area | Effort | Time | Input | Locality / Dependency |
| --- | --- | --- | --- | --- | --- | --- |
| `#139` | Integrate Better Auth with separate auth database | Backend + Infra + light Frontend | XL | 1w+ | High | Cross: auth, DB, env, migrations, Docker |
| `#135` | Migrate GitHub App to Org Account and Add Gmail Auth with Auto-Repo Creation | Backend + Frontend + Manual setup | XL | 1w+ | High | Cross; requires GitHub org app, Google OAuth creds, env updates |

## Dependency Map

```text
Current MSWEA path:
#162 remaining contract/codegen hardening
  -> New structured mode-result artifact issue
  -> #173 Architect contract
  -> #174 Tester contract
  -> #175 Coder handoff/PR proof
  -> New issue-creation-to-execution handoff issue
  -> #179 only if ChatOps/session flow becomes the integration boundary

Deferred first-class agent framework:
#163, #164, #165, #167, #170
  -> #171
  -> #177 -> #178
  -> #172
  -> #176

Sandbox provider:
#166 should be renamed or closed
#167-#170 should wait for a confirmed second-provider requirement

Frontend UX:
Re-audit #180, #181, #184, #186, #185 against AgentWorkbench first
#183 is closed as not planned
#182 remaining work is progress/cancel/retry/recovery polish

Auth:
Choose architecture first:
#139 first if Better Auth/separate DB is the direction
#135 first only if org GitHub App + Google login is urgent
```

## Suggested Worktree Strategy

Use separate worktrees for independent streams:

```bash
cd /home/yudai/YudaiV3
git fetch origin

git worktree add -b feat/mswea-contract-hardening ../YudaiV3-mswea-contract origin/main
git worktree add -b feat/frontend-workbench-polish ../YudaiV3-frontend-polish origin/main
git worktree add -b feat/github-automation ../YudaiV3-github-automation origin/main
git worktree add -b feat/auth-epic ../YudaiV3-auth origin/main
```

Recommended branch grouping:

| Branch | Issues |
| --- | --- |
| `feat/mswea-contract-hardening` | Remaining `#162`, `#173`, `#174`, `#175`, plus the new structured-result and issue-handoff issues |
| `feat/frontend-workbench-polish` | Re-audited `#180`, `#181`, `#184`, `#186`, `#185`, `#182` |
| `feat/sandbox-provider` | Only if `#166` is renamed and `#167`-`#170` are still justified |
| `feat/agent-framework-deferred` | `#163`, `#164`, `#165`, `#171`, `#177`, `#178`, `#172`, `#176` after MSWEA path is stable |
| `feat/chatops-execution-handoff` | `#179` only if issue creation/chat must own execution orchestration |
| `feat/github-automation` | `#60`, `#63`, `#16` |
| `feat/auth-epic` | `#139` or `#135`, after architecture decision |

Do not mix MSWEA contract hardening with UI polish. The current backend execution path needs reliable mode contracts and production proof, while the UI issues should be re-triaged from the shipped workbench.
