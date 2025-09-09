# YudaiV3 Production Deployment Guide

## Overview

This guide covers the complete production deployment setup for YudaiV3, including all configuration differences between development and production environments.

## Configuration Files Analysis

### 1. Docker Compose Differences

#### `docker-compose-dev.yml` vs `docker-compose.prod.yml`

**Key Differences:**

| Aspect | Development | Production |
|--------|-------------|------------|
| **Database** | `yudai_dev` | Environment variables (`${POSTGRES_DB}`) |
| **Ports** | DB: 5433, Backend: 8001, Frontend: 3000 | DB: Internal, Backend: 8000, Frontend: 80/443 |
| **Resource Limits** | None | None (unlimited for flexibility) |
| **Security** | Basic | Security hardening, capabilities, privileges |
| **Logging** | Basic | Structured JSON logging with rotation |
| **Health Checks** | Basic | Enhanced with better timing |
| **Volumes** | Development paths | Production backup paths |
| **Environment** | Debug enabled | Production optimized |

**Production-Specific Features:**
- Security hardening (no-new-privileges, apparmor, capability drops)
- Production PostgreSQL tuning (200 connections, 256MB shared buffers, etc.)
- Enhanced health checks with proper timeouts
- Network isolation with custom subnet (172.20.0.0/16)
- Backup volume management
- Unlimited resources for maximum flexibility

### 2. Backend Dockerfile Differences

#### `backend/Dockerfile.dev` vs `backend/Dockerfile`

**Key Differences:**

| Aspect | Development | Production |
|--------|-------------|------------|
| **User** | Root user | Non-root user (`appuser`) |
| **Dependencies** | `libpq-dev` (dev) | `postgresql-client` (minimal) |
| **Caching** | No cache purge | `--no-cache-dir` and `pip cache purge` |
| **Health Check** | 15s interval | 30s interval |
| **Security** | Basic | User permissions, minimal privileges |

**Production Security Features:**
- Non-root user execution
- Minimal system dependencies
- Cache cleanup for smaller image size
- Proper file permissions

### 3. Frontend Dockerfile Differences

#### `Dockerfile.dev` vs `Dockerfile`

**Key Differences:**

| Aspect | Development | Production |
|--------|-------------|------------|
| **Build Process** | Single stage (Vite dev server) | Multi-stage (builder + nginx) |
| **Server** | Vite dev server with hot reload | Nginx alpine for static file serving |
| **Ports** | 3000 (dev) | 80/443 (HTTP/HTTPS) |
| **Static Assets** | Hot reload, source maps | Pre-built optimized assets, minified |
| **Environment** | `NODE_ENV=development` | Production build with `VITE_API_BASE_URL` |
| **Health Check** | Checks `localhost:3000` | Checks `localhost/health` |
| **Image Size** | Larger (includes dev dependencies) | Smaller (only production assets) |
| **Security** | Root user, full Node.js access | Nginx user, read-only static files |

**Production Deployment Impact:**
- **Build Time**: Multi-stage build reduces final image size by ~70-80%
- **Security**: No Node.js runtime in production image, reducing attack surface
- **Performance**: Pre-built optimized assets load faster
- **Resource Usage**: Smaller image footprint, faster container startup
- **SSL Support**: Built-in HTTPS support with certificate mounting
- **Health Monitoring**: Dedicated health endpoint for load balancers

**Build Arguments Required:**
```dockerfile
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
```

**Volume Mounts for SSL:**
```yaml
volumes:
  - /etc/nginx/ssl/fullchain.pem:/etc/nginx/ssl/fullchain.pem:ro
  - /etc/nginx/ssl/privkey.pem:/etc/nginx/ssl/privkey.pem:ro
```

### 4. Nginx Configuration Differences

#### `nginx.dev.conf` vs `nginx.prod.conf`

**Key Differences:**

| Aspect | Development | Production |
|--------|-------------|------------|
| **SSL/TLS** | HTTP only (port 80) | HTTPS with SSL certificates (port 443) |
| **Security Headers** | Minimal (`server_tokens off`) | Comprehensive security headers |
| **CORS Origin** | `http://localhost:3000` | `https://yudai.app` |
| **Server Names** | `localhost` only | Multiple domains + redirect |
| **SSL Protocols** | N/A | TLSv1.2/TLSv1.3 only |
| **HTTP Redirect** | None | Automatic HTTP to HTTPS redirect |
| **Certificate Paths** | N/A | `/etc/nginx/ssl/fullchain.pem` |
| **API Routes Include** | Absolute host path | Container-relative path |

**Production Security Features:**
- **SSL/TLS Encryption**: Full HTTPS with Let's Encrypt certificates
- **Security Headers**:
  - `Strict-Transport-Security`: Forces HTTPS for 1 year
  - `X-Frame-Options`: Prevents clickjacking attacks
  - `X-Content-Type-Options`: Prevents MIME type sniffing
  - `X-XSS-Protection`: Enables XSS filtering
- **Domain-based Routing**: Supports multiple subdomains
- **Certificate-based Authentication**: SSL client certificates ready

**Deployment Impact:**
- **SSL Certificate Management**: Requires Let's Encrypt setup and renewal
- **Domain Configuration**: DNS pointing to server IP required
- **Firewall Rules**: Must allow ports 80/443, block port 3000
- **Certificate Mounting**: Docker volumes for certificate files
- **HTTP Redirect**: All traffic automatically redirected to HTTPS
- **API Route Configuration**: Requires `api-routes.conf` template file

**SSL Certificate Requirements:**
```bash
# Certificate files needed:
/etc/letsencrypt/live/yudai.app/fullchain.pem
/etc/letsencrypt/live/yudai.app/privkey.pem
```

**Domain Configuration Required:**
```bash
# DNS A records:
yudai.app      → YOUR_SERVER_IP
www.yudai.app  → YOUR_SERVER_IP
api.yudai.app  → YOUR_SERVER_IP
dev.yudai.app  → YOUR_SERVER_IP
```

## Production Setup Steps

### Prerequisites

1. **Domain Setup**
   ```bash
   # Point these domains to your server IP:
   # - yudai.app
   # - www.yudai.app
   # - api.yudai.app (optional)
   # - dev.yudai.app (optional)
   ```

2. **SSL Certificates**
   ```bash
   # Install certbot for Let's Encrypt
   sudo apt update
   sudo apt install certbot

   # Generate SSL certificates
   sudo certbot certonly --standalone -d yudai.app -d www.yudai.app

   # Certificates will be saved to:
   # /etc/letsencrypt/live/yudai.app/fullchain.pem
   # /etc/letsencrypt/live/yudai.app/privkey.pem
   ```

3. **Environment Variables Setup**

   Create production environment files:

   **`.env.prod`** (Application Configuration)
   ```bash
   # Domain Configuration
   DOMAIN=yudai.app
   FRONTEND_URL=https://yudai.app
   BACKEND_URL=https://yudai.app/api
   API_DOMAIN=yudai.app
   DEV_DOMAIN=yudai.app

   # Database Configuration
   POSTGRES_DB=yudai_prod
   POSTGRES_USER=yudai_user
   POSTGRES_PASSWORD=your_secure_db_password

   # Authentication
   SECRET_KEY=your_256_bit_secret_key
   JWT_SECRET=your_jwt_secret_key

   # GitHub App OAuth (Production)
   GITHUB_APP_ID=your_github_app_id
   GITHUB_APP_CLIENT_ID=your_github_app_client_id
   GITHUB_APP_CLIENT_SECRET=your_github_app_client_secret
   GITHUB_APP_PRIVATE_KEY_PATH=/app/yudaiv3.2025-08-02.private-key.pem
   GITHUB_APP_INSTALLATION_ID=your_installation_id

   # API Configuration
   HOST=0.0.0.0
   PORT=8000
   SALT=your_salt_value

   # OpenRouter API
   OPENROUTER_API_KEY=your_openrouter_api_key

   # SWE-agent Configuration
   SWEAGENT_CONFIG_PATH=/app/solver/config.yaml
   SWEAGENT_DATA_PATH=/data/swe_runs
   MAX_SOLVE_TIME_MINUTES=30
   MAX_CONCURRENT_SOLVES=3
   SOLVER_TIMEOUT_SECONDS=1800
   ```

## Root Cause Analysis - Issues and Misconfigurations

After comprehensive analysis of the Contract One implementation and the application architecture, the following critical issues and misconfigurations have been identified:

### 🚨 **Critical Configuration Issues**

#### 0. Repository selection breaks in `RepositorySelectionToast.tsx` ❌ NOT FIXED
**Symptom**: After successful auth, repository dropdown fails to load; UI shows an error and no repos are listed.

**What we observed (current code):**
- Frontend uses `buildApiUrl(API.GITHUB.REPOS)` → `${API_BASE}/github/repositories` (in `src/stores/sessionStore.ts:707`).
- Backend exposes both:
  - `GET /github/repositories` (via `backend/github/routes.py` mounted at `/github`)
  - `GET /daifu/github/repositories` (duplicated under `backend/daifuUserAgent/session_routes.py` mounted at `/daifu`)
- Dev setup sets `VITE_API_BASE_URL=http://localhost:8001/api` (see `docker-compose-dev.yml:126`).
- Vite proxy forwards `/api/*` to `target` without path rewrite (see `vite.config.ts`), so a request to `/api/github/repositories` becomes `http://localhost:8001/api/github/repositories` which the backend does not serve (no `/api` prefix in FastAPI).

**Root cause (dev):** Path-prefix mismatch. In dev there is no nginx to strip `/api`, and the Vite proxy does not rewrite `/api` → `/`. Combined with `VITE_API_BASE_URL` including `/api`, calls hit `http://localhost:8001/api/...` and 404.

**Root cause (prod sanity):** Nginx template correctly rewrites `/api/*` to backend root (see `nginx/templates/api-routes.conf`), so prod is fine as long as `VITE_API_BASE_URL` is set to `https://<host>/api`. The breakage is primarily in the dev path.

**Fix required (dev):** Choose one consistent approach:
- Option A (recommended): Set `VITE_API_BASE_URL=http://localhost:8001` for dev and add a Vite proxy rewrite so `'/api'` is stripped:
  - In `vite.config.ts` under `server.proxy['/api']`, add `rewrite: (path) => path.replace(/^\/api/, '')`.
  - Keep frontend using `API_BASE='/api'` by default for local dev convenience.
- Option B: Keep `VITE_API_BASE_URL=http://localhost:8001/api` and remove the Vite `/api` proxy entirely so requests go directly to the backend URL. Ensure all frontend calls are absolute and include the correct base.

Until this is applied, repo selection will continue to fail despite the correct `API.GITHUB.REPOS` usage.

#### 1. **API Configuration Inconsistency** ✅ **FIXED**
**Issue**: The frontend uses two different API imports:
- `src/stores/sessionStore.ts` imports `API_CONFIG` (line 25)
- `src/config/api.ts` exports `API` but not `API_CONFIG`

**Impact**: Runtime errors when sessionStore methods are called
**Fix Applied**: Updated sessionStore.ts to import and use `API` instead of `API_CONFIG`, fixed all 19 endpoint references

#### 2. **Solver Endpoint Mismatch** ❌ NOT FIXED
**Issue**: Frontend solver implementation has inconsistent endpoint usage:
- Direct fetch call in `Chat.tsx` line 423: `/api/sessions/${activeSessionId}/solve/start`
- Hook in `useSessionQueries.ts` line 502: `API_CONFIG.SESSIONS.SOLVER.START` (undefined)

**Impact**: Solver functionality completely broken
**Fix Required**: Standardize all solver calls to use the proper API endpoints (use `API.SESSIONS.SOLVER.START/STATUS/CANCEL` via `buildApiUrl`, remove hard-coded `/api/...`).

#### 3. **Missing GitHub Issue Creation Route** ✅ FIXED
**Issue**: Frontend calls `API_CONFIG.SESSIONS.ISSUES.CREATE_GITHUB_ISSUE` but this route doesn't exist in `api.ts`
**Backend Route**: `/sessions/{session_id}/issues/{issue_id}/create-github-issue`
**Fix Applied**: Added `CREATE_GITHUB_ISSUE` endpoint to API configuration and updated sessionStore to use it

### ⚠️ **Functional Issues**

#### 4. **Dual Issue Creation Endpoints Confusion**
**Issue**: Two similar but different issue creation workflows:

1. **`createIssueWithContext`** (Chat.tsx "Create Issue" button):
   - Creates UserIssue record in database
   - Generates issue preview using LLM
   - Shows modal for GitHub issue creation

2. **`createGitHubIssueFromUserIssue`** (DiffModal "Create GitHub Issue" button):
   - Takes existing UserIssue and creates actual GitHub issue
   - Updates UserIssue with GitHub URL

**Current Problem**: Frontend implementation incorrectly treats these as duplicates
**Fix Required**: Ensure proper workflow: CreateIssue → Preview → CreateGitHubIssue

#### 5. **File Embedding Data Exposure** ✅ FIXED
**Issue**: Frontend types include embedding vector fields unnecessarily:
- `CreateFileEmbeddingRequest` should not include embedding vector data
- Frontend only needs file metadata, not vector embeddings

**Security/Performance Impact**: 
- Unnecessary data transfer
- Potential exposure of embedding vectors to frontend
**Current Status**: Frontend types no longer expose embeddings or raw chunk vectors (`src/types/sessionTypes.ts`), only file metadata is sent/received.

#### 6. **Solver Backend Integration Gap** ⚠️ PARTIAL
**Issue**: Solver endpoints exist in backend but are not properly integrated:
- Routes exist: `/solve/start`, `/solve/sessions/{id}`, `/solve/cancel`
- Frontend has partial implementation but uses wrong API configuration
- No proper error handling or status tracking

**Impact**: AI solving functionality completely non-functional
**Fix Required**: Complete solver integration using `API.SESSIONS.SOLVER.*` consistently; remove hard-coded `fetch('/api/...')` in `Chat.tsx` and wire status polling.

### 🔧 **Implementation Issues**

#### 7. **File Dependencies Processing** ✅ CLARIFIED
**Issue**: File embeddings are intended for backend semantic search only, but frontend types suggest client-side processing:
```typescript
// This should not exist in frontend
embedding?: Vector // pgvector data
chunk_text: string // Raw text chunks
```

**Clarification**: Frontend should only receive:
- File metadata (name, path, type, tokens)
- Not embedding vectors or raw content chunks

#### 8. **Session Context Loading Inconsistency** ⚠️ PARTIAL
**Issue**: Session loading uses different API patterns:
- Some methods use `API.SESSIONS.DETAIL`
- Others use direct fetch with manual URL construction
- sessionStore methods inconsistent with useSessionQueries hooks

**Impact**: Potential data synchronization issues
**Current Status**: Most calls are unified through Zustand store (`useSessionStore` and `useSessionQueries`). Remaining outlier: solver call in `src/components/Chat.tsx` uses a hard-coded `fetch('/api/...')`.
**Fix Required**: Standardize remaining outliers to `API` + `buildApiUrl`.

#### 9. **Missing API Routes in Configuration** ⚠️ PARTIAL
**Current State in `src/config/api.ts`:**
- `SESSIONS.ISSUES.CREATE_GITHUB_ISSUE` present.
- `SESSIONS.SOLVER.START`, `SESSIONS.SOLVER.STATUS`, `SESSIONS.SOLVER.CANCEL` present.
- No explicit `SESSIONS.STATS` endpoint; if needed, add later when backend supports it.

**Action**: Use existing `STATUS` for solver session tracking; add any missing routes only when required by UI.

#### 10. **Environment Variable Inconsistencies**
**Issue**: Different environment handling between dev/prod and missing path rewrite in dev:
- Development (current): `VITE_API_BASE_URL=http://localhost:8001/api` → conflicts with Vite proxy that does not rewrite `/api`.
- Production: `VITE_API_BASE_URL=/api` (fine behind nginx where `/api` is rewritten).
- Some hardcoded URLs in solver implementation.

**Impact**: Repo selection and solver calls 404 in dev due to double `/api` prefix; inconsistent behavior between dev and prod.
**Fix Required**: For dev set `VITE_API_BASE_URL=http://localhost:8001` and add Vite proxy rewrite `'/api'` → `''`. Ensure all API calls use `API` + `buildApiUrl`.

### 📋 **Priority Fix List**

1. **CRITICAL**: Fix API_CONFIG vs API import issue in sessionStore.ts
2. **CRITICAL**: Add missing API routes to api.ts configuration
3. **HIGH**: Complete solver endpoint integration 
4. **HIGH**: Clarify and fix dual issue creation workflow
5. **MEDIUM**: Remove unnecessary embedding data from frontend types
6. **MEDIUM**: Standardize session API call patterns
7. **LOW**: Update environment variable documentation

### 🔍 **Recommended Immediate Actions**

1. **Update sessionStore.ts**: Change `API_CONFIG` to `API` throughout
2. **Complete api.ts**: Add all missing SOLVER and GitHub issue routes  
3. **Fix solver integration**: Ensure Chat.tsx uses proper API configuration
4. **Document workflows**: Clarify issue creation vs GitHub issue creation flows
5. **Clean frontend types**: Remove backend-only fields from file embedding types

### 🎯 **Architecture Validation**

**Contract One Implementation**: ✅ **Correct**
- Nginx properly strips `/api/` prefix
- Backend routes properly configured
- Frontend API calls correctly prefixed

**Context Cards & File Dependencies**: ✅ **Fixed** 
- Routes properly added to both frontend and backend
- Backend endpoints verified and working

**Issue Creation Workflow**: ⚠️ **Needs Clarification**
- Two-step process is correct but poorly documented
- Frontend implementation needs cleanup

**Solver Integration**: ❌ **Broken**
- API configuration incomplete
- Frontend implementation inconsistent  
- Requires immediate attention

## Extended Root Cause Analysis - Implementation Gaps & Critical Issues

After analyzing the recent changes and documentation additions, additional critical implementation gaps and architectural problems have been identified:

### 🚨 **Backend Implementation Gaps (From TODO Documentation)**

#### 11. **LLM Service Integration Inconsistencies**
**Issue**: Conflicting method references and incomplete implementations:
- `session_routes.py` line 13 documents: "The chat endpoint calls LLMService.generate_response_with_history() which doesn't exist"
- But `llm_service.py` line 187 **DOES implement** `generate_response_with_history()` method
- `ChatOps.py` line 13 claims: "_generate_ai_response() method is a placeholder" but it's actually implemented

**Impact**: Documentation is outdated and misleading, causing confusion about actual implementation status
**Root Cause**: Documentation not synchronized with actual code state

#### 12. **Database Schema Drift and Inconsistencies**
**Issue**: Multiple database initialization methods with different schemas:
- `db/init.sql` contains complete schema with all tables
- `db/init_db.py` contains partial schema missing critical tables
- Models in `models.py` don't match either init script exactly

**Specific Schema Problems**:
```sql
-- MISSING in init_db.py but EXISTS in init.sql:
CREATE TABLE chat_sessions (...);
CREATE TABLE chat_messages (...);
CREATE TABLE context_cards (...);
CREATE TABLE file_embeddings (...);
CREATE TABLE ai_solve_sessions (...);
```

**Impact**: Database initialization will fail depending on which method is used
**Production Risk**: Critical - deployment will fail with missing tables

#### 13. **Foreign Key Constraint Violations**
**Issue**: Multiple foreign key relationships have constraint validation problems:

**UserIssue Model** (line 557-558 in models.py):
```python
context_card_id: Mapped[Optional[int]] = mapped_column(
    ForeignKey("context_cards.id"), nullable=True
)
```
But no foreign key constraint exists in database initialization scripts.

**Missing Cascade Deletes**:
- `user_issues.context_card_id` → `context_cards.id` (no CASCADE)
- `file_embeddings.session_id` → `chat_sessions.id` (no CASCADE) 
- `ai_solve_sessions.issue_id` → `issues.id` (no CASCADE)

**Impact**: Orphaned records and referential integrity violations
**Production Risk**: Data corruption and cascade delete failures

#### 14. **Service Layer Architecture Inconsistencies** 
**Issue**: Inconsistent service layer patterns across modules:

**IssueOps.py** (lines 13-16):
- Documents "Implement IssueService.update_issue_status() with actual LLM calls"
- But IssueService class doesn't have update_issue_status() method
- Method exists in session_service.py with different signature

**ChatOps vs ChatService** confusion:
- `ChatOps.py` exists as operational class
- No `ChatService` in session_service.py
- Inconsistent naming patterns across service modules

**Impact**: Service layer coupling and circular dependencies
**Code Quality**: Poor separation of concerns

#### 15. **Authentication & Authorization Gaps**
**Issue**: Multiple security validation gaps documented:

**From session_routes.py** (lines 44-48):
- "Ensure all endpoints properly validate user access"
- "Add role-based access control where needed" 
- "Implement proper session token validation"
- "Add audit logging for sensitive operations"

**Specific Security Issues**:
- No role-based access control implemented
- Missing audit logging for GitHub API calls
- Session token validation incomplete
- No rate limiting on API endpoints

**Impact**: Security vulnerabilities in production
**Compliance Risk**: Audit trail gaps

#### 16. **GitHub API Integration Reliability Issues**(NOT REQUIRED TO SOLVE RIGHT NOW)
**Issue**: Documented reliability problems across multiple modules:

**From ChatOps.py** (lines 19-22):
- "Implement exponential backoff for rate limits"
- "Add proper error recovery for network failures" 
- "Handle GitHub API token refresh scenarios"

**From IssueOps.py** (lines 18-22):
- "Implement robust GitHub API error handling"
- "Handle GitHub API rate limiting with exponential backoff"
- "Add GitHub webhook integration for issue updates"

**Impact**: GitHub API failures will cause system-wide issues
**Production Risk**: Service degradation during GitHub API issues

### 🔧 **Database Architecture Problems**

#### 17. **Missing Database Indexes and Performance Issues**
**Issue**: No performance optimization documented or implemented:

**From session_routes.py** (lines 36-40):
- "Add proper indexing for all query operations"
- "Implement database connection pooling" 
- "Add query result caching (Redis)"
- "Optimize bulk operations for messages and context cards"

**Missing Indexes**:
```sql
-- Critical missing indexes:
CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX idx_file_embeddings_session_id ON file_embeddings(session_id);
CREATE INDEX idx_user_issues_session_id ON user_issues(session_id);
```

**Impact**: Poor query performance with large datasets
**Scalability Risk**: System will degrade with user growth

#### 18. **Vector Database Configuration Issues** ✅ **FIXED**
**Issue**: pgvector extension and embedding storage problems:

**From llm_service.py** implementation:
- Uses `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- But models.py line 630 specified `Vector(1536)` (OpenAI dimensions)
- Dimension mismatch caused insertion failures

**Fix Applied**:
- ✅ Updated `backend/models.py` to use `Vector(384)`
- ✅ Updated `backend/db/init.sql` to use `VECTOR(384)`
- ✅ Updated `backend/db/init_db.py` to use `VECTOR(384)`
- ✅ Added missing vector index with ivfflat for cosine distance
- ✅ Updated comments to reflect sentence-transformers model

**Status**: Vector database configuration now properly aligned with LLM service
**Impact**: Embedding functionality restored and file context search operational

### 📊 **Integration & Workflow Problems**

#### 19. **Session Management Lifecycle Issues**
**Issue**: Multiple session management gaps documented:

**From session_routes.py** (lines 24-28):
- "Add session timeout and cleanup mechanisms"
- "Implement session persistence across browser sessions"
- "Add session export/import functionality" 
- "Implement session collaboration features"

**Session State Problems**:
- No session expiration handling
- No session cleanup on user logout
- Session tokens can accumulate indefinitely
- No session sharing or collaboration support

**Impact**: Memory leaks and session accumulation
**Resource Risk**: Server resource exhaustion

#### 20. **Message Threading and Context Window Issues**
**Issue**: Chat message management gaps:

**From session_routes.py** (lines 56-60):
- "Add message search and filtering capabilities"
- "Implement message threading and conversation management"
- "Add message export/import functionality"
- "Support message attachments and rich content"

**Context Window Problems**:
- No message context window management
- No conversation threading
- No message deduplication
- Limited to basic text messages

**Impact**: Poor conversation experience
**User Experience**: Degraded chat functionality

### 📋 **Extended Priority Fix List**

**CRITICAL (Production Blocking)**:
1. Fix database schema initialization inconsistencies
2. Resolve foreign key constraint violations
3. ✅ Fix vector database dimension mismatch - COMPLETED
4. Complete missing table creation in init_db.py

**HIGH (Core Functionality)**:
5. Implement missing database indexes for performance
6. Add proper cascade delete constraints
7. Implement GitHub API error handling and rate limiting
8. Add security audit logging and access control

**MEDIUM (Feature Gaps)**:
9. Implement session lifecycle management
10. Add message threading and context management
11. Complete service layer architecture standardization
12. Add proper error handling across all endpoints

**LOW (Technical Debt)**:
13. Synchronize TODO documentation with actual implementation
14. Standardize service layer naming conventions
15. Add comprehensive API documentation
16. Implement proper logging configuration

### 🎯 **Critical Production Readiness Assessment**

**Database Layer**: ⚠️ **PARTIAL RESOLUTION**
- Schema initialization inconsistencies will cause deployment failures
- Missing foreign key constraints risk data corruption
- ✅ Vector database configuration fixed - embedding functionality restored

**API Layer**: ⚠️ **PARTIAL IMPLEMENTATION**
- Core endpoints exist but lack proper error handling
- No rate limiting or security validation
- GitHub API integration unreliable

**Security Layer**: ❌ **MAJOR GAPS**
- No role-based access control
- Missing audit logging
- Session management incomplete

**Performance Layer**: ❌ **NOT OPTIMIZED**
- No database indexes for query performance
- No connection pooling or caching
- Bulk operations not optimized

**Conclusion**: Current implementation has critical gaps. Immediate blockers for basic flow are dev API path mismatch (repo selection) and solver endpoint inconsistency. ✅ Database vector dimension mismatch resolved - embedding features now operational. Security and performance hardening remain open for production readiness.

## NEXT STEPS
 #TODOS: prod likely fixed
Phase 0 — Unblock Repository Selection (prod) (Li) 
- Fix `VITE_API_BASE_URL` in dev to `http://localhost:8001` (not including `/api`).
- Add Vite proxy rewrite for `'/api'` → `''` in `vite.config.ts` under `server.proxy['/api']`.
- Alternatively, remove the `/api` proxy and keep absolute `VITE_API_BASE_URL` without `/api`.
- Verify `GET /github/repositories` returns 200 with `Authorization: Bearer <session_token>` after login.

Phase 1 — Unify Frontend API Usage
#TODOs: unified the api but also changed Solver types make sure CHAT and ISSUES work before jumping SOLVER
- Replace hard-coded `fetch('/api/...')` usages in `src/components/Chat.tsx` with `API` + `buildApiUrl` (solver start and future status/cancel).
- Ensure repository branches call uses `API.GITHUB.REPO_BRANCHES` everywhere (already done in `sessionStore`).
- Remove any lingering `API_CONFIG` references (current code appears clean).

Phase 2 — Solver Integration Completion
- Wire `useStartSolveSession` everywhere solver is triggered; add polling using `API.SESSIONS.SOLVER.STATUS`.
- Add basic UI state: starting, in-progress, completed, failed.
- Handle 4xx/5xx with user-friendly errors and retries.

Phase 3 — Embedding Pipeline Alignment
- Decide on embedding dimension: switch DB to `VECTOR(384)` or switch model to 1536-d.
- Update `backend/db/init_db.py` and `backend/models.py` or `LLMService.embed_text()` accordingly.
- Add migration for existing `file_embeddings.embedding` column.

Phase 4 — Security & Observability
- Add audit logging for GitHub API calls and session actions.
- Rate limit critical endpoints (auth, repo listing, solver start).
- Expand `ALLOW_ORIGINS` as env var with clear docs for prod.
- Add structured JSON logging and request IDs end-to-end.

Phase 5 — Performance & DB Health
- Create missing indexes listed in this doc where applicable; verify with `EXPLAIN`.
- Add connection pooling and optional Redis caching.
- Verify health checks and tighten timeouts in docker-compose and nginx.

Phase 6 — Cleanup & Consistency
- Consider removing duplicated GitHub routes under `/daifu/github/*` or switch frontend to use them consistently.
- Standardize service layer naming (`*Ops` vs `*Service`) and move shared logic behind clear interfaces.
- Document final API surface in `src/config/api.ts` and backend docs.
