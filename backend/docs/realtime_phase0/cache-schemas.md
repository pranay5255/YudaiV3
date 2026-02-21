# Sandbox Cache JSON Schemas

Cache root (inside sandbox):

`/home/yudai/.cache/`

## Files

1. Session cache JSON schema:
`backend/docs/realtime_phase0/schemas/session-cache.schema.json`
2. Artifact bundle metadata schema:
`backend/docs/realtime_phase0/schemas/artifact-bundle.schema.json`
3. Session cache sample:
`backend/docs/realtime_phase0/samples/session-cache.sample.json`
4. Artifact metadata sample:
`backend/docs/realtime_phase0/samples/artifact-bundle-metadata.sample.json`

## Write Strategy

1. Cache is append-only for message, solver, issue, and audit event arrays.
2. Export step snapshots the latest cache manifest to an artifact metadata row.
3. Controller stores metadata pointers/checksum in `session_artifacts`.

