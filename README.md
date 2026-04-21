# YudaiV3

YudaiV3 is a GitHub-native AI coding workspace. You sign in with GitHub, pick a repo/branch, chat with the agent, generate implementation-ready issues, run solver workflows, and track solver trajectories in the UI.

This repository contains the frontend, backend API, solver integration, and in-progress real-time session architecture (controller + sandbox session server split).

## What You Can Do Today

- Sign in with GitHub OAuth
- Select a repository and branch
- Create persistent chat sessions for a repo context
- Generate context cards from chat and uploaded context
- Draft issues from chat context and create GitHub issues
- Start solver runs for issues and track progress
- View solver trajectories (SSE streaming path exists)
- Use real-time session runtime/tunnel lifecycle APIs (controller/sandbox foundation)

## Realtime Session Work (Phases 1-3)

This codebase now includes real-time session foundations and partial implementation for the split controller/sandbox model:

- Controller entrypoint: `backend/run_controller.py`
- Sandbox session server entrypoint: `backend/run_sandbox_server.py`
- Lifecycle APIs: create/get/delete sandbox, resolve tunnel, heartbeat, cleanup
- Runtime/session persistence tables: `sandboxes`, `session_runtime`, `session_artifacts`, `session_audit_events`
- Append-only sandbox cache + artifact export metadata under `/home/yudai/.cache/`
- Completion detection for `GitHub issue created` + `PR created` with auto-termination flow
- SSE trajectory streaming endpoint (existing solver stream path)
- WebSocket chat endpoint shell in sandbox server (MVP foundation)

Planning and scope documents are in:

- `REAL_TIME_PHASE_TASK_LIST.md`
- `REAL_TIME_IMPLEMENTATION_QUESTIONNAIRE.md`
- `backend/docs/realtime_phase0/`

## Tech Stack

- Frontend: React + Vite + TypeScript + Tailwind CSS + Zustand
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL
- Solver: Python-based sandbox/trajectory orchestration
- Realtime: SSE + WebSocket (phase rollout via feature flags)

## Project Structure

- `src/` — standalone frontend app/package (chat, session UI, trajectory viewer)
- `backend/` — FastAPI backend, auth, GitHub APIs, solver, realtime services
- `backend/realtime/` — controller/sandbox lifecycle services, schemas, cache/artifact export
- `backend/db/` — schema init + migrations

## Running Locally

### 1. Prerequisites

- Node.js 18+
- Python 3.10+
- PostgreSQL

### 2. Install Dependencies

Frontend:

```bash
cd src
npm ci
```

Backend (example using local venv):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 3. Configure Environment

Minimum backend requirement:

- `DATABASE_URL` (PostgreSQL connection string)

You will also need GitHub OAuth and model provider credentials for full app functionality. Check the existing `.env*` files in the repo for expected keys.

### 4. Start the App (Single Backend Entrypoint)

Backend:

```bash
python backend/run_server.py
```

Frontend:

```bash
cd src
npm run dev
```

Frontend production build:

```bash
cd src
npm run build
```

### 5. Start the Realtime Split Entrypoints (Optional / MVP Work)

Controller host:

```bash
python backend/run_controller.py
```

Sandbox session server:

```bash
python backend/run_sandbox_server.py
```

Realtime behavior is controlled by feature flags (`REALTIME_*` / `VITE_REALTIME_*`).

## Feature Flags (Realtime Rollout)

Backend and frontend read rollout flags for the real-time phases:

- `REALTIME_CONTROLLER_SPLIT_ENABLED`
- `REALTIME_TUNNEL_MODE_ENABLED`
- `REALTIME_WS_CHAT_ENABLED`
- `REALTIME_SSE_STREAM_ENABLED`
- `REALTIME_CONTRACT_VERSION`

Frontend equivalents:

- `VITE_REALTIME_CONTROLLER_SPLIT_ENABLED`
- `VITE_REALTIME_TUNNEL_MODE_ENABLED`
- `VITE_REALTIME_WS_CHAT_ENABLED`
- `VITE_REALTIME_SSE_STREAM_ENABLED`
- `VITE_REALTIME_CONTRACT_VERSION`

## Current Status

YudaiV3 is under active development. The real-time controller/sandbox split, artifact persistence, and streaming features are being implemented in phases. Expect active iteration and API changes while the MVP is stabilized.

## Contributing

You can contribute improvements to the frontend, backend, solver, or realtime lifecycle work.

1. Fork the repo
2. Create a branch (`feat/your-change`)
3. Open a PR with a clear description

## License

License is currently under consideration.

## Contact

- Website: `https://yudai.app`
- Issues: `https://github.com/pranay5255/YudaiV3/issues`
