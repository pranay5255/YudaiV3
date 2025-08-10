### YudaiV3: Breaking Issues, Improvements, and Open Questions

### Backend: Breaking functionality by folder

- **backend/run_server.py**
  - **CORS origins**: Hardcoded to `http://localhost:3000`, `http://localhost:5173`, `https://yudai.app`. If frontend served elsewhere, requests will be blocked.
  - **Router prefixes vs. frontend**: Routers are mounted at `"/auth"`, `"/github"`, `"/daifu"`, `"/issues"`, `"/filedeps"`. Several frontend paths don’t match these (see table below).

- **backend/auth/**
  - `auth_routes.py`
    - Login flow relies on `CLIENT_ID`/`CLIENT_SECRET`; missing envs returns HTTP 500 from `/auth/api/login`.
    - Session token is returned via OAuth callback querystring (`session_token`), but most protected backend endpoints do NOT accept this token for auth.
  - `github_oauth.py`
    - `get_current_user` expects a Bearer token that matches an active row in `AuthToken` (GitHub access token), not the session token returned to the frontend. This conflicts with how the frontend authenticates subsequent calls.
    - Redirect URI defaults to production `https://yudai.app/auth/callback`; local callback requires env override.

- **backend/github/**
  - `github_routes.py`
    - All routes depend on `get_current_user` (GitHub token required). Frontend sends session token, causing 401/403.
  - `github_api.py`
    - Assumes valid GitHub token available per-user; no graceful degradation path without GitHub token.

- **backend/stateManagement/**
  - `session_routes.py`
    - Endpoints require `get_current_user` (GitHub token). Frontend provides session token header → 401/403.
    - Response models are fine, but session lifecycle depends on auth mismatch above.

- **backend/daifuUserAgent/**
  - `chat_api.py`
    - Route paths defined as `"/chat/daifu"` and `"/chat/create-issue"` are mounted under `"/daifu"` prefix → final paths are `"/daifu/chat/daifu"` and `"/daifu/chat/create-issue"`. Frontend calls `"/chat/..."` (missing `/daifu`), causing 404.
    - `ChatRequest` usage expects `request.repository.owner/name`, but model defines `repo_owner`/`repo_name` fields. This will raise runtime attribute errors.
    - Depends on `get_current_user` (GitHub token). Frontend sends session token.
  - `llm_service.py`
    - Likely requires external model API keys/config; no guards for missing keys.
  - `message_service.py`
    - Stores messages; relies on valid session/user; blocked if auth mismatch.

- **backend/repo_processorGitIngest/**
  - `filedeps.py`
    - Router prefix mounted at `"/filedeps"`. Frontend calls `"/file-dependencies/..."` and different endpoints → 404.
    - Endpoints require `get_current_user` (GitHub token). Frontend sends session token.
    - `get_or_create_repository` generates `github_repo_id` from URL hash; model now allows non-unique field, OK.

- **backend/db/**
  - `database.py`
    - `init_db()` uses `Base.metadata.create_all` only; no migrations. Schema drift requires manual cleanup.
    - Sample data helpers reference real tables but aren’t gated behind env.

- **backend/models.py**
  - `Repository.github_repo_id` added as optional, indexed, non-unique (resolved previous unique constraint issue). If a unique index still exists in DB (from earlier runs), a migration/drop index is needed.
  - `ChatRequest` doesn’t include `repository` object but `chat_api.py` uses it.

- **backend/issueChatServices/**
  - Business logic likely OK, but endpoints behind auth mismatch.

### Frontend: Breaking functionality

- **src/services/api.ts**
  - Uses `Authorization: Bearer <session_token>` for all protected endpoints. Backend expects GitHub access token (from OAuth) for `/github`, `/daifu`, `/filedeps`.
  - Path mismatches:
    - Sends `POST ${API_BASE_URL}/chat/daifu` and `POST ${API_BASE_URL}/chat/create-issue`; backend paths are under `/daifu/chat/...`.
    - File deps: uses `/file-dependencies/analyze` and `/file-dependencies/{id}`; backend uses `/filedeps/extract` and `/filedeps/repositories/{id}/files`.
    - Repository mgmt: uses `/repositories` and `/repositories/{owner}/{name}` under `API_BASE_URL` (which prefixes `/api`). Backend mounts GitHub router under `/github/...` and filedeps under `/filedeps/...`.
  - `createSession`, `getSessionContext` target `/daifu/sessions` (correct), but still send session token instead of GitHub token.

- **src/contexts/AuthProvider.tsx**
  - Stores `session_token` from OAuth callback and uses `/auth/api/user` to validate. Does not store GitHub access token required by backend protected routes.

- **src/contexts/SessionProvider.tsx**
  - `loadRepositories()` calls `api.getUserRepositories()` which hits `/github/repositories` with session token → 401/403.

- **src/App.tsx and components**
  - App expects authenticated flow working; repository selection toast depends on successful `/github` calls.

### Cross-cutting breaking changes

| **Area** | **Frontend Path/Auth** | **Backend Path/Auth** | **Dependency** | **Impact** | **Suggested fix** |
|---|---|---|---|---|---|
| Chat send | `POST /chat/daifu` using session token | `POST /daifu/chat/daifu` requires GitHub Bearer | Router prefix, auth scheme | 404 or 401/403 | Align path to `/daifu/chat/daifu`; change backend to accept session token or frontend to send GitHub token |
| Chat create-issue | `POST /chat/create-issue` using session token | `POST /daifu/chat/create-issue` requires GitHub Bearer | Router prefix, auth | 404 or 401/403 | Same as above |
| Session create/context | `POST/GET /daifu/sessions` using session token | `POST/GET /daifu/sessions` requires GitHub Bearer | Auth scheme | 401/403 | Accept session token in `get_current_user` or add parallel session-token dependency |
| GitHub repos/details | `GET /github/...` using session token | `GET /github/...` requires GitHub Bearer | Auth scheme | 401/403 | Same as above |
| File deps extract/files | `POST /file-dependencies/analyze`, `GET /file-dependencies/{id}` | `POST /filedeps/extract`, `GET /filedeps/repositories/{id}/files` | Path mismatch, auth | 404 and/or 401/403 | Align endpoint names and auth |
| OAuth callback | Frontend reads `session_token` from URL | Backend returns session token; GitHub token only in DB | Token strategy | Subsequent calls fail auth | Decide single token of record; either issue frontend-usable JWT or let backend accept session token as Bearer |
| ChatRequest shape | Sends `repoOwner/repoName` (varies) | Backend `chat_api.py` expects `request.repository.owner/name` | Model-contract mismatch | 500 at runtime | Standardize `ChatRequest` to `repo_owner`/`repo_name` and update backend usage |
| DB schema: github_repo_id | Tests reusing same ID previously failed | Now non-unique field; DB index may still be unique from earlier runs | Migration | Inserts can still fail if unique index remains | Drop old unique index or reset DB |
| CORS | Depends on origin | Whitelist limited | Deployment env | Requests blocked | Expand `allow_origins` via env |

### Open questions to finalize the build

- **Auth strategy**: Should protected APIs accept the frontend `session_token` as the Bearer credential, or should the frontend store and send the GitHub access token? Preferred approach: issue a backend-signed session JWT and accept it everywhere.
- **API base path**: Should the frontend use a unified proxy (`/api`) that maps to the backend prefixes (`/auth`, `/github`, `/daifu`, `/issues`, `/filedeps`), or should it call those prefixes directly? If proxying, provide the mapping.
- **ChatRequest contract**: Confirm the canonical schema: keep `repo_owner`/`repo_name` or introduce a `repository` object? I recommend keeping flat fields to match existing Pydantic models and update `chat_api.py` accordingly.
- **File dependencies API**: Confirm desired public routes and names: `filedeps` vs `file-dependencies`, and the exact endpoints (`/extract`, `/repositories/{id}/files`, etc.).
- **Tokens and headers**: If we keep session tokens, do we still need per-user GitHub tokens on each API call, or should the backend resolve GitHub tokens server-side from the user session?
- **Local vs prod callback**: What should be the default OAuth redirect URI for local dev? Provide `.env` guidance.
- **Migrations**: Is wiping/recreating the DB acceptable now, or should we add Alembic migrations (e.g., dropping the old unique index on `repositories.github_repo_id`)?
- **LLM config**: Which provider and model are we using for `LLMService`? Where do keys live and what are fallback behaviors when absent?
- **Rate limiting / retries**: Any constraints for GitHub API usage that require caching or backoff?

### High-priority fixes (suggested order)

1. Unify auth: update backend to accept `session_token` as Bearer for protected routes (or return/store GitHub token on frontend consistently).
2. Align API paths between frontend and backend (`/daifu/chat/...`, `/filedeps/...`).
3. Fix `chat_api.py` to use `repo_owner`/`repo_name` from `ChatRequest` (or update model and frontend accordingly).
4. Ensure DB index on `repositories.github_repo_id` is non-unique in the live database.
5. Provide dev `.env` with `CLIENT_ID`, `CLIENT_SECRET`, and local `GITHUB_REDIRECT_URI`.
