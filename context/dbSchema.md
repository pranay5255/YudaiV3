# YudaiV3 Database Schema Documentation

This document provides a comprehensive overview of all database tables in the YudaiV3 application, their structure, purpose, and which backend services interact with them.

## Database Overview

The YudaiV3 application uses PostgreSQL as its primary database with SQLAlchemy ORM for data management. The database supports user authentication via GitHub OAuth, repository management, chat conversations, context management, and issue tracking.

## Table Definitions

### 1. `users` - User Management
**Purpose**: Stores user account information for GitHub OAuth authentication.
**Used By**: `auth`, `github`, `daifuUserAgent`, `issueChatServices`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `github_username` | `String` | GitHub username (unique) |
| `github_user_id` | `Integer` | GitHub user ID (unique) |
| `email` | `String` | User email address |
| `display_name` | `String` | User display name |
| `avatar_url` | `String` | GitHub profile picture URL |

**Relationships**:
- One-to-many with `auth_tokens`
- One-to-many with `repositories`
- One-to-many with `chat_sessions`
- One-to-many with `context_cards`
- One-to-many with `idea_items`
- One-to-many with `user_issues`
- One-to-many with `file_embeddings`

---

### 2. `auth_tokens` - Authentication Tokens
**Purpose**: Stores GitHub OAuth access tokens for authenticated users.
**Used By**: `auth`, `github`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `user_id` | `Integer` | Foreign Key to `users.id` |
| `access_token` | `String` | GitHub OAuth access token |
| `refresh_token` | `String` | GitHub OAuth refresh token |
| `token_type` | `String` | Token type (e.g., "bearer") |
| `scope` | `String` | OAuth token scope |
| `expires_at` | `DateTime` | Token expiration timestamp |
| `is_active` | `Boolean` | Token status |

**Relationships**:
- Many-to-one with `users`

---

### 3. `repositories` - Repository Metadata
**Purpose**: Stores GitHub repository metadata.
**Used By**: `github`, `repo_processorGitIngest`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `github_repo_id` | `Integer` | GitHub repository ID (unique) |
| `user_id` | `Integer` | Foreign Key to `users.id` |
| `name` | `String` | Repository name |
| `owner` | `String` | Repository owner |
| `full_name` | `String` | Full repository name (owner/repo) |

**Relationships**:
- Many-to-one with `users`
- One-to-many with `issues`, `pull_requests`, `commits`, `file_items`

---

### 4. `issues` - GitHub Issues
**Purpose**: Stores issues fetched from GitHub repositories.
**Used By**: `github`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `github_issue_id` | `Integer` | GitHub issue ID (unique) |
| `repository_id` | `Integer` | Foreign Key to `repositories.id` |
| `number` | `Integer` | GitHub issue number |
| `title` | `String` | Issue title |
| `state` | `String` | Issue state (open/closed) |

**Relationships**:
- Many-to-one with `repositories`

---

### 5. `pull_requests` - GitHub Pull Requests
**Purpose**: Stores pull requests fetched from GitHub repositories.
**Used By**: `github`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `github_pr_id` | `Integer` | GitHub PR ID (unique) |
| `repository_id` | `Integer` | Foreign Key to `repositories.id` |
| `number` | `Integer` | GitHub PR number |
| `title` | `String` | PR title |
| `state` | `String` | PR state (open/closed) |

**Relationships**:
- Many-to-one with `repositories`

---

### 6. `commits` - Repository Commits
**Purpose**: Stores commit information from GitHub repositories.
**Used By**: `github`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `sha` | `String` | Git commit hash |
| `repository_id` | `Integer` | Foreign Key to `repositories.id` |
| `message` | `String` | Commit message |

**Relationships**:
- Many-to-one with `repositories`

---

### 7. `file_items` - Repository File Analysis
**Purpose**: Stores file structure and analysis data.
**Used By**: `repo_processorGitIngest`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `repository_id` | `Integer` | Foreign Key to `repositories.id` |
| `name` | `String` | File/directory name |
| `path` | `String` | Full file path |
| `is_directory` | `Boolean` | True if it's a directory |
| `parent_id` | `Integer` | Self-referencing Foreign Key |

**Relationships**:
- Many-to-one with `repositories`
- Self-referencing tree structure

---

### 8. `file_analyses` - File Analysis Results
**Purpose**: Stores results of file analysis operations.
**Used By**: `repo_processorGitIngest`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `repository_id` | `Integer` | Foreign Key to `repositories.id` |
| `status` | `String` | Analysis status |

**Relationships**:
- Many-to-one with `repositories`

---

### 9. `context_cards` - User Context Cards
**Purpose**: Stores user-created context cards.
**Used By**: `issueChatServices`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `user_id` | `Integer` | Foreign Key to `users.id` |
| `title` | `String` | Card title |
| `content` | `String` | Card content |

**Relationships**:
- Many-to-one with `users`
- Referenced by `user_issues`

---

### 10. `idea_items` - Implementation Ideas
**Purpose**: Stores user-generated ideas.
**Used By**: `issueChatServices`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `user_id` | `Integer`| Foreign Key to `users.id` |
| `title` | `String` | Idea title |
| `description` | `String` | Idea description |

**Relationships**:
- Many-to-one with `users`

---

### 11. `chat_sessions` - Chat Sessions
**Purpose**: Manages chat conversations.
**Used By**: `daifuUserAgent`, `issueChatServices`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `user_id` | `Integer` | Foreign Key to `users.id` |
| `session_id` | `String` | External session identifier |
| `title` | `String` | Session title |

**Relationships**:
- Many-to-one with `users`
- One-to-many with `chat_messages`
- Referenced by `user_issues`

---

### 12. `chat_messages` - Chat Messages
**Purpose**: Stores messages within chat sessions.
**Used By**: `daifuUserAgent`, `issueChatServices`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `session_id` | `Integer` | Foreign Key to `chat_sessions.id` |
| `message_text` | `String` | Message content |
| `sender_type` | `String` | "user", "assistant", or "system" |

**Relationships**:
- Many-to-one with `chat_sessions`

---

### 13. `user_issues` - User-Generated Issues
**Purpose**: Stores user-generated issues from chat conversations.
**Used By**: `daifuUserAgent`, `issueChatServices`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `user_id` | `Integer` | Foreign Key to `users.id` |
| `chat_session_id` | `Integer` | Foreign Key to `chat_sessions.id` |
| `title` | `String` | Issue title |
| `description` | `String` | Issue description |

**Relationships**:
- Many-to-one with `users`
- Many-to-one with `chat_sessions` (optional)

---

### 14. `file_embeddings` - File Embeddings
**Purpose**: Stores vector embeddings for file content.
**Used By**: `daifuUserAgent`

| Field | Type | Description |
|---|---|---|
| `id` | `Integer` | **Primary Key** |
| `session_id` | `String` | Session identifier |
| `file_path` | `String` | Path to the file |
| `embedding` | `pgvector` | Vector embedding of the file content |

**Relationships**:
- Many-to-one with `users`

## Unused/Deprecated Tables

- **`context_cards`**: Table exists but management APIs are not fully implemented.
- **`idea_items`**: Table exists but management APIs are not fully implemented.

## Database Initialization
The database is initialized via:
- `backend/db/database.py`
- `backend/db/init_db.py`
- `backend/db/init.sql`

## Migration Strategy
1. Update models in `backend/models.py`.
2. Update the expected tables list in `backend/db/init_db.py`.
3. Run `python backend/db/init_db.py --init`.
4. Update this documentation.
