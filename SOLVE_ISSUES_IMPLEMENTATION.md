# Solve Issues Implementation Guide

**Status**: Partially Implemented
**Version**: 1.0.0
**Last Updated**: January 2026

## Overview

The Solve Issues feature enables users to automatically solve GitHub issues using AI-powered agents running in E2B sandboxes. The system:
1. Creates issues with full conversation and file context
2. Launches mini-swe-agent in isolated E2B containers
3. Monitors progress in real-time
4. Generates pull requests with fixes
5. Tracks costs, iterations, and results

---

## Current Implementation Status

### ✅ Implemented
- **Backend Infrastructure**:
  - Solver API router included in `session_routes.py` (line 127)
  - E2B sandbox executor (`solver/sandbox.py`)
  - HeadlessSandboxExecutor with full lifecycle management
  - TFBD config generation (`solver/manager.py`)
  - Agent script generation (`solver/agentScriptGen.py`)
  - Demo scripts proving E2B integration works

- **Database**:
  - `Solve` table for solve sessions
  - `SolveRun` table for individual agent runs
  - `Issue` table for GitHub issues
  - Trajectory storage via JSONB + file paths

- **API Endpoints**:
  - `GET /github/repositories/{owner}/{repo}/issues` - Fetch issues
  - `GET /ai-models` - List available models
  - Solver router endpoints (need verification)

### ❌ Missing
- **Frontend Components**:
  - SolveConfigModal (configuration UI)
  - SolveProgressModal (real-time monitoring)
  - "Solve This Issue" button integration
  - Session store methods for solve operations

- **Integration Layer**:
  - Bridge between user issue creation → solve trigger
  - Workflow to prepare HeadlessSandboxRequest from issue data
  - Status polling implementation
  - Error handling and retry logic

---

## Architecture

### Data Flow: Issue Creation → Solve → PR

```
1. User creates issue in chat
   ↓
2. Issue saved to user_issues table with context
   ↓
3. Optional: Create GitHub issue
   ↓
4. User clicks "Solve This Issue"
   ↓
5. SolveConfigModal opens (AI model, small_change, best_effort, etc.)
   ↓
6. POST /sessions/{session_id}/solve/start
   ↓
7. Backend workflow:
   - Fetch Issue (get GitHub URL, repo info)
   - Fetch Repository (owner, name, branch, clone_url)
   - Fetch AIModel (get model_id like "anthropic/claude-4.5")
   - Create Solve record (status: PENDING)
   - Create SolveRun record(s)
   - Build HeadlessSandboxRequest
   - Launch async: HeadlessSandboxExecutor.run()
   - Update Solve (status: RUNNING)
   - Return solve_session_id
   ↓
8. Frontend opens SolveProgressModal
   ↓
9. Poll GET /solve/status/{solve_id} every 3s
   ↓
10. E2B sandbox workflow (async):
    - Create E2B sandbox (~30-60s)
    - Install mini-swe-agent
    - Clone repository
    - Generate TFBD config + agent script
    - Execute agent (5-30 minutes)
    - Agent: reads issue → analyzes code → makes changes → runs tests → creates PR
    - Capture output, trajectory, PR URL
    - Update SolveRun (status: COMPLETED, pr_url, trajectory_data)
    - Update Solve (status: COMPLETED, champion_run_id)
    - Cleanup sandbox
    ↓
11. Frontend displays completion:
    - Champion run highlighted
    - PR URL clickable
    - Cost and metrics shown
```

### Database Schema

```sql
-- Core relationships
User
 └─ ChatSession
     ├─ UserIssue (user-created issue with context)
     │   └─ Issue (GitHub issue record)
     │       └─ Repository
     └─ Solve (solve session)
         ├─ SolveRun[] (individual executions)
         │   ├─ model: string (e.g., "anthropic/claude-4.5")
         │   ├─ status: PENDING | RUNNING | COMPLETED | FAILED
         │   ├─ pr_url: string
         │   ├─ trajectory_data: JSONB
         │   ├─ error_message: string
         │   └─ timestamps
         └─ champion_run_id: int (best result)
```

---

## API Reference

### 1. Start Solve Session
```http
POST /daifu/sessions/{session_id}/solve/start
```

**Request**:
```json
{
  "issue_id": 123,                    // Database issue ID (not GitHub number)
  "ai_model_id": 5,                   // AIModel.id
  "repo_url": "https://github.com/owner/repo",
  "branch_name": "main",              // Optional, default: "main"
  "small_change": false,              // Limit to minimal changes
  "best_effort": false,               // Continue if tests fail
  "max_iterations": 50,               // Max agent iterations
  "max_cost": 10.0                    // Max cost in USD
}
```

**Response**:
```json
{
  "solve_session_id": "solve_abc123",
  "status": "PENDING"
}
```

### 2. Get Solve Status
```http
GET /daifu/sessions/{session_id}/solve/status/{solve_id}
```

**Response**:
```json
{
  "solve_session_id": "solve_abc123",
  "status": "RUNNING",
  "progress": {
    "runs_total": 1,
    "runs_completed": 0,
    "runs_failed": 0,
    "runs_running": 1,
    "last_update": "2026-01-28T10:30:00Z",
    "message": "Agent analyzing codebase..."
  },
  "runs": [
    {
      "id": "run_xyz789",
      "model": "anthropic/claude-sonnet-4-5",
      "status": "RUNNING",
      "started_at": "2026-01-28T10:25:00Z",
      "completed_at": null,
      "pr_url": null,
      "error_message": null
    }
  ],
  "champion_run": null,
  "error_message": null
}
```

### 3. Cancel Solve
```http
POST /daifu/sessions/{session_id}/solve/cancel/{solve_id}
```

**Response**:
```json
{
  "success": true,
  "message": "Solve session cancelled"
}
```

### 4. Get Available AI Models
```http
GET /daifu/ai-models
```

**Response**:
```json
[
  {
    "id": 1,
    "name": "Claude Sonnet 4.5",
    "provider": "anthropic",
    "model_id": "anthropic/claude-sonnet-4-5-20250929",
    "description": "Most capable model for complex reasoning"
  },
  {
    "id": 2,
    "name": "DeepSeek V3.2",
    "provider": "deepseek",
    "model_id": "deepseek/deepseek-v3.2-exp",
    "description": "Fast and cost-effective"
  }
]
```

### 5. Fetch Repository Issues
```http
GET /daifu/github/repositories/{owner}/{repo}/issues
```

**Response**:
```json
[
  {
    "id": 123,                       // Database ID (use this for solving)
    "number": 45,                    // GitHub issue number
    "title": "Fix authentication bug",
    "body": "Users can't login with...",
    "state": "open",
    "html_url": "https://github.com/owner/repo/issues/45",
    "labels": ["bug", "chat-generated"],
    "comments": 2,
    "created_at": "2026-01-20T12:00:00Z",
    "updated_at": "2026-01-28T09:00:00Z"
  }
]
```

---

## Implementation Plan

### Phase 1: Backend Verification (Priority: HIGH)

**Files to verify**:
- `backend/solver/solver.py` - Confirm router endpoints exist
- `backend/models.py` - Verify StartSolveRequest model

**Required Logic** (`backend/solver/workflow.py` - new file):
```python
async def prepare_solve_from_issue(
    db: Session,
    issue_id: int,
    ai_model_id: int,
    config: dict
) -> HeadlessSandboxRequest:
    """
    Build HeadlessSandboxRequest from issue data

    Steps:
    1. Fetch Issue (get html_url, repository_id)
    2. Fetch Repository (get clone_url, owner, name, branch)
    3. Fetch AIModel (get model_id string)
    4. Return HeadlessSandboxRequest
    """
    pass

async def start_solve_session(
    db: Session,
    session_id: str,
    user_id: int,
    request: StartSolveRequest
) -> dict:
    """
    Orchestrate solve session start

    Steps:
    1. Validate user owns session
    2. Create Solve record (status: PENDING)
    3. Create SolveRun record(s)
    4. Prepare HeadlessSandboxRequest
    5. Launch background task: HeadlessSandboxExecutor.run()
    6. Update Solve (status: RUNNING)
    7. Return solve_session_id
    """
    pass

async def get_solve_status(
    db: Session,
    solve_session_id: str,
    user_id: int
) -> dict:
    """
    Query solve status and progress

    Steps:
    1. Fetch Solve record
    2. Fetch all SolveRun records
    3. Calculate progress metrics
    4. Determine champion run
    5. Return structured status
    """
    pass
```

**Checklist**:
- [ ] Verify solver router is properly mounted
- [ ] Test `/solve/start` endpoint with demo data
- [ ] Test `/solve/status` endpoint returns correct format
- [ ] Confirm HeadlessSandboxExecutor integration works
- [ ] Add workflow functions to bridge issue → sandbox

### Phase 2: Frontend Components (Priority: HIGH)

#### 2.1 SolveConfigModal Component
**File**: `src/components/SolveConfigModal.tsx` (new)

**Props**:
```typescript
interface SolveConfigModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStartSolve: (config: SolveConfig) => Promise<void>;
  issueId: string;
  repositoryInfo: {
    owner: string;
    name: string;
    branch: string;
  };
}

interface SolveConfig {
  ai_model_id: number;
  small_change: boolean;
  best_effort: boolean;
  max_iterations: number;
  max_cost: number;
}
```

**UI Elements**:
- AI Model dropdown (fetched from `/ai-models`)
- Small Change checkbox
- Best Effort checkbox
- Max Iterations slider (10-100, default: 50)
- Max Cost slider ($1-$50, default: $10)
- Cancel + Start Solve buttons

#### 2.2 SolveProgressModal Component
**File**: `src/components/SolveProgressModal.tsx` (new)

**Props**:
```typescript
interface SolveProgressModalProps {
  isOpen: boolean;
  onClose: () => void;
  solveSessionId: string;
  sessionId: string;
}
```

**Features**:
- Poll status every 3 seconds via `GET /solve/status/{solve_id}`
- Display overall status with animation
- Show progress bar and metrics
- List all runs with individual status
- Highlight champion run when complete
- Show PR URL as clickable link
- Cancel button (calls cancel endpoint)
- Auto-stop polling when status is terminal (COMPLETED/FAILED/CANCELLED)

#### 2.3 Integrate into DiffModal
**File**: `src/components/DiffModal.tsx`

**Changes**:
1. Add "Solve This Issue" button next to "Create GitHub Issue"
2. Show button only when:
   - Issue has been created (userIssue exists)
   - Repository info is available
3. Add state for solve configuration modal
4. Wire up solve trigger:
   ```typescript
   const handleStartSolve = async (config: SolveConfig) => {
     const solveSessionId = await startSolveSession(issueId, config);
     setShowSolveProgress(true);
     setActiveSolveId(solveSessionId);
   };
   ```

#### 2.4 Session Store Methods
**File**: `src/stores/sessionStore.ts`

**New methods**:
```typescript
// Fetch available AI models
getAvailableAiModels: async () => Promise<AIModel[]>

// Start solve session
startSolveSession: async (
  issueId: string,
  config: SolveConfig
) => Promise<{ solve_session_id: string }>

// Get solve status (for polling)
getSolveStatus: async (
  solveSessionId: string
) => Promise<SolveStatusResponse>

// Cancel solve
cancelSolve: async (
  solveSessionId: string
) => Promise<{ success: boolean }>
```

**Checklist**:
- [ ] Create SolveConfigModal component
- [ ] Create SolveProgressModal component
- [ ] Add "Solve This Issue" button to DiffModal
- [ ] Add session store methods
- [ ] Wire up solve trigger flow
- [ ] Test end-to-end: create issue → configure → monitor → view PR

### Phase 3: E2B Sandbox Management (Priority: MEDIUM)

**Background Task Implementation**:

```python
# In backend/solver/solver.py or background_tasks.py

async def execute_solve_in_sandbox(
    db: Session,
    solve_id: int,
    solve_run_id: int,
    request: HeadlessSandboxRequest
):
    """
    Background task that runs the actual solve

    Steps:
    1. Update SolveRun status: RUNNING
    2. Call HeadlessSandboxExecutor.run(request)
    3. Wait for completion (5-30 minutes)
    4. Parse result:
       - Extract PR URL from output
       - Save trajectory to file
       - Store trajectory metadata
    5. Update SolveRun:
       - status: COMPLETED or FAILED
       - pr_url: extracted URL
       - trajectory_data: { local_path, metadata }
       - error_message: if failed
    6. Update Solve:
       - Recalculate overall status
       - Set champion_run_id if all complete
    7. Handle errors gracefully
    """
    try:
        result = await HeadlessSandboxExecutor().run(request)

        # Save trajectory file
        trajectory_path = save_trajectory(
            solve_id, solve_run_id, result.trajectory_file
        )

        # Update database
        solve_run = db.query(SolveRun).get(solve_run_id)
        solve_run.status = "COMPLETED" if result.exit_code == 0 else "FAILED"
        solve_run.pr_url = result.pr_url
        solve_run.trajectory_data = {
            "local_path": str(trajectory_path),
            "metadata": result.trajectory_metadata
        }
        solve_run.completed_at = utc_now()

        # Update parent Solve
        update_solve_status(db, solve_id)

        db.commit()

    except Exception as e:
        # Mark as failed
        solve_run = db.query(SolveRun).get(solve_run_id)
        solve_run.status = "FAILED"
        solve_run.error_message = str(e)
        db.commit()
```

**Checklist**:
- [ ] Implement background task execution
- [ ] Add trajectory file saving logic
- [ ] Implement champion run selection algorithm
- [ ] Add sandbox cleanup on failure
- [ ] Test concurrent solves (respect SOLVER_MAX_PARALLEL)

### Phase 4: Error Handling & Polish (Priority: LOW)

**Backend Error Scenarios**:
- [ ] E2B API key missing → return 500 with clear message
- [ ] Sandbox creation fails → retry once, then fail gracefully
- [ ] Repository clone fails → capture logs, return error
- [ ] Agent exceeds cost limit → stop execution, mark as FAILED
- [ ] Agent timeout → cleanup sandbox, save partial trajectory
- [ ] Concurrent solve limit reached → return 429 with retry-after

**Frontend Error Scenarios**:
- [ ] API call fails → show error banner in modal
- [ ] Polling fails → exponential backoff, max 3 retries
- [ ] User closes modal → keep polling in background, show notification
- [ ] Solve fails → display error, offer to view logs
- [ ] No AI models available → disable solve button with tooltip

---

## Configuration

### Environment Variables

**Backend** (`.env`):
```bash
# Required
OPENROUTER_API_KEY=sk-or-...              # For AI model access
E2B_API_KEY=e2b_...                       # For sandbox creation
GITHUB_TOKEN=ghp_...                      # For repo access
DATABASE_URL=postgresql://...

# Solver Configuration
SOLVER_MAX_PARALLEL=3                     # Max concurrent solves
SOLVER_TIME_BUDGET_SECONDS=5400           # 90 minutes timeout
SOLVER_DEFAULT_MODEL=deepseek/deepseek-v3.2-exp
SOLVER_ENABLE_TRAJECTORY_STORAGE=true
```

### Frontend Configuration

**File**: `src/config/solver.ts` (new)
```typescript
export const SOLVER_CONFIG = {
  POLL_INTERVAL_MS: 3000,              // Poll status every 3s
  MAX_POLL_RETRIES: 3,                 // Max failed polls before error
  DEFAULT_MAX_ITERATIONS: 50,
  DEFAULT_MAX_COST: 10.0,
  COST_SLIDER_RANGE: [1, 50] as const,
  ITERATIONS_SLIDER_RANGE: [10, 100] as const,
};
```

---

## TFBD Configuration Options

### Small Change Mode
```yaml
agent:
  max_iterations: 20          # Reduced from 50
  max_cost: 5.0              # Reduced from 10.0
  instructions: |
    Limit code edits to minimal, targeted changes directly tied to the issue.
```

### Best Effort Mode
```yaml
agent:
  mode: "best_effort"        # Continue even if tests fail
  instructions: |
    Continue working toward a solution even if automated checks fail,
    documenting any failures.
```

### Standard Mode (Default)
```yaml
agent:
  mode: "yolo"
  max_iterations: 50
  max_cost: 10.0

model:
  model_name: "anthropic/claude-sonnet-4-5-20250929"
  model_class: "openrouter"
  model_kwargs:
    temperature: 0.4
```

---

## Testing Strategy

### Backend Tests
```bash
# Unit tests
pytest backend/tests/test_solver_workflow.py
pytest backend/tests/test_tfbd_generation.py

# Integration tests
pytest backend/tests/integration/test_solve_api.py
pytest backend/tests/integration/test_e2b_sandbox.py
```

**Test scenarios**:
- [ ] Create solve from issue data
- [ ] TFBD config generation with various parameters
- [ ] Solve status polling and aggregation
- [ ] Trajectory parsing and storage
- [ ] Concurrent solve execution
- [ ] Solve cancellation
- [ ] Error handling (missing keys, sandbox failures)

### Frontend Tests
```bash
npm run test src/components/SolveConfigModal.test.tsx
npm run test src/components/SolveProgressModal.test.tsx
```

**Test scenarios**:
- [ ] Modal renders and validates input
- [ ] AI models dropdown populates
- [ ] Solve config validation
- [ ] Progress polling updates UI
- [ ] Error states display properly
- [ ] Cancel button works

### E2E Test
```bash
# Manual test flow
1. Create issue in chat
2. Click "Solve This Issue"
3. Configure solver
4. Monitor progress
5. Verify PR created
6. Check trajectory saved
```

---

## Troubleshooting

### Solve Not Starting
**Symptoms**: POST /solve/start returns 500 or 404

**Debug steps**:
1. Check backend logs: `tail -f backend/logs/app.log`
2. Verify issue exists: `psql -d yudai -c "SELECT * FROM issues WHERE id = <issue_id>"`
3. Verify AI model exists: `psql -d yudai -c "SELECT * FROM ai_models WHERE id = <model_id>"`
4. Check OPENROUTER_API_KEY is set: `echo $OPENROUTER_API_KEY`
5. Check E2B_API_KEY is set: `echo $E2B_API_KEY`

### Sandbox Creation Fails
**Symptoms**: Status stuck on PENDING, logs show E2B errors

**Debug steps**:
1. Verify E2B API key: `curl -H "Authorization: Bearer $E2B_API_KEY" https://api.e2b.dev/sandboxes`
2. Check E2B quota/limits in dashboard
3. Review sandbox creation logs in backend
4. Try manual sandbox creation: `python backend/solver/e2b_standalone_demo.py`

### Progress Not Updating
**Symptoms**: Frontend shows stale status

**Debug steps**:
1. Open browser console, check for network errors
2. Verify polling is active (should see requests every 3s)
3. Check backend returns valid JSON: `curl http://localhost:8000/daifu/sessions/{session_id}/solve/status/{solve_id}`
4. Check database: `psql -d yudai -c "SELECT * FROM solves WHERE id = <solve_id>"`

### Agent Fails to Create PR
**Symptoms**: Status COMPLETED but no pr_url

**Debug steps**:
1. Check trajectory file for errors
2. Verify GITHUB_TOKEN has push permissions
3. Check agent output logs: Look in trajectory data → stdout/stderr
4. Check repository settings (branch protection, required reviews)

---

## Critical Implementation Checklist

### Backend (Must-Have)
- [ ] Verify `/solve/start` endpoint exists and works
- [ ] Verify `/solve/status` endpoint returns correct format
- [ ] Implement `prepare_solve_from_issue()` workflow function
- [ ] Implement background task for sandbox execution
- [ ] Add trajectory file saving logic
- [ ] Test E2B integration end-to-end

### Frontend (Must-Have)
- [ ] Create SolveConfigModal component
- [ ] Create SolveProgressModal component
- [ ] Add "Solve This Issue" button to DiffModal
- [ ] Add session store methods (startSolve, getStatus, cancel)
- [ ] Wire up solve trigger flow
- [ ] Implement status polling with 3s interval

### Testing (Must-Have)
- [ ] Test solve creation with real issue
- [ ] Test sandbox execution with demo script
- [ ] Test status polling updates UI correctly
- [ ] Test PR URL appears when complete
- [ ] Test error scenarios (missing keys, failures)

### Nice-to-Have (Post-MVP)
- [ ] Solve history viewer
- [ ] Batch solving (multiple issues)
- [ ] Custom TFBD templates
- [ ] Cost tracking dashboard
- [ ] Email notifications when complete
- [ ] Trajectory diff viewer

---

## File Changes Required

### New Files
1. `backend/solver/workflow.py` - Workflow orchestration functions
2. `src/components/SolveConfigModal.tsx` - Configuration UI
3. `src/components/SolveProgressModal.tsx` - Progress monitoring UI
4. `src/config/solver.ts` - Frontend configuration
5. `backend/tests/test_solver_workflow.py` - Unit tests
6. `src/components/SolveConfigModal.test.tsx` - Component tests

### Files to Modify
1. `src/components/DiffModal.tsx` - Add solve button and trigger
2. `src/stores/sessionStore.ts` - Add solve-related methods
3. `backend/solver/solver.py` - Verify/enhance endpoints
4. `backend/models.py` - Verify StartSolveRequest model
5. `src/types/api.ts` - Add SolveConfig and SolveStatus types

---

## Future Enhancements

1. **Solve History**: View past solves for comparison and learning
2. **Batch Solving**: Solve multiple issues simultaneously with queue management
3. **Custom Templates**: Save and reuse TFBD configuration templates
4. **Cost Tracking**: Dashboard showing cumulative costs, cost per issue, ROI metrics
5. **Notifications**: Email/Slack alerts when solve completes
6. **Advanced Filters**: Filter issues by label, assignee, date range, complexity
7. **Trajectory Diff Viewer**: Side-by-side comparison of multiple solve attempts
8. **Auto-merge**: Automatically merge successful PRs with approval workflows
9. **Learning Mode**: Agent learns from failed solves and improves over time

---

**Implementation Date**: November 2025 - January 2026
**Status**: Integration Phase
**Next Steps**: Complete backend verification → Build frontend components → E2E testing
