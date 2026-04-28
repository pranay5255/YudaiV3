# Workflow State Review Follow-Up

Last updated: 2026-04-28

GitHub tracker: `#191` - Fix workflow state and execution objective regressions.

## Summary

A review of the current session/workbench patch found three P2 regressions that should be fixed before the patch is considered correct. They affect normal workflow issue selection, workflow context updates, and pipeline start requests.

## Findings

| Finding | Area | Files | Fix direction |
| --- | --- | --- | --- |
| Partial workflow context updates clear saved affected systems | Backend/session | `backend/yudai/daifuUserAgent/session_actions.py` | Use `exclude_unset=True` or `model_fields_set` so omitted fields are not treated as clears. |
| Selecting an issue without `html_url` can keep a stale issue URL | Backend/session | `backend/yudai/daifuUserAgent/session_actions.py` | Assign, infer, or clear `architect_issue_url` on every issue selection. |
| Long issue bodies can exceed `ExecutionRequest.objective` limit | Frontend/workbench | `src/components/AgentWorkbench.tsx` | Truncate or summarize the issue body before calling `startExecution`. |

## Acceptance Criteria

- Partial `workflow.context.update` requests preserve existing `affected_systems` unless the client explicitly clears them.
- Selecting issue B without `html_url` cannot leave `architect_issue_url` pointed at issue A.
- `buildExecutionObjective()` cannot produce a payload that exceeds the backend 10,000-character objective limit.
- Backend tests cover partial context update behavior and issue selection URL clearing.
- Frontend tests cover long issue body truncation before execution start.

## Backlog Mapping

- `#191`: Dedicated bug tracker for these review findings.
- `#179`: Related backend/session umbrella.
- `#182`: Related frontend runtime UX umbrella.
