# Sandbox Identity Canonicalization

Phase 0 canonical key format:

`<org>:<repo_owner>/<repo_name>:<environment>`

Example:

`yudai:octocat/yudaiv3:feature-realtime`

## Rules

1. Input sources:
   - `org`: internal org selected in authenticated session.
   - `repo_owner` + `repo_name`: GitHub repository owner/name.
   - `environment`: selected branch or explicit environment selector.
2. Normalization for each segment:
   - trim whitespace
   - lowercase
   - replace unsupported characters (`[^a-z0-9._-]`) with `-`
   - collapse duplicate `-`
   - strip leading/trailing `-`, `_`, `.`
3. Empty segments after normalization are rejected.
4. Branch normalization:
   - if missing, default to `main`.
   - normalized branch string is used as `environment`.
5. Repo normalization:
   - owner and name are normalized independently.
   - canonical repo string is `<owner>/<name>`.

## Reference Implementation

Code: `backend/config/realtime_identity.py`

Test coverage:
`backend/tests/test_realtime_identity.py`

