-- Phase 1 migration for fixed 3-mode workflow and execution tracking.
-- Adds mode-state columns to chat_sessions and creates agent_executions.

BEGIN;

ALTER TABLE chat_sessions
    ADD COLUMN IF NOT EXISTS repo_url VARCHAR(1000),
    ADD COLUMN IF NOT EXISTS runtime_workspace_path VARCHAR(512),
    ADD COLUMN IF NOT EXISTS current_mode VARCHAR(32) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS mode_status VARCHAR(32) NOT NULL DEFAULT 'idle',
    ADD COLUMN IF NOT EXISTS mode_updated_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS architect_issue_url VARCHAR(1000),
    ADD COLUMN IF NOT EXISTS architect_issue_number INTEGER,
    ADD COLUMN IF NOT EXISTS architect_completed_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS tester_status VARCHAR(32),
    ADD COLUMN IF NOT EXISTS tester_completed_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS coder_pr_url VARCHAR(1000),
    ADD COLUMN IF NOT EXISTS coder_pr_number INTEGER,
    ADD COLUMN IF NOT EXISTS coder_completed_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS workflow_completed_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS mode_metadata JSONB;

CREATE INDEX IF NOT EXISTS idx_chat_sessions_current_mode ON chat_sessions(current_mode);

CREATE TABLE IF NOT EXISTS agent_executions (
    id VARCHAR(64) PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    mode VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'running',
    execution_plan JSONB,
    output_summary JSONB,
    error_message TEXT,
    execution_metadata JSONB,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_agent_executions_session_id ON agent_executions(session_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_mode ON agent_executions(mode);
CREATE INDEX IF NOT EXISTS idx_agent_executions_status ON agent_executions(status);
CREATE INDEX IF NOT EXISTS idx_agent_executions_created_at ON agent_executions(created_at);

DROP TRIGGER IF EXISTS update_agent_executions_updated_at ON agent_executions;
CREATE TRIGGER update_agent_executions_updated_at
    BEFORE UPDATE ON agent_executions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;
