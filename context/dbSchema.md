# YudaiV3 Database Schema Documentation

**Last Updated**: January 2025  
**Database**: PostgreSQL 13+  
**ORM**: SQLAlchemy  
**Status**: 🟡 PARTIALLY IMPLEMENTED - CRITICAL EXTENSIONS MISSING

## 🚨 CRITICAL DATABASE ISSUES

**pgvector Extension Missing**: File embeddings completely broken
```sql
-- ❌ MISSING: Required for file_embeddings table
CREATE EXTENSION IF NOT EXISTS vector;
```

**Impact**: Core file dependencies feature non-functional, demo blocker

---

## 📊 DATABASE OVERVIEW

The YudaiV3 application uses PostgreSQL as its primary database with SQLAlchemy ORM. The schema supports:
- ✅ User authentication via GitHub OAuth
- ✅ Repository management and caching
- ✅ Chat conversations with AI agent
- ✅ Issue tracking and GitHub integration
- ❌ **File analysis and embeddings (BROKEN)**

### Database Statistics
- **Total Tables**: 14 defined, 12 working, 2 broken
- **Primary Services**: 5 backend services
- **Extensions Required**: pgvector (MISSING), pg_trgm
- **Connection Pool**: 20 connections, 30 max overflow

---

## 🗄️ CORE DATABASE TABLES

### 1. `users` - User Management ✅ WORKING
**Purpose**: Stores user account information for GitHub OAuth authentication  
**Used By**: All services requiring authentication  
**Status**: Production ready

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    github_username VARCHAR(255) UNIQUE NOT NULL,
    github_user_id VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    display_name VARCHAR(255),
    avatar_url VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    last_login TIMESTAMPTZ
);
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `SERIAL` | **PRIMARY KEY** | Auto-incrementing user ID |
| `github_username` | `VARCHAR(255)` | UNIQUE, NOT NULL | GitHub username |
| `github_user_id` | `VARCHAR(255)` | UNIQUE, NOT NULL | GitHub user ID |
| `email` | `VARCHAR(255)` | UNIQUE | User email address |
| `display_name` | `VARCHAR(255)` | | User display name |
| `avatar_url` | `VARCHAR(500)` | | GitHub profile picture URL |
| `created_at` | `TIMESTAMPTZ` | DEFAULT NOW() | Account creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | | Last update timestamp |
| `last_login` | `TIMESTAMPTZ` | | Last login timestamp |

**Relationships**:
- One-to-many with `auth_tokens`
- One-to-many with `repositories`
- One-to-many with `chat_sessions`
- One-to-many with `user_issues`
- One-to-many with `context_cards`
- One-to-many with `file_embeddings`

---

### 2. `auth_tokens` - Authentication Tokens ✅ WORKING
**Purpose**: Stores GitHub OAuth access tokens with expiration tracking  
**Used By**: `auth`, `github` services  
**Status**: Production ready

```sql
CREATE TABLE auth_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    access_token VARCHAR(500) NOT NULL,
    refresh_token VARCHAR(500),
    token_type VARCHAR(50) DEFAULT 'bearer',
    scope VARCHAR(500),
    expires_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `SERIAL` | **PRIMARY KEY** | Token ID |
| `user_id` | `INTEGER` | **FOREIGN KEY** | References `users.id` |
| `access_token` | `VARCHAR(500)` | NOT NULL | GitHub OAuth access token |
| `refresh_token` | `VARCHAR(500)` | | GitHub OAuth refresh token |
| `token_type` | `VARCHAR(50)` | DEFAULT 'bearer' | Token type |
| `scope` | `VARCHAR(500)` | | OAuth token scope |
| `expires_at` | `TIMESTAMPTZ` | | Token expiration timestamp |
| `is_active` | `BOOLEAN` | DEFAULT TRUE | Token status |

**Security Features**:
- ✅ Automatic token deactivation on new login
- ✅ Expiration tracking
- ✅ Cascade delete on user removal

---

### 3. `repositories` - Repository Metadata ✅ WORKING
**Purpose**: Caches GitHub repository metadata for quick access  
**Used By**: `github`, `repo_processorGitIngest` services  
**Status**: Production ready

```sql
CREATE TABLE repositories (
    id SERIAL PRIMARY KEY,
    github_repo_id BIGINT UNIQUE NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    description TEXT,
    private BOOLEAN DEFAULT FALSE,
    default_branch VARCHAR(255) DEFAULT 'main',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

**Relationships**:
- Many-to-one with `users`
- One-to-many with `issues`, `pull_requests`, `commits`
- One-to-many with `file_items`, `file_analyses`

---

### 4. `issues` - GitHub Issues Cache ✅ WORKING
**Purpose**: Caches GitHub issues for performance and offline access  
**Used By**: `github` service  
**Status**: Production ready

```sql
CREATE TABLE issues (
    id SERIAL PRIMARY KEY,
    github_issue_id BIGINT UNIQUE NOT NULL,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    state VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

---

### 5. `pull_requests` - GitHub Pull Requests Cache ✅ WORKING
**Purpose**: Caches GitHub pull requests for tracking and analysis  
**Used By**: `github` service  
**Status**: Production ready

```sql
CREATE TABLE pull_requests (
    id SERIAL PRIMARY KEY,
    github_pr_id BIGINT UNIQUE NOT NULL,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    number INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    state VARCHAR(20) DEFAULT 'open',
    base_branch VARCHAR(255),
    head_branch VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

---

### 6. `commits` - Repository Commits ✅ WORKING
**Purpose**: Tracks repository commit history for analysis  
**Used By**: `github` service  
**Status**: Production ready

```sql
CREATE TABLE commits (
    id SERIAL PRIMARY KEY,
    sha VARCHAR(40) UNIQUE NOT NULL,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    author_name VARCHAR(255),
    author_email VARCHAR(255),
    commit_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 💬 CHAT SYSTEM TABLES

### 7. `chat_sessions` - Chat Sessions ✅ WORKING
**Purpose**: Manages AI chat conversations with repository context  
**Used By**: `daifuUserAgent`, `issueChatServices`  
**Status**: Production ready, but session ID inconsistency issues

```sql
CREATE TABLE chat_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500),
    repository_owner VARCHAR(255),
    repository_name VARCHAR(255),
    repository_branch VARCHAR(255) DEFAULT 'main',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    last_activity TIMESTAMPTZ DEFAULT NOW()
);
```

**⚠️ Current Issues**:
- Session ID format inconsistency between services
- Mixed usage of `session_id` vs `conversation_id`

---

### 8. `chat_messages` - Chat Messages ✅ WORKING
**Purpose**: Stores all chat messages with AI agent  
**Used By**: `daifuUserAgent`  
**Status**: Production ready

```sql
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_text TEXT NOT NULL,
    sender_type VARCHAR(20) NOT NULL CHECK (sender_type IN ('user', 'assistant', 'system')),
    is_code BOOLEAN DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

| Field | Type | Description |
|-------|------|-------------|
| `sender_type` | `VARCHAR(20)` | 'user', 'assistant', or 'system' |
| `is_code` | `BOOLEAN` | TRUE if message contains code |
| `metadata` | `JSONB` | Additional message metadata |

---

### 9. `context_cards` - User Context Cards ✅ WORKING
**Purpose**: Stores user-created context cards for chat enhancement  
**Used By**: `issueChatServices`  
**Status**: Production ready

```sql
CREATE TABLE context_cards (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    source VARCHAR(50) DEFAULT 'manual',
    category VARCHAR(100),
    session_id INTEGER REFERENCES chat_sessions(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

---

## 📋 ISSUE MANAGEMENT TABLES

### 10. `user_issues` - User-Generated Issues ✅ WORKING
**Purpose**: Manages user-created issues from chat conversations  
**Used By**: `issueChatServices`  
**Status**: Production ready

```sql
CREATE TABLE user_issues (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chat_session_id INTEGER REFERENCES chat_sessions(id) ON DELETE SET NULL,
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'open',
    priority VARCHAR(20) DEFAULT 'medium',
    github_issue_id BIGINT REFERENCES issues(github_issue_id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

**GitHub Integration**:
- Links to GitHub issues via `github_issue_id`
- Preserves context from chat sessions
- Tracks issue lifecycle and status

---

### 11. `idea_items` - Implementation Ideas ⚠️ UNDERUTILIZED
**Purpose**: Stores user-generated implementation ideas  
**Used By**: `issueChatServices` (minimal usage)  
**Status**: Table exists but features not fully implemented

```sql
CREATE TABLE idea_items (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(100),
    complexity_level VARCHAR(10) DEFAULT 'M',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ
);
```

**⚠️ Issues**:
- Management APIs not fully implemented
- Frontend integration incomplete
- No clear user workflow

---

## 📁 FILE ANALYSIS TABLES ❌ BROKEN

### 12. `file_items` - Repository File Structure ❌ BROKEN
**Purpose**: Stores repository file hierarchy for analysis  
**Used By**: `repo_processorGitIngest`  
**Status**: ❌ **BROKEN** - File tree extraction fails

```sql
CREATE TABLE file_items (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    path TEXT NOT NULL,
    is_directory BOOLEAN DEFAULT FALSE,
    parent_id INTEGER REFERENCES file_items(id) ON DELETE CASCADE,
    file_size BIGINT,
    mime_type VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**🔴 Critical Issues**:
- Database queries timeout on large repositories
- Infinite recursion in file hierarchy rendering
- Memory leaks during file tree extraction
- Self-referencing foreign key issues

---

### 13. `file_analyses` - File Analysis Results ❌ BROKEN
**Purpose**: Stores results of repository file analysis operations  
**Used By**: `repo_processorGitIngest`  
**Status**: ❌ **BROKEN** - Analysis never completes

```sql
CREATE TABLE file_analyses (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    analysis_type VARCHAR(100),
    results JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);
```

---

### 14. `file_embeddings` - Vector Embeddings ❌ MISSING EXTENSION
**Purpose**: Stores vector embeddings for semantic file search  
**Used By**: `daifuUserAgent` (AI context)  
**Status**: ❌ **COMPLETELY BROKEN** - pgvector extension missing

```sql
-- ❌ FAILS: pgvector extension not installed
CREATE TABLE file_embeddings (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    embedding vector(1536),  -- ❌ FAILS: vector type unavailable
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**🔴 Critical Missing Extension**:
```sql
-- ❌ REQUIRED: This needs to be added to database initialization
CREATE EXTENSION IF NOT EXISTS vector;
```

---

## 🔧 DATABASE CONFIGURATION

### Connection Settings
```python
# backend/db/database.py
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://yudai_user:yudai_password@db:5432/yudai_db"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,           # ⚠️ Too high for development
    max_overflow=30,        # ⚠️ Excessive
    pool_recycle=3600,      # Could be optimized
    pool_timeout=30,
    echo=bool(os.getenv("DB_ECHO", "false").lower() == "true")
)
```

### Required Extensions
```sql
-- ❌ MISSING: Critical for file embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ✅ RECOMMENDED: For text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ✅ RECOMMENDED: For UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### Database Initialization Issues
```python
# backend/db/database.py:49-62
def init_db():
    """
    ⚠️ INCOMPLETE: Missing extension setup
    - Creates tables correctly
    - BUT: No pgvector extension installation
    - BUT: No initial data seeding
    - BUT: No migration system
    """
    try:
        Base.metadata.create_all(bind=engine)
        return True
    except Exception as e:
        print(f"✗ Failed to initialize database: {e}")
        return False
```

---

## 🗂️ DATABASE RELATIONSHIPS

### User-Centric Relationships
```
users (1) ←→ (∞) auth_tokens
users (1) ←→ (∞) repositories  
users (1) ←→ (∞) chat_sessions
users (1) ←→ (∞) user_issues
users (1) ←→ (∞) context_cards
users (1) ←→ (∞) file_embeddings
```

### Repository-Centric Relationships
```
repositories (1) ←→ (∞) issues
repositories (1) ←→ (∞) pull_requests
repositories (1) ←→ (∞) commits
repositories (1) ←→ (∞) file_items ❌
repositories (1) ←→ (∞) file_analyses ❌
```

### Chat System Relationships
```
chat_sessions (1) ←→ (∞) chat_messages
chat_sessions (1) ←→ (∞) user_issues
chat_sessions (1) ←→ (∞) context_cards
```

---

## 🔍 DATABASE INDEXES

### Current Indexes (Automatic)
```sql
-- Primary keys (automatic)
users_pkey, auth_tokens_pkey, repositories_pkey, etc.

-- Unique constraints (automatic)
users_github_username_key, users_github_user_id_key, etc.

-- Foreign key indexes (recommended)
CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_id ON auth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_repositories_user_id ON repositories(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_user_issues_user_id ON user_issues(user_id);
CREATE INDEX IF NOT EXISTS idx_context_cards_user_id ON context_cards(user_id);
```

### ❌ Missing Performance Indexes
```sql
-- ❌ MISSING: Performance indexes for common queries
CREATE INDEX IF NOT EXISTS idx_chat_sessions_activity ON chat_sessions(last_activity DESC);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_issues_status ON user_issues(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_repositories_full_name ON repositories(full_name);

-- ❌ MISSING: Composite indexes for complex queries
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_repo ON chat_sessions(user_id, repository_owner, repository_name);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_active ON auth_tokens(user_id, is_active) WHERE is_active = TRUE;
```

---

## 🚨 CRITICAL DATABASE FIXES REQUIRED

### Phase 1: Core Functionality (Day 1)
1. **Install pgvector Extension**
   ```sql
   -- Add to database initialization
   CREATE EXTENSION IF NOT EXISTS vector;
   
   -- Recreate file_embeddings table
   ALTER TABLE file_embeddings ADD COLUMN embedding vector(1536);
   ```

2. **Fix File Analysis Tables**
   ```sql
   -- Add missing constraints and optimizations
   CREATE INDEX IF NOT EXISTS idx_file_items_repository ON file_items(repository_id);
   CREATE INDEX IF NOT EXISTS idx_file_items_parent ON file_items(parent_id);
   CREATE INDEX IF NOT EXISTS idx_file_items_path ON file_items USING GIN(path gin_trgm_ops);
   ```

3. **Add Performance Indexes**
   ```sql
   -- Critical performance indexes for demo
   CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chat_sessions_activity 
   ON chat_sessions(last_activity DESC);
   ```

### Phase 2: Data Integrity (Day 2)
1. **Add Missing Constraints**
   ```sql
   -- Ensure data integrity
   ALTER TABLE chat_sessions ADD CONSTRAINT check_session_id_format 
   CHECK (session_id ~ '^[a-zA-Z0-9_]+$');
   
   ALTER TABLE user_issues ADD CONSTRAINT check_priority 
   CHECK (priority IN ('low', 'medium', 'high', 'critical'));
   ```

2. **Implement Proper Cascades**
   ```sql
   -- Fix cascade behaviors
   ALTER TABLE chat_messages DROP CONSTRAINT chat_messages_session_id_fkey;
   ALTER TABLE chat_messages ADD CONSTRAINT chat_messages_session_id_fkey 
   FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE;
   ```

### Phase 3: Optimization (Day 3)
1. **Connection Pool Optimization**
   ```python
   # Environment-specific connection pools
   if os.getenv("NODE_ENV") == "production":
       pool_size = 10
       max_overflow = 20
   else:
       pool_size = 5
       max_overflow = 10
   ```

2. **Add Monitoring Tables**
   ```sql
   -- Database monitoring and metrics
   CREATE TABLE database_metrics (
       id SERIAL PRIMARY KEY,
       metric_name VARCHAR(100) NOT NULL,
       metric_value NUMERIC,
       recorded_at TIMESTAMPTZ DEFAULT NOW()
   );
   ```

---

## 📊 DATABASE HEALTH METRICS

| Table | Status | Records (Est.) | Issues | Priority |
|-------|--------|---------------|--------|----------|
| `users` | ✅ Healthy | < 1K | None | Low |
| `auth_tokens` | ✅ Healthy | < 1K | None | Low |
| `repositories` | ✅ Healthy | < 10K | None | Low |
| `chat_sessions` | ⚠️ Partial | < 5K | Session ID inconsistency | High |
| `chat_messages` | ✅ Healthy | < 50K | None | Low |
| `user_issues` | ✅ Healthy | < 5K | None | Low |
| `context_cards` | ✅ Healthy | < 10K | None | Low |
| `file_items` | ❌ Broken | 0 | Query timeouts | Critical |
| `file_analyses` | ❌ Broken | 0 | Never completes | Critical |
| `file_embeddings` | ❌ Missing | 0 | No pgvector | Critical |

---

## 🎯 DATABASE SUCCESS CRITERIA FOR DEMO

- [ ] pgvector extension installed and working
- [ ] All file analysis tables functional
- [ ] Fast query performance (< 100ms for simple queries)
- [ ] Proper indexes for all common query patterns
- [ ] No exposed connection strings or credentials
- [ ] Backup and recovery procedures documented
- [ ] Database monitoring and alerting functional
- [ ] All foreign key constraints properly defined
- [ ] Data migration strategy documented

---

## 🔄 DATABASE MIGRATION STRATEGY

### Current State: ❌ NO MIGRATION SYSTEM
```python
# ❌ CURRENT: Manual table creation only
def init_db():
    Base.metadata.create_all(bind=engine)
```

### ✅ RECOMMENDED: Alembic Integration
```python
# Add to project
pip install alembic

# Initialize migrations
alembic init migrations

# Create migration for pgvector
alembic revision -m "Add pgvector extension"

# Apply migrations
alembic upgrade head
```

---

**Status**: The database schema requires immediate fixes to support core functionality. Priority should be on installing pgvector extension and fixing file analysis tables before demo deployment.
