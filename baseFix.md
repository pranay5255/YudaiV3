
## Concrete Fix Plan

### Chat response mismatch:

**Problem**: The `generate_response_with_history` method in `backend/daifuUserAgent/llm_service.py` is not properly configured to handle file contexts.

**Solution**:
1. Update `backend/daifuUserAgent/llm_service.py:174`:
   - Make `generate_response_with_history` a `@staticmethod`.
   - Add `file_contexts: List[str] | None` argument and pass it to `build_daifu_prompt(...)`.
   - Alternatively, build the prompt directly in `chat_in_session` and call `await LLMService.generate_response(prompt=...)`.

### Issue endpoints paths:

**Problem**: The issue endpoints in `backend/daifuUserAgent/session_routes.py` are using incorrect path patterns.

**Solution**:
Change all `@router.*("/{session_id}/...")` → `@router.*("/sessions/{session_id}/...")` for:
- Create with context (backend/daifuUserAgent/session_routes.py)
- List issues (backend/daifuUserAgent/session_routes.py)
- Create GitHub issue (backend/daifuUserAgent/session_routes.py)
- All solver routes (backend/daifuUserAgent/session_routes.py and companions)

### IssueOps token vs user_id:

**Problem**: The `_fetch_github_repo_context` method in `backend/daifuUserAgent/IssueOps.py` is not properly using the user_id parameter.

**Solution**:
Update `backend/daifuUserAgent/IssueOps.py:367` to pass `user_id` to `_fetch_github_repo_context`.

### Optional: Unify chat handling:

**Suggestion**: Have `chat_in_session` call `ChatOps.process_chat_message` and map its output to `ChatResponse` for a more unified chat handling approach.

## Performance Considerations

1. **Background Processing**: All solver operations run asynchronously
2. **Database Indexing**: Proper indexes on frequently queried fields
3. **Caching**: Cache solver configurations and model settings
4. **Monitoring**: Track solver performance and resource