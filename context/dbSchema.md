# YudaiV3 Database Schema Documentation

This document provides a comprehensive overview of all database tables in the YudaiV3 application, their structure, purpose, and which backend services interact with them.

## Database Overview

The YudaiV3 application uses PostgreSQL as its primary database with SQLAlchemy ORM for data management. The database supports user authentication via GitHub OAuth, repository management, chat conversations, context management, and issue tracking.

## Table Definitions

### 1. `users` - User Management
**Purpose**: Stores user account information for GitHub OAuth authentication.

**Key Fields**:
- `id` (Primary Key): Internal user identifier
- `github_username`: GitHub username (unique)
- `github_user_id`: GitHub user ID (unique)
- `email`: User email address
- `display_name`: User display name
- `avatar_url`: GitHub profile picture URL
- `created_at`, `updated_at`, `last_login`: Timestamps

**Used By**:
- `backend/auth/github_oauth.py` - OAuth flow and user authentication
- `backend/auth/auth_routes.py` - Authentication API endpoints
- `backend/github/github_api.py` - GitHub API operations
- `backend/github/github_routes.py` - GitHub API endpoints
- `backend/daifuUserAgent/chat_api.py` - Chat operations (TODO: integrate with auth)
- `backend/issueChatServices/chat_service.py` - Chat session management
- `backend/issueChatServices/issue_service.py` - Issue management

**Relationships**:
- One-to-many with `auth_tokens`
- One-to-many with `repositories`
- One-to-many with `chat_sessions`
- One-to-many with `context_cards`
- One-to-many with `idea_items`
- One-to-many with `user_issues`

---

### 2. `auth_tokens` - Authentication Tokens
**Purpose**: Stores GitHub OAuth access tokens and refresh tokens for authenticated users.

**Key Fields**:
- `id` (Primary Key): Token record identifier
- `user_id` (Foreign Key): References `users.id`
- `access_token`: GitHub OAuth access token
- `refresh_token`: GitHub OAuth refresh token
- `token_type`: Token type (usually "bearer")
- `scope`: OAuth token scope
- `expires_at`: Token expiration timestamp
- `is_active`: Token status flag

**Used By**:
- `backend/auth/github_oauth.py` - Token management and validation
- `backend/auth/auth_routes.py` - Authentication endpoints
- `backend/github/github_api.py` - GitHub API authentication

**Relationships**:
- Many-to-one with `users`

---

### 3. `repositories` - Repository Metadata
**Purpose**: Stores GitHub repository metadata and information.

**Key Fields**:
- `id` (Primary Key): Internal repository identifier
- `github_repo_id`: GitHub repository ID (unique)
- `user_id` (Foreign Key): References `users.id`
- `name`: Repository name
- `owner`: Repository owner username
- `full_name`: Full repository name (owner/repo)
- `description`: Repository description
- `private`: Private repository flag
- `html_url`, `clone_url`: Repository URLs
- `language`: Primary programming language
- `stargazers_count`, `forks_count`, `open_issues_count`: Repository statistics
- GitHub timestamps: `github_created_at`, `github_updated_at`, `pushed_at`

**Used By**:
- `backend/github/github_api.py` - Repository data management
- `backend/github/github_routes.py` - Repository API endpoints
- `backend/repo_processorGitIngest/filedeps.py` - File dependency analysis

**Relationships**:
- Many-to-one with `users`
- One-to-many with `issues`
- One-to-many with `pull_requests`
- One-to-many with `commits`
- One-to-many with `file_items`

---

### 4. `issues` - GitHub Issues (External)
**Purpose**: Stores GitHub issues fetched from repositories (distinct from user-generated issues).

**Key Fields**:
- `id` (Primary Key): Internal issue identifier
- `github_issue_id`: GitHub issue ID (unique)
- `repository_id` (Foreign Key): References `repositories.id`
- `number`: GitHub issue number
- `title`: Issue title
- `body`: Issue description
- `state`: Issue state (open, closed)
- `html_url`: GitHub issue URL
- `author_username`: Issue creator username
- GitHub timestamps: `github_created_at`, `github_updated_at`, `github_closed_at`

**Used By**:
- `backend/github/github_api.py` - GitHub issue synchronization
- `backend/github/github_routes.py` - GitHub issue API endpoints

**Relationships**:
- Many-to-one with `repositories`

---

### 5. `pull_requests` - GitHub Pull Requests
**Purpose**: Stores GitHub pull requests fetched from repositories.

**Key Fields**:
- `id` (Primary Key): Internal PR identifier
- `github_pr_id`: GitHub PR ID (unique)
- `repository_id` (Foreign Key): References `repositories.id`
- `number`: GitHub PR number
- `title`: PR title
- `body`: PR description
- `state`: PR state (open, closed)
- `html_url`: GitHub PR URL
- `author_username`: PR creator username
- GitHub timestamps: `github_created_at`, `github_updated_at`, `github_closed_at`, `merged_at`

**Used By**:
- `backend/github/github_api.py` - GitHub PR synchronization
- `backend/github/github_routes.py` - GitHub PR API endpoints

**Relationships**:
- Many-to-one with `repositories`

---

### 6. `commits` - Repository Commits
**Purpose**: Stores commit information from GitHub repositories.

**Key Fields**:
- `id` (Primary Key): Internal commit identifier
- `sha`: Git commit hash (unique)
- `repository_id` (Foreign Key): References `repositories.id`
- `message`: Commit message
- `html_url`: GitHub commit URL
- `author_name`, `author_email`, `author_date`: Author information

**Used By**:
- `backend/github/github_api.py` - Commit data synchronization
- `backend/github/github_routes.py` - Commit API endpoints

**Relationships**:
- Many-to-one with `repositories`

---

### 7. `file_items` - Repository File Analysis
**Purpose**: Stores file structure and analysis data from repository processing.

**Key Fields**:
- `id` (Primary Key): File item identifier
- `repository_id` (Foreign Key): References `repositories.id`
- `name`: File/directory name
- `path`: Full file path
- `file_type`: File type classification (INTERNAL, EXTERNAL)
- `category`: File category
- `tokens`: Estimated token count
- `is_directory`: Directory flag
- `parent_id` (Foreign Key): Self-reference for tree structure
- `content`: File content (optional)
- `content_size`: File size in bytes

**Used By**:
- `backend/repo_processorGitIngest/filedeps.py` - File dependency analysis
- `backend/repo_processorGitIngest/scraper_script.py` - Repository processing

**Relationships**:
- Many-to-one with `repositories`
- Self-referencing tree structure (parent/children)

---

### 8. `file_analyses` - File Analysis Results
**Purpose**: Stores results of repository file analysis operations.

**Key Fields**:
- `id` (Primary Key): Analysis identifier
- `repository_id` (Foreign Key): References `repositories.id`
- `total_files`: Number of files analyzed
- `total_tokens`: Total estimated tokens
- `max_file_size`: Maximum file size limit used
- `raw_data`: Raw analysis data (JSON)
- `processed_data`: Processed analysis results (JSON)
- `status`: Analysis status
- `processed_at`: Analysis completion timestamp

**Used By**:
- `backend/repo_processorGitIngest/filedeps.py` - File analysis operations

**Relationships**:
- Many-to-one with `repositories`

---

### 9. `context_cards` - User Context Cards
**Purpose**: Stores user-created context cards for chat and issue management.

**Key Fields**:
- `id` (Primary Key): Context card identifier
- `user_id` (Foreign Key): References `users.id`
- `title`: Card title
- `description`: Card description
- `content`: Card content
- `source`: Context source (chat, file-deps, upload)
- `tokens`: Token count
- `is_active`: Active status flag

**Used By**:
- Context card management APIs (implementation pending)
- Referenced by `user_issues` for issue context

**Relationships**:
- Many-to-one with `users`
- Referenced by `user_issues`

---

### 10. `idea_items` - Implementation Ideas
**Purpose**: Stores user-generated ideas for future implementation.

**Key Fields**:
- `id` (Primary Key): Idea identifier
- `user_id` (Foreign Key): References `users.id`
- `title`: Idea title
- `description`: Idea description
- `complexity`: Complexity level (S, M, L, XL)
- `status`: Implementation status
- `is_active`: Active status flag

**Used By**:
- Idea management APIs (implementation pending)

**Relationships**:
- Many-to-one with `users`

---

### 11. `chat_sessions` - Chat Sessions
**Purpose**: Manages chat conversation sessions between users and the DAifu agent.

**Key Fields**:
- `id` (Primary Key): Session identifier
- `user_id` (Foreign Key): References `users.id`
- `session_id`: External session identifier (string)
- `title`: Session title
- `description`: Session description
- `is_active`: Active status flag
- `total_messages`: Message count
- `total_tokens`: Total tokens used
- `last_activity`: Last activity timestamp

**Used By**:
- `backend/issueChatServices/chat_service.py` - Chat session management
- `backend/daifuUserAgent/chat_api.py` - Chat API endpoints

**Relationships**:
- Many-to-one with `users`
- One-to-many with `chat_messages`
- Referenced by `user_issues`

---

### 12. `chat_messages` - Chat Messages
**Purpose**: Stores individual chat messages within chat sessions.

**Key Fields**:
- `id` (Primary Key): Message identifier
- `session_id` (Foreign Key): References `chat_sessions.id`
- `message_id`: External message identifier (string)
- `message_text`: Message content
- `sender_type`: Sender type (user, assistant, system)
- `role`: Message role (user, assistant, system)
- `is_code`: Code message flag
- `tokens`: Token count
- `model_used`: AI model used for response
- `processing_time`: Response processing time (ms)
- `context_cards`: Referenced context cards (JSON)
- `referenced_files`: Referenced files (JSON)
- `error_message`: Error information (if any)

**Used By**:
- `backend/issueChatServices/chat_service.py` - Message management
- `backend/daifuUserAgent/chat_api.py` - Chat message processing

**Relationships**:
- Many-to-one with `chat_sessions`

---

### 13. `user_issues` - User-Generated Issues
**Purpose**: Stores user-generated issues created from chat conversations for agent processing (distinct from GitHub issues).

**Key Fields**:
- `id` (Primary Key): Issue identifier
- `user_id` (Foreign Key): References `users.id`
- `issue_id`: External issue identifier (string, unique)
- `context_card_id` (Foreign Key): References `context_cards.id` (optional)
- `issue_text_raw`: Raw issue text from user
- `issue_steps`: Issue steps (JSON array)
- `title`: Issue title
- `description`: Issue description
- `conversation_id`: Related chat conversation ID
- `chat_session_id` (Foreign Key): References `chat_sessions.id` (optional)
- `context_cards`: Associated context card IDs (JSON)
- `ideas`: Associated idea IDs (JSON)
- `repo_owner`, `repo_name`: Target repository information
- `priority`: Issue priority (low, medium, high)
- `status`: Processing status (pending, processing, completed, failed)
- `agent_response`: Agent processing response
- `processing_time`: Processing time (ms)
- `tokens_used`: Tokens consumed during processing
- `github_issue_url`: Created GitHub issue URL
- `github_issue_number`: Created GitHub issue number
- `processed_at`: Processing completion timestamp

**Used By**:
- `backend/issueChatServices/issue_service.py` - Issue management and GitHub integration
- `backend/daifuUserAgent/chat_api.py` - Issue creation from chat

**Relationships**:
- Many-to-one with `users`
- Many-to-one with `context_cards` (optional)
- Many-to-one with `chat_sessions` (optional)

---

## Unused/Deprecated Tables

Currently, all defined tables are actively used by backend services. However, some tables have limited implementation:

1. **`context_cards`** - Table exists but management APIs are not fully implemented
2. **`idea_items`** - Table exists but management APIs are not fully implemented

## Database Initialization

The database is initialized through:
- `backend/db/database.py` - SQLAlchemy engine and session management
- `backend/db/init_db.py` - Database creation and health checks
- `backend/db/init.sql` - Initial SQL setup (PostgreSQL extensions)

## Migration Strategy

When making schema changes:
1. Update models in `backend/models.py`
2. Update expected tables list in `backend/db/init_db.py`
3. Update imports in `backend/db/__init__.py`
4. Run database initialization: `python backend/db/init_db.py --init`
5. Update this documentation

## Frontend-Backend State Flow Documentation

### Overview
This section documents how database state changes propagate to frontend React state, ensuring consistency between backend data and user interface state.

### Authentication State Flow

#### Database → Frontend State Propagation

```mermaid
graph TD
    A[User Login Click] → B[GitHub OAuth]
    B → C[Backend /auth/callback]
    C → D[Query/Create User in 'users' table]
    D → E[Deactivate old tokens in 'auth_tokens']
    E → F[Create new token in 'auth_tokens']
    F → G[Return access_token to frontend]
    G → H[Update AuthContext state]
    H → I[Store token in localStorage]
    I → J[Update UI components]
```

**Database Tables Involved:**
- `users`: User profile data
- `auth_tokens`: Authentication tokens

**React State Updates:**
- `AuthContext`: `{ user, token, isAuthenticated, isLoading }`
- Local Storage: `auth_token`, `user_data`

### Session Management State Flow

#### Auto-Session Creation on Repository Selection

```mermaid
graph TD
    A[User Selects Repository] → B[RepositoryContext updates]
    B → C[SessionContext useEffect triggers]
    C → D[Check if session exists]
    D → E{Session exists?}
    E →|No| F[Call createOrGetSession API]
    E →|Yes| G[Use existing session]
    F → H[Backend creates session in 'chat_sessions']
    H → I[Create initial message in 'chat_messages']
    I → J[Return session object]
    J → K[Update SessionContext state]
    K → L[Store session_id in localStorage]
    G → K
```

**Database Tables Involved:**
- `chat_sessions`: Session metadata
- `chat_messages`: Session messages

**React State Updates:**
- `SessionContext`: `{ currentSessionId, isLoading, error }`
- Local Storage: `yudai_current_session_id`

### Chat Message State Flow

#### Message Creation and AI Response

```mermaid
graph TD
    A[User Types Message] → B[Add to local chat state immediately]
    B → C[Send API request to /daifu/chat/daifu]
    C → D[Backend processes with AI]
    D → E[Create user message in 'chat_messages']
    E → F[Generate AI response]
    F → G[Create AI message in 'chat_messages']
    G → H[Update session stats in 'chat_sessions']
    H → I[Return AI response]
    I → J[Add AI message to chat state]
    J → K[Update UI with new message]
```

**Database Tables Involved:**
- `chat_messages`: Individual messages
- `chat_sessions`: Updated statistics (total_messages, total_tokens, last_activity)

**React State Updates:**
- `Chat.tsx` local state: `messages[]` array
- Session statistics updated in background

### File Dependencies State Flow

#### Repository File Analysis

```mermaid
graph TD
    A[User Selects Repository] → B[Check if repo exists in DB]
    B → C{Repo exists?}
    C →|Yes| D[Query 'file_items' for file tree]
    C →|No| E[Call extractFileDependencies API]
    D → F[Build file tree from DB data]
    E → G[Backend extracts files from repo]
    G → H[Store repo in 'repositories' table]
    H → I[Store files in 'file_items' table]
    I → J[Store analysis in 'file_analyses' table]
    J → K[Return file tree structure]
    F → L[Update FileDependencies component state]
    K → L
    L → M[Update ContextCards if files selected]
```

**Database Tables Involved:**
- `repositories`: Repository metadata
- `file_items`: File tree structure with parent-child relationships
- `file_analyses`: Analysis results and statistics

**React State Updates:**
- `FileDependencies.tsx`: `files[]` state (tree structure)
- `ContextCards.tsx`: Context cards when files are selected
- Loading and error states during processing

### Issue Creation State Flow

#### From Chat to GitHub Issue

```mermaid
graph TD
    A[User Clicks Create Issue] → B[Gather chat messages + file context]
    B → C[Call createIssueWithContext API]
    C → D[Backend processes context]
    D → E[Create entry in 'user_issues' table]
    E → F[Generate issue preview]
    F → G[Return preview to frontend]
    G → H[Show DiffModal with preview]
    H → I[User approves issue creation]
    I → J[Call createGitHubIssueFromUserIssue API]
    J → K[Backend creates GitHub issue via API]
    K → L[Update 'user_issues' with GitHub details]
    L → M[Return GitHub URL]
    M → N[Update UI with success state]
```

**Database Tables Involved:**
- `user_issues`: User-created issues with context
- `context_cards`: Referenced context (optional)
- `chat_sessions`: Referenced chat session (optional)

**React State Updates:**
- `DiffModal.tsx`: Preview state, creation status
- Issue lists in various components updated with new issue

### Repository Management State Flow

#### Repository Selection and Persistence

```mermaid
graph TD
    A[User Selects Repository] → B[Update RepositoryContext]
    B → C[Store in localStorage]
    C → D[Trigger dependent contexts]
    D → E[SessionContext creates session]
    D → F[FileDependencies loads files]
    E → G[Database operations for session]
    F → H[Database operations for files]
    G → I[Update session UI]
    H → J[Update file dependency UI]
```

**Database Tables Involved:**
- Repository selection triggers operations in multiple tables via contexts

**React State Updates:**
- `RepositoryContext`: `selectedRepository` object
- Local Storage: `yudai_selected_repository`
- Cascading updates to dependent contexts

### Error State Propagation

#### Database Errors → Frontend Error States

```mermaid
graph TD
    A[Database Error] → B[Backend API Error Response]
    B → C[Frontend API Service catches error]
    C → D{Error Type?}
    D →|401 Unauthorized| E[Clear auth state, redirect to login]
    D →|404 Not Found| F[Show not found message]
    D →|500 Server Error| G[Show retry option]
    E → H[Update AuthContext]
    F → I[Update component error state]
    G → I
    H → J[Update UI to login page]
    I → K[Show error message to user]
```

### State Consistency Patterns

#### Optimistic Updates
- **Chat Messages**: Add to UI immediately, rollback on error
- **Repository Selection**: Update context first, then trigger API calls
- **File Selection**: Update context cards immediately

#### Pessimistic Updates  
- **Authentication**: Wait for backend confirmation
- **Issue Creation**: Show loading until backend completes
- **File Extraction**: Show progress during backend processing

#### State Synchronization
- **Session State**: Auto-sync with backend on repository change
- **Auth State**: Periodic validation against backend
- **File State**: Cache with invalidation on repository change

### Performance Optimizations

#### Database Query Optimization
- **File Trees**: Use parent-child relationships for efficient tree building
- **Chat Messages**: Paginated queries for large conversations
- **Repository Lists**: Cache frequently accessed repository data

#### Frontend State Optimization
- **Context Providers**: Minimize re-renders with React.memo
- **Local Storage**: Persist critical state across page reloads
- **Error Boundaries**: Isolate component failures

### Data Validation

#### Frontend → Backend Validation
- **Type Checking**: TypeScript interfaces ensure correct data shapes
- **Schema Validation**: API service validates request/response structures
- **Error Handling**: Graceful degradation for invalid data

#### Backend → Database Validation
- **SQLAlchemy Models**: Enforce database constraints
- **Foreign Key Constraints**: Maintain referential integrity
- **Unique Constraints**: Prevent duplicate records

## Notes

- All timestamps use UTC timezone (`DateTime(timezone=True)`)
- JSON fields store complex data structures (arrays, objects)
- Foreign key relationships maintain referential integrity
- Cascade deletes are used for dependent records (e.g., user deletion removes all related data)
- Unique constraints prevent duplicate external IDs (GitHub IDs, issue IDs, etc.)
