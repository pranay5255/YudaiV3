# GitHub Issue Triage

Generated from open issues in `pranay5255/YudaiV3` using `gh api`.

Scope: open GitHub issues only, excluding pull requests.

## Legend

| Field | Meaning |
| --- | --- |
| Effort | `XS` < 2h, `S` 0.5-1d, `M` 1-2d, `L` 3-5d, `XL` 1w+ |
| Input | `Low` can implement from issue, `Med` needs UX/API choice, `High` needs product, credential, or account decision |
| Locality | Whether changes are local to a few files/folders or cross-cutting |

## Recommended Execution Order

1. Close/verify solved drift: `#138`
2. Finish immediate 3-mode MSWEA pipeline: reframe `#173`, `#174`, `#175` around mode configs/contracts, then add end-to-end controller tests.
3. Frontend execution visibility: keep `#182` open only for remaining loading/progress polish after chat streaming and controller-proxied sandbox streams.
4. Quick frontend wins / low risk: `#180`, `#181`, `#184`
5. Frontend UX batch: `#186`, `#183`, `#185`
6. Backend agent-framework epic after current MSWEA path is stable: `#162` -> `#163/#164/#165/#167` -> `#166/#168/#169/#170` -> `#171/#177/#178/#172` -> `#176` -> `#179`
7. GitHub automation: `#60`, `#63`, then `#16`
8. Auth/org epic: decide `#139` vs `#135` architecture first; do not start both independently.
9. Needs product design first: `#143`

## 2026-04-20 Drift Resolution Flags

| Issue | Flag | Action |
| --- | --- | --- |
| `#138` | Solved pending merge/close | Modal image now installs `pgvector`; `uv run modal` preflight and workflow probes verified sandbox creation, healthcheck, exec, artifacts, and termination. Close after this branch lands or after one production preflight. |
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
| `#138` | ModuleNotFoundError: No module named `pgvector` in Modal sandbox | Backend/Infra | XS | <2h | Low | Local: `backend/requirements`, Modal image config |
| `#180` | Persist sidebar collapsed/expanded state across sessions | Frontend | S | 0.5-1d | Low | Local: `src/components/Sidebar.tsx` or store |
| `#181` | Add contextual quick-start suggestions in empty states | Frontend | S | 0.5-1d | Med | Local: `Chat`, `ContextCards`, repo metadata hook |
| `#184` | Improve toast notification UX | Frontend | S/M | 1-2d | Low | Local: `src/components/Toast.tsx` |
| `#186` | Replace repository selection Toast with slide-over panel | Frontend | M | 1-2d | Med | Local-ish: replace `RepositorySelectionToast`, touches TopBar/sidebar |
| `#183` | Add grouping, filtering, and search to context cards | Frontend | M | 1-2d | Med | Local: `src/components/ContextCards.tsx` |
| `#185` | Add actionable recovery buttons to error states | Frontend + maybe Backend | M | 1-2d | Med | Cross: `Toast`, error boundaries, API error shapes |
| `#182` | Improve loading feedback with streaming tokens and step progress | Frontend + Backend | L | 3-5d | Med | Cross: chat, context, solve tabs, streaming/cancel semantics |
| `#60` | Implement constraints for GitHub issue and PR creation | Backend | M | 1-2d | Med | Local-ish: `IssueOps`, `githubOps`, `ChatOps` |
| `#63` | Implement PR complexity code categorisation | CI + Backend | M | 1-2d | Low/Med | Cross: `.github/workflows`, classifier/report script |
| `#16` | CHANGELOG after PR creation and before PR merge | Frontend + Backend + Remotion | L | 3-5d | Med/High | Cross: PR flow, changelog table, video explainer |
| `#143` | Let every agent mode confirmation be handed off to different users | Product + Backend | XL | 1w+ | High | Architecture issue; needs design before coding |

## Agent Framework Epic

| Issue | Title | Area | Effort | Time | Input | Locality / Dependency |
| --- | --- | --- | --- | --- | --- | --- |
| `#162` | Typed config dataclasses + Pydantic API models + TypeScript codegen pipeline | Backend + Frontend | L | 3-5d | Med | Cross; root dependency for most agent issues |
| `#163` | Add ToolErrorHandlingMiddleware for graceful tool failures | Backend | M | 1-2d | Low | Local: `backend/yudai/agents/middlewares`; depends `#162` |
| `#164` | Add LoopDetectionMiddleware for agent safety | Backend | M | 1-2d | Low | Local: middleware; depends `#162` |
| `#165` | Add TypedThreadState schema for agent state | Backend | S/M | 1-2d | Low | Local: `backend/yudai/agents/thread_state.py`; depends `#162` |
| `#167` | Create Sandbox ABC and SandboxProvider ABC abstractions | Backend | M | 1-2d | Low | Local: new `backend/yudai/sandbox`; depends `#162` |
| `#166` | Wire SandboxProvider into lifecycle, sandbox_exec_broker, and sandbox_transport | Backend | L | 3-5d | Med | Cross: `backend/realtime/*`; depends `#167` |
| `#168` | Implement ModalSandboxProvider as a pluggable SandboxProvider | Backend | M/L | 2-4d | Med | Local-ish: `backend/yudai/sandbox/modal_impl.py`; depends `#166/#167` |
| `#169` | Implement LocalSandboxProvider for local development mode | Backend | M | 1-2d | Low | Local: `backend/yudai/sandbox/local_impl.py`; depends `#167` |
| `#170` | Add SandboxMiddleware to inject sandbox state into ThreadState | Backend | M | 1-2d | Low | Local: agent middleware; depends `#165/#167` |
| `#171` | Create yudai agents package with MiddlewareChain and lead_agent factory | Backend | L | 3-5d | Med | Cross/additive; depends `#163/#164/#165/#170` |
| `#177` | Create BaseTool ABC and `@tool` decorator for YudaiV3 | Backend | M | 1-2d | Low | Local: `backend/yudai/tools`; depends `#165/#167` |
| `#178` | Implement builtin tools | Backend | M/L | 2-4d | Low | Local: `backend/yudai/tools/builtin`; depends `#170/#177` |
| `#172` | Create SubagentExecutor for composable subagent execution | Backend | L | 3-5d | Med | Local-ish: `backend/yudai/subagents`; depends `#167/#170/#171` |
| `#173` | Implement ArchitectSubagent | Backend | M | 1-2d | Low | Local: subagent; depends `#172/#178` |
| `#174` | Implement TesterSubagent | Backend | M | 1-2d | Low | Local: subagent; depends `#172/#173/#178` |
| `#175` | Implement CoderSubagent + pipeline | Backend | L | 3-5d | Med | Local-ish: subagents/pipeline; depends `#172/#173/#174/#178` |
| `#176` | Create `@task` tool for dynamic subagent delegation | Backend | M/L | 2-4d | Med | Cross within agent package; depends `#172/#173/#174/#175/#177` |
| `#179` | Migrate ChatOps.process_chat_message() to lead_agent framework | Backend | XL | 1w+ | High | Cross: `ChatOps`, `session_service`, `mode_orchestrator`; final integration |

## Auth / Org Epic

| Issue | Title | Area | Effort | Time | Input | Locality / Dependency |
| --- | --- | --- | --- | --- | --- | --- |
| `#139` | Integrate Better Auth with separate auth database | Backend + Infra + light Frontend | XL | 1w+ | High | Cross: auth, DB, env, migrations, Docker |
| `#135` | Migrate GitHub App to Org Account and Add Gmail Auth with Auto-Repo Creation | Backend + Frontend + Manual setup | XL | 1w+ | High | Cross; requires GitHub org app, Google OAuth creds, env updates |

## Dependency Map

```text
Agent framework:
#162
  -> #163, #164, #165, #167
  -> #166 -> #168
  -> #169
  -> #170
  -> #171
  -> #177 -> #178
  -> #172 -> #173 -> #174 -> #175
  -> #176
  -> #179 final integration

Frontend UX:
#184 should happen before #185
#186 can run separately but overlaps with toast/repo selector UX
#182 likely needs backend streaming/cancel API decisions

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

git worktree add -b feat/frontend-ux ../YudaiV3-frontend-ux origin/main
git worktree add -b feat/agent-framework-foundation ../YudaiV3-agent-framework origin/main
git worktree add -b feat/github-automation ../YudaiV3-github-automation origin/main
git worktree add -b feat/auth-epic ../YudaiV3-auth origin/main
```

Recommended branch grouping:

| Branch | Issues |
| --- | --- |
| `feat/frontend-ux` | `#180`, `#181`, `#184`, `#186`, `#183`, `#185`, `#182` |
| `feat/agent-framework-foundation` | Start with `#162`, `#163`, `#164`, `#165`, `#167` |
| `feat/sandbox-provider` | `#166`, `#168`, `#169`, `#170` after foundation lands |
| `feat/subagents` | `#171`, `#177`, `#178`, `#172`, `#173`, `#174`, `#175`, `#176` |
| `feat/chatops-lead-agent` | `#179` only, after subagents land |
| `feat/github-automation` | `#60`, `#63`, `#16` |
| `feat/auth-epic` | `#139` or `#135`, after architecture decision |

Do not mix `#162-#179` with UI issues in the same branch. The backend agent chain is broad and long-lived, while the UI issues can ship independently.
