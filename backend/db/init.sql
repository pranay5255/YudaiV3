-- PostgreSQL bootstrap script for YudaiV3.
-- This file is intentionally minimal: schema is created by SQLAlchemy models
-- in db/init_db.py and db/database.py so DB shape always matches API usage.

-- Extensions used by the application.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS vector;

-- Use UTC by default.
SET timezone = 'UTC';

-- Helper trigger function available for optional updated_at triggers.
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Helper notification function available for optional realtime triggers.
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
$$ LANGUAGE plpgsql;

SELECT 'YudaiV3 DB bootstrap complete; schema managed by SQLAlchemy init_db()' AS status;
