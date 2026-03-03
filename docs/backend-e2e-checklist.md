# Backend E2E Checklist (Deployed Docker Backend)

Run script:

```bash
bash scripts/e2e/backend_e2e_suite.sh
```

Optional overrides:

```bash
COMPOSE_FILE=docker-compose.backend-only.yml \
REPO_OWNER=pranay5255 REPO_NAME=TrustlessLocalAgents REPO_BRANCH=main \
EMBED_REPO_OWNER=pranay5255 EMBED_REPO_NAME=picoclaw EMBED_REPO_BRANCH=main \
RUN_LLM_CHAT=0 \
bash scripts/e2e/backend_e2e_suite.sh
```

## Coverage Matrix

### Infrastructure and health
- `INF-001`: Docker Compose services are up and backend is healthy.
- `INF-002`: `GET /health`.
- `INF-003`: `GET /auth/health` with `oauth_configured=true`.

### Authentication
- `AUTH-001`: `gh auth token` available.
- `AUTH-002`: Seed backend `auth_tokens` for default user from GH token.
- `AUTH-003`: `GET /auth/api/user` returns authenticated user.
- `AUTH-004`: Invalid bearer token is rejected (`401`).

### GitHub integration
- `GH-001`: `GET /github/repositories`.
- `GH-002`: `GET /github/repositories/{owner}/{repo}/branches`.
- `GH-003`: `GET /daifu/github/repositories`.
- `GH-004`: `GET /daifu/github/repositories/{owner}/{repo}/issues`.
- `GH-005`: `GET /daifu/ai-models`.

### Session creation and modal/controller runtime provisioning
- `SES-001`: `POST /daifu/sessions`.
- `SES-002`: `GET /controller/sessions/{session_id}/runtime`.
- `SES-003`: `GET /controller/sandboxes/{sandbox_id}`.
- `SES-004`: `POST /controller/sandboxes/{sandbox_id}/resolve-tunnel`.

### Chat/session behavior
- `CHAT-001`: `POST /daifu/sessions/{session_id}/messages`.
- `CHAT-002`: `POST /daifu/sessions/{session_id}/messages/bulk`.
- `CHAT-003`: `GET /daifu/sessions/{session_id}/messages`.
- `CHAT-004`: `POST /daifu/sessions/{session_id}/context-cards`.
- `CHAT-005`: `GET /daifu/sessions/{session_id}/context-cards`.
- `CHAT-006`: `POST /daifu/sessions/{session_id}/conversation`.
- `CHAT-007`: `POST /daifu/sessions/{session_id}/chat` (optional; set `RUN_LLM_CHAT=1`).
- `CHAT-008`: `GET /daifu/sessions/{session_id}` context envelope.

### Embeddings and pgvector
- `EMB-001`: Create session with `index_codebase=true` and `generate_embeddings=true`.
- `EMB-002`: `file_items` populated for embedding session.
- `EMB-003`: `file_embeddings` populated for embedding session.
- `EMB-004`: pgvector extension exists (`pg_extension` contains `vector`).
- `EMB-005`: `file_embeddings.embedding` DB type is `vector`.
- `EMB-006`: `vector_dims(embedding)` is valid (`>0`).
- `EMB-007`: pgvector distance operator `<->` executes.
- `EMB-008`: `GET /daifu/sessions/{session_id}/file-deps/session` returns indexed files.

### Cleanup
- `CLN-001`: `DELETE /controller/sandboxes/{sandbox_id}` for primary session.
- `CLN-002`: `DELETE /controller/sandboxes/{sandbox_id}` for embedding session.

## Artifacts
- The suite writes a detailed markdown report to:
  - `logs/e2e/backend_e2e_report_<UTC timestamp>.md`
