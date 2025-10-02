# Minimal File Tree Plan

Goal: expose a lightweight abstract syntax tree of the indexed repository and render it in React with the least possible moving parts. We only rely on four functions—two backend helpers, one FastAPI endpoint, and one frontend renderer.

---

## Function 1 — `_build_file_tree(files: Iterable[RepositoryFile]) -> List[FileTreeNode]`
- Input: iterable of GitIngest `RepositoryFile` objects or plain dicts.
- Output: flat list of `{ id, name, path, type, tokens, isDirectory, children? }` nodes.
- Implementation notes: reuse the existing helper in `session_routes.py`; keep the body small (group by path, attach children, nothing extra).

## Function 2 — `_get_file_tree_payload(db, chat_session, repository) -> Tuple[str, Dict[str, Any]]`
- Checks cached sources in order: `chat_session.repo_context`, `repository.github_context`, disk cache through `LLMService.read_github_context_cache`.
- Falls back to serializing `FileItem` rows only when caches are empty.
- Returns a `(source, payload)` pair where `payload = {"tree": [...], "generatedAt": iso_time}`.
- Lives next to `_build_file_tree` in `session_routes.py`; keep logic to a few guard clauses.

## Function 3 — `@router.get("/sessions/{session_id}/file-deps/tree")`
- Calls `SessionService.ensure_owned_session` for auth, looks up the related `Repository`, then delegates to `_get_file_tree_payload`.
- Response shape: `{ "source": source, **payload }`.
- No optional behaviours, no locks—just return whatever the cache yields.

## Function 4 — `renderFileTree(nodes: FileTreeNode[])` in `FileDependencies.tsx`
- A tiny recursive function that prints directories with a toggle and files with badges.
- Depends on existing component hooks for `sessionId`; no new hooks or providers.
- Keeps state minimal: one `Set<string>` for expanded node IDs and a `useEffect` to fetch via `fetch('/sessions/${sessionId}/file-deps/tree')`.

---

## Suggested Flow
1. Indexing (`_index_repository_for_session_background`) already calls `_build_file_tree` and stores the result in the cache; no extra work required.
2. The new helper `_get_file_tree_payload` reads those cached values.
3. The endpoint exposes that payload to the frontend.
4. `renderFileTree` renders the nodes inside `FileDependencies.tsx`.

This keeps the implementation focused and easy to iterate on when we add summaries, filters, or graph views later.
