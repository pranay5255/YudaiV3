# YudaiV3 Architecture

This is the canonical architecture and product-surface document for the current
YudaiV3 app. It replaces the older plan-era docs for frontend architecture,
3-mode execution, Daifu context probes, UI refactor guidance, and standalone
architecture visualizations.

The two retained historical docs are intentionally separate:

- `docs/GITHUB_ISSUE_TRIAGE.md`: point-in-time GitHub backlog notes.
- `docs/REAL_TIME_IMPLEMENTATION_QUESTIONNAIRE.md`: original requirements Q&A.

## System Map

YudaiV3 is a Vite React frontend on Vercel plus a Python FastAPI backend that
owns auth, organization and repository access, session persistence, GitHub
operations, Modal sandbox lifecycle, runtime profile versions, and
Architect -> Tester -> Coder execution.

```mermaid
flowchart LR
    Browser[Browser] --> Vercel[Vercel frontend and API routes]
    Vercel --> React[React AgentWorkbench]
    Vercel --> AiRoute[/api/ai/sessions/:id/stream]
    Vercel --> Proxy[/api/proxy/*]
    Vercel --> Realtime[/api/realtime/*/events]

    AiRoute --> Backend[FastAPI backend]
    Proxy --> Backend
    Realtime --> Backend

    Backend --> Postgres[(PostgreSQL)]
    Backend --> Modal[Modal sandbox]
    Backend --> GitHub[GitHub API]
    AiRoute --> Model[OpenRouter-compatible model provider]

    Backend --> Org[Organization model]
    Org --> Profile[Runtime profile version]
    Profile --> Modal
    Modal --> Repo[Cloned repo workspace]
    Modal --> Mini[mini-swe-agent modes]
```

## Deployment Shape

### Frontend

The frontend package lives in `src/`.

Important files:

- `src/App.tsx`: route setup and auth bootstrap.
- `src/components/AgentWorkbench.tsx`: active authenticated product surface.
- `src/config/api.ts`: same-origin app API config plus auth backend config.
- `src/api/proxy/[...path].ts`: Vercel proxy route to Python backend.
- `src/api/realtime/sessions/[sessionId]/events.ts`: backend WebSocket to browser
  SSE bridge.
- `src/api/ai/sessions/[sessionId]/stream.ts`: AI SDK UI-message stream route.
- `src/vercel.json`: rewrites `/ai`, `/daifu`, `/github`, `/controller`, and
  `/realtime` into Vercel API routes or backend auth.

Production defaults:

- Auth API origin: `https://api.yudai.app`.
- Non-auth app APIs: same-origin Vercel routes unless `VITE_API_BASE_URL` is set.
- AI stream endpoint: `/ai/sessions/{sessionId}/stream`.

### Backend

The active backend package is under `backend/yudai/`.

Important files:

- `backend/yudai/run_controller.py`: FastAPI controller entrypoint.
- `backend/yudai/daifuUserAgent/session_routes.py`: Daifu session, messages,
  questions, issues, AI context/turns, and execution endpoints.
- `backend/yudai/realtime/controller_routes.py`: runtime and unified realtime
  routes.
- `backend/yudai/realtime/lifecycle.py`: sandbox lifecycle, runtime creation,
  git bootstrap, artifact finalization, and audit events.
- `backend/yudai/realtime/modal_sandbox.py`: Modal sandbox image and tunnel setup.
- `backend/yudai/realtime/mode_orchestrator.py`: current 3-mode execution
  orchestrator.
- `backend/yudai/daifuUserAgent/context_probe.py`: lightweight code exploration
  probes for Daifu.
- `backend/yudai/models.py`: SQLAlchemy models and API schemas.
- `backend/yudai/db/init.sql`: database bootstrap schema.

`docker-compose.backend-only.yml` runs:

- `db`: PostgreSQL 15.
- `modal-preflight`: Modal sandbox smoke check.
- `backend`: FastAPI controller on port `8000`.

The backend image builds from `backend/Dockerfile` and starts through
`backend/start.sh`.

## Auth And Routing

GitHub OAuth is handled by the Python backend.

```text
LoginPage -> /auth/api/login -> GitHub OAuth
GitHub callback -> backend -> /auth/success?session_token=...
AuthSuccess -> authStore -> AgentWorkbench
```

The browser stores the session token in frontend auth state and sends it as:

```text
Authorization: Bearer <session_token>
```

Vercel middleware routes authenticate by calling backend auth/user endpoints and
then forward requests to protected Python endpoints with the user identity.

## Organization And Access Model

The default product model is organization-first:

```text
organization -> repositories -> runtime profiles -> user sessions -> Modal executions
```

A user creates or joins an organization before starting meaningful work. The
user who creates an organization becomes `owner` by default. An organization owns
repositories, runtime profiles, env/secret bindings, tool manifests, sessions,
executions, and audit events.

Human identity and repository capability are separate:

- Human identity comes from GitHub OAuth today and should support Google/Gmail
  after the auth decision in `#205`.
- Repository capability comes from a GitHub App installation, a user GitHub
  token where still required, or a future Yudai-managed repository under an org.
- Google-authenticated users do not automatically have personal GitHub repo
  capability; onboarding must either invite them into an organization with
  existing repo access or create a managed repository path.

Initial roles:

| Role | Intended access |
| --- | --- |
| `owner` | Full organization control, including deleting the organization and assigning admins. |
| `admin` | Manage members, repositories, runtime profiles, tools, env vars, secrets, validation, and audit review. |
| `maintainer` | Create sessions, run agents, view profile details, and request profile changes for allowed repositories. |
| `member` | Create sessions on allowed repositories and use approved runtime profiles. |
| `viewer` | Read-only access to allowed sessions, runs, profile metadata, and artifacts. |

Access rules:

- Admin-only changes include member management, repo connection, secret writes,
  tool manifest changes, runtime profile draft edits, validation, publish, and
  rollback.
- Maintainers and members may request Agent Evolution suggestions but cannot
  publish runtime profile versions.
- Maintainers and members may submit approval requests for harness, config,
  tool, env, secret binding, runtime reprovision, and generated-artifact changes.
- Non-admin users never see raw secret values.
- Every new session must be scoped to one organization, one organization
  repository, and one published runtime profile version.
- Every execution must keep the same immutable profile version as the session
  unless an explicit admin-mediated reprovision creates a new session/runtime.

## Active Product Surface

`AgentWorkbench` is the active app shell. It owns the current user workflow:

- organization selection and organization dashboard access
- repository and branch selection
- runtime profile selection or defaulting
- session creation
- AI chat stream
- pending clarification questions
- context cards
- session-created issues
- execution status
- trajectory summaries
- workflow/mode progress

Admins should see an organization dashboard inside the main app. The dashboard
contains:

- overview
- members and roles
- repositories
- runtime profiles
- secrets and env bindings
- tool manifests and validation runs
- approval requests
- Agent Evolution suggestions
- audit log

Non-admin users see a limited dashboard for repositories they can access,
approved runtime profiles, their sessions, run history, and read-only profile
metadata. They can submit approval requests with evidence from their sessions or
GitHub artifacts, and they can track admin feedback/status. Admin mutation
controls must be hidden or disabled based on backend authorization, not frontend
state alone.

Several older components still exist for compatibility or secondary paths:

- `TopBar`
- `Sidebar`
- `Chat`
- `ContextCards`
- `SolveIssues`
- `TrajectoryViewer`
- `RepositorySelectionToast`
- `Toast`
- `SessionOrchestrator`
- `sessionStore`

Do not assume those older components are mounted in the active root route. Check
`src/App.tsx` and `AgentWorkbench` before changing user-facing behavior.

## Chat And AI Stream

The active chat submit path is AI SDK based:

```text
AgentWorkbench.handleSendMessage()
  -> useChat sendMessage()
  -> /ai/sessions/{sessionId}/stream
  -> backend /daifu/sessions/{sessionId}/ai-context
  -> model stream
  -> backend /daifu/sessions/{sessionId}/ai-turns
  -> UI-message stream back to AgentWorkbench
```

The Vercel AI route:

- validates auth
- verifies the URL session ID matches the request body
- loads session context from Python
- runs AI SDK `streamText` with an OpenRouter-compatible provider
- uses Zod schemas for the `{ text, questions, probes, actions }` response
- exposes Daifu backend operations as typed AI SDK tools
- emits status, text, tool, question, and action UI-message parts
- persists the user/assistant turn and structured data parts back to Python

If `OPENROUTER_API_KEY` or model config is missing, the route returns a connected
fallback message instead of failing the UI stream.

## Daifu Questions And Context Probes

Daifu can ask clarification questions, emit frontend actions, and request
read-only code exploration probes through the AI SDK structured response. The
active Agent Workbench chat path no longer depends on `llm_service.py` regex
directives or `ChatOps` continuation/tool-dispatch parsing.

Current active implementation:

- `src/api/ai/_lib/schema.ts` defines the Zod output and tool input/output
  contracts.
- `src/api/ai/_lib/daifu-tools.ts` defines native AI SDK tools for GitHub issue
  publishing and Architect, Tester, and Coder stage execution.
- `src/api/ai/sessions/[sessionId]/stream.ts` emits `data-agent-question` parts;
  backend `/ai-turns` persists those as `UserQuestion` records.
- `ContextProbeService` remains the backend owner for actual probe execution
  when a probe is scheduled through the runtime path.

Legacy implementation notes:

- `llm_service.py` and `ChatOps.py` still exist for legacy/non-active callers
  during the migration.
- Do not add new active Agent Workbench behavior that relies on `Button{}`,
  `Question{}`, `Probe{}`, `Tool{}`, XML blocks, or fenced JSON parsing.

Probe config lives at:

```text
backend/yudai/realtime/mswea_mode_configs/probe/config.yaml
```

Probe agents are read-only. They may write only their probe output file under the
sandbox workspace.

## Runtime Profiles And Agent Evolution

A runtime profile is the organization/repository-specific harness definition for
agents. It contains:

- mode configs or config overlays for Architect, Tester, Coder, Browser, and
  Probe
- tool manifest entries for apt, pip, npm, and custom bash tools
- non-secret env vars
- secret binding names
- sandbox image/build metadata
- validation and smoke-check status
- publish metadata and author

Profiles have mutable drafts and immutable published versions. Sessions and
executions may only use published versions. Draft edits must not affect running
or historical sessions.

Runtime profile lifecycle:

```text
draft profile
  -> validate config and tool manifest
  -> run sandbox/profile smoke checks
  -> publish immutable profile version
  -> assign as organization repository default
  -> new sessions use the published version
```

Modal sandbox env vars are start-time inputs. Changes to tools, secrets, env
vars, or profile versions require a new sandbox or explicit runtime reprovision.

Agent Evolution is the evidence loop that improves repo-specific agent harnesses
over time:

```text
session history + sandbox traces + GitHub artifacts + repo manifests
  -> evidence records
  -> evolution suggestions
  -> admin review
  -> validation sandbox
  -> immutable runtime profile version
  -> better future sessions
```

Evidence sources include previous messages, execution traces, failed commands,
missing package errors, repeated manual setup commands, generated GitHub issues,
generated PRs, CI failures, dependency manifests, Dockerfiles, Makefiles, and
workflow YAML. Suggestions may propose packages, bash helpers, env bindings,
secret bindings, config guidance, timeout/step-limit changes, or smoke checks.

Suggestions and user-submitted changes are never applied automatically. They
become approval requests. Admins approve, validate, publish, reject, request
changes, and roll back runtime profile versions.

Approval request lifecycle:

```text
draft -> submitted -> needs_changes -> approved -> validated -> published
                                  \-> rejected
                                  \-> superseded
```

Approval requests should record requester, target organization, target
repository, target runtime profile, requested change payload, evidence links,
risk, validation status, admin decision, and audit metadata.

## Runtime And Realtime

The backend owns sandbox runtime state. The browser does not talk directly to the
Modal sandbox for command execution.

Runtime flow:

```text
POST /controller/sessions/{session_id}/runtime
  -> create or reuse Sandbox and SessionRuntime rows
  -> provision Modal sandbox when enabled
  -> clone/bootstrap repo in sandbox workspace
  -> record audit events
  -> expose controller-managed runtime status
```

Realtime event paths:

- Controller WebSocket: `/controller/sessions/{session_id}/ws/unified`.
- Browser-facing Vercel SSE bridge: `/realtime/sessions/{session_id}/events`.
- Sandbox internal exec WebSocket:
  `/internal/sessions/{session_id}/ws/exec` inside the Modal sandbox tunnel.

The backend emits unified events for status, mode progress, trajectory updates,
sandbox stream output, tool calls, user questions, errors, and completion.

## 3-Mode Execution

The current execution orchestrator is:

```text
backend/yudai/realtime/mode_orchestrator.py
```

The public execution endpoint is:

```text
POST /daifu/sessions/{session_id}/execution
```

Execution is server-controlled. The backend determines the next legal mode for a
session and rejects invalid forced mode switches.

Mode order:

```text
Architect -> Tester -> Coder
```

Mode configs copied into the Modal image:

```text
backend/yudai/realtime/mswea_mode_configs/architect/config.yaml
backend/yudai/realtime/mswea_mode_configs/tester/config.yaml
backend/yudai/realtime/mswea_mode_configs/coder/config.yaml
backend/yudai/realtime/mswea_mode_configs/browser/config.yaml
backend/yudai/realtime/mswea_mode_configs/probe/config.yaml
```

The orchestrator builds `mini` commands using config paths like:

```text
/app/mswea_mode_configs/architect/config.yaml
/app/mswea_mode_configs/tester/config.yaml
/app/mswea_mode_configs/coder/config.yaml
```

It writes and tracks per-mode execution data under `.yudai/executions`, updates
`ChatSession` workflow fields, persists `AgentExecution` rows, broadcasts
`mode_event` messages, and finalizes session artifacts when the workflow is
complete.

## Key Data Model

Core tables:

- `users`
- `auth_tokens`
- `organizations`
- `organization_members`
- `organization_repositories`
- `runtime_profiles`
- `runtime_profile_versions`
- `runtime_profile_tools`
- `runtime_profile_env_bindings`
- `profile_validation_runs`
- `approval_requests`
- `approval_request_evidence`
- `approval_decisions`
- `agent_evolution_suggestions`
- `agent_evolution_evidence`
- `chat_sessions`
- `chat_messages`
- `user_questions`
- `user_issues`
- `sandboxes`
- `session_runtime`
- `session_artifacts`
- `session_audit_events`
- `agent_executions`

Important session scoping fields to add or preserve:

- `organization_id`
- `organization_repository_id`
- `runtime_profile_version_id`
- `repo_branch`
- `repo_commit_sha`
- `user_id`

Important `ChatSession` workflow fields:

- `current_mode`
- `mode_status`
- `mode_updated_at`
- `architect_issue_url`
- `architect_issue_number`
- `architect_completed_at`
- `tester_status`
- `tester_completed_at`
- `coder_pr_url`
- `coder_pr_number`
- `coder_completed_at`
- `workflow_completed_at`
- `mode_metadata`

## GitHub Issue And PR Flow

The app supports both local session issue records and upstream GitHub issue/PR
operations.

Current endpoint families:

- create local issue preview:
  `/daifu/sessions/{session_id}/issues/create-with-context`
- create upstream GitHub issue from a session issue:
  `/daifu/sessions/{session_id}/issues/{issue_id}/create-github-issue`
- run execution:
  `/daifu/sessions/{session_id}/execution`

When changing this area, preserve the distinction between a local `UserIssue`
record and a real GitHub issue number. Ambiguity here can cause agents to act on
the wrong issue.

## UI Direction

The public visual source of truth is the Yudai Labs landing/auth page:

```text
src/components/LoginPage.tsx
src/index.css
docs/LANDING_PAGE_DESIGN_REVIEW.md
```

Public landing-page goals:

- Godel-inspired structure without copied assets, copy, or product claims
- sticky toolbar, centered announcement pill, first-screen hero, and anchor
  sections for Product, Workflow, Security, Docs, and Get Started
- warm near-black background, cream primary text, taupe secondary text, orange
  CTA/accent states, dotted vertical rules, and subtle grain
- large Yudai Labs logo/wordmark from `/assets/baseLogo.png`
- real workflow media from `/videos/yudai-enterprise-intro.mp4` inside a framed,
  contained product/workflow section
- concise engineering copy about governed GitHub delivery, repo context, tests,
  PRs, Modal-backed execution, and traceability

Authenticated workspace goals remain operational and dense:

- clear hierarchy for repository, session, issue, and run state
- restrained cyan/sky/emerald accents for runtime status
- amber reserved for warnings or cautionary solve actions
- mono labels only where they help identify IDs, branches, counters, commands,
  or code-like state

Use these files as design references:

- `src/components/LoginPage.tsx`
- `src/index.css`
- `docs/LANDING_PAGE_DESIGN_REVIEW.md`
- `src/public/assets/baseLogo.png`
- `src/public/videos/yudai-enterprise-intro.mp4`
- `src/components/AgentWorkbench.tsx`

Older shell components still contain amber-forward and mono-heavy styling. Treat
that as legacy unless the component is intentionally retained.

## Change Guidance

Before editing architecture-sensitive code:

1. Confirm whether the active path goes through `AgentWorkbench`.
2. Confirm the organization, repository, role, and runtime profile version
   boundaries for the change.
3. Confirm whether the endpoint is same-origin Vercel middleware or direct
   Python backend auth.
4. Keep bearer tokens in headers, not query params or request bodies, unless a
   legacy realtime path explicitly requires otherwise.
5. Keep execution mode transitions server-controlled.
6. Prefer structured mode results and typed tool output over parsing free text.
7. Keep runtime profile published versions immutable.
8. Do not expose raw secret values through frontend-visible metadata, logs, or
   artifacts.
9. Preserve sandbox cleanup and artifact export behavior when touching runtime
   lifecycle code.
10. Update this file when changing the active frontend route, API routing,
    organization model, execution flow, sandbox lifecycle, runtime profile
    contract, or mode contracts.
