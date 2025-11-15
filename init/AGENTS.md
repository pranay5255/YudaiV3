# YudaiV3 Codebase Overview

This repository contains both the FastAPI backend (`@backend`) and the Vite/React frontend (`src/`). The goal of this document is to capture the moving parts developers need to understand before making changes.

## Repository Layout

- `backend/` – Python 3.11 FastAPI service that exposes all HTTP APIs under the Contract One `/api/*` umbrella (see `backend/run_server.py`).
- `src/` – React 18 + TypeScript single-page application bootstrapped with Vite; talks to the backend via `/api`.
- `docker-compose*.yml`, `Dockerfile*`, `nginx/` – container and proxy definitions for local/dev/prod deployments.
- `public/`, `index.html` – static files served by Vite.
- `env-dev-template.txt`, `requirements.txt`, `backend/requirements.txt` – environment variable templates and Python dependency lock-files.

## Backend (`backend/`)

### Stack and Entry Points

- `run_server.py` creates the FastAPI app, configures CORS, and mounts the routers from `auth`, `github`, `daifuUserAgent`, and `solver` at `/auth`, `/github`, and `/daifu` respectively. The router contract matches the constants in `backend/config/routes.py`.
- `run_db_init.py` and `db/init_db.py` initialize the relational database by calling `Base.metadata.create_all()` against the configured `DATABASE_URL`.
- `start.sh`, `Dockerfile`, and `Dockerfile.dev` wrap uvicorn for local and containerized startups.

### Routing and Features

- `auth/` handles GitHub OAuth (`auth/github_oauth.py`) and issues JWT/session tokens returned to the frontend (`auth/auth_routes.py`).
- `github/` contains adapter routes that proxy GitHub REST operations and coordinate with the OAuth tokens already stored for a user.
- `daifuUserAgent/session_routes.py` exposes the high-volume DAifu endpoints used by the frontend: session CRUD, chat messages, context cards, file dependencies, repository selection, issue creation, and solver orchestration. The router imports solver routes so everything lives under `/daifu/*`.
- `daifuUserAgent/session_service.py`, `llm_service.py`, and the `context/` package (embedding pipeline, repository snapshots, memories) supply the backend logic that the FastAPI endpoints delegate to.
- `solver/` bundles the agent/orchestration layer (see `solver/solver.py` and `solver/manager.py`) plus sandbox helpers for executing code.

### Database / Models

- `models.py` houses the single source of truth for SQLAlchemy ORM entities (users, sessions, chat messages, issues, AI models, etc.) and mirrors them with Pydantic schemas returned by the API.
- `db/database.py` centralizes engine/session creation, enables the `pgvector` extension when Postgres is used, and offers helpers like `get_db()` dependency wiring and `fetch_and_add_openrouter_models()`.
- Persistence helpers inside `daifuUserAgent` rely on `SessionLocal` for transactions, keeping FastAPI dependencies thin.

### Supporting Utilities

- `utils.py` collects shared helpers (timestamps, JWT utilities, etc.).
- `download_model.py` plus `repo_processorGitIngest/` and `context/` scripts support background ingestion jobs.
- `tests/` stores FastAPI unit/integration tests; `logs/` captures runtime output when running the backend in long-lived environments.

## Frontend (`src/`)

### Stack and Bootstrapping

- `main.tsx` wires the React 18 root with `BrowserRouter`, React Query (`QueryClientProvider`), and devtools so network state is centralized.
- `App.tsx` manages the desktop-style layout (sidebar, topbar, chat area) and coordinates session-aware views (`Chat`, `ContextCards`, `TrajectoryViewer`, `SolveIssues`).
- The build uses Vite + SWC, TailwindCSS/PostCSS (`tailwind.config.{cjs,js}`, `postcss.config.{cjs,js}`), and Vitest for unit tests.

### Components and UI

- `components/` holds major surfaces such as `TopBar`, `Sidebar`, chat UX, repository selection flows, OAuth callback views, and route guards (`ProtectedRoute`, `SessionErrorBoundary`).
- `index.css` defines the Tailwind-driven design tokens that are shared across components.

### State Management and Data Fetching

- `stores/sessionStore.ts` is a Zustand store (persisted to `localStorage`) that mirrors backend models and contains all imperative actions (auth, repository selection, session CRUD, chat/context/file/issue mutations, solver state).
- `hooks/useSessionManagement.ts` tracks view-level UI state (active tab, collapsed sidebar).
- `hooks/useSessionQueries.ts` wraps React Query around the Zustand actions to enforce rate limiting, backoff, cache scoping, and standardized error handling.
- `hooks/useAuth.tsx` and `useRepository.ts` expose slices of the store for convenient access from components.
- `config/api.ts` defines every backend route (matching `backend/config/routes.py`) and exposes `buildApiUrl()` so hooks can easily substitute parameters.
- `types/` (notably `types/sessionTypes.ts`) mirrors the backend Pydantic/ORM models, ensuring typed API responses and store operations stay aligned.

### Services, Docs, and Utilities

- `services/` is the staging ground for API abstractions should the team choose to extract network code from the hooks/store.
- `data/` and `docs/` contain static seed data and product documentation leveraged in onboarding views.
- `utils/` contains formatting helpers, toast utilities, and other view-specific logic.

## Shared Infrastructure and Workflows

- `package.json` scripts expose `pnpm dev`, `pnpm build`, `pnpm preview`, tighter lint/test pipelines, and Docker/deployment helpers. The backend can be launched independently with `python backend/run_server.py` or via uvicorn.
- `docker-compose.dev.yml` and `docker-compose.prod.yml` wire the backend, frontend, database, and nginx proxy together; nginx (`nginx/*.conf`) strips the `/api` prefix before requests hit FastAPI per the Contract One architecture.
- SSL materials (`ssl/`), temporary files (`tmp/`, `logs/`), and `memories.md` (agent knowledge) round out the operational support files.

## Getting Started Locally

1. Install Python deps with `uv pip install -r backend/requirements.txt` (or `pip install -r backend/requirements.txt`) and Node deps with `pnpm install`.
2. Export the environment variables from `env-dev-template.txt` (ensure `DATABASE_URL` and GitHub OAuth secrets are set).
3. Initialize the DB: `python backend/run_db_init.py`.
4. Start the backend: `uvicorn backend.run_server:app --reload`.
5. Start the frontend: `pnpm dev` (defaults to `http://localhost:5173`, proxying API requests to `/api/*`).

With this baseline, new contributors can quickly find the relevant slice of the codebase whether they are touching the API in `@backend` or the UI in `src/`.
