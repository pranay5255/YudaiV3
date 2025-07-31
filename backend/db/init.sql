-- PostgreSQL initialization script for YudaiV3
-- This script runs when the PostgreSQL container starts for the first time
-- Optimized for real-time features and Server-Sent Events

-- Create the database if it doesn't exist (PostgreSQL creates it automatically from env vars)
-- But we can add any additional setup here

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON DATABASE yudai_db TO yudai_user;

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
ALTER DATABASE yudai_db SET timezone = 'UTC';

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

-- Log initialization
SELECT 'YudaiV3 database initialized with SSE optimization' as status; 