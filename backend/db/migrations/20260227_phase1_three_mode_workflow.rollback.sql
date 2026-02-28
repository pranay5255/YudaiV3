-- Rollback for phase 1 three-mode workflow migration.

BEGIN;

DROP TRIGGER IF EXISTS update_agent_executions_updated_at ON agent_executions;
DROP TABLE IF EXISTS agent_executions;

DROP INDEX IF EXISTS idx_chat_sessions_current_mode;

ALTER TABLE chat_sessions
    DROP COLUMN IF EXISTS mode_metadata,
    DROP COLUMN IF EXISTS workflow_completed_at,
    DROP COLUMN IF EXISTS coder_completed_at,
    DROP COLUMN IF EXISTS coder_pr_number,
    DROP COLUMN IF EXISTS coder_pr_url,
    DROP COLUMN IF EXISTS tester_completed_at,
    DROP COLUMN IF EXISTS tester_status,
    DROP COLUMN IF EXISTS architect_completed_at,
    DROP COLUMN IF EXISTS architect_issue_number,
    DROP COLUMN IF EXISTS architect_issue_url,
    DROP COLUMN IF EXISTS mode_updated_at,
    DROP COLUMN IF EXISTS mode_status,
    DROP COLUMN IF EXISTS current_mode,
    DROP COLUMN IF EXISTS runtime_workspace_path,
    DROP COLUMN IF EXISTS repo_url;

COMMIT;
