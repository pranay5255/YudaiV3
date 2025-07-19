# YudaiV3 Application State Flow

## Overview
This document outlines the complete state flow of the YudaiV3 application, including user authentication, repository management, database operations, and component interactions.

## 1. Authentication Flow

### 1.1 Initial State
```typescript
AuthState {
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true
}
```

### 1.2 User Login Process
1. **User clicks "Sign in with GitHub"** → `AuthService.login()`
2. **Redirect to GitHub OAuth** → `http://localhost:8000/auth/login`
3. **GitHub callback** → `http://localhost:8000/auth/callback?code=...`
4. **Backend processes OAuth**:
   - Creates/updates `User` record in database
   - Creates `AuthToken` record
   - Returns user data and access token
5. **Frontend updates AuthContext**:
   ```typescript
   AuthState {
     user: User {
       id: number,
       github_username: string,
       github_user_id: string,
       email?: string,
       display_name?: string,
       avatar_url?: string,
       active_repository?: string
     },
     token: string,
     isAuthenticated: true,
     isLoading: false
   }
   ```

### 1.3 Database Operations (Authentication)
- **Table**: `users`
  - Insert/update user record on login
  - Update `last_login` timestamp
- **Table**: `auth_tokens`
  - Store GitHub OAuth token
  - Mark previous tokens as inactive

## 2. Repository Selection Flow

### 2.1 Repository Context State
```typescript
RepositoryContextState {
  selectedRepository: SelectedRepository | null,
  hasSelectedRepository: boolean,
  repositories: GitHubRepository[]
}

SelectedRepository {
  repository: GitHubRepository,
  branch: string
}
```

### 2.2 Repository Selection Process
1. **Show Repository Selection Toast** (if no repository selected)
2. **Fetch User Repositories** → `GET /github/repositories`
   - Calls GitHub API to get user's repositories
   - Updates database `repositories` table
3. **User Selects Repository** → Updates RepositoryContext
4. **Update User's Active Repository** → Database update
5. **Store Selection in Context**

### 2.3 Database Operations (Repository)
- **Table**: `repositories`
  - Insert/update repository metadata from GitHub
  - Fields: name, owner, full_name, description, html_url, clone_url, etc.
- **Table**: `users`
  - Update `active_repository` field with selected repository

## 3. GitHub API Integration Flow

### 3.1 User Profile and Repository Data
After repository selection, the system calls GitHub APIs to populate:

1. **User Profile Data** → `GET /auth/profile`
   - Updates TopBar with user information
   - Shows username, avatar, signout button

2. **Repository Details** → `GET /github/repositories/{owner}/{repo}`
   - Fetches detailed repository information
   - Updates database with latest repository data

3. **Repository Issues** → `GET /github/repositories/{owner}/{repo}/issues`
   - Fetches repository issues
   - Stores in `issues` table

4. **Repository Pull Requests** → `GET /github/repositories/{owner}/{repo}/pulls`
   - Fetches repository PRs
   - Stores in `pull_requests` table

### 3.2 Database Operations (GitHub Data)
- **Table**: `issues`
  - Store GitHub issues with metadata
- **Table**: `pull_requests`
  - Store GitHub PRs with metadata
- **Table**: `commits`
  - Store commit history

## 4. File Dependencies Extraction Flow

### 4.1 Extract API Call
After repository selection, `FileDependencies.tsx` component calls:
```
POST /filedeps/extract
{
  "repo_url": "https://github.com/owner/repo",
  "max_file_size": 30000
}
```

### 4.2 Database Operations (File Analysis)
- **Table**: `file_analyses`
  - Store analysis metadata (status, total_files, total_tokens)
- **Table**: `file_items`
  - Store hierarchical file structure
  - Fields: name, path, file_type, category, tokens, is_directory

### 4.3 Component State Update
```typescript
FileDependenciesState {
  files: FileItem[],
  loading: boolean,
  error: string | null
}
```

## 5. Chat Session Management Flow

### 5.1 Chat Session Creation
When user starts chatting:
1. **Auto-create Chat Session**:
   ```typescript
   ChatSession {
     session_id: string,
     user_id: number,
     title?: string,
     is_active: true,
     total_messages: 0,
     total_tokens: 0
   }
   ```

2. **Store Messages**:
   ```typescript
   ChatMessage {
     session_id: number,
     message_id: string,
     message_text: string,
     sender_type: "user" | "assistant" | "system",
     role: "user" | "assistant" | "system",
     is_code: boolean,
     tokens: number
   }
   ```

### 5.2 Database Operations (Chat)
- **Table**: `chat_sessions`
  - Create session on first message
  - Update statistics (total_messages, total_tokens, last_activity)
- **Table**: `chat_messages`
  - Store all user and assistant messages
  - Track context cards and referenced files

## 6. Context Management Flow

### 6.1 Context Cards
User can add content to context from:
- Chat messages → `addToContext(content, 'chat')` → `POST /context/cards`
- File dependencies → `addFileToContext(file)` → `POST /context/cards`
- Manual uploads → `addToContext(content, 'upload')` → `POST /context/cards`

### 6.2 Database Operations (Context)
- **Table**: `context_cards`
  - Store user's context cards via REST API
  - Fields: title, description, content, source, tokens
- **API Endpoints**:
  - `POST /context/cards` - Create context card
  - `GET /context/cards` - Get user's context cards
  - `PUT /context/cards/{id}` - Update context card
  - `DELETE /context/cards/{id}` - Delete context card

## 7. Issue Creation Flow

### 7.1 User Issue Generation
From chat or context cards:
1. **Create User Issue** → `POST /chat/create-issue`
2. **Store in Database**:
   ```typescript
   UserIssue {
     issue_id: string,
     user_id: number,
     title: string,
     description: string,
     chat_session_id?: number,
     context_cards?: string[], // JSON array
     status: "pending" | "processing" | "completed"
   }
   ```

3. **Optional GitHub Issue Creation** → `POST /github/repositories/{owner}/{repo}/issues`

### 7.2 Database Operations (Issues)
- **Table**: `user_issues`
  - Store user-generated issues
- **Table**: `issues` (if GitHub issue created)
  - Store GitHub issue metadata

## 8. Complete Application State Object

```typescript
ApplicationState {
  // Authentication
  auth: {
    user: User | null,
    token: string | null,
    isAuthenticated: boolean,
    isLoading: boolean
  },
  
  // Repository Management
  repository: {
    selectedRepository: SelectedRepository | null,
    hasSelectedRepository: boolean,
    repositories: GitHubRepository[]
  },
  
  // UI State
  ui: {
    activeTab: TabType,
    currentStep: ProgressStep,
    sidebarCollapsed: boolean,
    modals: {
      isDiffModalOpen: boolean,
      isDetailModalOpen: boolean,
      showRepositorySelection: boolean
    }
  },
  
  // Data Management
  data: {
    contextCards: ContextCard[],
    fileItems: FileItem[],
    chatSessions: ChatSession[],
    currentChatSession: ChatSession | null,
    toasts: Toast[]
  }
}
```

## 9. API Endpoints Summary

### Authentication
- `GET /auth/login` - GitHub OAuth redirect
- `GET /auth/callback` - Handle OAuth callback
- `GET /auth/profile` - Get user profile
- `PATCH /auth/profile` - Update user profile (active_repository)
- `POST /auth/logout` - Logout user

### GitHub Integration
- `GET /github/repositories` - Get user repositories
- `GET /github/repositories/{owner}/{repo}` - Get repository details
- `GET /github/repositories/{owner}/{repo}/issues` - Get repository issues
- `POST /github/repositories/{owner}/{repo}/issues` - Create GitHub issue

### File Analysis
- `POST /filedeps/extract` - Extract repository file dependencies

### Chat Services
- `POST /chat/daifu` - Send message to DAifu agent
- `GET /chat/sessions` - Get user chat sessions
- `GET /chat/sessions/{session_id}/messages` - Get session messages

### Context Management
- `POST /context/cards` - Create context card
- `GET /context/cards` - Get user context cards
- `PUT /context/cards/{id}` - Update context card
- `DELETE /context/cards/{id}` - Delete context card
- `GET /context/statistics` - Get context statistics

### Issue Management
- `POST /chat/create-issue` - Create issue from chat
- `GET /issues` - Get user issues

## 10. Data Flow Sequence

1. **User Login** → Update `users`, `auth_tokens` tables
2. **Repository Selection** → Update `repositories`, `users.active_repository`
3. **GitHub Data Sync** → Update `issues`, `pull_requests`, `commits`
4. **File Analysis** → Update `file_analyses`, `file_items`
5. **Chat Interaction** → Update `chat_sessions`, `chat_messages`
6. **Context Management** → Create/update/delete `context_cards` via REST API
7. **Issue Creation** → Update `user_issues`, optionally `issues`

## 11. Error Handling

Each component should handle:
- **Network failures** → Show error toast
- **Authentication errors** → Redirect to login
- **API rate limits** → Show appropriate message
- **Database errors** → Log and show user-friendly message

## 12. State Persistence

- **Authentication**: Stored in localStorage (`auth_token`, `user_data`)
- **Repository Selection**: Stored in database (`users.active_repository`)
- **Chat Sessions**: Persistent in database
- **Context Cards**: Persistent in database
- **UI State**: Session-based (not persistent)
