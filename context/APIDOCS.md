# YudaiV3 Backend API

A unified FastAPI server that combines all backend services for the YudaiV3 application.

## Services Included

### 🔐 Authentication (`/auth`)
- **Purpose**: Handles user authentication, session management, and profile retrieval.
- **Functions**:
  - `github_login()`: [Used] Initiates the GitHub OAuth2 flow.
  - `github_callback()`: [Used] Handles the callback from GitHub after authentication.
  - `get_user_profile()`: [Used] Retrieves the authenticated user's profile.
  - `logout()`: [Used] Logs the user out and invalidates their session.
  - `auth_status()`: [Used] Checks the current authentication status.
  - `get_auth_config()`: [Used] Provides public authentication configuration.

### 🐙 GitHub Integration (`/github`)
- **Purpose**: Manages interactions with the GitHub API, including repositories, issues, and pull requests.
- **Functions**:
  - `get_my_repositories()`: [Used] Fetches the authenticated user's repositories.
  - `get_repository_info()`: [Used] Retrieves details for a specific repository.
  - `create_repository_issue()`: [Used] Creates a new issue in a repository.
  - `get_repository_issues_list()`: [Used] Lists issues for a repository.
  - `get_repository_pulls_list()`: [Used] Lists pull requests for a repository.
  - `get_repository_commits_list()`: [Used] Lists commits for a repository.
  - `get_repository_branches_list()`: [Used] Lists branches for a repository.
  - `search_github_repositories()`: [Used] Searches for repositories on GitHub.

### 💬 Chat Services (`/daifu`)
- **Purpose**: Integrates with the DAifu AI agent, manages chat sessions, and handles real-time communication.
- **Functions**:
  - `create_or_get_session()`: [Used] Creates or retrieves a chat session.
  - `get_session_context()`: [Used] Gets the comprehensive context for a session.
  - `touch_session()`: [Used] Updates the last activity timestamp for a session.
  - `get_user_sessions()`: [Used] Retrieves all sessions for a user.
  - `chat_daifu()`: [Used] Processes a chat message with the DAifu agent (legacy).
  - `get_chat_sessions()`: [Used] Retrieves chat sessions (legacy).
  - `websocket_session_endpoint()`: [Used] Handles WebSocket connections for real-time updates.
  - `handle_websocket_message()`: [Used] Processes incoming WebSocket messages.
  - `handle_new_message_realtime()`: [Used] Manages new messages in real-time.
  - `process_ai_response_async()`: [Used] Asynchronously processes AI responses.
  - `generate_daifu_response_async()`: [Used] Generates DAifu responses asynchronously.
  - `chat_daifu_v2()`: [Used] Processes a chat message with WebSocket support.
  - `get_session_statistics()`: [Used] Retrieves statistics for a session.
  - `update_session_title()`: [Used] Updates the title of a session.
  - `deactivate_session()`: [Used] Deactivates a chat session.
  - `create_issue_from_chat()`: [Used] Creates an issue from a chat conversation.

### 📋 Issue Management (`/issues`)
- **Purpose**: Manages user-generated issues, tracks their status, and integrates with GitHub issues.
- **Functions**:
  - `create_issue()`: [Used] Creates a new user issue.
  - `get_issues()`: [Used] Retrieves a list of user issues.
  - `get_issue()`: [Used] Retrieves a specific user issue.
  - `create_issue_with_context()`: [Used] Creates an issue with context from a chat.
  - `update_issue_status()`: [Used] Updates the status of an issue.
  - `create_github_issue_from_user_issue()`: [Used] Converts a user issue to a GitHub issue.
  - `create_issue_from_chat()`: [Used] Creates an issue directly from a chat request.
  - `get_issue_statistics()`: [Used] Retrieves statistics for user issues.

### 📁 File Dependencies (`/filedeps`)
- **Purpose**: Analyzes repository file structures and dependencies.
- **Functions**:
  - `root()`: [Used] Provides basic API information.
  - `get_repository_by_url()`: [Used] Retrieves a repository by its URL.
  - `get_repository_files()`: [Used] Lists files for a repository.
  - `extract_file_dependencies()`: [Used] Extracts file dependencies from a repository.

## Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL database
- GitHub OAuth app configured

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp env.example .env
# Edit .env with your configuration
```

3. Initialize the database:
```bash
python init_db.py
```

4. Start the server:
```bash
python run_server.py
```

The server will be available at:
- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Production Deployment

### Docker Compose Production Setup

The production environment uses Docker Compose with the following services:

#### 1. Database Service (`db`)
- **Container**: `yudai-db`
- **Port**: Internal only (5432)
- **Health Check**: PostgreSQL readiness check
- **Volumes**: Persistent PostgreSQL data

#### 2. Backend Service (`backend`)
- **Container**: `yudai-be`
- **Port**: 127.0.0.1:8000 (localhost only)
- **Health Check**: HTTP health endpoint
- **Environment Variables**:
  - `DATABASE_URL`: PostgreSQL connection string
  - `GITHUB_CLIENT_ID`: GitHub OAuth app client ID
  - `GITHUB_CLIENT_SECRET`: GitHub OAuth app client secret
  - `GITHUB_REDIRECT_URI`: https://yudai.app/auth/callback
  - `API_DOMAIN`: api.yudai.app
  - `DEV_DOMAIN`: dev.yudai.app

#### 3. Frontend Service (`frontend`)
- **Container**: `yudai-fe`
- **Ports**: 80 (HTTP), 443 (HTTPS)
- **Environment Variables**:
  - `VITE_API_URL`: https://yudai.app/api
- **SSL**: Mounted from `./ssl` directory
- **Health Check**: Frontend health endpoint

### Nginx Configuration

The production setup uses nginx as a reverse proxy with SSL termination. There are two nginx configuration files:

#### `nginx.prod.conf` - Production Configuration
- **SSL/TLS**: Full SSL configuration with modern ciphers
- **Multiple Domains**:
  - `yudai.app` (main application)
  - `api.yudai.app` (API subdomain)
  - `dev.yudai.app` (development subdomain)
- **Security Headers**: HSTS, X-Frame-Options, CSP, etc.
- **CORS**: Configured for cross-origin requests
- **Proxy Rules**:
  - `/auth/*` → `backend:8000/auth/*` (direct auth proxy)
  - `/api/*` → `backend:8000/*` (API proxy with prefix removal)
  - `/` → Static frontend files

#### `nginx.conf` - Development Configuration
- **HTTP Only**: No SSL configuration
- **Single Domain**: localhost
- **Simplified CORS**: Allow all origins (`*`)
- **Proxy Rules**:
  - `/auth/*` → `backend:8000/auth/*`
  - `/api/*` → `backend:8000/*`

### Production Deployment Commands

```bash
# Start production environment
docker compose -f docker-compose.prod.yml up -d

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Stop production environment
docker compose -f docker-compose.prod.yml down

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build
```

## API Endpoints

### Root Endpoints
- `GET /` - API information and service overview
- `GET /health` - Health check

### Authentication (`/auth`)
- `GET /auth/login` - GitHub OAuth login (redirects to GitHub)
- `GET /auth/callback` - OAuth callback (handles GitHub response)
- `GET /auth/profile` - User profile (requires authentication)
- `POST /auth/logout` - Logout (requires authentication)
- `GET /auth/status` - Auth status (optional authentication)
- `GET /auth/config` - Auth configuration (public)

### GitHub Integration (`/github`)
- `GET /github/repositories` - User repositories (requires auth)
- `GET /github/repositories/{owner}/{repo}` - Repository details
- `POST /github/repositories/{owner}/{repo}/issues` - Create issue
- `GET /github/repositories/{owner}/{repo}/issues` - Repository issues
- `GET /github/repositories/{owner}/{repo}/pulls` - Repository PRs
- `GET /github/repositories/{owner}/{repo}/commits` - Repository commits
- `GET /github/search/repositories` - Search repositories

### Chat Services (`/daifu`)
- `POST /daifu/chat/daifu` - Chat with DAifu agent (requires auth)
- `POST /daifu/chat/daifu/v2` - WebSocket-enabled chat (requires auth)
- `GET /daifu/chat/sessions` - Chat sessions (requires auth)
- `GET /daifu/chat/sessions/{session_id}/messages` - Session messages
- `GET /daifu/chat/sessions/{session_id}/statistics` - Session statistics
- `PUT /daifu/chat/sessions/{session_id}/title` - Update session title
- `DELETE /daifu/chat/sessions/{session_id}` - Deactivate session
- `POST /daifu/chat/create-issue` - Create issue from chat
- `POST /daifu/sessions` - Create new session
- `GET /daifu/sessions/{session_id}` - Get session context
- `POST /daifu/sessions/{session_id}/touch` - Update session activity
- `GET /daifu/sessions` - Get user sessions
- `WS /daifu/sessions/{session_id}/ws` - WebSocket for real-time updates

### Issue Management (`/issues`)
- `POST /issues/` - Create user issue (requires auth)
- `GET /issues/` - Get user issues (requires auth)
- `GET /issues/{issue_id}` - Get specific issue
- `PUT /issues/{issue_id}/status` - Update issue status
- `POST /issues/{issue_id}/convert-to-github` - Convert to GitHub issue
- `POST /issues/from-chat` - Create issue from chat
- `GET /issues/statistics` - Issue statistics

### File Dependencies (`/filedeps`)
- `GET /filedeps/` - File dependencies API info
- `GET /filedeps/repositories` - User repositories (requires auth)
- `GET /filedeps/repositories?repo_url=<url>` - Repository lookup by URL
- `GET /filedeps/repositories/{repository_id}` - Repository details
- `GET /filedeps/repositories/{repository_id}/files` - Repository files
- `POST /filedeps/extract` - Extract file dependencies

## Frontend Integration

### Environment Variables
- `VITE_API_URL`: Base URL for API requests
  - Development: `http://localhost:8000`
  - Production: `https://yudai.app/api`

### Authentication Flow
1. User clicks login → `GET /auth/login`
2. Redirected to GitHub OAuth
3. GitHub redirects to → `GET /auth/callback?code=...&state=...`
4. Backend exchanges code for token
5. Frontend stores token in localStorage
6. Subsequent requests include `Authorization: Bearer <token>` header

### API Request Patterns
```javascript
// Auth endpoints (direct proxy)
const authUrl = `${API_BASE_URL}/auth/login`;

// API endpoints (with /api prefix)
const apiUrl = `${API_BASE_URL}/github/repositories`;
```

## 🚨 CRITICAL FRONTEND-BACKEND INTEGRATION ISSUES

### 1. **BROKEN WEBSOCKET URL CONSTRUCTION** ⚠️
**Issue**: WebSocket connections fail in production due to incorrect URL construction
```typescript
// BROKEN: src/services/api.ts:619-637
static createSessionWebSocket(sessionId: string, token: string | null): WebSocket {
  const wsUrl = API_BASE_URL.replace('http', 'ws'); // ❌ WRONG
  const url = new URL(`${wsUrl}/daifu/sessions/${sessionId}/ws`);
  // ...
}
```
**Problem**:
- `API_BASE_URL` is `https://yudai.app/api` in production
- `replace('http', 'ws')` creates `wss://yudai.app/api/daifu/sessions/...`
- Backend expects `wss://yudai.app/daifu/sessions/...` (no `/api` prefix)
- **Result**: All WebSocket connections fail in production

### 2. **INCONSISTENT SESSION ID NAMING** ⚠️
**Issue**: Frontend uses `session_id` but backend expects `conversation_id`
```typescript
// Frontend: src/services/api.ts:22-28
export interface ChatRequest {
  conversation_id?: string; // ✅ Correct
  message: ChatMessage;
  // ...
}

// But in SessionContext: src/contexts/SessionContext.tsx
const ws = ApiService.createSessionWebSocket(activeSessionId, token); // ❌ Uses session_id
```

### 3. **DUPLICATE CHAT ENDPOINTS** ⚠️
**Issue**: Two chat endpoints with different behaviors
```python
# Backend has both:
@router.post("/chat/daifu")        # Legacy endpoint
@router.post("/chat/daifu/v2")     # New WebSocket-enabled endpoint
```
**Problem**:
- Frontend uses legacy endpoint (`/chat/daifu`)
- WebSocket functionality only works with `/chat/daifu/v2`
- **Result**: Real-time updates don't work

### 4. **INSECURE WEBSOCKET AUTHENTICATION** ⚠️
**Issue**: WebSocket authentication is insecure
```python
# Backend: backend/daifuUserAgent/chat_api.py:320-380
if not token:
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return

user = get_current_user(token, db)  # ❌ Simple token lookup, no JWT validation
```

## Environment Variables

### Required Environment Variables
- `DATABASE_URL` - PostgreSQL connection string
- `GITHUB_CLIENT_ID` - GitHub OAuth app client ID
- `GITHUB_CLIENT_SECRET` - GitHub OAuth app client secret
- `GITHUB_REDIRECT_URI` - OAuth redirect URI
- `OPENROUTER_API_KEY` - OpenRouter API key for DAifu agent
- `SECRET_KEY` - Application secret key
- `JWT_SECRET` - JWT token signing secret

### Production-Specific Variables
- `POSTGRES_DB` - Database name
- `POSTGRES_USER` - Database user
- `POSTGRES_PASSWORD` - Database password
- `API_DOMAIN` - API subdomain (api.yudai.app)
- `DEV_DOMAIN` - Development subdomain (dev.yudai.app)

## Security Configuration

### SSL/TLS
- **Protocols**: TLSv1.2, TLSv1.3
- **Ciphers**: Modern ECDHE-RSA ciphers
- **HSTS**: 1 year with includeSubDomains
- **Certificate**: Full chain required

### Security Headers
- `Strict-Transport-Security`: HTTPS enforcement
- `X-Frame-Options`: Clickjacking protection
- `X-Content-Type-Options`: MIME type sniffing protection
- `X-XSS-Protection`: XSS protection
- `Referrer-Policy`: Referrer information control

### CORS Configuration
- **Allowed Origins**: https://yudai.app
- **Methods**: GET, POST, PUT, DELETE, OPTIONS
- **Headers**: Authorization, Content-Type, etc.
- **Credentials**: Supported

## Error Handling

All endpoints include proper error handling with appropriate HTTP status codes:
- `400` - Bad Request
- `401` - Unauthorized
- `404` - Not Found
- `500` - Internal Server Error

## Health Checks

### Container Health Checks
- **Database**: PostgreSQL readiness check
- **Backend**: HTTP health endpoint
- **Frontend**: Nginx health endpoint

### Health Endpoints
- `GET /health` - Backend health check
- `GET /` - Frontend health check (nginx)

## Monitoring and Logging

### Nginx Logs
- **Access Logs**: Request/response logging
- **Error Logs**: Error condition logging
- **Format**: JSON format for production

### Application Logs
- **Backend**: FastAPI application logs
- **Database**: PostgreSQL logs
- **Container**: Docker container logs

## Development vs Production

### Development Environment
- **File**: `docker-compose.yml`
- **Nginx**: `nginx.conf`
- **SSL**: Disabled
- **CORS**: Allow all origins
- **Ports**: Exposed directly

### Production Environment
- **File**: `docker-compose.prod.yml`
- **Nginx**: `nginx.prod.conf`
- **SSL**: Enabled with certificates
- **CORS**: Restricted to specific domains
- **Ports**: Internal networking with nginx proxy

## Troubleshooting

### Common Issues

1. **SSL Certificate Errors**
   - Verify certificate files in `./ssl/`
   - Check certificate expiration
   - Validate domain names

2. **CORS Errors**
   - Verify nginx CORS headers
   - Check frontend API_BASE_URL
   - Validate allowed origins

3. **Authentication Failures**
   - Verify GitHub OAuth app configuration
   - Check GITHUB_REDIRECT_URI matches
   - Validate environment variables

4. **Database Connection Issues**
   - Check DATABASE_URL format
   - Verify PostgreSQL container health
   - Validate network connectivity

5. **WebSocket Connection Failures** ⚠️
   - Check WebSocket URL construction
   - Verify nginx WebSocket proxy configuration
   - Validate token authentication

### Debug Commands
```bash
# Check container status
docker ps

# View container logs
docker logs yudai-be
docker logs yudai-fe

# Test nginx configuration
docker exec yudai-fe nginx -t

# Test backend connectivity
curl -I http://localhost:8000/health

# Test frontend connectivity
curl -I https://yudai.app/health

# Test WebSocket connection (requires wscat)
wscat -c "wss://yudai.app/daifu/sessions/test/ws?token=test"
```

## Priority Fixes Required

### 🔴 Critical (Immediate)
1. **Fix WebSocket URL construction** - All real-time features broken
2. **Standardize session/conversation ID naming** - Inconsistent state management
3. **Implement proper WebSocket authentication** - Security vulnerability
4. **Switch to WebSocket-enabled chat endpoint** - Real-time updates not working

### 🟡 High Priority (Next Sprint)
5. **Add WebSocket error handling and reconnection** - Poor user experience
6. **Fix auth URL configuration** - Potential auth issues
7. **Standardize API response structures** - Inconsistent error handling

### 🟢 Medium Priority (Future)
8. **Implement missing WebSocket message handlers** - Incomplete real-time features
9. **Add comprehensive error boundaries** - Better error recovery
10. **Implement connection health monitoring** - Proactive issue detection
