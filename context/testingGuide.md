# YudaiV3 Manual Testing Guide

This guide provides a comprehensive testing framework for YudaiV3 functionality, categorizing features by implementation status and providing step-by-step testing procedures.

## Environment Setup

### Required .env File
Create a `.env` file in the project root with the following variables:

```env
# Database Configuration
DATABASE_URL=postgresql://yudai_user:yudai_password@db:5432/yudai_db
DB_ECHO=false
POSTGRES_DB=yudai_db
POSTGRES_USER=yudai_user
POSTGRES_PASSWORD=yudai_password

# GitHub OAuth Configuration
# Get these from https://github.com/settings/developers
GITHUB_CLIENT_ID=your_github_client_id_here
GITHUB_CLIENT_SECRET=your_github_client_secret_here
GITHUB_REDIRECT_URI=http://localhost:3000/auth/callback

# OpenRouter API Configuration (for DAifu chat)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# API Configuration
HOST=0.0.0.0
PORT=8000
API_WORKERS=1

# Frontend Configuration
VITE_API_URL=http://localhost:8000
NODE_ENV=development

# JWT Configuration (optional)
JWT_SECRET_KEY=your_jwt_secret_key_change_this_in_production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Development
PYTHONPATH=/app
```

### Setup Instructions
1. **Clone Repository**: `git clone <repo_url> && cd YudaiV3`
2. **Environment File**: Copy the .env template above and fill in your API keys
3. **Start Services**: `docker-compose -f docker-compose.dev.yml up -d`
4. **Initialize Database**: `docker-compose -f docker-compose.dev.yml exec backend python db/init_db.py --init`
5. **Verify Services**: 
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs

---

## Testing Categories

## 🟢 Category 1: Implemented in Backend

### 1.1 GitHub OAuth Authentication

**Endpoints**: `/auth/*`  
**Status**: ✅ Fully Implemented  
**Test Coverage**: Extensive integration tests available

#### Test Cases:

**T1.1.1: OAuth Configuration Check**
```bash
# Test: Verify OAuth configuration endpoint
curl -X GET "http://localhost:8000/auth/status"
# Expected: JSON with auth configuration details
```

**T1.1.2: Login Flow Initiation**
```bash
# Test: Start OAuth login flow
curl -X GET "http://localhost:8000/auth/login"
# Expected: HTTP 307 redirect to GitHub OAuth URL
```

**T1.1.3: OAuth Callback Handling**
- **Manual Test**: Complete OAuth flow in browser
- Navigate to: `http://localhost:8000/auth/login`
- Authorize with GitHub
- **Expected**: Successful callback processing and token storage

**T1.1.4: User Profile Retrieval**
```bash
# Test: Get authenticated user profile
# Note: Requires valid auth token from successful OAuth
curl -X GET "http://localhost:8000/auth/profile" \
  -H "Authorization: Bearer <token>"
# Expected: User profile data from GitHub
```

**T1.1.5: Logout Functionality**
```bash
# Test: User logout
curl -X POST "http://localhost:8000/auth/logout"
# Expected: Success response and token deactivation
```

### 1.2 GitHub API Integration

**Endpoints**: `/github/*`  
**Status**: ✅ Fully Implemented  
**Dependencies**: Requires GitHub OAuth authentication

#### Test Cases:

**T1.2.1: User Repositories**
```bash
# Test: Fetch authenticated user's repositories
curl -X GET "http://localhost:8000/github/repositories" \
  -H "Authorization: Bearer <token>"
# Expected: List of user's GitHub repositories
```

**T1.2.2: Repository Details**
```bash
# Test: Get specific repository details
curl -X GET "http://localhost:8000/github/repositories/owner/repo" \
  -H "Authorization: Bearer <token>"
# Expected: Detailed repository metadata
```

**T1.2.3: Repository Issues**
```bash
# Test: Fetch repository issues
curl -X GET "http://localhost:8000/github/repositories/owner/repo/issues" \
  -H "Authorization: Bearer <token>"
# Expected: List of repository issues
```

**T1.2.4: Repository Pull Requests**
```bash
# Test: Fetch repository pull requests
curl -X GET "http://localhost:8000/github/repositories/owner/repo/pulls" \
  -H "Authorization: Bearer <token>"
# Expected: List of repository pull requests
```

**T1.2.5: Create GitHub Issue**
```bash
# Test: Create new issue in repository
curl -X POST "http://localhost:8000/github/repositories/owner/repo/issues" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Issue from API",
    "body": "This is a test issue created via API",
    "labels": ["bug", "api-test"]
  }'
# Expected: Created issue details
```

### 1.3 DAifu Chat API

**Endpoints**: `/chat/daifu`  
**Status**: ✅ Implemented with Authentication  
**Dependencies**: Requires OpenRouter API key and user authentication

#### Test Cases:

**T1.3.1: Chat Message Processing**
```bash
# Test: Send chat message to DAifu agent
curl -X POST "http://localhost:8000/chat/daifu" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "content": "Help me create a GitHub issue for implementing a dark mode toggle",
      "is_code": false
    },
    "conversation_id": "test-conv-1",
    "context_cards": [],
    "repo_owner": "testuser",
    "repo_name": "test-repo"
  }'
# Expected: DAifu agent response with GitHub context
```

**T1.3.2: Conversation History**
```bash
# Test: Retrieve chat sessions
curl -X GET "http://localhost:8000/chat/sessions" \
  -H "Authorization: Bearer <token>"
# Expected: List of user's chat sessions
```

### 1.4 File Dependencies API

**Endpoints**: `/extract`, `/repositories/*`  
**Status**: ✅ Implemented with Database Persistence  
**Dependencies**: Requires GitIngest integration

#### Test Cases:

**T1.4.1: Repository Analysis**
```bash
# Test: Extract file dependencies from repository
curl -X POST "http://localhost:8000/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/nodejs/node",
    "max_file_size": 100000
  }'
# Expected: Hierarchical file structure with analysis data
```

**T1.4.2: Repository Listing**
```bash
# Test: Get all processed repositories
curl -X GET "http://localhost:8000/repositories" \
  -H "Authorization: Bearer <token>"
# Expected: List of analyzed repositories for user
```

**T1.4.3: Repository Files**
```bash
# Test: Get files for specific repository
curl -X GET "http://localhost:8000/repositories/1/files"
# Expected: List of file items for repository ID 1
```

### 1.5 Issue Management Service

**Endpoints**: `/issues/*`  
**Status**: ✅ Implemented  
**Dependencies**: Requires user authentication

#### Test Cases:

**T1.5.1: Create User Issue**
```bash
# Test: Create new user-generated issue
curl -X POST "http://localhost:8000/issues" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Implement Dark Mode Toggle",
    "description": "Add a dark mode toggle to the settings page",
    "repo_owner": "testuser",
    "repo_name": "test-repo",
    "priority": "medium",
    "issue_text_raw": "We need a dark mode toggle in the UI"
  }'
# Expected: Created issue with unique issue_id
```

**T1.5.2: List User Issues**
```bash
# Test: Retrieve user's issues with filtering
curl -X GET "http://localhost:8000/issues?status=pending&limit=10" \
  -H "Authorization: Bearer <token>"
# Expected: Filtered list of user issues
```

### 1.6 Database Operations

**Status**: ✅ Fully Implemented with PostgreSQL  
**Test Coverage**: Database schema and CRUD operations

#### Test Cases:

**T1.6.1: Database Health Check**
```bash
# Test: Verify database connection
docker-compose -f docker-compose.dev.yml exec backend python db/init_db.py --check
# Expected: All tables exist and connections successful
```

**T1.6.2: Database Initialization**
```bash
# Test: Initialize/recreate database schema
docker-compose -f docker-compose.dev.yml exec backend python db/init_db.py --init
# Expected: All tables created successfully
```

---

## 🟡 Category 2: Implemented in Frontend

### 2.1 FileDependencies Component

**Location**: `src/components/FileDependencies.tsx`  
**Status**: ✅ Implemented with Backend Integration  
**Connected**: ✅ `/extract` endpoint

#### Test Cases:

**T2.1.1: Component Rendering**
- Navigate to FileDependencies tab
- **Expected**: Component loads with file tree interface

**T2.1.2: Repository Analysis**
- Click refresh button or provide repo URL
- **Expected**: Loading state, then file tree with categorized files

**T2.1.3: File Tree Interaction**
- Expand/collapse directories
- **Expected**: Tree structure updates correctly

**T2.1.4: File Details**
- Click on file items
- **Expected**: File details display with token counts

### 2.2 Chat Component

**Location**: `src/components/Chat.tsx`  
**Status**: ✅ UI Implemented  
**Connected**: ❌ Not connected to backend

#### Test Cases:

**T2.2.1: Message Input**
- Type message and press Enter
- **Expected**: Message appears in chat history (local only)

**T2.2.2: Code Detection**
- Type code-like content
- **Expected**: Code formatting applied

**T2.2.3: Context Addition**
- Hover over messages and click "Add to Context"
- **Expected**: Context addition UI triggers

### 2.3 Context Cards Component

**Location**: `src/components/ContextCards.tsx`  
**Status**: ✅ UI Implemented  
**Connected**: ❌ Not connected to backend

#### Test Cases:

**T2.3.1: Empty State**
- Navigate to Context Cards tab
- **Expected**: Empty state message displayed

**T2.3.2: Card Display**
- **Manual**: Add sample context cards via props
- **Expected**: Cards display with source icons and token counts

### 2.4 Ideas Component

**Location**: `src/components/IdeasToImplement.tsx`  
**Status**: ✅ UI Implemented  
**Connected**: ❌ Not connected to backend

#### Test Cases:

**T2.4.1: Generate Ideas**
- Click "Generate Ideas" button
- **Expected**: Loading state, then sample ideas appear

**T2.4.2: Create Issue from Idea**
- Click "Create Issue" on any idea
- **Expected**: Issue creation callback triggers

### 2.5 Navigation & Layout

**Components**: `TopBar`, `Sidebar`, Modals  
**Status**: ✅ Fully Implemented

#### Test Cases:

**T2.5.1: Tab Navigation**
- Click through all sidebar tabs
- **Expected**: Content areas switch correctly

**T2.5.2: Sidebar Collapse**
- Click collapse/expand button
- **Expected**: Sidebar width toggles

**T2.5.3: Progress Indicators**
- **Visual**: Check TopBar progress states
- **Expected**: Current step highlighted correctly

---

## 🔴 Category 3: Integration Implementation Needed

### 3.1 Frontend Authentication Flow

**Status**: ❌ Missing Integration  
**Backend**: ✅ Available  
**Frontend**: ❌ Not implemented

#### Missing Implementation:

**T3.1.1: Login Component**
```typescript
// NEEDS IMPLEMENTATION: Login/Auth component
// Location: src/components/Auth.tsx (doesn't exist)
// Required: GitHub OAuth button and callback handling
```

**T3.1.2: Auth Context Provider**
```typescript
// NEEDS IMPLEMENTATION: Authentication context
// Location: src/contexts/AuthContext.tsx (doesn't exist)
// Required: User state management, token storage
```

**T3.1.3: Protected Routes**
```typescript
// NEEDS IMPLEMENTATION: Route protection
// Required: Redirect unauthenticated users to login
```

#### Test Requirements:
- [ ] User can click "Login with GitHub"
- [ ] OAuth callback redirects properly
- [ ] User state persists across sessions
- [ ] Protected features require authentication

### 3.2 Chat-Backend Integration

**Status**: ❌ Missing Integration  
**Backend**: ✅ `/chat/daifu` available  
**Frontend**: ✅ UI ready but not connected

#### Missing Implementation:

**T3.2.1: Chat API Integration**
```typescript
// NEEDS IMPLEMENTATION: Chat service
// Location: src/services/chatService.ts (doesn't exist)
// Required: HTTP client for DAifu API
```

**T3.2.2: Conversation Management**
```typescript
// NEEDS IMPLEMENTATION: Conversation state
// Required: Message history, conversation IDs
```

#### Test Requirements:
- [ ] Send message to DAifu agent
- [ ] Receive AI responses
- [ ] Maintain conversation history
- [ ] Handle loading/error states

### 3.3 Context Cards Management

**Status**: ❌ Missing Integration  
**Backend**: ❌ API endpoints not fully implemented  
**Frontend**: ✅ UI ready

#### Missing Implementation:

**T3.3.1: Context Cards API**
```bash
# NEEDS IMPLEMENTATION: Backend endpoints
# POST /context-cards
# GET /context-cards
# PUT /context-cards/{id}
# DELETE /context-cards/{id}
```

**T3.3.2: Context Cards Service**
```typescript
// NEEDS IMPLEMENTATION: Frontend service
// Location: src/services/contextService.ts (doesn't exist)
```

#### Test Requirements:
- [ ] Create context cards from chat/files
- [ ] Edit and delete context cards
- [ ] Apply context to chat conversations
- [ ] Manage token limits

### 3.4 Ideas Management Integration

**Status**: ❌ Missing Integration  
**Backend**: ❌ API endpoints not fully implemented  
**Frontend**: ✅ UI ready with sample data

#### Missing Implementation:

**T3.4.1: Ideas API**
```bash
# NEEDS IMPLEMENTATION: Backend endpoints
# POST /ideas
# GET /ideas
# PUT /ideas/{id}
# DELETE /ideas/{id}
```

**T3.4.2: Ideas Service**
```typescript
// NEEDS IMPLEMENTATION: Frontend service
// Location: src/services/ideasService.ts (doesn't exist)
```

#### Test Requirements:
- [ ] Generate ideas from AI
- [ ] Create issues from ideas
- [ ] Track idea complexity and status
- [ ] Manage idea lifecycle

### 3.5 Full Issue Creation Workflow

**Status**: ❌ Missing Integration  
**Backend**: ✅ Partially available  
**Frontend**: ❌ Not connected

#### Missing Implementation:

**T3.5.1: Issue Creation Flow**
```typescript
// NEEDS IMPLEMENTATION: End-to-end issue creation
// Flow: Chat → Context → Issue → GitHub
// Required: Multi-step wizard or workflow
```

#### Test Requirements:
- [ ] Create issue from chat conversation
- [ ] Include context cards in issue
- [ ] Submit to GitHub via backend API
- [ ] Track issue creation status

### 3.6 File Dependencies Full Integration

**Status**: ⚠️ Partially Integrated  
**Backend**: ✅ Available but some features disabled  
**Frontend**: ✅ Connected to `/extract`

#### Missing Implementation:

**T3.6.1: Repository Management**
```typescript
// NEEDS IMPLEMENTATION: Repository selection UI
// Required: Browse user repositories, select for analysis
```

**T3.6.2: Analysis History**
```typescript
// NEEDS IMPLEMENTATION: Analysis management
// Required: View past analyses, re-analyze repositories
```

#### Test Requirements:
- [ ] Select repositories from GitHub
- [ ] View analysis history
- [ ] Re-analyze existing repositories
- [ ] Export analysis results

---

## Testing Priorities

### High Priority (Blocking User Flows)
1. **Frontend Authentication** - Critical for all protected features
2. **Chat-Backend Integration** - Core application functionality
3. **Issue Creation Workflow** - Primary user goal

### Medium Priority (Enhanced Functionality)
4. **Context Cards Management** - Improves user experience
5. **Repository Management UI** - Better file dependency workflow

### Low Priority (Future Enhancements)
6. **Ideas Management** - Nice-to-have feature
7. **Advanced Analytics** - Analysis insights and reporting

---

## Known Issues & Limitations

### Current Issues
1. **T-Issue-001**: `/extract` endpoint disabled in latest backend version
2. **T-Issue-002**: DAifu agent requires manual repo_owner/repo_name parameters
3. **T-Issue-003**: No user authentication UI in frontend
4. **T-Issue-004**: Context cards backend API incomplete

### Testing Limitations
1. **GitHub OAuth**: Requires valid GitHub App configuration
2. **OpenRouter API**: Requires valid API key for DAifu chat
3. **Docker Dependencies**: All tests require Docker environment
4. **Database State**: Tests may affect shared database state

---

## Test Execution Commands

### Backend Tests
```bash
# Run all backend integration tests
cd backend && python run_tests.py -v

# Run specific test categories
python run_tests.py --auth -v      # Authentication tests
python run_tests.py --github -v    # GitHub API tests
python run_tests.py --daifu -v     # DAifu integration tests
```

### Frontend Tests
```bash
# Run frontend tests (when implemented)
pnpm test

# Run E2E tests (when implemented)
pnpm test:e2e
```

### Full Stack Tests
```bash
# Start all services
docker-compose -f docker-compose.dev.yml up -d

# Run backend tests
docker-compose -f docker-compose.dev.yml exec backend python run_tests.py -v

# Manual frontend testing at http://localhost:5173
```

---

## Success Criteria

### Backend Implementation ✅
- [x] All API endpoints respond correctly
- [x] Database operations work reliably
- [x] Authentication flow completes
- [x] GitHub API integration functional
- [x] DAifu chat responses generated

### Frontend Implementation ⚠️
- [x] All UI components render
- [x] Navigation works correctly
- [x] FileDependencies connects to backend
- [ ] Authentication integrated
- [ ] Chat connects to backend
- [ ] Context management functional

### Integration Complete ❌
- [ ] End-to-end user workflows work
- [ ] All frontend components connected
- [ ] Real user data flows through system
- [ ] Full GitHub issue creation pipeline
- [ ] Production-ready stability

---

*Last Updated: Current Date*  
*Next Review: After integration implementations*
