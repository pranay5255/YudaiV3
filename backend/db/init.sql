-- PostgreSQL initialization script for YudaiV3
-- This script runs when the PostgreSQL container starts for the first time
-- Optimized for real-time features and Server-Sent Events
-- Tables match the exact schema defined in models.py

-- Create the database if it doesn't exist (PostgreSQL creates it automatically from env vars)
-- But we can add any additional setup here


-- Create extensions for enhanced functionality
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
-- Note: pgvector extension will be added when needed for embeddings

-- Configure PostgreSQL for SSE and real-time features
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';

-- Configure for real-time features
ALTER SYSTEM SET wal_level = 'logical';
ALTER SYSTEM SET max_wal_senders = 10;
ALTER SYSTEM SET max_replication_slots = 10;

-- JSON and JSONB optimization
ALTER SYSTEM SET max_locks_per_transaction = 64;

-- Connection pooling optimization
ALTER SYSTEM SET idle_in_transaction_session_timeout = '10min';
ALTER SYSTEM SET statement_timeout = '30s';

-- Set timezone globally
SET timezone = 'UTC';

-- Create custom functions for session management
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create notification function for real-time updates
CREATE OR REPLACE FUNCTION notify_session_update()
RETURNS TRIGGER AS $$
DECLARE
    payload JSON;
BEGIN
    payload = json_build_object(
        'table', TG_TABLE_NAME,
        'action', TG_OP,
        'data', row_to_json(NEW)
    );
    
    PERFORM pg_notify('session_updates', payload::text);
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ============================================================================
-- TABLE CREATION - EXACTLY MATCHING MODELS.PY SCHEMA
-- ============================================================================

-- Users table
CREATE TABLE IF NOT EXISTS users (
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

-- Auth tokens table
CREATE TABLE IF NOT EXISTS auth_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    access_token VARCHAR(500) NOT NULL,
    refresh_token VARCHAR(500),
    token_type VARCHAR(50) DEFAULT 'bearer',
    scope VARCHAR(500),
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Session tokens table
CREATE TABLE IF NOT EXISTS session_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Repositories table
CREATE TABLE IF NOT EXISTS repositories (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    github_repo_id INTEGER,
    name VARCHAR(255) NOT NULL,
    owner VARCHAR(255) NOT NULL,
    full_name VARCHAR(512) NOT NULL,
    repo_url VARCHAR(500),
    description TEXT,
    private BOOLEAN DEFAULT FALSE,
    html_url VARCHAR(500) NOT NULL,
    clone_url VARCHAR(500) NOT NULL,
    language VARCHAR(100),
    stargazers_count INTEGER DEFAULT 0,
    forks_count INTEGER DEFAULT 0,
    open_issues_count INTEGER DEFAULT 0,
    default_branch VARCHAR(100),
    github_created_at TIMESTAMP WITH TIME ZONE,
    github_updated_at TIMESTAMP WITH TIME ZONE,
    pushed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Issues table
CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    github_issue_id INTEGER UNIQUE NOT NULL,
    repository_id INTEGER REFERENCES repositories(id),
    number INTEGER NOT NULL,
    title VARCHAR(1000) NOT NULL,
    body TEXT,
    state VARCHAR(50) NOT NULL,
    html_url VARCHAR(1000) NOT NULL,
    author_username VARCHAR(255),
    github_created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    github_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    github_closed_at TIMESTAMP WITH TIME ZONE
);

-- Pull requests table
CREATE TABLE IF NOT EXISTS pull_requests (
    id SERIAL PRIMARY KEY,
    github_pr_id INTEGER UNIQUE NOT NULL,
    repository_id INTEGER REFERENCES repositories(id),
    number INTEGER NOT NULL,
    title VARCHAR(1000) NOT NULL,
    body TEXT,
    state VARCHAR(50) NOT NULL,
    html_url VARCHAR(1000) NOT NULL,
    author_username VARCHAR(255),
    github_created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    github_updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    github_closed_at TIMESTAMP WITH TIME ZONE,
    merged_at TIMESTAMP WITH TIME ZONE
);

-- Commits table
CREATE TABLE IF NOT EXISTS commits (
    id SERIAL PRIMARY KEY,
    sha VARCHAR(40) UNIQUE NOT NULL,
    repository_id INTEGER REFERENCES repositories(id),
    message TEXT NOT NULL,
    html_url VARCHAR(1000) NOT NULL,
    author_name VARCHAR(255),
    author_email VARCHAR(255),
    author_date TIMESTAMP WITH TIME ZONE
);

-- File items table
CREATE TABLE IF NOT EXISTS file_items (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id),
    name VARCHAR(500) NOT NULL,
    path VARCHAR(1000) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    category VARCHAR(100) NOT NULL,
    tokens INTEGER DEFAULT 0,
    is_directory BOOLEAN DEFAULT FALSE,
    parent_id INTEGER REFERENCES file_items(id),
    content TEXT,
    content_size INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- File analyses table
CREATE TABLE IF NOT EXISTS file_analyses (
    id SERIAL PRIMARY KEY,
    repository_id INTEGER REFERENCES repositories(id),
    raw_data JSON,
    processed_data JSON,
    total_files INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    max_file_size INTEGER,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE
);

-- User issues table
CREATE TABLE IF NOT EXISTS user_issues (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    issue_id VARCHAR(255) UNIQUE NOT NULL,
    context_card_id INTEGER,
    issue_text_raw TEXT NOT NULL,
    issue_steps JSON,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    session_id VARCHAR(255),
    context_cards JSON,
    ideas JSON,
    repo_owner VARCHAR(255),
    repo_name VARCHAR(255),
    priority VARCHAR(20) DEFAULT 'medium',
    status VARCHAR(50) DEFAULT 'pending',
    agent_response TEXT,
    processing_time FLOAT,
    tokens_used INTEGER DEFAULT 0,
    github_issue_url VARCHAR(1000),
    github_issue_number INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    processed_at TIMESTAMP WITH TIME ZONE
);

-- Chat sessions table (MISSING FROM ORIGINAL)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(255),
    description TEXT,
    repo_owner VARCHAR(255),
    repo_name VARCHAR(255),
    repo_branch VARCHAR(255) DEFAULT 'main',
    repo_context JSON,
    is_active BOOLEAN DEFAULT TRUE,
    total_messages INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    last_activity TIMESTAMP WITH TIME ZONE
);

-- Chat messages table (MISSING FROM ORIGINAL)
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
    message_id VARCHAR(255) NOT NULL,
    message_text TEXT NOT NULL,
    sender_type VARCHAR(50) NOT NULL,
    role VARCHAR(50) NOT NULL,
    is_code BOOLEAN DEFAULT FALSE,
    tokens INTEGER DEFAULT 0,
    model_used VARCHAR(100),
    processing_time FLOAT,
    context_cards JSON,
    referenced_files JSON,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Context cards table (MISSING FROM ORIGINAL)
CREATE TABLE IF NOT EXISTS context_cards (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    content TEXT NOT NULL,
    source VARCHAR(50) NOT NULL,
    tokens INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- File embeddings table (FIXED - ADDED session_id COLUMN)
CREATE TABLE IF NOT EXISTS file_embeddings (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
    repository_id INTEGER REFERENCES repositories(id),
    file_path VARCHAR(1000) NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    file_type VARCHAR(100) NOT NULL,
    file_content TEXT,
    embedding TEXT,
    chunk_index INTEGER DEFAULT 0,
    chunk_text TEXT NOT NULL,
    tokens INTEGER DEFAULT 0,
    file_metadata JSON,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- OAuth states table
CREATE TABLE IF NOT EXISTS oauth_states (
    state VARCHAR(255) PRIMARY KEY,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_used BOOLEAN DEFAULT FALSE
);

-- ============================================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================================

-- User indexes
CREATE INDEX IF NOT EXISTS idx_users_github_username ON users(github_username);
CREATE INDEX IF NOT EXISTS idx_users_github_user_id ON users(github_user_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Auth token indexes
CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_id ON auth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_tokens_is_active ON auth_tokens(is_active);

-- Session token indexes
CREATE INDEX IF NOT EXISTS idx_session_tokens_session_token ON session_tokens(session_token);
CREATE INDEX IF NOT EXISTS idx_session_tokens_user_id ON session_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_session_tokens_is_active ON session_tokens(is_active);
CREATE INDEX IF NOT EXISTS idx_session_tokens_expires_at ON session_tokens(expires_at);

-- Repository indexes
CREATE INDEX IF NOT EXISTS idx_repositories_user_id ON repositories(user_id);
CREATE INDEX IF NOT EXISTS idx_repositories_github_repo_id ON repositories(github_repo_id);
CREATE INDEX IF NOT EXISTS idx_repositories_owner ON repositories(owner);
CREATE INDEX IF NOT EXISTS idx_repositories_full_name ON repositories(full_name);
CREATE INDEX IF NOT EXISTS idx_repositories_repo_url ON repositories(repo_url);

-- Issue indexes
CREATE INDEX IF NOT EXISTS idx_issues_github_issue_id ON issues(github_issue_id);
CREATE INDEX IF NOT EXISTS idx_issues_repository_id ON issues(repository_id);

-- Pull request indexes
CREATE INDEX IF NOT EXISTS idx_pull_requests_github_pr_id ON pull_requests(github_pr_id);
CREATE INDEX IF NOT EXISTS idx_pull_requests_repository_id ON pull_requests(repository_id);

-- Commit indexes
CREATE INDEX IF NOT EXISTS idx_commits_sha ON commits(sha);
CREATE INDEX IF NOT EXISTS idx_commits_repository_id ON commits(repository_id);

-- File item indexes
CREATE INDEX IF NOT EXISTS idx_file_items_repository_id ON file_items(repository_id);
CREATE INDEX IF NOT EXISTS idx_file_items_path ON file_items(path);
CREATE INDEX IF NOT EXISTS idx_file_items_parent_id ON file_items(parent_id);

-- File analysis indexes
CREATE INDEX IF NOT EXISTS idx_file_analyses_repository_id ON file_analyses(repository_id);
CREATE INDEX IF NOT EXISTS idx_file_analyses_status ON file_analyses(status);

-- User issue indexes
CREATE INDEX IF NOT EXISTS idx_user_issues_user_id ON user_issues(user_id);
CREATE INDEX IF NOT EXISTS idx_user_issues_issue_id ON user_issues(issue_id);
CREATE INDEX IF NOT EXISTS idx_user_issues_session_id ON user_issues(session_id);
CREATE INDEX IF NOT EXISTS idx_user_issues_status ON user_issues(status);

-- Chat session indexes (NEW)
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_session_id ON chat_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_repo_owner ON chat_sessions(repo_owner);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_repo_name ON chat_sessions(repo_name);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_is_active ON chat_sessions(is_active);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_last_activity ON chat_sessions(last_activity);

-- Chat message indexes (NEW)
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_message_id ON chat_messages(message_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_sender_type ON chat_messages(sender_type);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at);

-- Context card indexes (NEW)
CREATE INDEX IF NOT EXISTS idx_context_cards_user_id ON context_cards(user_id);
CREATE INDEX IF NOT EXISTS idx_context_cards_session_id ON context_cards(session_id);
CREATE INDEX IF NOT EXISTS idx_context_cards_source ON context_cards(source);
CREATE INDEX IF NOT EXISTS idx_context_cards_is_active ON context_cards(is_active);

-- File embedding indexes (UPDATED - ADDED session_id INDEX)
CREATE INDEX IF NOT EXISTS idx_file_embeddings_session_id ON file_embeddings(session_id);
CREATE INDEX IF NOT EXISTS idx_file_embeddings_repository_id ON file_embeddings(repository_id);
CREATE INDEX IF NOT EXISTS idx_file_embeddings_file_path ON file_embeddings(file_path);

-- OAuth state indexes
CREATE INDEX IF NOT EXISTS idx_oauth_states_expires_at ON oauth_states(expires_at);
CREATE INDEX IF NOT EXISTS idx_oauth_states_is_used ON oauth_states(is_used);

-- ============================================================================
-- TRIGGERS FOR UPDATED_AT COLUMNS
-- ============================================================================

-- Create triggers for updated_at columns
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_auth_tokens_updated_at BEFORE UPDATE ON auth_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_session_tokens_updated_at BEFORE UPDATE ON session_tokens
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_repositories_updated_at BEFORE UPDATE ON repositories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_file_items_updated_at BEFORE UPDATE ON file_items
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_file_analyses_updated_at BEFORE UPDATE ON file_analyses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_issues_updated_at BEFORE UPDATE ON user_issues
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_sessions_updated_at BEFORE UPDATE ON chat_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_chat_messages_updated_at BEFORE UPDATE ON chat_messages
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_context_cards_updated_at BEFORE UPDATE ON context_cards
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_file_embeddings_updated_at BEFORE UPDATE ON file_embeddings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Log initialization
SELECT 'YudaiV3 database initialized with complete schema matching models.py' as status; 