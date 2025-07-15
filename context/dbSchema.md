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

## Notes

- All timestamps use UTC timezone (`DateTime(timezone=True)`)
- JSON fields store complex data structures (arrays, objects)
- Foreign key relationships maintain referential integrity
- Cascade deletes are used for dependent records (e.g., user deletion removes all related data)
- Unique constraints prevent duplicate external IDs (GitHub IDs, issue IDs, etc.)
