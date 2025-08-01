# YudaiV3 Backend API

A unified FastAPI server that combines all backend services for the YudaiV3 application.

## Services Included

### 🔐 Authentication (`/auth`)
- GitHub OAuth authentication
- User session management
- Profile management

### 🐙 GitHub Integration (`/github`)
- Repository management
- Issue creation and management
- Pull request handling
- Repository search

### 💬 Chat Services (`/daifu`)
- DAifu AI agent integration
- Chat session management
- Message history
- Issue creation from chat

### 📋 Issue Management (`/issues`)
- User issue creation and management
- Issue status tracking
- GitHub issue conversion
- Issue statistics

### 📁 File Dependencies (`/filedeps`)
- Repository file structure extraction
- File dependency analysis
- GitIngest integration
- File categorization

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
// BROKEN: src/services/api.ts:615-622
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

// But in SessionContext: src/contexts/SessionContext.tsx:99
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
# Backend: backend/daifuUserAgent/chat_api.py:325-330
if not token:
    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
    return
    
user = get_current_user(token, db)  # ❌ Simple token lookup, no JWT validation
```

## Frontend-Backend API Dependency Table

### Overview
This section documents the complete mapping between frontend components/services and backend API endpoints, including state flow from user interactions to database operations.

### Component-to-API Mapping

#### Authentication Flow
| Frontend Component | Frontend Service | Backend Endpoint | HTTP Method | Database Table | State Flow |
|-------------------|------------------|------------------|-------------|----------------|------------|
| `LoginPage.tsx` | `AuthService.login()` | `/auth/login` | GET | - | Redirect to GitHub OAuth |
| `AuthProvider.tsx` | `AuthService.handleCallback()` | `/auth/callback` | GET | `users`, `auth_tokens` | OAuth → Create/Update User → Store Token → Update React State |
| `AuthProvider.tsx` | `AuthService.checkAuthStatus()` | `/auth/status` | GET | `users`, `auth_tokens` | Check Token → Validate User → Update Auth State |
| `AuthProvider.tsx` | `AuthService.getProfile()` | `/auth/profile` | GET | `users` | Get User Profile → Update User State |
| `AuthProvider.tsx` | `AuthService.logout()` | `/auth/logout` | POST | `auth_tokens` | Deactivate Token → Clear Local Storage → Reset Auth State |
| - | `AuthService.getAuthConfig()` | `/auth/config` | GET | - | Get OAuth Configuration |

#### Session Management Flow
| Frontend Component | Frontend Service | Backend Endpoint | HTTP Method | Database Table | State Flow |
|-------------------|------------------|------------------|-------------|----------------|------------|
| `SessionContext.tsx` | `ApiService.createOrGetSession()` | `/daifu/chat/daifu` | POST | `chat_sessions`, `chat_messages` | Create Message → Auto-create Session → Update Session State |
| `SessionContext.tsx` | `ApiService.getSessionContext()` | `/daifu/chat/sessions` | GET | `chat_sessions` | Get Sessions → Find Session → Return Context |
| `SessionContext.tsx` | `ApiService.getSessionMessages()` | `/daifu/chat/sessions/{id}/messages` | GET | `chat_messages` | Get Messages → Update Context |
| `SessionContext.tsx` | `ApiService.getSessionStatistics()` | `/daifu/chat/sessions/{id}/statistics` | GET | `chat_sessions` | Get Stats → Update Repository Info |

#### Chat Interface Flow
| Frontend Component | Frontend Service | Backend Endpoint | HTTP Method | Database Table | State Flow |
|-------------------|------------------|------------------|-------------|----------------|------------|
| `Chat.tsx` | `ApiService.sendChatMessage()` | `/daifu/chat/daifu` | POST | `chat_sessions`, `chat_messages` | User Input → Create Message → AI Response → Update Chat State |
| `Chat.tsx` | `ApiService.createIssueWithContext()` | `/issues/create-with-context` | POST | `user_issues`, `context_cards` | Chat Context → Create Issue → Preview Response |

#### Repository Management Flow  
| Frontend Component | Frontend Service | Backend Endpoint | HTTP Method | Database Table | State Flow |
|-------------------|------------------|------------------|-------------|----------------|------------|
| `RepositoryProvider.tsx` | Local Storage Only | - | - | - | Select Repository → Store in localStorage → Update Context |
| Various Components | `ApiService.getUserRepositories()` | `/github/repositories` | GET | `repositories` | Get User Repos → Update Repository Options |
| Various Components | `ApiService.getRepositoryBranches()` | `/github/repositories/{owner}/{repo}/branches` | GET | - | Get Branches → Update Branch Options |
| Various Components | `ApiService.searchRepositories()` | `/github/search/repositories` | GET | - | Search Query → Return Results |

#### File Dependencies Flow
| Frontend Component | Frontend Service | Backend Endpoint | HTTP Method | Database Table | State Flow |
|-------------------|------------------|------------------|-------------|----------------|------------|
| `FileDependencies.tsx` | `ApiService.getRepositoryByUrl()` | `/filedeps/repositories?repo_url=` | GET | `repositories`, `file_analyses` | Check DB for Repo → Return if Exists |
| `FileDependencies.tsx` | `ApiService.getRepositoryFiles()` | `/filedeps/repositories/{id}/files` | GET | `file_items` | Get File Tree → Update File State |
| `FileDependencies.tsx` | `ApiService.extractFileDependencies()` | `/filedeps/extract` | POST | `repositories`, `file_items`, `file_analyses` | Extract Files → Store Analysis → Return Tree |

#### Issue Management Flow
| Frontend Component | Frontend Service | Backend Endpoint | HTTP Method | Database Table | State Flow |
|-------------------|------------------|------------------|-------------|----------------|------------|
| `Chat.tsx` | `ApiService.createIssueWithContext()` | `/issues/create-with-context` | POST | `user_issues` | Chat + File Context → Create Issue → Return Preview |
| `DiffModal.tsx` | `ApiService.createGitHubIssueFromUserIssue()` | `/issues/{id}/create-github-issue` | POST | `user_issues` | User Issue → Create GitHub Issue → Update Status |
| Various Components | `ApiService.getUserIssues()` | `/issues/` | GET | `user_issues` | Get User Issues → Update Issue List |
| Various Components | `ApiService.getUserIssue()` | `/issues/{id}` | GET | `user_issues` | Get Specific Issue → Show Details |

#### GitHub Integration Flow
| Frontend Component | Frontend Service | Backend Endpoint | HTTP Method | Database Table | State Flow |
|-------------------|------------------|------------------|-------------|----------------|------------|
| Various Components | `ApiService.getRepository()` | `/github/repositories/{owner}/{repo}` | GET | `repositories` | Get Repo Details → Update Repository Info |
| Various Components | `ApiService.createRepositoryIssue()` | `/github/repositories/{owner}/{repo}/issues` | POST | `issues` | Create GitHub Issue → Store in DB |
| Various Components | `ApiService.getRepositoryIssues()` | `/github/repositories/{owner}/{repo}/issues` | GET | `issues` | Get GitHub Issues → Update Issue State |

### WebSocket Integration

#### Real-Time Session Updates
| Frontend Component | WebSocket Endpoint | Message Types | Status |
|-------------------|-------------------|---------------|--------|
| `SessionContext.tsx` | `WS /daifu/sessions/{session_id}/ws` | `SESSION_UPDATE`, `MESSAGE`, `CONTEXT_CARD` | ⚠️ Broken (URL issues) |

**WebSocket Message Flow**:
```typescript
// Frontend: src/contexts/SessionContext.tsx:99-120
const ws = ApiService.createSessionWebSocket(activeSessionId, token);

ws.onmessage = (event) => {
  const message: UnifiedWebSocketMessage = JSON.parse(event.data);
  switch (message.type) {
    case WebSocketMessageType.SESSION_UPDATE:
      return message.data as UnifiedSessionState;
    case WebSocketMessageType.MESSAGE:
      return { ...prevState, messages: [...prevState.messages, message.data] };
    // ...
  }
};
```

**Backend WebSocket Handler**:
```python
# backend/daifuUserAgent/chat_api.py:317-351
@router.websocket("/sessions/{session_id}/ws")
async def websocket_session_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = None,
    db: Session = Depends(get_db)
):
    await unified_manager.connect(websocket, session_id, db)
    # Real-time message broadcasting
```

### State Flow Patterns

#### Authentication State Flow
```
User Click Login → GitHub OAuth → Callback → Backend Validation → Database Update → Frontend State Update
```

1. **User Interaction**: Click login button
2. **Frontend Action**: Redirect to `/auth/login`
3. **Backend Processing**: Generate OAuth URL, redirect to GitHub
4. **External Service**: GitHub OAuth flow
5. **Backend Callback**: Handle `/auth/callback`, validate code
6. **Database Operations**: 
   - Query/Create user in `users` table
   - Deactivate old tokens in `auth_tokens` table  
   - Create new token in `auth_tokens` table
7. **Frontend State Update**: Update `AuthContext` with user and token
8. **Local Storage**: Store token and user data

#### Session Creation State Flow
```
Repository Selection → Auto-create Session → Database Insert → Context Update
```

1. **User Interaction**: Select repository
2. **Frontend Trigger**: `RepositoryContext` updates
3. **Auto-trigger**: `SessionContext` detects repository change
4. **API Call**: `createOrGetSession()` via chat message
5. **Backend Processing**: 
   - Check for existing session in `chat_sessions`
   - Create new session if none exists
   - Create initial message in `chat_messages`
6. **Database Operations**:
   - INSERT into `chat_sessions` table
   - INSERT into `chat_messages` table
7. **Frontend State Update**: Update `SessionContext` with session ID
8. **Local Storage**: Store session ID

#### Chat Message State Flow
```
User Input → API Call → AI Processing → Database Storage → UI Update
```

1. **User Interaction**: Type and send message
2. **Frontend Processing**: Add message to local state immediately
3. **API Call**: `sendChatMessage()` to `/daifu/chat/daifu`
4. **Backend Processing**:
   - Validate session/create if needed
   - Process message with AI
   - Generate response
5. **Database Operations**:
   - INSERT user message into `chat_messages`
   - INSERT AI response into `chat_messages`
   - UPDATE session statistics in `chat_sessions`
6. **Frontend State Update**: Add AI response to chat state

#### File Context State Flow
```
Repository Selection → File Extraction → Database Storage → Context Cards
```

1. **User Interaction**: Select repository in `FileDependencies`
2. **Frontend Check**: Look for existing analysis
3. **API Calls**: 
   - `getRepositoryByUrl()` - check if exists
   - `extractFileDependencies()` - if not exists
4. **Backend Processing**:
   - Extract repository files
   - Analyze file structure
   - Calculate tokens and categories
5. **Database Operations**:
   - INSERT/UPDATE in `repositories` table
   - INSERT files into `file_items` table
   - INSERT analysis into `file_analyses` table
6. **Frontend State Update**: Build file tree, update context cards

#### Issue Creation State Flow
```
Chat Context → Issue Preview → GitHub Issue → Database Update
```

1. **User Interaction**: Click "Create GitHub Issue" in chat
2. **Frontend Processing**: Gather chat messages and file context
3. **API Call**: `createIssueWithContext()` with preview=true
4. **Backend Processing**:
   - Generate issue preview
   - Store user issue
5. **Database Operations**:
   - INSERT into `user_issues` table
6. **Frontend Display**: Show preview modal
7. **User Confirmation**: Approve GitHub issue creation
8. **API Call**: `createGitHubIssueFromUserIssue()`
9. **Backend Processing**:
   - Create GitHub issue via API
   - Update user issue with GitHub details
10. **Database Operations**:
    - UPDATE `user_issues` with GitHub URL and number
11. **Frontend State Update**: Show success and GitHub link

### Error Handling Patterns

#### Authentication Errors
- **401 Unauthorized**: Clear auth state, redirect to login
- **Token Expiration**: Auto-refresh or force re-login
- **Network Errors**: Show error message, maintain state

#### Session Errors  
- **Session Not Found**: Create new session automatically
- **Invalid Session**: Clear session state, create new
- **Timeout**: Retry with exponential backoff

#### API Rate Limiting
- **GitHub API Limits**: Show friendly error, suggest retry
- **Backend Rate Limits**: Queue requests, show loading state

### Performance Optimizations

#### Caching Strategy
- **Auth Token**: Local storage with expiration check
- **User Profile**: Local storage with refresh capability
- **Repository List**: Cache for session duration
- **File Tree**: Cache per repository with refresh option

#### Lazy Loading
- **File Dependencies**: Load on repository selection
- **Chat History**: Paginated loading of old messages
- **Issue History**: Load on demand

#### State Management
- **Context Optimization**: Minimize re-renders with memo
- **Local Storage**: Persist critical state across sessions
- **Error Boundaries**: Graceful error handling per component

### Security Considerations

#### Token Management
- **Storage**: HttpOnly cookies preferred, localStorage as fallback  
- **Expiration**: Automatic refresh before expiration
- **Validation**: Server-side validation on every request

#### CORS Configuration
- **Production**: Restricted to `https://yudai.app`
- **Development**: Localhost origins only
- **Preflight**: Proper OPTIONS handling

#### Data Sanitization
- **User Input**: Sanitize before API calls
- **Response Data**: Validate structure before state updates
- **File Content**: Limit file sizes and types

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

