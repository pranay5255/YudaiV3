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

#### 1. **API Configuration Inconsistency**
**Issue**: The frontend uses two different API imports:
- `src/stores/sessionStore.ts` imports `API_CONFIG` (line 25)
- `src/config/api.ts` exports `API` but not `API_CONFIG`

**Impact**: Runtime errors when sessionStore methods are called
**Fix Required**: Update sessionStore.ts to use `API` instead of `API_CONFIG`

#### 2. **Solver Endpoint Mismatch** 
**Issue**: Frontend solver implementation has inconsistent endpoint usage:
- Direct fetch call in `Chat.tsx` line 423: `/api/sessions/${activeSessionId}/solve/start`
- Hook in `useSessionQueries.ts` line 502: `API_CONFIG.SESSIONS.SOLVER.START` (undefined)

**Impact**: Solver functionality completely broken
**Fix Required**: Standardize all solver calls to use the proper API endpoints

#### 3. **Missing GitHub Issue Creation Route**
**Issue**: Frontend calls `API_CONFIG.SESSIONS.ISSUES.CREATE_GITHUB_ISSUE` but this route doesn't exist in `api.ts`
**Backend Route**: `/sessions/{session_id}/issues/{issue_id}/create-github-issue`
**Fix Required**: Add missing route to frontend API configuration

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

#### 5. **File Embedding Data Exposure**
**Issue**: Frontend types include embedding vector fields unnecessarily:
- `CreateFileEmbeddingRequest` should not include embedding vector data
- Frontend only needs file metadata, not vector embeddings

**Security/Performance Impact**: 
- Unnecessary data transfer
- Potential exposure of embedding vectors to frontend
**Fix Required**: Remove embedding vector fields from frontend types

#### 6. **Solver Backend Integration Gap**
**Issue**: Solver endpoints exist in backend but are not properly integrated:
- Routes exist: `/solve/start`, `/solve/sessions/{id}`, `/solve/cancel`
- Frontend has partial implementation but uses wrong API configuration
- No proper error handling or status tracking

**Impact**: AI solving functionality completely non-functional
**Fix Required**: Complete solver integration with proper API configuration

### 🔧 **Implementation Issues**

#### 7. **File Dependencies Processing**
**Issue**: File embeddings are intended for backend semantic search only, but frontend types suggest client-side processing:
```typescript
// This should not exist in frontend
embedding?: Vector // pgvector data
chunk_text: string // Raw text chunks
```

**Clarification Needed**: Frontend should only receive:
- File metadata (name, path, type, tokens)
- Not embedding vectors or raw content chunks

#### 8. **Session Context Loading Inconsistency**
**Issue**: Session loading uses different API patterns:
- Some methods use `API.SESSIONS.DETAIL`
- Others use direct fetch with manual URL construction
- sessionStore methods inconsistent with useSessionQueries hooks

**Impact**: Potential data synchronization issues
**Fix Required**: Standardize all session API calls

#### 9. **Missing API Routes in Configuration**
**Issues Found**:
```typescript
// Missing from src/config/api.ts:
SESSIONS.ISSUES.CREATE_GITHUB_ISSUE  // For DiffModal
SESSIONS.SOLVER.SESSION_DETAIL       // For solver status
SESSIONS.SOLVER.SESSION_STATS        // For solver monitoring  
SESSIONS.SOLVER.LIST_SESSIONS        // For solver history
SESSIONS.SOLVER.HEALTH               // For solver health checks
```

#### 10. **Environment Variable Inconsistencies**
**Issue**: Different environment handling between dev/prod:
- Development: `VITE_API_BASE_URL=http://localhost:8001/api`
- Production: `VITE_API_BASE_URL=/api`
- Some hardcoded URLs in solver implementation

**Impact**: Solver and some API calls may fail in production
**Fix Required**: Ensure all API calls use environment-aware base URL

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

#### 16. **GitHub API Integration Reliability Issues**
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

#### 18. **Vector Database Configuration Issues**
**Issue**: pgvector extension and embedding storage problems:

**From llm_service.py** implementation:
- Uses `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)
- But models.py line 630 specifies `Vector(1536)` (OpenAI dimensions)
- Dimension mismatch will cause insertion failures

**Missing Vector Configuration**:
```sql
-- Missing from database init:
CREATE EXTENSION IF NOT EXISTS vector;
CREATE INDEX ON file_embeddings USING ivfflat (embedding);
```

**Impact**: Embedding functionality completely broken
**Production Risk**: File context search will fail

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
3. Fix vector database dimension mismatch
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

**Database Layer**: ❌ **CRITICAL ISSUES**
- Schema initialization inconsistencies will cause deployment failures
- Missing foreign key constraints risk data corruption
- Vector database misconfiguration breaks embedding functionality

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

**Conclusion**: Current implementation has **CRITICAL BLOCKING ISSUES** that prevent safe production deployment. Database schema inconsistencies and security gaps must be resolved before any production release.

 