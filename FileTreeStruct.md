# File Tree Structure Implementation Guide

## Goal
Deliver a repository-aware tree view inside `FileDependencies.tsx` that visualizes directories, files, functions, and classes by reusing the GitHub context cache that `session_routes.py` already maintains. The backend must expose that cached structure through a dedicated endpoint, and the frontend must consume it without introducing new files—only `session_routes.py` and `FileDependencies.tsx` contain implementation logic.

## High-Level Flow
- The background repository indexing task builds or refreshes the GitHub context cache (stored on the `Repository.github_context` column and on disk via `LLMService`).
- A new FastAPI handler in `session_routes.py` reads the cached GitHub context, extracts or rebuilds the tree via existing helpers, and returns a normalized tree payload.
- `FileDependencies.tsx` requests that endpoint, maps the tree payload into a lightweight React tree, and renders expand/collapse UI alongside existing dependency information.

## Scope Constraints
- ✅ Touch only `backend/daifuUserAgent/session_routes.py` and `src/components/FileDependencies.tsx`.
- ✅ Keep implementation local to those files; do not create additional service or utility modules.
- ✅ Reuse existing logic such as `_build_file_tree`, `_index_repository_for_session_background`, `SessionService.ensure_owned_session`, and `LLMService.read_github_context_cache`.
- ✅ Final UI lives inside `FileDependencies.tsx` (no separate component file).

---

## Backend Plan — `backend/daifuUserAgent/session_routes.py`

### Step 1 — Enrich Cached Context During Indexing (`_index_repository_for_session_background`)
- **Task 1.1**: After `files_data` is fetched, call `_build_file_tree(files_payload, repo_name)` to derive the hierarchical structure. `_build_file_tree` already exists; ensure it accepts the GitIngest snapshot data (`RepositoryFile` objects or dicts).
- **Task 1.2**: Consolidate the returned tree into a serializable dict (e.g., `{ "file_tree": tree, "summaries": ... }`). Store it under `repo_context` for the `ChatSession` (e.g., `chat_session.repo_context["file_tree"]`).
- **Task 1.3**: Merge or append the same tree into the repository’s GitHub context cache: read any existing `Repository.github_context`, add/replace a `file_tree` key, and persist (`db.commit()`). This keeps DB + cache aligned for the new endpoint.
- **Task 1.4**: When the cache path metadata exists (`repository.github_context`), load the JSON payload from disk via `LLMService.read_github_context_cache`, merge the tree, and rewrite metadata with `LLMService.write_github_context_cache` so the on-disk cache stays in sync.

### Step 2 — Helper To Load Tree From Cache (`_load_cached_file_tree`)
- **Task 2.1**: Implement a private helper near `_build_file_tree` that:
  - Accepts `db`, `Repository`, and `ChatSession` references.
  - Checks, in order: `chat_session.repo_context.get("file_tree")`, `repository.github_context.get("file_tree")`, and the disk cache via `LLMService.read_github_context_cache(repository.github_context)`.
  - Falls back to regenerating the tree from `FileItem` rows (via existing `_build_file_tree` applied over `FileItem` serialization) if caches are empty.
- **Task 2.2**: Normalize the tree response to a consistent structure with `id`, `name`, `path`, `type`, `tokens`, `isDirectory`, `children`, `functions`, and `classes` arrays (use existing metadata when available; default gracefully when missing).
- **Task 2.3**: Return both the tree and summary metadata (`totalFiles`, `totalDirectories`, etc.) so the endpoint response is self-contained.

### Step 3 — Public Endpoint (`get_session_file_tree_from_cache`)
- **Task 3.1**: Add `@router.get("/sessions/{session_id}/file-deps/tree", response_model=dict)`.
- **Task 3.2**: Reuse `SessionService.ensure_owned_session` to authorize, then locate the associated `Repository` row for the session owner/repo.
- **Task 3.3**: Call `_load_cached_file_tree` and return the payload. Include flags like `"source": "github_context_cache"` or `"source": "database_fallback"` for observability.
- **Task 3.4**: Provide coherent error handling: 404 if no session/repository, 503 if cache refresh is in progress, and 500 for unexpected errors (using `create_standardized_error`). Log cache misses and regeneration steps for traceability.

### Step 4 — Optional Refresh Hook (same file, minimal logic)
- **Task 4.1**: Accept an optional `refresh=true` query param on the new endpoint. When present, trigger `ensure_github_context` (imported from `.services.context_utils`) to refresh cache before returning.
- **Task 4.2**: Guard the refresh with debounce/lock semantics using an in-memory `asyncio.Lock` stored at module scope to prevent concurrent expensive refreshes.

---

## Frontend Plan — `src/components/FileDependencies.tsx`

### Step 1 — Data Wiring
- **Task 1.1**: Extend the existing data fetch logic to hit `/sessions/{session_id}/file-deps/tree`. Prefer the existing React Query hook or instantiate a new query key (`['session-file-tree', sessionId]`) inside this file.
- **Task 1.2**: Update local TypeScript types to represent tree nodes and metadata (`FileTreeNode`, `FileTreeMeta`). Reuse existing `FileItem` fields where possible to avoid duplication.

### Step 2 — UI State & Controls
- **Task 2.1**: Introduce component state to track expanded nodes (`Set<string>`). Provide handlers for toggling directories.
- **Task 2.2**: Offer a simple toolbar with a refresh button (calls the query with `refresh=true`) and a toggle between “List” (current view) and “Tree” if the legacy list must remain accessible. Keep all JSX inside this file.

### Step 3 — Tree Rendering
- **Task 3.1**: Implement a small recursive renderer (`renderNode`) within the file. It should:
  - Render directories with chevrons and call `toggleNode` on click.
  - Render files with optional badges (tokens, type) and reveal nested functions/classes if provided by the backend payload.
- **Task 3.2**: Keep styling consistent with existing component patterns (Tailwind classes already used elsewhere in the file).
- **Task 3.3**: Show loading, empty, and error states using the existing design tokens.

### Step 4 — Function/Class Overlay
- **Task 4.1**: When the backend tree includes `functions` or `classes`, render them as nested bullet items beneath the file node with subtle indentation.
- **Task 4.2**: Provide optional filters (e.g., search field) reusing existing handlers if available; otherwise, add a debounced local filter inside this file only if time allows.

### Step 5 — Integration Clean-up
- **Task 5.1**: Remove or repurpose obsolete list-specific helpers if they are no longer needed, ensuring the file stays lean.
- **Task 5.2**: Confirm that props expected by parent components remain unchanged; if new data is required (e.g., sessionId), retrieve it from existing hooks/context rather than changing the component API.

---

## Data Contract
- **Request**: `GET /sessions/{session_id}/file-deps/tree[?refresh=true]`
- **Response**:
  ```json
  {
    "source": "github_context_cache",
    "generatedAt": "ISO timestamp",
    "summary": {
      "totalFiles": 120,
      "totalDirectories": 24,
      "totalTokens": 54000,
      "maxDepth": 8
    },
    "tree": [
      {
        "id": "src",
        "name": "src",
        "path": "src",
        "type": "directory",
        "tokens": 12000,
        "isDirectory": true,
        "children": [
          {
            "id": "src/components/FileDependencies.tsx",
            "name": "FileDependencies.tsx",
            "path": "src/components/FileDependencies.tsx",
            "type": "file",
            "tokens": 900,
            "isDirectory": false,
            "functions": ["FileDependencies"],
            "classes": []
          }
        ]
      }
    ]
  }
  ```
- **Fallback**: When cache is missing, `source` shifts to `database_fallback` and `tree` stems from serialized `FileItem` rows.

---

## Testing Matrix
- **Backend**
  - Hit `/sessions/{session_id}/file-deps/tree` with existing cache → expect HTTP 200 + `source=github_context_cache`.
  - Hit with `refresh=true` to ensure cache regeneration path works.
  - Delete/rename cache file temporarily → expect graceful fallback and `source=database_fallback`.
- **Frontend**
  - Verify loading/error UI.
  - Expand/collapse directories; ensure state persists across rerenders.
  - Refresh button triggers re-fetch and updates tree.
  - Validate functions/classes nesting renders when provided.

---

## Future Enhancements (Out of Scope)
- Streaming tree updates via WebSocket during long-running indexing.
- Virtualized rendering for huge repositories.
- Persisting expand/collapse state per user session on the backend.
- Visual dependency graphs beyond the hierarchical tree.
