-- Rollback for Phase 0 migration.

BEGIN;

DROP TRIGGER IF EXISTS update_session_runtime_updated_at ON session_runtime;
DROP TRIGGER IF EXISTS update_sandboxes_updated_at ON sandboxes;

DROP INDEX IF EXISTS idx_session_audit_events_created_at;
DROP INDEX IF EXISTS idx_session_audit_events_runtime_id;
DROP INDEX IF EXISTS idx_session_audit_events_sandbox_id;
DROP INDEX IF EXISTS idx_session_audit_events_session_id;
DROP INDEX IF EXISTS idx_session_audit_events_user_id;
DROP INDEX IF EXISTS idx_session_audit_events_event_name;
DROP INDEX IF EXISTS idx_session_artifacts_exported_at;
DROP INDEX IF EXISTS idx_session_artifacts_artifact_key;
DROP INDEX IF EXISTS idx_session_artifacts_runtime_id;
DROP INDEX IF EXISTS idx_session_artifacts_session_id;
DROP INDEX IF EXISTS idx_session_runtime_updated_at;
DROP INDEX IF EXISTS idx_session_runtime_status;
DROP INDEX IF EXISTS idx_session_runtime_sandbox_id;
DROP INDEX IF EXISTS idx_session_runtime_session_id;
DROP INDEX IF EXISTS idx_session_runtime_runtime_id;
DROP INDEX IF EXISTS idx_sandboxes_updated_at;
DROP INDEX IF EXISTS idx_sandboxes_status;
DROP INDEX IF EXISTS idx_sandboxes_org_repo_env;
DROP INDEX IF EXISTS idx_sandboxes_identity_key;

DROP TABLE IF EXISTS session_audit_events;
DROP TABLE IF EXISTS session_artifacts;
DROP TABLE IF EXISTS session_runtime;
DROP TABLE IF EXISTS sandboxes;

COMMIT;

