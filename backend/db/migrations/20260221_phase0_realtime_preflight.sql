-- Phase 0 migration for real-time session architecture contracts.
-- Adds lifecycle, runtime, artifact, and audit tables required for Phase 1.

BEGIN;

CREATE TABLE IF NOT EXISTS sandboxes (
    id VARCHAR(64) PRIMARY KEY,
    identity_key VARCHAR(512) UNIQUE NOT NULL,
    org_slug VARCHAR(255) NOT NULL,
    repo_owner VARCHAR(255) NOT NULL,
    repo_name VARCHAR(255) NOT NULL,
    environment VARCHAR(255) NOT NULL,
    repo_branch VARCHAR(255) NOT NULL DEFAULT 'main',
    status VARCHAR(32) NOT NULL DEFAULT 'provisioning',
    tunnel_url VARCHAR(1000),
    tunnel_auth_mode VARCHAR(64) NOT NULL DEFAULT 'session_jwt_passthrough',
    tunnel_token_ttl_seconds INTEGER DEFAULT 3600,
    last_heartbeat_at TIMESTAMP WITH TIME ZONE,
    terminated_at TIMESTAMP WITH TIME ZONE,
    created_by_user_id INTEGER REFERENCES users(id),
    active_session_id INTEGER REFERENCES chat_sessions(id),
    lifecycle_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS session_runtime (
    id SERIAL PRIMARY KEY,
    runtime_id VARCHAR(64) UNIQUE NOT NULL,
    session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
    sandbox_id VARCHAR(64) REFERENCES sandboxes(id) ON DELETE SET NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'provisioning',
    completion_issue_created BOOLEAN DEFAULT FALSE,
    completion_pr_created BOOLEAN DEFAULT FALSE,
    completion_detected BOOLEAN DEFAULT FALSE,
    completion_reason VARCHAR(255),
    tunnel_url VARCHAR(1000),
    tunnel_resolved_at TIMESTAMP WITH TIME ZONE,
    tunnel_expires_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    runtime_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS session_artifacts (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES chat_sessions(id) ON DELETE CASCADE,
    runtime_id INTEGER REFERENCES session_runtime(id) ON DELETE SET NULL,
    artifact_key VARCHAR(512) NOT NULL,
    artifact_type VARCHAR(50) NOT NULL DEFAULT 'bundle_metadata',
    cache_manifest_path VARCHAR(1000),
    bundle_path VARCHAR(1000),
    checksum_sha256 VARCHAR(128),
    object_etag VARCHAR(255),
    byte_size INTEGER,
    artifact_metadata JSONB,
    exported_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS session_audit_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(64) UNIQUE NOT NULL,
    event_name VARCHAR(64) NOT NULL,
    user_id INTEGER REFERENCES users(id),
    session_id INTEGER REFERENCES chat_sessions(id),
    sandbox_id VARCHAR(64) REFERENCES sandboxes(id),
    runtime_id INTEGER REFERENCES session_runtime(id),
    event_payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sandboxes_identity_key ON sandboxes(identity_key);
CREATE INDEX IF NOT EXISTS idx_sandboxes_org_repo_env ON sandboxes(org_slug, repo_owner, repo_name, environment);
CREATE INDEX IF NOT EXISTS idx_sandboxes_status ON sandboxes(status);
CREATE INDEX IF NOT EXISTS idx_sandboxes_updated_at ON sandboxes(updated_at);
CREATE INDEX IF NOT EXISTS idx_session_runtime_runtime_id ON session_runtime(runtime_id);
CREATE INDEX IF NOT EXISTS idx_session_runtime_session_id ON session_runtime(session_id);
CREATE INDEX IF NOT EXISTS idx_session_runtime_sandbox_id ON session_runtime(sandbox_id);
CREATE INDEX IF NOT EXISTS idx_session_runtime_status ON session_runtime(status);
CREATE INDEX IF NOT EXISTS idx_session_runtime_updated_at ON session_runtime(updated_at);
CREATE INDEX IF NOT EXISTS idx_session_artifacts_session_id ON session_artifacts(session_id);
CREATE INDEX IF NOT EXISTS idx_session_artifacts_runtime_id ON session_artifacts(runtime_id);
CREATE INDEX IF NOT EXISTS idx_session_artifacts_artifact_key ON session_artifacts(artifact_key);
CREATE INDEX IF NOT EXISTS idx_session_artifacts_exported_at ON session_artifacts(exported_at);
CREATE INDEX IF NOT EXISTS idx_session_audit_events_event_name ON session_audit_events(event_name);
CREATE INDEX IF NOT EXISTS idx_session_audit_events_user_id ON session_audit_events(user_id);
CREATE INDEX IF NOT EXISTS idx_session_audit_events_session_id ON session_audit_events(session_id);
CREATE INDEX IF NOT EXISTS idx_session_audit_events_sandbox_id ON session_audit_events(sandbox_id);
CREATE INDEX IF NOT EXISTS idx_session_audit_events_runtime_id ON session_audit_events(runtime_id);
CREATE INDEX IF NOT EXISTS idx_session_audit_events_created_at ON session_audit_events(created_at);

DROP TRIGGER IF EXISTS update_sandboxes_updated_at ON sandboxes;
CREATE TRIGGER update_sandboxes_updated_at
    BEFORE UPDATE ON sandboxes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_session_runtime_updated_at ON session_runtime;
CREATE TRIGGER update_session_runtime_updated_at
    BEFORE UPDATE ON session_runtime
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;

