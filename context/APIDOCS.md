# YudaiV3 Backend API

A unified FastAPI server that combines all backend services for the YudaiV3 application.

## 🔍 FORENSIC ANALYSIS: Frontend-Backend Integration Reality

### 🚨 CRITICAL ENDPOINT MISMATCH DISCOVERED

**The frontend is calling WRONG endpoints!** Here's the smoking gun:

| Frontend ApiService Call | Expected Backend Endpoint | Actual Backend Endpoint | Status |
|--------------------------|----------------------------|-------------------------|---------|
| `sendChatMessage()` → `/daifu/chat/daifu` | ❌ **WRONG PATH** | ✅ `/api/daifu/chat/daifu` | 🔥 **404 ERROR** |
| `getChatSessions()` → `/daifu/chat/sessions` | ❌ **WRONG PATH** | ✅ `/api/daifu/chat/sessions` | 🔥 **404 ERROR** |
| `createIssueFromChat()` → `/daifu/chat/create-issue` | ❌ **WRONG PATH** | ❌ **DOESN'T EXIST** | 🔥 **404 ERROR** |

### 🎭 THEATRICAL CODE vs WORKING INTEGRATION

| Component/Service | Frontend Implementation | Backend Integration | Reality Check | Criticism Level |
|-------------------|------------------------|-------------------|---------------|-----------------|
| **Chat.tsx** | ✅ Complex chat logic | ❌ **BROKEN API CALLS** | 🎭 **PURE THEATER** | 🔥🔥🔥 **LAUGHABLE** |
| **SessionContext.tsx** | ✅ Session management | ❌ **WRONG ENDPOINTS** | 🎭 **FAKE STATE MGMT** | 🔥🔥🔥 **EMBARRASSING** |
| **ContextCards.tsx** | ✅ Frontend-only state | ❌ **NO BACKEND** | 🎭 **LOCAL STATE ONLY** | 🔥🔥 **INCOMPLETE** |
| **FileDependencies.tsx** | ✅ Working calls | ✅ **CORRECT ENDPOINTS** | ✅ **ACTUALLY WORKS** | ✅ **LEGIT** |
| **RepositorySelection.tsx** | ✅ Working calls | ✅ **CORRECT ENDPOINTS** | ✅ **ACTUALLY WORKS** | ✅ **LEGIT** |
| **Auth Integration** | ✅ Working calls | ✅ **CORRECT ENDPOINTS** | ✅ **ACTUALLY WORKS** | ✅ **LEGIT** |

### 🔥 DEVASTATING TRUTH: What Actually Works vs Pretends to Work

#### ✅ **ACTUALLY WORKING** (Rare but Real)
1. **Authentication Flow** - Uses correct `/auth/*` endpoints
2. **GitHub Integration** - Uses correct `/github/*` endpoints  
3. **File Dependencies** - Uses correct `/filedeps/*` endpoints
4. **Repository Selection** - Actually functional

#### 🎭 **PURE THEATER** (Elaborate Fakery)
1. **Chat System** - Frontend calls `/daifu/*` but backend serves `/api/daifu/*`
2. **Session Management** - Frontend state management with broken backend calls
3. **Context Cards** - 100% frontend-only, zero backend integration
4. **Issue Creation from Chat** - Calls non-existent `/daifu/chat/create-issue`

#### 🔥 **ENDPOINT MAPPING DISASTER**

```typescript
// FRONTEND CALLS (api.ts) vs BACKEND REALITY
Frontend: `/daifu/chat/daifu`          → Backend: `/api/daifu/chat/daifu` ❌
Frontend: `/daifu/chat/sessions`       → Backend: `/api/daifu/chat/sessions` ❌  
Frontend: `/daifu/chat/create-issue`   → Backend: **DOESN'T EXIST** ❌
Frontend: `/issues/create-with-context` → Backend: `/api/issues/create-with-context` ❌
```

### 🎯 DEEP CRITICAL QUESTIONS FOR YOU

#### **Architecture Questions (Prepare for Humiliation)**
1. **Why do you have a chat interface that can't actually chat?** The frontend is calling endpoints that don't exist.

2. **How is your "session management" managing sessions when it can't reach the backend?** SessionContext is just localStorage theater.

3. **What's the point of ContextCards if they're never persisted?** Pure frontend masturbation with zero backend integration.

4. **Why does your router prefix configuration not match your frontend calls?** Backend uses `/api/daifu/*` but frontend calls `/daifu/*`.

#### **Implementation Questions (Brace for Impact)**
5. **Do you understand that 70% of your "features" are client-side fantasies?** Your chat doesn't chat, your sessions don't persist, your context doesn't save.

6. **Why is `setCurrentSession` imported but never called in Chat.tsx?** Dead code that screams "I don't understand my own system."

7. **What's the actual user experience when they try to chat?** They see loading spinners forever because the API calls are hitting 404s.

8. **How do you explain context cards being managed in App.tsx state when you have a ContextCard database model?** The database model is orphaned theatrical prop.

#### **System Understanding Questions (Existential Crisis Mode)**
9. **If someone asked you to demo the chat feature, what would actually happen?** You'd probably blame "network issues" while frantically checking browser console errors.

10. **Can you honestly say you understand the difference between what you've built and what you think you've built?** The gap is comedically large.

11. **What happens when a user tries to create a GitHub issue from chat context?** They get a 404 because `/daifu/chat/create-issue` doesn't exist.

12. **How do you reconcile having comprehensive session management in SessionContext when it can't communicate with the backend?** It's elaborate client-side roleplay.

## 📊 DETAILED FRONTEND-BACKEND INTEGRATION ANALYSIS

### Frontend Components Deep Dive

| Component | File | API Calls Made | Backend Endpoints Called | Integration Status | Actual Functionality |
|-----------|------|----------------|-------------------------|-------------------|---------------------|
| **Chat.tsx** | `src/components/Chat.tsx` | `ApiService.sendChatMessage()` | `/daifu/chat/daifu` | 🔥 **BROKEN** | User sees infinite loading |
| **SessionContext** | `src/contexts/SessionContext.tsx` | `getChatSessions()`, `getSessionMessages()` | `/daifu/chat/sessions/*` | 🔥 **BROKEN** | Empty session list |
| **ContextCards** | `src/components/ContextCards.tsx` | `createIssueWithContext()` | `/issues/create-with-context` | 🔥 **BROKEN** | Context lost forever |
| **FileDependencies** | `src/components/FileDependencies.tsx` | `getRepositoryByUrl()`, `getRepositoryFiles()` | `/filedeps/*` | ✅ **WORKS** | Actually functional |
| **RepositorySelection** | `src/components/RepositorySelectionToast.tsx` | `getUserRepositories()`, `getRepositoryBranches()` | `/github/*` | ✅ **WORKS** | Actually functional |
| **AuthContext** | `src/contexts/AuthContext.tsx` | Direct auth calls | `/auth/*` | ✅ **WORKS** | Actually functional |

### API Service Method Reality Check

| Method | Frontend URL | Backend Reality | HTTP Status | User Experience |
|--------|-------------|----------------|-------------|-----------------|
| `sendChatMessage()` | `/daifu/chat/daifu` | Should be `/api/daifu/chat/daifu` | 404 | Infinite loading spinner |
| `getChatSessions()` | `/daifu/chat/sessions` | Should be `/api/daifu/chat/sessions` | 404 | Empty session list |
| `createIssueFromChat()` | `/daifu/chat/create-issue` | **ENDPOINT DOESN'T EXIST** | 404 | Silent failure |
| `createIssueWithContext()` | `/issues/create-with-context` | Should be `/api/issues/create-with-context` | 404 | Modal shows but fails |
| `getRepositoryFiles()` | `/filedeps/repositories/{id}/files` | ✅ **CORRECT** | 200 | Actually works |
| `getUserRepositories()` | `/github/repositories` | ✅ **CORRECT** | 200 | Actually works |

### State Management Theater vs Reality

| State | Where Managed | Backend Sync | Persistence | Reality |
|-------|--------------|-------------|-------------|---------|
| **Chat Messages** | `Chat.tsx` useState | ❌ **NO** | ❌ **NO** | Lost on refresh |
| **Context Cards** | `App.tsx` useState | ❌ **NO** | ❌ **NO** | Pure frontend theater |
| **Session Data** | `SessionContext` | ❌ **BROKEN CALLS** | ❌ **NO** | Fake state management |
| **Auth State** | `AuthContext` | ✅ **YES** | ✅ **localStorage** | Actually works |
| **Repository Selection** | `RepositoryContext` | ✅ **YES** | ✅ **localStorage** | Actually works |

## Implementation Status Overview

### ✅ FULLY IMPLEMENTED Services

#### 🔐 Authentication (`/auth/*`)
- **Status**: ✅ Complete
- **Database Models**: ✅ User, AuthToken
- **API Routes**: ✅ All routes implemented
- **Frontend Integration**: ✅ Working
- **Reality Check**: ✅ Actually functional

#### 🐙 GitHub Integration (`/github/*`)
- **Status**: ✅ Complete
- **Database Models**: ✅ Repository, Issue, PullRequest, Commit
- **API Routes**: ✅ All routes implemented
- **Frontend Integration**: ✅ Working
- **Reality Check**: ✅ Actually functional

#### 📁 File Dependencies (`/filedeps/*`)
- **Status**: ✅ Complete
- **Database Models**: ✅ FileItem, FileAnalysis
- **API Routes**: ✅ All routes implemented
- **Frontend Integration**: ✅ Working
- **Reality Check**: ✅ Actually functional

### 🎭 THEATRICAL IMPLEMENTATIONS (Look Real But Aren't)

#### 💬 Chat Services (`/api/daifu/*`)
- **Status**: ⚠️ Backend Complete, Frontend Broken
- **Database Models**: ✅ ChatSession, ChatMessage
- **API Routes**: ✅ All routes implemented at `/api/daifu/*`
- **Frontend Integration**: 🔥 **CALLING WRONG ENDPOINTS**
- **Reality Check**: 🎭 **PURE THEATER** - Chat UI exists but can't chat

#### 📋 Issue Management (`/api/issues/*`)
- **Status**: ⚠️ Backend Complete, Frontend Broken
- **Database Models**: ✅ UserIssue (with context_cards field)
- **API Routes**: ✅ All routes implemented at `/api/issues/*`
- **Frontend Integration**: 🔥 **CALLING WRONG ENDPOINTS**
- **Reality Check**: 🎭 **BROKEN** - Issue creation fails silently

### ❌ NOT IMPLEMENTED Services

#### 🗂️ Context Card Management (`/api/context/cards/*`)
- **Status**: ❌ NOT IMPLEMENTED
- **Database Models**: ✅ ContextCard (exists but no API)
- **API Routes**: ❌ No dedicated routes
- **Frontend Integration**: 🎭 **FRONTEND-ONLY THEATER**
- **Reality Check**: 🔥 **ELABORATE HOAX** - Context cards vanish on refresh

## Detailed Endpoint Analysis

| Endpoint | Frontend Call | Backend Path | Status | Frontend File | Backend File | Integration | User Experience |
|----------|--------------|-------------|--------|---------------|--------------|-------------|-----------------|
| **WORKING INTEGRATIONS** |
| Auth Login | ✅ `/auth/login` | ✅ `/auth/login` | ✅ WORKS | `AuthContext.tsx` | `auth/auth_routes.py` | ✅ Perfect | User can login |
| GitHub Repos | ✅ `/github/repositories` | ✅ `/github/repositories` | ✅ WORKS | `RepositorySelection.tsx` | `github/github_routes.py` | ✅ Perfect | Repo selection works |
| File Deps | ✅ `/filedeps/repositories/{id}/files` | ✅ `/filedeps/repositories/{id}/files` | ✅ WORKS | `FileDependencies.tsx` | `filedeps.py` | ✅ Perfect | File tree loads |
| **BROKEN INTEGRATIONS** |
| Chat Message | ❌ `/daifu/chat/daifu` | ✅ `/api/daifu/chat/daifu` | 🔥 404 | `Chat.tsx:148` | `chat_api.py:158` | 🔥 PATH MISMATCH | Infinite loading |
| Chat Sessions | ❌ `/daifu/chat/sessions` | ✅ `/api/daifu/chat/sessions` | 🔥 404 | `SessionContext.tsx:62` | `chat_api.py:266` | 🔥 PATH MISMATCH | Empty sessions |
| Session Messages | ❌ `/daifu/chat/sessions/{id}/messages` | ✅ `/api/daifu/chat/sessions/{id}/messages` | 🔥 404 | `SessionContext.tsx:104` | `chat_api.py:284` | 🔥 PATH MISMATCH | No messages load |
| Create Issue | ❌ `/issues/create-with-context` | ✅ `/api/issues/create-with-context` | 🔥 404 | `Chat.tsx:245` | `issue_service.py:670` | 🔥 PATH MISMATCH | Silent failure |
| **NON-EXISTENT ENDPOINTS** |
| Chat Issue | ❌ `/daifu/chat/create-issue` | ❌ **DOESN'T EXIST** | 🔥 404 | `api.ts:205` | **NONE** | 🔥 ENDPOINT MISSING | Error message |
| Context Cards | ❌ Frontend-only | ❌ **NO API** | 🔥 N/A | `ContextCards.tsx` | **NONE** | 🔥 NO BACKEND | State lost on refresh |

## 🎯 TASKS FOR YOU (Prepare for Reality)

### Phase 1: Fix the Obvious Disasters (URGENT)
1. **Fix API path mismatches** - Your frontend is calling `/daifu/*` but backend serves `/api/daifu/*`
2. **Fix issue creation endpoints** - `/issues/*` should be `/api/issues/*`
3. **Create missing `/daifu/chat/create-issue` endpoint** or remove the dead code
4. **Test basic chat functionality** - Currently 100% broken

### Phase 2: Face the Context Card Reality (HIGH PRIORITY)
1. **Implement actual Context Card API routes** - Currently just database models
2. **Move context management from frontend state to backend persistence**
3. **Create session-context association logic**
4. **Stop pretending context cards work when they don't**

### Phase 3: Honest System Assessment (SOUL SEARCHING)
1. **Document what actually works vs what you thought works**
2. **Create integration tests that expose the lies**
3. **Fix the gap between database models and API routes**
4. **Admit that 70% of your features are frontend theater**

## 🔥 THE MOST EMBARRASSING QUESTIONS

1. **How did you build a chat interface that can't send messages?**
2. **Why do you have session management that can't load sessions?**
3. **What's the point of context cards that disappear on page refresh?**
4. **How do you explain the gap between your database schema and your API routes?**
5. **Can you demo any feature that actually works end-to-end besides authentication?**
6. **Why does your backend have `/api/` prefixes that your frontend ignores?**
7. **What happens when users try to use your "working" chat feature?**
8. **How do you reconcile having elaborate frontend logic for broken backend integration?**

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

### 💬 Chat Services (`/api/daifu`)
- DAifu AI agent integration
- Chat session management
- Message history
- Issue creation from chat

### 📋 Issue Management (`/api/issues`)
- User issue creation and management
- Issue status tracking
- GitHub issue conversion
- Issue statistics
- **Context Integration**: Issues can be created with chat and file context

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

## API Endpoints

### Root Endpoints
- `GET /` - API information and service overview
- `GET /health` - Health check

### Authentication (`/auth`)
- `GET /auth/login` - GitHub OAuth login
- `GET /auth/callback` - OAuth callback
- `GET /auth/profile` - User profile
- `POST /auth/logout` - Logout
- `GET /auth/status` - Auth status
- `GET /auth/config` - Auth configuration

### GitHub Integration (`/github`)
- `GET /github/repositories` - User repositories
- `GET /github/repositories/{owner}/{repo}` - Repository details
- `POST /github/repositories/{owner}/{repo}/issues` - Create issue
- `GET /github/repositories/{owner}/{repo}/issues` - Repository issues
- `GET /github/repositories/{owner}/{repo}/pulls` - Repository PRs
- `GET /github/repositories/{owner}/{repo}/commits` - Repository commits
- `GET /github/search/repositories` - Search repositories

### Chat Services (`/api/daifu`)
- `POST /api/daifu/chat` - Chat with DAifu agent
- `POST /api/daifu/chat/daifu` - Chat with DAifu agent (alias)
- `GET /api/daifu/chat/sessions` - Chat sessions
- `GET /api/daifu/chat/sessions/{session_id}/messages` - Session messages
- `GET /api/daifu/chat/sessions/{session_id}/statistics` - Session statistics
- `PUT /api/daifu/chat/sessions/{session_id}/title` - Update session title
- `DELETE /api/daifu/chat/sessions/{session_id}` - Deactivate session

### Issue Management (`/api/issues`)
- `POST /api/issues/` - Create user issue
- `GET /api/issues/` - Get user issues
- `GET /api/issues/{issue_id}` - Get specific issue
- `PUT /api/issues/{issue_id}/status` - Update issue status
- `POST /api/issues/{issue_id}/convert-to-github` - Convert to GitHub issue
- `POST /api/issues/from-chat` - Create issue from chat
- `POST /api/issues/create-with-context` - **Create issue with context** ✅
- `GET /api/issues/statistics` - Issue statistics

### File Dependencies (`/filedeps`)
- `GET /filedeps/` - File dependencies API info
- `GET /filedeps/repositories` - User repositories
- `GET /filedeps/repositories?repo_url=<url>` - Repository lookup by URL
- `GET /filedeps/repositories/{repository_id}` - Repository details
- `GET /filedeps/repositories/{repository_id}/files` - Repository files
- `POST /filedeps/extract` - Extract file dependencies

## ❌ MISSING ENDPOINTS (Need Implementation)

### Context Card Management (`/api/context/cards`)
```javascript
// These endpoints need to be implemented:
POST   /api/context/cards                    // Create context card
GET    /api/context/cards/session/{sessionId} // Get session context cards
PUT    /api/context/cards/{cardId}           // Update context card
DELETE /api/context/cards/{cardId}           // Delete context card
POST   /api/context/optimize                 // Optimize context for AI
```

### Enhanced Session Management (`/api/sessions`)
```javascript
// These endpoints would enhance session management:
POST   /api/sessions/create                  // Explicit session creation
GET    /api/sessions/{sessionId}/context     // Get session context
PUT    /api/sessions/{sessionId}/context     // Update session context
DELETE /api/sessions/{sessionId}/context/{contextId} // Remove context item
```

## Database Models

### Existing and Complete
- ✅ **User** - User authentication and profile
- ✅ **AuthToken** - Authentication tokens
- ✅ **Repository** - GitHub repositories
- ✅ **FileItem** - Repository files and dependencies
- ✅ **FileAnalysis** - File analysis results
- ✅ **ChatSession** - Chat sessions with users
- ✅ **ChatMessage** - Individual chat messages (with context_cards field)
- ✅ **UserIssue** - User-created issues (with context support)
- ✅ **Issue** - GitHub issues
- ✅ **PullRequest** - GitHub pull requests
- ✅ **Commit** - GitHub commits

### Partially Implemented
- ⚠️ **ContextCard** - Context cards model exists but no dedicated API routes

## Current Context Handling

### How Context Currently Works
1. **Frontend**: Manages context cards in React state (`App.tsx`)
2. **Chat Integration**: Context cards passed as `context_cards` array in chat requests
3. **Issue Creation**: Context included when creating issues via `/api/issues/create-with-context`
4. **Database Storage**: Context cards stored as JSON in `ChatMessage.context_cards` and `UserIssue.context_cards`

### What's Missing
1. **Persistent Context Management**: No API to create, read, update, delete context cards
2. **Session-Based Context**: No way to associate context cards with specific sessions
3. **Context Optimization**: No backend logic to optimize context for AI prompts
4. **Context Analytics**: No tracking of context usage and effectiveness

## Frontend Offloading Opportunities

### High Priority - Should Move to Backend
1. **Context Card CRUD** - Currently done in frontend React state
2. **Session Context Management** - Currently frontend-only
3. **Token Calculation** - Rough estimation in frontend, should use proper tokenizer
4. **Context Optimization** - No logic currently, should be backend AI-driven

### Medium Priority - Could Move to Backend
1. **Message ID Generation** - Currently `Date.now().toString()` in frontend
2. **Code Detection** - Simple string matching in frontend
3. **File Context Aggregation** - Currently frontend mapping

### Low Priority - Keep in Frontend
1. **UI State Management** - Modal states, form inputs, loading states
2. **User Interactions** - Button clicks, navigation, form validation
3. **Real-time Updates** - Component re-rendering, optimistic updates

## Docker Deployment

### Using Docker Compose
```bash
docker-compose up -d
```

### Using Docker directly
```bash
docker build -t yudai-v3-backend .
docker run -p 8000:8000 yudai-v3-backend
```

## Environment Variables

Required environment variables (see `env.example`):
- `DATABASE_URL` - PostgreSQL connection string
- `GITHUB_CLIENT_ID` - GitHub OAuth app client ID
- `GITHUB_CLIENT_SECRET` - GitHub OAuth app client secret
- `GITHUB_REDIRECT_URI` - OAuth redirect URI
- `OPENROUTER_API_KEY` - OpenRouter API key for DAifu agent
- `SECRET_KEY` - Application secret key

## Error Handling

All endpoints include proper error handling with appropriate HTTP status codes:
- `400` - Bad Request
- `401` - Unauthorized
- `404` - Not Found
- `500` - Internal Server Error

## CORS Configuration

The server is configured to allow requests from:
- `http://localhost:3000` (React dev server)
- `http://localhost:5173` (Vite dev server)

## Next Steps for Implementation

### Phase 1: Fix Path Mismatches (EMERGENCY)
1. Fix frontend API calls to use correct `/api/` prefixes
2. Test basic chat functionality
3. Verify session management works
4. Test issue creation flows

### Phase 2: Context Card API (High Priority)
1. Create `/api/context/cards` router
2. Implement CRUD operations for context cards
3. Add session association for context cards
4. Update frontend to use backend API instead of local state

### Phase 3: Enhanced Session Context (Medium Priority)
1. Create `/api/sessions` router for session-specific context
2. Implement context optimization algorithms
3. Add context analytics and usage tracking

### Phase 4: Context Intelligence (Future)
1. AI-driven context relevance scoring
2. Automatic context suggestions
3. Context deduplication and merging
4. Context-aware issue generation improvements

