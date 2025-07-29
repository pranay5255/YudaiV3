# YudaiV3 Backend API Documentation

A unified FastAPI server that provides session-scoped operations for the YudaiV3 application with GitHub OAuth authentication and AI-powered chat functionality.

## Architecture Overview

### 🔐 Authentication Flow
1. **GitHub OAuth**: Users authenticate via GitHub OAuth
2. **Token Management**: Access tokens stored in `auth_tokens` table with 8-hour expiration
3. **Session Scoped**: All operations are scoped to authenticated user sessions
4. **Repository Context**: Sessions are linked to specific GitHub repositories

### 📊 State Management
- **Frontend State**: Managed via React Context (AuthContext, SessionContext, RepositoryContext)
- **Backend State**: Persisted in PostgreSQL with session-scoped data
- **Session Backbone**: Every chat, issue, and context operation is session-scoped

## Services Included

### 🔐 Authentication (`/auth`)
- GitHub OAuth authentication
- User session management  
- Profile management
- Shared authentication utilities (`auth_utils.py`)

### 🐙 GitHub Integration (`/github`)
- Repository management
- Issue creation and management
- Pull request handling
- Repository search

### 💬 Session-Scoped Chat Services (`/daifu`)
- Session management for repository contexts
- DAifu AI agent integration with OpenRouter
- Session-scoped chat history
- Context-aware conversations

### 📋 Enhanced Issue Management (`/issues`)
- Session-based issue creation with CodeInspector analysis
- GitHub issue conversion
- Issue status tracking
- Comprehensive context preservation

### 📁 File Dependencies (`/filedeps`)
- Repository file structure extraction
- File dependency analysis
- GitIngest integration
- File categorization

## API Endpoints

### Root Endpoints
- `GET /` - API information and service overview
- `GET /health` - Health check

### Authentication (`/auth`)
All authentication endpoints use GitHub OAuth flow.

- `GET /auth/login` - GitHub OAuth login redirect
- `GET /auth/callback` - OAuth callback handler
- `GET /auth/profile` - Get current user profile (requires Bearer token)
- `POST /auth/logout` - Logout and invalidate token
- `GET /auth/status` - Check authentication status
- `GET /auth/config` - Get OAuth configuration

**Authentication Headers Required:**
```
Authorization: Bearer <github_access_token>
```

### Session Management (`/daifu`)
Session-scoped operations for repository-aware conversations.

#### Session Operations
- `POST /daifu/sessions` - Create or get session for repository
  - **Frontend Usage**: `ApiService.createOrGetSession()`
  - **Request**: `CreateSessionRequest` (repo_owner, repo_name, repo_branch, title, description)
  - **Response**: `SessionResponse` with session_id, repo context
  
- `GET /daifu/sessions/{session_id}` - Get complete session context
  - **Frontend Usage**: `ApiService.getSessionContext()`
  - **Response**: `SessionContextResponse` with session, messages, context_cards

- `POST /daifu/sessions/{session_id}/touch` - Update session activity
  - **Purpose**: Keep session active and update last_activity timestamp

- `GET /daifu/sessions` - List user sessions by repository
  - **Query Params**: repo_owner, repo_name for filtering

#### Chat Operations
- `POST /daifu/chat/daifu` - Send message to DAifu agent
  - **Frontend Usage**: `ApiService.sendChatMessage()`
  - **Request**: `ChatRequest` with conversation_id (session_id), message, context_cards
  - **Response**: Chat response with reply, message_id, processing_time
  - **Validation**: Session must exist and belong to user

- `GET /daifu/chat/sessions` - Get user chat sessions
- `GET /daifu/chat/sessions/{session_id}/messages` - Get session messages  
- `GET /daifu/chat/sessions/{session_id}/statistics` - Get session statistics
- `PUT /daifu/chat/sessions/{session_id}/title` - Update session title
- `DELETE /daifu/chat/sessions/{session_id}` - Deactivate session

### Enhanced Issue Management (`/issues`)
Comprehensive issue management with session context and CodeInspector analysis.

#### Core Issue Operations
- `POST /issues/` - Create basic user issue
- `GET /issues/` - Get user issues with filtering (status, priority, repo_owner, repo_name)
- `GET /issues/{issue_id}` - Get specific issue
- `PUT /issues/{issue_id}/status` - Update issue status

#### Session-Based Issue Creation (Enhanced)
- `POST /issues/from-session-enhanced` - **PRIMARY ENDPOINT** for issue creation
  - **Frontend Usage**: `ApiService.createIssueFromSessionEnhanced()`
  - **Request**: `CreateIssueFromSessionRequest`
    ```json
    {
      "session_id": "string",
      "title": "string", 
      "description": "string",
      "priority": "medium",
      "use_code_inspector": true,
      "create_github_issue": false
    }
    ```
  - **Features**: 
    - CodeInspector agent analysis
    - Complete session context inclusion
    - Complexity scoring and time estimation
    - Optional GitHub issue creation
  - **Response**: `UserIssueResponse` with enhanced analysis

- `POST /issues/from-session` - Basic session-based issue creation
  - **Status**: Legacy endpoint, use `/from-session-enhanced` instead

#### GitHub Integration  
- `POST /issues/{issue_id}/create-github-issue` - Convert user issue to GitHub issue
- `POST /issues/create-with-context` - Create issue with file and chat context

#### Statistics
- `GET /issues/statistics` - Get user issue statistics

### GitHub Integration (`/github`)
- `GET /github/repositories` - User repositories
- `GET /github/repositories/{owner}/{repo}` - Repository details
- `POST /github/repositories/{owner}/{repo}/issues` - Create GitHub issue
- `GET /github/repositories/{owner}/{repo}/issues` - Repository issues
- `GET /github/repositories/{owner}/{repo}/pulls` - Repository PRs
- `GET /github/repositories/{owner}/{repo}/commits` - Repository commits
- `GET /github/search/repositories` - Search repositories

### File Dependencies (`/filedeps`)
- `GET /filedeps/` - File dependencies API info
- `GET /filedeps/repositories` - User repositories
- `GET /filedeps/repositories?repo_url=<url>` - Repository lookup by URL
- `GET /filedeps/repositories/{repository_id}` - Repository details
- `GET /filedeps/repositories/{repository_id}/files` - Repository files
- `POST /filedeps/extract` - Extract file dependencies

## Frontend-Backend API Mapping

### Session Flow
1. **Repository Selection** (Frontend)
   ```typescript
   // RepositoryContext selects repo
   selectedRepository = { repository: GitHubRepo, branch: string }
   ```

2. **Session Creation** (Frontend → Backend)
   ```typescript
   // SessionContext.createSession()
   const session = await ApiService.createOrGetSession(owner, name, branch)
   // session.session_id stored in SessionContext
   ```

3. **Chat Operations** (Frontend → Backend)  
   ```typescript
   // Chat.tsx sends messages
   const request: ChatRequest = {
     conversation_id: currentSessionId, // session.session_id
     message: { content, is_code },
     context_cards: string[]
   }
   await ApiService.sendChatMessage(request)
   ```

4. **Issue Creation** (Frontend → Backend)
   ```typescript
   // Enhanced issue creation from session
   await ApiService.createIssueFromSessionEnhanced({
     session_id: currentSessionId,
     title, description, priority,
     use_code_inspector: true
   })
   ```

### Authentication Flow
1. **Login**: `AuthService.login()` → `/auth/login` → GitHub OAuth
2. **Callback**: GitHub redirects to `/auth/callback` → token stored
3. **Token Storage**: Frontend stores token in localStorage as 'auth_token'
4. **API Requests**: All requests include `Authorization: Bearer <token>`

### State Persistence
- **Frontend**: SessionContext manages currentSessionId, auto-creates sessions
- **Backend**: Sessions persisted in chat_sessions table with repository context
- **Validation**: All operations validate session ownership and existence

## Removed/Deprecated Endpoints

The following redundant endpoints have been removed:

- ❌ `POST /daifu/chat/create-issue` - **REMOVED** (use `/issues/from-session-enhanced`)
- ❌ `POST /issues/from-chat` - **REMOVED** (use `/issues/from-session-enhanced`)

## Error Handling

### HTTP Status Codes
- `400` - Bad Request (invalid session, missing required fields)
- `401` - Unauthorized (invalid/expired token, authentication required)
- `404` - Not Found (session not found, user not found)
- `502` - Bad Gateway (OpenRouter API errors, upstream service issues)
- `500` - Internal Server Error (database errors, unexpected errors)

### Authentication Errors
All endpoints use shared authentication utilities (`auth_utils.py`):
- Invalid/expired tokens return 401 with re-authentication message
- Missing authentication returns 401 with login requirement
- User validation ensures proper session ownership

### Session Validation
- All session-scoped operations validate session existence
- Sessions must belong to authenticated user
- Invalid sessions return 400 Bad Request

## Development Configuration

### Environment Variables
```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost/yudai_v3

# GitHub OAuth
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret  
GITHUB_REDIRECT_URI=http://localhost:5173/auth/callback

# AI Integration
OPENROUTER_API_KEY=your_api_key
OPENROUTER_URL=https://openrouter.ai/api/v1/chat/completions
OPENROUTER_MODEL=deepseek/deepseek-r1-0528:free

# Security
SECRET_KEY=your_secret_key
```

### CORS Configuration
Configured for development:
- `http://localhost:3000` (React dev server)
- `http://localhost:5173` (Vite dev server)

### Docker Deployment
```bash
# Using Docker Compose (recommended)
docker compose up -d

# Direct Docker
docker build -t yudai-v3-backend .
docker run -p 8000:8000 yudai-v3-backend
```

## API Documentation Access
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Implementation Status

### ✅ Fully Implemented
- Session-scoped chat with repository context
- GitHub OAuth authentication with proper token management
- Enhanced issue creation with CodeInspector analysis  
- Session management and validation
- File dependency extraction
- GitHub repository integration

### 🚧 Partially Implemented
- Context cards (database ready, management APIs pending)
- Idea items (database ready, management APIs pending)

### 📋 Architecture Highlights
- **Session Backbone**: All operations are session-scoped with repository context
- **Type Safety**: Frontend TypeScript types match backend Pydantic models
- **Authentication**: Centralized auth utilities with consistent error handling
- **State Management**: Persistent session state with automatic session creation
- **AI Integration**: OpenRouter-powered chat with proper error handling

