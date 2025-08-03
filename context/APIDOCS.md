# YudaiV3 Backend API Documentation

**Last Updated**: January 2025  
**Version**: 1.0.0  
**Status**: 🟡 PARTIALLY READY - CRITICAL FIXES REQUIRED  
**Base URL**: `http://localhost:8000` (dev), `https://yudai.app/api` (prod)

## 🚨 CRITICAL NOTICE

**This API is NOT DEMO READY** - Several critical issues must be resolved before production deployment:
- 🔒 Security vulnerabilities in WebSocket authentication
- 💾 Missing pgvector database extension
- 🐛 File dependencies service broken
- ⚠️ Debug code exposed in production

---

## 📋 QUICK REFERENCE

| Service | Prefix | Status | Endpoints | Issues |
|---------|--------|--------|-----------|--------|
| Authentication | `/auth` | ✅ Stable | 6 | None |
| GitHub Integration | `/github` | ✅ Stable | 8 | None |
| Chat Services | `/daifu` | ⚠️ Partial | 12 | Security, consistency |
| Issue Management | `/issues` | ✅ Stable | 7 | None |
| File Dependencies | `/filedeps` | ❌ Broken | 4 | Core functionality |

**Total Endpoints**: 37 | **Working**: 31 (84%) | **Broken**: 6 (16%)

---

## 🏗️ UNIFIED FASTAPI ARCHITECTURE

### Core Server Structure
```python
# backend/run_server.py
app = FastAPI(
    title="YudaiV3 Backend API",
    description="Unified backend API for YudaiV3",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)
```

### Service Mounting
```python
app.include_router(auth_router, prefix="/auth", tags=["authentication"])
app.include_router(github_router, prefix="/github", tags=["github"])
app.include_router(daifu_router, prefix="/daifu", tags=["chat"])
app.include_router(issue_router, prefix="/issues", tags=["issues"])
app.include_router(filedeps_router, prefix="/filedeps", tags=["file-dependencies"])
```

### Database Layer
- **Engine**: PostgreSQL with SQLAlchemy ORM
- **Connection Pool**: 20 connections, 30 max overflow
- **Extensions**: **❌ MISSING pgvector** (critical for file embeddings)

---

## 🔐 AUTHENTICATION SERVICE (`/auth`) ✅ STABLE

**Purpose**: GitHub OAuth2 authentication with JWT token management  
**Implementation**: `backend/auth/auth_routes.py`  
**Status**: Production ready, no known issues

### Endpoints

#### `GET /auth/login`
**Purpose**: Initiate GitHub OAuth2 flow  
**Authentication**: None required  
**Response**: Redirects to GitHub OAuth page

```bash
curl -X GET "http://localhost:8000/auth/login"
```

#### `GET /auth/callback`
**Purpose**: Handle GitHub OAuth callback with authorization code  
**Parameters**: 
- `code` (query): OAuth authorization code
- `state` (query): OAuth state parameter

```bash
curl -X GET "http://localhost:8000/auth/callback?code=123&state=xyz"
```

#### `GET /auth/profile`
**Purpose**: Get authenticated user profile  
**Authentication**: Bearer token required  
**Response**: Complete user profile object

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/auth/profile"
```

#### `POST /auth/logout`
**Purpose**: Invalidate user session and token  
**Authentication**: Bearer token required

```bash
curl -X POST -H "Authorization: Bearer <token>" "http://localhost:8000/auth/logout"
```

#### `GET /auth/status`
**Purpose**: Check current authentication status  
**Authentication**: Optional Bearer token

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/auth/status"
```

#### `GET /auth/config`
**Purpose**: Get public authentication configuration  
**Authentication**: None required

```bash
curl "http://localhost:8000/auth/config"
```

### Authentication Flow
```
1. Frontend → GET /auth/login → Redirect to GitHub
2. GitHub → GET /auth/callback?code=xxx → Exchange for token
3. Backend → Store user & token → Return JWT to frontend
4. Frontend → Store token → Use in Authorization header
```

---

## 🐙 GITHUB INTEGRATION SERVICE (`/github`) ✅ STABLE

**Purpose**: Full GitHub API integration for repository and issue management  
**Implementation**: `backend/github/github_routes.py`  
**Status**: Production ready, comprehensive GitHub integration

### Repository Management

#### `GET /github/repositories`
**Purpose**: Get user's GitHub repositories  
**Authentication**: Bearer token required  
**Response**: List of repositories with metadata

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/github/repositories"
```

#### `GET /github/repositories/{owner}/{repo}`
**Purpose**: Get specific repository details  
**Authentication**: Bearer token required

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/github/repositories/owner/repo"
```

#### `GET /github/repositories/{owner}/{repo}/branches`
**Purpose**: List repository branches  
**Authentication**: Bearer token required

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/github/repositories/owner/repo/branches"
```

### Issue Management

#### `GET /github/repositories/{owner}/{repo}/issues`
**Purpose**: List repository issues  
**Authentication**: Bearer token required  
**Parameters**: Standard GitHub API filters

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/github/repositories/owner/repo/issues"
```

#### `POST /github/repositories/{owner}/{repo}/issues`
**Purpose**: Create new issue in repository  
**Authentication**: Bearer token required  
**Body**: Issue creation data

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Bug report","body":"Issue description"}' \
  "http://localhost:8000/github/repositories/owner/repo/issues"
```

### Additional Endpoints

#### `GET /github/repositories/{owner}/{repo}/pulls`
**Purpose**: List repository pull requests

#### `GET /github/repositories/{owner}/{repo}/commits`
**Purpose**: List repository commits

#### `GET /github/search/repositories`
**Purpose**: Search public GitHub repositories

---

## 💬 DAIFU CHAT SERVICE (`/daifu`) ⚠️ PARTIALLY WORKING

**Purpose**: AI-powered chat with real-time WebSocket communication  
**Implementation**: `backend/daifuUserAgent/chat_api.py`  
**Status**: Core functionality works but has critical security issues

### 🔴 CRITICAL ISSUES
1. **WebSocket Authentication Race Conditions**: Auth validation happens after connection
2. **Session ID Inconsistency**: Mixed `session_id` vs `conversation_id` usage
3. **Missing Rate Limiting**: Vulnerable to abuse
4. **Deprecated Endpoints**: Legacy endpoints still in use

### Session Management

#### `POST /daifu/sessions`
**Purpose**: Create new chat session  
**Authentication**: Bearer token required  
**Body**: Session creation request

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"repo_owner":"owner","repo_name":"repo","repo_branch":"main"}' \
  "http://localhost:8000/daifu/sessions"
```

#### `GET /daifu/sessions`
**Purpose**: Get user's chat sessions  
**Authentication**: Bearer token required

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/daifu/sessions"
```

#### `GET /daifu/sessions/{session_id}`
**Purpose**: Get session context and metadata  
**Authentication**: Bearer token required

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/daifu/sessions/123"
```

#### `POST /daifu/sessions/{session_id}/touch`
**Purpose**: Update session last activity timestamp  
**Authentication**: Bearer token required

```bash
curl -X POST -H "Authorization: Bearer <token>" "http://localhost:8000/daifu/sessions/123/touch"
```

### Chat Operations

#### `POST /daifu/chat/daifu`
**Purpose**: Send chat message to AI agent  
**Authentication**: Bearer token required  
**Body**: Chat request with message and context  
**⚠️ Issue**: Legacy endpoint, inconsistent behavior

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":"123","message":{"content":"Hello","is_code":false}}' \
  "http://localhost:8000/daifu/chat/daifu"
```

#### `GET /daifu/chat/sessions/{session_id}/messages`
**Purpose**: Get chat message history  
**Authentication**: Bearer token required

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/daifu/chat/sessions/123/messages"
```

#### `PUT /daifu/chat/sessions/{session_id}/title`
**Purpose**: Update session title  
**Authentication**: Bearer token required

```bash
curl -X PUT \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"New Session Title"}' \
  "http://localhost:8000/daifu/chat/sessions/123/title"
```

#### `DELETE /daifu/chat/sessions/{session_id}`
**Purpose**: Deactivate chat session  
**Authentication**: Bearer token required

```bash
curl -X DELETE -H "Authorization: Bearer <token>" "http://localhost:8000/daifu/chat/sessions/123"
```

### Statistics and Analytics

#### `GET /daifu/chat/sessions/{session_id}/statistics`
**Purpose**: Get session usage statistics  
**Authentication**: Bearer token required

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/daifu/chat/sessions/123/statistics"
```

#### `POST /daifu/chat/create-issue`
**Purpose**: Create issue from chat conversation  
**Authentication**: Bearer token required

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id":"123","title":"Issue from chat"}' \
  "http://localhost:8000/daifu/chat/create-issue"
```

### 🔌 WebSocket Real-time Communication

#### `WS /daifu/sessions/{session_id}/ws`
**Purpose**: Real-time chat updates and notifications  
**Authentication**: Token via query parameter  
**⚠️ CRITICAL SECURITY ISSUE**: Authentication race conditions

```javascript
// ❌ VULNERABLE: Current implementation
const ws = new WebSocket(`ws://localhost:8000/daifu/sessions/123/ws?token=${token}`);

// Connection establishes BEFORE authentication validation
ws.onopen = () => {
  // User already connected, auth happens async
};
```

#### WebSocket Message Types
| Type | Direction | Purpose | Status |
|------|-----------|---------|--------|
| `SESSION_UPDATE` | Server → Client | Session state changes | ✅ Working |
| `MESSAGE` | Bidirectional | Chat messages | ✅ Working |
| `CONTEXT_CARD` | Server → Client | Context updates | ✅ Working |
| `AGENT_STATUS` | Server → Client | AI agent status | ✅ Working |
| `STATISTICS` | Server → Client | Usage statistics | ✅ Working |
| `HEARTBEAT` | Bidirectional | Connection health | ✅ Working |
| `ERROR` | Server → Client | Error notifications | ✅ Working |

---

## 📋 ISSUE MANAGEMENT SERVICE (`/issues`) ✅ STABLE

**Purpose**: User-generated issue management with GitHub integration  
**Implementation**: `backend/issueChatServices/issue_service.py`  
**Status**: Production ready, comprehensive issue lifecycle

### Issue CRUD Operations

#### `POST /issues/`
**Purpose**: Create new user issue  
**Authentication**: Bearer token required

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Bug report","description":"Detailed description","priority":"high"}' \
  "http://localhost:8000/issues/"
```

#### `GET /issues/`
**Purpose**: Get user's issues with filtering  
**Authentication**: Bearer token required  
**Parameters**: status, priority, created_after, limit

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/issues/?status=open&limit=10"
```

#### `GET /issues/{issue_id}`
**Purpose**: Get specific issue details  
**Authentication**: Bearer token required

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/issues/123"
```

### Advanced Issue Operations

#### `POST /issues/create-with-context`
**Purpose**: Create issue with chat context  
**Authentication**: Bearer token required  
**Body**: Issue data with context references

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Issue","description":"Desc","chat_session_id":"123","context_cards":["card1"]}' \
  "http://localhost:8000/issues/create-with-context"
```

#### `POST /issues/{issue_id}/create-github-issue`
**Purpose**: Convert user issue to GitHub issue  
**Authentication**: Bearer token required  
**Body**: Repository information

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"repo_owner":"owner","repo_name":"repo"}' \
  "http://localhost:8000/issues/123/create-github-issue"
```

#### `POST /issues/from-chat`
**Purpose**: Create issue directly from chat request  
**Authentication**: Bearer token required

```bash
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"chat_session_id":"123","title":"Chat Issue"}' \
  "http://localhost:8000/issues/from-chat"
```

#### `GET /issues/statistics`
**Purpose**: Get user issue statistics  
**Authentication**: Bearer token required

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/issues/statistics"
```

---

## 📁 FILE DEPENDENCIES SERVICE (`/filedeps`) ❌ BROKEN

**Purpose**: Repository file analysis and dependency extraction  
**Implementation**: `backend/repo_processorGitIngest/filedeps.py`  
**Status**: ❌ **COMPLETELY BROKEN** - Core functionality non-functional

### 🔴 CRITICAL ISSUES
1. **Missing pgvector Extension**: File embeddings completely broken
2. **Infinite Recursion Bug**: Frontend crashes when using file context
3. **Database Schema Issues**: File analysis tables not properly initialized
4. **Memory Leaks**: Large repositories cause server crashes

### Repository Analysis

#### `GET /filedeps/`
**Purpose**: File dependencies API information  
**Status**: ✅ Working (basic info only)

```bash
curl "http://localhost:8000/filedeps/"
```

#### `GET /filedeps/repositories`
**Purpose**: Get user repositories for file analysis  
**Authentication**: Bearer token required  
**Status**: ✅ Working

```bash
curl -H "Authorization: Bearer <token>" "http://localhost:8000/filedeps/repositories"
```

#### `GET /filedeps/repositories/{repository_id}/files`
**Purpose**: Get repository file structure  
**Authentication**: Bearer token required  
**Status**: ❌ **BROKEN** - File tree rendering issues

```bash
# ❌ THIS WILL FAIL
curl -H "Authorization: Bearer <token>" "http://localhost:8000/filedeps/repositories/123/files"
```

#### `POST /filedeps/extract`
**Purpose**: Extract file dependencies and create embeddings  
**Authentication**: Bearer token required  
**Status**: ❌ **BROKEN** - pgvector dependency missing

```bash
# ❌ THIS WILL FAIL - Missing pgvector
curl -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"repository_url":"https://github.com/owner/repo"}' \
  "http://localhost:8000/filedeps/extract"
```

---

## 🔧 PRODUCTION DEPLOYMENT

### Environment Configuration

#### Required Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/db

# GitHub OAuth
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret
GITHUB_REDIRECT_URI=https://yudai.app/auth/callback

# Security
SECRET_KEY=your_secret_key_here
JWT_SECRET=your_jwt_secret_here

# AI Integration
OPENROUTER_API_KEY=your_openrouter_key

# Domain Configuration
API_DOMAIN=api.yudai.app
DEV_DOMAIN=dev.yudai.app
```

#### ⚠️ Current Configuration Issues
```bash
# ❌ SECURITY RISK: Development secrets exposed
SECRET_KEY=${SECRET_KEY:-dev_secret}        # Hardcoded fallback
JWT_SECRET=${JWT_SECRET:-dev_jwt_secret}    # Hardcoded fallback

# ❌ INCONSISTENT: Different ports across environments
# Dev: 127.0.0.1:8001:8000
# Prod: 127.0.0.1:8000:8000
```

### Docker Deployment

#### Development Environment
```bash
# ❌ CURRENT ISSUES:
# - Exposed secrets in docker-compose.dev.yml
# - Container naming inconsistency
# - Missing health check endpoints
docker compose up -d
```

#### Production Environment
```bash
# ❌ CURRENT ISSUES:
# - SSL certificate validation missing
# - No rate limiting configured
# - Debug code still present
docker compose -f docker-compose.prod.yml up -d
```

### Database Setup

#### Current Database Issues
```python
# backend/db/database.py:34
#TODO: Add pgvector (very important vector db)  # ❌ CRITICAL MISSING
```

#### Required Database Extensions
```sql
-- ❌ MISSING: This needs to be added
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

---

## 🔒 SECURITY CONFIGURATION

### Current Security Status: ❌ **VULNERABLE**

#### Authentication Security
- ✅ JWT token implementation
- ✅ GitHub OAuth2 flow
- ❌ **WebSocket authentication bypass**
- ❌ **No rate limiting**
- ❌ **Token leakage in logs**

#### CORS Configuration
```python
# ❌ SECURITY ISSUE: HTTP in production
allow_origins=[
    "http://yudai.app"  # Should be HTTPS only
]
```

#### SSL/TLS Issues
- ❌ **No certificate validation**
- ❌ **Mixed HTTP/HTTPS references**
- ❌ **No HSTS headers**

---

## 🔍 HEALTH CHECKS & MONITORING

### Health Check Endpoints

#### `GET /`
**Purpose**: API root with service information  
**Status**: ✅ Working

```bash
curl "http://localhost:8000/"
```

#### `GET /health`
**Purpose**: Backend health check  
**Status**: ✅ Working

```bash
curl "http://localhost:8000/health"
```

#### ❌ Missing Health Checks
```yaml
# docker-compose.yml references non-existent endpoints
test: ["CMD", "curl", "-f", "http://localhost/health"]  # ❌ MISSING
```

### Current Monitoring Gaps
- ❌ **No error tracking** (Sentry, etc.)
- ❌ **No performance metrics** 
- ❌ **No log aggregation**
- ❌ **No alerting system**

---

## 🧪 TESTING & VALIDATION

### API Testing Status

| Service | Unit Tests | Integration Tests | E2E Tests | Status |
|---------|-----------|------------------|-----------|--------|
| Auth | ⚠️ Partial | ❌ Missing | ❌ Missing | Poor |
| GitHub | ⚠️ Partial | ❌ Missing | ❌ Missing | Poor |
| Chat | ❌ Missing | ❌ Missing | ❌ Missing | None |
| Issues | ⚠️ Partial | ❌ Missing | ❌ Missing | Poor |
| FileDeps | ❌ Missing | ❌ Missing | ❌ Missing | None |

### Manual Testing Checklist
```bash
# ✅ Working endpoints
curl -H "Authorization: Bearer <token>" "http://localhost:8000/auth/profile"
curl -H "Authorization: Bearer <token>" "http://localhost:8000/github/repositories"
curl -H "Authorization: Bearer <token>" "http://localhost:8000/issues/"

# ❌ Broken endpoints
curl -H "Authorization: Bearer <token>" "http://localhost:8000/filedeps/repositories/1/files"
```

---

## 🚨 IMMEDIATE ACTION REQUIRED

### Phase 1: Critical Security Fixes (Day 1)
1. **Fix WebSocket Authentication**
   - Move auth validation before connection establishment
   - Implement proper token verification
   - Add connection rate limiting

2. **Remove Exposed Secrets**
   - Eliminate hardcoded development secrets
   - Implement proper secret management
   - Add environment validation

3. **Fix CORS Configuration**
   - HTTPS-only in production
   - Restrict origins properly
   - Add security headers

### Phase 2: Core Functionality (Day 2)
1. **Implement pgvector Extension**
   - Add to database initialization
   - Update Docker container setup
   - Test file embeddings

2. **Fix File Dependencies Service**
   - Resolve infinite recursion bug
   - Fix file tree rendering
   - Implement proper error handling

3. **Remove Debug Code**
   - Clean production builds
   - Implement proper logging
   - Remove development artifacts

### Phase 3: Production Readiness (Day 3)
1. **Implement Health Checks**
   - Add missing endpoints
   - Fix Docker health checks
   - Add monitoring endpoints

2. **Add Error Handling**
   - Implement error boundaries
   - Add user-friendly messages
   - Create fallback mechanisms

3. **Performance Optimization**
   - Add request caching
   - Optimize database queries
   - Implement rate limiting

---

## 📚 API REFERENCE QUICK ACCESS

### Interactive Documentation
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

### Postman Collection
```bash
# Generate OpenAPI spec
curl "http://localhost:8000/openapi.json" > yudai-api.json
```

### Error Response Format
```json
{
  "detail": "Error message",
  "status_code": 400,
  "timestamp": "2025-01-XX T12:00:00Z",
  "path": "/api/endpoint"
}
```

---

**⚠️ DEMO READINESS**: This API is currently **NOT READY** for demo deployment. Critical security and functionality issues must be resolved first. See the issues sections above for specific fixes required.
