# Audit Log Schema

Database table: `session_audit_events`

Model: `SessionAuditEvent` in `backend/models.py`.

## Required Event Names

1. `sandbox_start`
2. `solve_start`
3. `github_issue_create`
4. `pr_create`
5. `sandbox_terminate`

## Column Contract

1. `event_id` (unique idempotency key)
2. `event_name` (one of required names)
3. `user_id` (nullable when automated)
4. `session_id` (nullable during pre-session setup)
5. `sandbox_id` (nullable for pre-provisioning errors)
6. `runtime_id` (nullable until runtime record exists)
7. `event_payload` (JSONB)
8. `created_at` (UTC)

## Example Row

```json
{
  "event_id": "evt_01JT8D0FTF1GWKSNMMTBSKB0QH",
  "event_name": "pr_create",
  "user_id": 42,
  "session_id": 9001,
  "sandbox_id": "sbx_01JT8BKHGCE4A5T8G7V6P2M0A3",
  "runtime_id": 112,
  "event_payload": {
    "pr_number": 102,
    "pr_url": "https://github.com/octocat/yudaiv3/pull/102",
    "repo": "octocat/yudaiv3"
  },
  "created_at": "2026-02-21T15:41:00Z"
}
```

