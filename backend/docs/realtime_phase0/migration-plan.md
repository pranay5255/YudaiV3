# DB Migration Plan (Phase 0)

## Goal

Prepare controller metadata persistence for Phase 1 lifecycle features without
changing existing session APIs.

## SQL Files

1. Apply:
`backend/db/migrations/20260221_phase0_realtime_preflight.sql`
2. Rollback:
`backend/db/migrations/20260221_phase0_realtime_preflight.rollback.sql`

## SQLAlchemy Model Scope

Added in `backend/models.py`:

1. `Sandbox` (`sandboxes`)
2. `SessionRuntime` (`session_runtime`)
3. `SessionArtifact` (`session_artifacts`)
4. `SessionAuditEvent` (`session_audit_events`)

Related enums:

1. `SandboxStatus`
2. `SessionRuntimeStatus`
3. `SessionAuditEventName`

## Table Intent

1. `sandboxes`: lifecycle + tunnel metadata by `org/repo/environment`.
2. `session_runtime`: one runtime record per active session/sandbox lifecycle.
3. `session_artifacts`: exported bundle metadata/checksum/etag refs.
4. `session_audit_events`: append-only lifecycle and side-effect events.

## Index Plan

1. Identity and lifecycle lookups:
   - `sandboxes(identity_key)`
   - `sandboxes(org_slug, repo_owner, repo_name, environment)`
   - `sandboxes(status)`
2. Runtime lookups:
   - `session_runtime(runtime_id)`
   - `session_runtime(session_id)`
   - `session_runtime(sandbox_id)`
   - `session_runtime(status)`
3. Artifact and audit lookups:
   - `session_artifacts(session_id, runtime_id, artifact_key, exported_at)`
   - `session_audit_events(event_name, user_id, session_id, sandbox_id, runtime_id, created_at)`

## Trigger Plan

`updated_at` triggers are enabled for:

1. `sandboxes`
2. `session_runtime`

