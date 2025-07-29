# Architect Agent: Backend & DB State Flow for Issue Creation

## State Flow: User Issue to GitHub Issue

1. **Chat Interaction**
   - User sends a message via chat (frontend → `/chat/daifu` in `chat_api.py`).
   - Message is stored as a `ChatMessage` in the database.
   - DAifu agent (LLM) generates a reply, which is also stored.

2. **User Issue Creation**
   - User (or agent) initiates issue creation from chat or context (e.g., `/chat/create-issue` or `/issues/create-with-context`).
   - Backend calls `IssueService.create_user_issue` or `create_issue_from_chat`.
   - A new `UserIssue` is created in the DB with status `pending`.
   - Context (chat, files, etc.) is attached to the issue.

3. **GitHub Issue Preview (Architect Agent)**
   - Architect agent (LLM) is invoked via `generate_github_issue_preview`.
   - Generates a draft GitHub issue (title, body, labels, etc.) from the context.
   - Preview is returned to the user/agent for review (not yet in GitHub).

4. **Final GitHub Issue Creation**
   - On approval, `/issues/{issue_id}/create-github-issue` is called.
   - Backend calls `IssueService.create_github_issue_from_user_issue`:
     - Fetches the `UserIssue` from DB.
     - Calls GitHub API to create the issue.
     - Updates the `UserIssue` in DB:
       - Sets `github_issue_url`, `github_issue_number`.
       - Updates status to `completed` (or `failed` on error).

5. **DB Consistency**
   - All state transitions are reflected in the DB.
   - The UI/backend can always query the latest state of any issue.

---

## Next Steps: Debugging & Extending GitHub Issue Creation

- **Debugging**
  - Ensure all DB updates are atomic and error-handled.
  - Add logging for all state transitions (pending → completed/failed).
  - Validate that architect agent's LLM output is correctly parsed and mapped to GitHub issue fields.
  - Test with diverse chat/file contexts to ensure robust issue generation.

- **Extending Functionality**
  - Allow user/agent to edit the GitHub issue preview before final creation.
  - Support additional GitHub fields (milestones, projects, etc.).
  - Add more granular status tracking (e.g., "awaiting approval", "in review").
  - Integrate GitHub webhooks to update status if the issue is closed/updated externally.
  - Add UI/endpoint for re-trying failed GitHub issue creations.

---

**Note:**
- The final output is a GitHub issue (as defined by `GitHubIssue` in `models.py`), and the corresponding `UserIssue` in the DB is updated with the GitHub issue info and status.
- The architect agent is responsible for generating the high-quality issue content from context, and the backend ensures state consistency throughout the flow.
