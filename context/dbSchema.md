# YudaiV3 Database Schema & State Flow Documentation

This document provides a comprehensive overview of the YudaiV3 database schema, state management, and data flow patterns between frontend and backend systems.

## Database Overview

The YudaiV3 application uses PostgreSQL with SQLAlchemy ORM, implementing a **Session Backbone** architecture where all operations are scoped to authenticated user sessions linked to specific GitHub repositories.

### 🏗️ Architecture Principles
- **Session-Scoped Operations**: Every chat, issue, and context operation is linked to a session
- **Repository Context**: Sessions maintain repository metadata (owner, name, branch)
- **Type Safety**: Frontend TypeScript types match backend Pydantic models exactly
- **State Persistence**: All user interactions persist across sessions with proper relationships

## Core State Flow Patterns

### 🔄 User Authentication & Session Flow

```
1. GitHub OAuth → auth_tokens table → Frontend localStorage
2. Repository Selection → Session Creation → chat_sessions table
3. Chat Operations → chat_messages table (linked to session)
4. Issue Creation → user_issues table (with session context)
```

### 📊 Frontend ↔ Backend Type Mapping

| **Frontend Type** | **Backend Model** | **Database Table** | **State Storage** |
|-------------------|-------------------|-------------------|-------------------|
| `User` | `User` (SQLAlchemy) | `users` | AuthContext |
| `ChatSession` | `SessionResponse` | `chat_sessions` | SessionContext |
| `ChatMessageAPI` | `ChatMessageResponse` | `chat_messages` | Local component state |
| `FileItem` | `FileItemResponse` | `file_items` | Component state |
| `UserIssueResponse` | `UserIssueResponse` | `user_issues` | API responses |

## Table Definitions & State Management

### 1. `users` - User Identity & Authentication State
**Purpose**: Core user identity linked to GitHub OAuth with session-scoped access control.

**Schema**:
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    github_username VARCHAR(255) UNIQUE NOT NULL,
    github_user_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    display_name VARCHAR(255),
    avatar_url VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    last_login TIMESTAMP WITH TIME ZONE
);
```

**State Flow**:
- **Authentication**: GitHub OAuth → `auth_tokens` → Frontend `AuthContext`
- **Persistence**: User data cached in frontend localStorage
- **Validation**: All API operations validate user.id from Bearer token

**Frontend Mapping**:
```typescript
interface User {
  id: number;                    // maps to users.id
  github_username: string;       // maps to users.github_username
  github_user_id: string;        // maps to users.github_user_id
  email?: string;               // maps to users.email
  display_name?: string;        // maps to users.display_name
  avatar_url?: string;          // maps to users.avatar_url
  created_at: string;           // maps to users.created_at
  last_login?: string;          // maps to users.last_login
}
```

**Used By**:
- `backend/auth/github_oauth.py` - OAuth flow and token validation
- `frontend/contexts/AuthContext.tsx` - User state management
- All protected API endpoints for user validation

---

### 2. `auth_tokens` - Authentication State Persistence  
**Purpose**: Manages GitHub OAuth tokens with automatic expiration and session security.

**Schema**:
```sql
CREATE TABLE auth_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    access_token VARCHAR(500) NOT NULL,
    refresh_token VARCHAR(500),
    token_type VARCHAR(50) DEFAULT 'bearer',
    scope VARCHAR(500),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**State Flow**:
- **Creation**: GitHub OAuth callback → token storage → 8-hour expiration
- **Usage**: Every API request validates Bearer token against this table
- **Cleanup**: Expired/inactive tokens automatically invalidated

**Authentication Pattern**:
```
Frontend Request: Authorization: Bearer <access_token>
Backend Validation: auth_tokens.access_token WHERE is_active=true AND expires_at > NOW()
```

---

### 3. `chat_sessions` - Session Backbone Core
**Purpose**: **CORE TABLE** implementing Session Backbone - links all operations to repository context.

**Enhanced Schema** (Session Backbone):
```sql
CREATE TABLE chat_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) NOT NULL,  -- External identifier for frontend
    title VARCHAR(255),
    description TEXT,
    
    -- SESSION BACKBONE FIELDS (Repository Context)
    repo_owner VARCHAR(255),           -- GitHub repository owner
    repo_name VARCHAR(255),            -- GitHub repository name  
    repo_branch VARCHAR(255),          -- Git branch name
    repo_context JSON,                 -- Repository metadata
    
    -- Session State
    is_active BOOLEAN DEFAULT TRUE,
    total_messages INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    last_activity TIMESTAMP WITH TIME ZONE
);

-- Indexes for Session Backbone
CREATE INDEX idx_chat_sessions_repo_owner ON chat_sessions(repo_owner);
CREATE INDEX idx_chat_sessions_repo_name ON chat_sessions(repo_name);
CREATE INDEX idx_chat_sessions_repo_owner_name ON chat_sessions(repo_owner, repo_name);
```

**Session Lifecycle State Flow**:

1. **Repository Selection** (Frontend)
   ```typescript
   // RepositoryContext.tsx
   selectedRepository = { repository: GitHubRepo, branch: string }
   ```

2. **Auto-Session Creation** (Frontend → Backend)
   ```typescript
   // SessionContext.tsx - automatic session creation
   useEffect(() => {
     if (selectedRepository && !currentSessionId) {
       createSession(owner, name, branch) // → POST /daifu/sessions
     }
   }, [selectedRepository])
   ```

3. **Session Response** (Backend → Frontend)
   ```json
   {
     "id": 123,                    // Database primary key
     "session_id": "owner_repo_branch_timestamp",  // Frontend identifier
     "repo_owner": "pranay5255",
     "repo_name": "YudaiV3", 
     "repo_branch": "main",
     "repo_context": {"owner": "pranay5255", "name": "YudaiV3", ...},
     "is_active": true,
     "total_messages": 0,
     "total_tokens": 0
   }
   ```

4. **Frontend State Management**
   ```typescript
   // SessionContext stores session_id for all operations
   const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
   // All chat and issue operations use this session_id
   ```

**Frontend Type Mapping**:
```typescript
interface ChatSession {
  id: number;                           // chat_sessions.id
  session_id: string;                   // chat_sessions.session_id (USED BY FRONTEND)
  title?: string;                       // chat_sessions.title
  description?: string;                 // chat_sessions.description
  repo_owner?: string;                  // chat_sessions.repo_owner
  repo_name?: string;                   // chat_sessions.repo_name
  repo_branch?: string;                 // chat_sessions.repo_branch
  repo_context?: Record<string, unknown>; // chat_sessions.repo_context
  is_active: boolean;                   // chat_sessions.is_active
  total_messages: number;               // chat_sessions.total_messages
  total_tokens: number;                 // chat_sessions.total_tokens
  created_at: string;                   // chat_sessions.created_at
  updated_at?: string;                  // chat_sessions.updated_at
  last_activity?: string;               // chat_sessions.last_activity
}
```

---

### 4. `chat_messages` - Conversation State & Context
**Purpose**: Stores all chat interactions within sessions with full context preservation.

**Schema**:
```sql
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id VARCHAR(255) NOT NULL,    -- UUID for frontend tracking
    message_text TEXT NOT NULL,
    sender_type VARCHAR(50) NOT NULL,    -- 'user', 'assistant', 'system'
    role VARCHAR(50) NOT NULL,           -- 'user', 'assistant', 'system'
    is_code BOOLEAN DEFAULT FALSE,
    
    -- Processing Metadata
    tokens INTEGER DEFAULT 0,
    model_used VARCHAR(100),             -- OpenRouter model used
    processing_time FLOAT,               -- Response time in ms
    context_cards JSON,                  -- Context cards used for this message
    referenced_files JSON,               -- Files referenced in response
    error_message TEXT,                  -- Error details if failed
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Message State Flow**:

1. **User Input** (Frontend)
   ```typescript
   // Chat.tsx - user sends message
   const request: ChatRequest = {
     conversation_id: currentSessionId,  // Links to chat_sessions.session_id
     message: { content: input, is_code: boolean },
     context_cards: string[]             // Context card IDs
   }
   ```

2. **Message Processing** (Backend)
   ```python
   # backend/daifuUserAgent/chat_api.py
   # 1. Validate session exists and belongs to user
   session = SessionService.touch_session(db, user.id, conversation_id)
   
   # 2. Store user message
   user_message = ChatService.create_chat_message(db, user.id, message_request)
   
   # 3. Process with OpenRouter
   reply = call_openrouter_api(prompt)
   
   # 4. Store assistant response
   assistant_message = ChatService.create_chat_message(db, user.id, response_request)
   ```

3. **State Updates** (Automatic)
   ```sql
   -- Session statistics auto-updated on each message
   UPDATE chat_sessions SET 
     total_messages = total_messages + 1,
     total_tokens = total_tokens + message_tokens,
     last_activity = NOW()
   WHERE id = session_id;
   ```

**Frontend Type Mapping**:
```typescript
interface ChatMessageAPI {
  id: number;                       // chat_messages.id
  message_id: string;               // chat_messages.message_id
  content: string;                  // maps to message_text
  message_text: string;             // chat_messages.message_text
  role: 'user' | 'assistant' | 'system';  // chat_messages.role
  sender_type: 'user' | 'assistant' | 'system'; // chat_messages.sender_type
  timestamp: string;                // maps to created_at
  created_at: string;              // chat_messages.created_at
  is_code: boolean;                // chat_messages.is_code
  tokens: number;                  // chat_messages.tokens
  model_used?: string;             // chat_messages.model_used
  processing_time?: number;        // chat_messages.processing_time
  context_cards?: string[];        // chat_messages.context_cards
  referenced_files?: string[];     // chat_messages.referenced_files
  error_message?: string;          // chat_messages.error_message
}
```

---

### 5. `user_issues` - Enhanced Issue Management with Session Context
**Purpose**: Stores user-generated issues with complete session context and CodeInspector analysis.

**Schema**:
```sql
CREATE TABLE user_issues (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    issue_id VARCHAR(255) UNIQUE NOT NULL,    -- UUID for external reference
    
    -- Issue Content
    title VARCHAR(255) NOT NULL,
    description TEXT,
    issue_text_raw TEXT NOT NULL,
    issue_steps JSON,                          -- Array of implementation steps
    
    -- Session Backbone Links
    conversation_id VARCHAR(255),              -- Links to chat_sessions.session_id
    chat_session_id INTEGER REFERENCES chat_sessions(id),
    context_cards JSON,                        -- Context card IDs used
    
    -- Repository Context (from session)
    repo_owner VARCHAR(255),
    repo_name VARCHAR(255),
    
    -- Processing State
    priority VARCHAR(20) DEFAULT 'medium',     -- 'low', 'medium', 'high'
    status VARCHAR(50) DEFAULT 'pending',      -- State machine values
    agent_response TEXT,                       -- CodeInspector analysis
    processing_time FLOAT,
    tokens_used INTEGER DEFAULT 0,
    
    -- CodeInspector Analysis
    complexity_score VARCHAR(10),              -- 'S', 'M', 'L', 'XL'
    estimated_hours INTEGER,                   -- Time estimate
    
    -- GitHub Integration
    github_issue_url VARCHAR(1000),
    github_issue_number INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE
);
```

**Issue Creation State Flow**:

1. **Enhanced Issue Creation** (Frontend → Backend)
   ```typescript
   // Frontend: Chat.tsx or issue creation UI
   await ApiService.createIssueFromSessionEnhanced({
     session_id: currentSessionId,     // Links to chat_sessions.session_id
     title: "Implement Feature X",
     description: "User request details",
     priority: "medium",
     use_code_inspector: true,         // Enable AI analysis
     create_github_issue: false        // Create GitHub issue if true
   })
   ```

2. **Backend Processing** (Session Context Gathering)
   ```python
   # backend/issueChatServices/issue_service.py
   # 1. Validate session exists and belongs to user
   session_context = SessionService.get_session_context(db, user_id, session_id)
   
   # 2. Build comprehensive context bundle
   session_bundle = {
     "session_info": {
       "repo_owner": session.repo_owner,
       "repo_name": session.repo_name,
       "repo_branch": session.repo_branch
     },
     "messages": [...],               # All chat history
     "context_cards": [...],          # Context cards from session
     "repository_info": {...}         # Repository metadata
   }
   
   # 3. CodeInspector Analysis (if enabled)
   if use_code_inspector:
     agent_analysis = code_inspector.analyze_session_context(session_bundle)
     github_issue_data = code_inspector.generate_github_issue(analysis)
   
   # 4. Create UserIssue with enhanced context
   user_issue = IssueService.create_user_issue(db, user_id, enhanced_request)
   ```

3. **Issue Status State Machine**
   ```
   pending → ready_for_swe → swe_processing → completed/failed
                          ↘ 
                           github_issue_created
   ```

**Frontend Integration**:
```typescript
interface CreateIssueFromSessionRequest {
  session_id: string;                    // chat_sessions.session_id
  title: string;                         // user_issues.title
  description?: string;                  // user_issues.description
  priority?: string;                     // user_issues.priority
  use_code_inspector?: boolean;          // Enables AI analysis
  create_github_issue?: boolean;         // Auto-creates GitHub issue
}

interface UserIssueResponse {
  issue_id: string;                      // user_issues.issue_id
  title: string;                         // user_issues.title
  status: string;                        // user_issues.status
  agent_response?: string;               // user_issues.agent_response (CodeInspector)
  complexity_score?: string;             // user_issues.complexity_score
  estimated_hours?: number;              // user_issues.estimated_hours
  github_issue_url?: string;             // user_issues.github_issue_url
  repo_owner?: string;                   // user_issues.repo_owner
  repo_name?: string;                    // user_issues.repo_name
  // ... other fields
}
```

---

### 6. `file_items` - File Context & Dependencies
**Purpose**: Repository file structure for context-aware operations.

**Schema**:
```sql
CREATE TABLE file_items (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id) ON DELETE CASCADE,
    name VARCHAR(500) NOT NULL,
    path VARCHAR(1000) NOT NULL,
    file_type VARCHAR(50) NOT NULL,        -- 'INTERNAL', 'EXTERNAL' (uppercase)
    category VARCHAR(100) NOT NULL,
    tokens INTEGER DEFAULT 0,
    is_directory BOOLEAN DEFAULT FALSE,
    parent_id INTEGER REFERENCES file_items(id),  -- Tree structure
    content TEXT,                          -- File content (optional)
    content_size INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**File Type State Flow**:
- **Extraction**: GitIngest → Repository analysis → file_items population
- **Categorization**: Files classified as INTERNAL/EXTERNAL with token counts
- **Context Usage**: Files referenced in chat_messages.referenced_files

**Frontend Type Mapping**:
```typescript
interface FileItem {
  id: string;                           // file_items.id (as string)
  name: string;                         // file_items.name
  path?: string;                        // file_items.path
  type: 'INTERNAL' | 'EXTERNAL';        // file_items.file_type (enum match)
  tokens: number;                       // file_items.tokens
  Category: string;                     // file_items.category
  isDirectory: boolean;                 // file_items.is_directory
  children?: FileItem[];                // Recursive structure
  content?: string;                     // file_items.content
  content_size?: number;                // file_items.content_size
}
```

---

### 7. Supporting Tables

#### `repositories` - GitHub Repository Metadata
```sql
CREATE TABLE repositories (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    github_repo_id INTEGER UNIQUE,
    name VARCHAR(255) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    full_name VARCHAR(512) NOT NULL,
    description TEXT,
    private BOOLEAN DEFAULT FALSE,
    html_url VARCHAR(500) NOT NULL,
    clone_url VARCHAR(500) NOT NULL,
    language VARCHAR(100),
    stargazers_count INTEGER DEFAULT 0,
    forks_count INTEGER DEFAULT 0,
    open_issues_count INTEGER DEFAULT 0,
    github_created_at TIMESTAMP WITH TIME ZONE,
    github_updated_at TIMESTAMP WITH TIME ZONE,
    pushed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

#### `context_cards` - User Context Management
```sql
CREATE TABLE context_cards (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    content TEXT NOT NULL,
    source VARCHAR(50) NOT NULL,         -- 'chat', 'file-deps', 'upload'
    tokens INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

## State Flow Patterns

### 🔄 Complete User Journey State Flow

```
1. Authentication State Flow:
   GitHub OAuth → auth_tokens → Frontend AuthContext → localStorage

2. Repository Selection State Flow:
   Frontend RepositoryContext → Auto-create session → chat_sessions table

3. Chat Interaction State Flow:
   User input → Frontend Chat → Backend validation → OpenRouter → chat_messages table

4. Issue Creation State Flow:
   Session context → CodeInspector analysis → user_issues table → Optional GitHub issue

5. Context Preservation:
   All operations linked via session_id → Complete context recovery
```

### 📊 Frontend State Management

```typescript
// Primary State Contexts
interface AppState {
  auth: AuthContext;           // User authentication state
  session: SessionContext;     // Current session management
  repository: RepositoryContext; // Selected repository
}

// State Persistence Strategy
localStorage: {
  'auth_token': string,        // Authentication token
  'user_data': User,          // Cached user profile
  'yudai_current_session_id': string  // Current session identifier
}

// State Synchronization
- AuthContext: Syncs with backend on auth operations
- SessionContext: Auto-creates sessions, persists session_id
- Repository operations: All linked to current session
```

### 🔗 Database Relationship Patterns

```sql
-- Core Relationships (Session Backbone)
users (1) → (∞) chat_sessions → (∞) chat_messages
users (1) → (∞) user_issues
chat_sessions (1) → (∞) user_issues (via conversation_id)

-- Repository Context
users (1) → (∞) repositories → (∞) file_items
chat_sessions → repositories (via repo_owner, repo_name)

-- Context Linking
chat_messages.context_cards → context_cards.id[]
user_issues.context_cards → context_cards.id[]
user_issues.chat_session_id → chat_sessions.id
```

## Migration & Development Notes

### 🛠️ Schema Evolution
- **Current Version**: Session Backbone implemented
- **Type Safety**: Frontend types match backend models exactly
- **Migration Strategy**: Update models.py → Update frontend types → Database migration

### 🏗️ Development Patterns
- **Session Validation**: All operations validate session ownership
- **State Consistency**: Frontend state syncs with backend on operations
- **Error Handling**: Proper HTTP status codes with session validation
- **Context Preservation**: All user interactions maintain session context

### 📋 Implementation Status

**✅ Fully Implemented:**
- Session Backbone with repository context
- Type-safe frontend-backend communication
- Authentication with proper token management
- Enhanced issue creation with session context

**🚧 Partially Implemented:**
- Context cards (schema ready, APIs pending)
- Idea items (schema ready, APIs pending)

**🎯 Architecture Benefits:**
- Complete context preservation across all operations
- Repository-scoped sessions enable better context awareness
- Type safety eliminates frontend-backend mismatches
- Session validation ensures proper data isolation between users
