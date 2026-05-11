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
owns auth, repository/session persistence, GitHub operations, Modal sandbox
lifecycle, and Architect -> Tester -> Coder execution.

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

## Active Product Surface

`AgentWorkbench` is the active app shell. It owns the current user workflow:

- repository and branch selection
- session creation
- AI chat stream
- pending clarification questions
- context cards
- session-created issues
- execution status
- trajectory summaries
- workflow/mode progress

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
- `chat_sessions`
- `chat_messages`
- `user_questions`
- `user_issues`
- `sandboxes`
- `session_runtime`
- `session_artifacts`
- `session_audit_events`
- `agent_executions`

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

The visual source of truth is the landing page:

```text
src/components/LoginPage.tsx
```

Shared visual goals:

- dark operational workspace
- precise enterprise feel
- clear hierarchy for repository, session, issue, and run state
- restrained cyan/sky/emerald accents
- amber reserved for warnings or cautionary solve actions
- real logo asset from `/assets/baseLogo.png`
- Inter/sans for normal UI; mono only for IDs, branch names, counters, and code
  labels

Use these files as design references:

- `src/components/LoginPage.tsx`
- `src/index.css`
- `src/tailwind.config.js`
- `src/public/assets/baseLogo.png`
- `src/components/AgentWorkbench.tsx`

Older shell components still contain amber-forward and mono-heavy styling. Treat
that as legacy unless the component is intentionally retained.

## Change Guidance

Before editing architecture-sensitive code:

1. Confirm whether the active path goes through `AgentWorkbench`.
2. Confirm whether the endpoint is same-origin Vercel middleware or direct
   Python backend auth.
3. Keep bearer tokens in headers, not query params or request bodies, unless a
   legacy realtime path explicitly requires otherwise.
4. Keep execution mode transitions server-controlled.
5. Prefer structured mode results and typed tool output over parsing free text.
6. Preserve sandbox cleanup and artifact export behavior when touching runtime
   lifecycle code.
7. Update this file when changing the active frontend route, API routing,
   execution flow, sandbox lifecycle, or mode contracts.
