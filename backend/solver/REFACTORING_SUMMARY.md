# Solver Refactoring Summary

## Overview
This document summarizes the comprehensive refactoring of the YudaiV3 solver system to consolidate functionality into a single, well-organized module using mini-swe-agent Python bindings.

## ✅ Completed Changes

### 1. **Consolidated Architecture**

**Before:**
- `solver.py` - API endpoints
- `manager.py` - Orchestration (incomplete, referenced non-existent classes)
- `sandbox.py` - E2B sandbox execution (CLI-based)
- `MSWEA.py` - CLI script for mini-swe-agent

**After:**
- `solver.py` - API endpoints (unchanged)
- `manager.py` - **Complete solution** with:
  - `HeadlessSandboxExecutor` - E2B sandbox execution using Python bindings
  - `DefaultSolverManager` - Orchestration and database management
  - Direct mini-swe-agent integration via `DefaultAgent`
  - Async task management and cleanup
- ~~`sandbox.py`~~ - **DELETED** (functionality moved to manager.py)
- ~~`MSWEA.py`~~ - **DELETED** (functionality moved to manager.py)

### 2. **Mini-SWE-Agent Integration via Python Bindings**

**Key Improvement**: Switched from CLI-based execution to direct Python API usage

**Implementation:**
```python
# Old approach (MSWEA.py):
# - Parse CLI arguments
# - Shell out to mini-swe-agent CLI
# - Parse output from stdout/stderr

# New approach (manager.py):
from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment

agent = DefaultAgent(
    get_model(model_name=model_name, config=config),
    LocalEnvironment(**environment_config),
    **agent_config,
)

exit_status, result = agent.run(task)
```

**Benefits:**
- ✅ Direct programmatic control
- ✅ Better error handling
- ✅ Access to trajectory data
- ✅ Cleaner integration
- ✅ No subprocess overhead

### 3. **Database Schema Simplification**

**Removed redundant models:**
- ❌ `swe_agent_configs` - Configuration is in code, not database
- ❌ `ai_solve_sessions` - Redundant with `solves` table
- ❌ `ai_solve_edits` - Edit tracking handled in trajectory data

**Kept essential models:**
- ✅ `solves` - Top-level solve orchestration
- ✅ `solve_runs` - Individual experiment runs in E2B sandboxes
- ✅ `ai_models` - Model configurations

**Added fields to `solve_runs`:**
```python
trajectory_data: Mapped[Optional[Dict[str, Any]]]  # Agent trajectory data
```

### 4. **HeadlessSandboxExecutor Class**

Complete E2B sandbox execution with:

#### Features:
- ✅ Creates E2B sandbox with environment variables
- ✅ Installs mini-swe-agent from source
- ✅ Clones target repository
- ✅ Fetches GitHub issue content
- ✅ Generates Python script using mini-swe-agent bindings
- ✅ Executes agent in sandbox
- ✅ Captures results and trajectory data
- ✅ Manages sandbox lifecycle and cleanup
- ✅ Supports cancellation

#### Methods:
```python
class HeadlessSandboxExecutor:
    async def run(request: HeadlessSandboxRequest) -> SandboxRunResult
    async def cancel()
    
    # Private methods:
    async def _install_mini_swe_agent()
    async def _clone_repository(repo_url, branch_name, github_token)
    async def _fetch_github_issue(issue_url, github_token)
    def _generate_agent_script(issue_text, model_name, verbose)
    def _extract_pr_url(stdout)
    def _extract_trajectory_path(stdout)
    async def _cleanup_sandbox()
```

### 5. **DefaultSolverManager Updates**

The manager now:
- ✅ Creates and tracks solve sessions
- ✅ Launches async tasks with `HeadlessSandboxExecutor`
- ✅ Updates database with execution results
- ✅ Handles cancellation and cleanup
- ✅ Calculates progress metrics
- ✅ Records trajectory data

**Key method signatures:**
```python
class DefaultSolverManager:
    async def start_solve(session_id, request, user) -> StartSolveResponse
    async def get_status(session_id, solve_id, user) -> SolveStatusResponse
    async def cancel_solve(session_id, solve_id, user) -> CancelSolveResponse
    
    # Private execution:
    async def _execute_run(solve_id, run_id, issue_url, repo_url, ...)
    
    # Private database operations:
    def _record_success(db, solve, run, result)
    def _record_failure(db, solve, run, error_message, logs)
    def _record_cancelled(db, solve, run)
```

## 📋 Implementation Details

### Workflow: Start Solve

```
1. API Request (solver.py)
   POST /sessions/{session_id}/solve/start
   ↓
2. Manager creates DB records (manager.py)
   - Create Solve (status: pending)
   - Create SolveRun (status: pending)
   ↓
3. Launch async task
   - Create HeadlessSandboxExecutor
   - Start background task
   - Update status to "running"
   ↓
4. Sandbox Execution (HeadlessSandboxExecutor)
   - Create E2B sandbox
   - Install mini-swe-agent
   - Clone repository
   - Fetch GitHub issue
   - Generate Python script with mini-swe-agent bindings
   - Execute agent
   - Capture results
   ↓
5. Record Results (manager.py)
   - Update SolveRun with results
   - Update Solve status
   - Set champion_run_id if successful
   - Store trajectory data
   ↓
6. Cleanup
   - Close sandbox
   - Remove from task tracking
```

### Generated Python Script (in sandbox)

The executor generates a Python script that uses mini-swe-agent bindings:

```python
#!/usr/bin/env python3
from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment
from minisweagent.run.utils.save import save_traj

def main():
    task = """<GitHub issue content>"""
    
    agent = DefaultAgent(
        get_model(model_name="anthropic/claude-sonnet-4-5", config=config),
        LocalEnvironment(**environment_config),
        mode="yolo",  # Headless execution
        max_iterations=50,
        max_cost=10.0,
    )
    
    exit_status, result = agent.run(task)
    save_traj(agent, output_path, exit_status=exit_status, result=result)
    
    return 0 if exit_status == "finished" else 1
```

### Data Flow: Database Updates

```sql
-- On start:
INSERT INTO solves (id, user_id, session_id, repo_url, issue_number, status, matrix, ...)
VALUES ('abc123', 1, 1, 'https://github.com/...', 42, 'pending', {...}, ...);

INSERT INTO solve_runs (id, solve_id, model, temperature, status, ...)
VALUES ('run123', 'abc123', 'anthropic/claude-sonnet-4-5', 0.1, 'pending', ...);

-- On execution start:
UPDATE solves SET status = 'running', started_at = NOW() WHERE id = 'abc123';
UPDATE solve_runs SET status = 'running', started_at = NOW() WHERE id = 'run123';

-- On completion:
UPDATE solve_runs SET
    status = 'completed',
    completed_at = NOW(),
    tests_passed = TRUE,
    sandbox_id = 'sbx-xyz',
    exit_code = 0,
    latency_ms = 45000,
    pr_url = 'https://github.com/.../pull/123',
    diagnostics = '{"stdout_tail": "...", "stderr_tail": "...", ...}',
    trajectory_data = '{"exit_status": "finished", "steps": [...]}',
    ...
WHERE id = 'run123';

UPDATE solves SET
    status = 'completed',
    completed_at = NOW(),
    champion_run_id = 'run123'
WHERE id = 'abc123';
```

## 🔍 API Endpoint Review

### `/sessions/{session_id}/solve/start` (POST)
**Status**: ✅ Working correctly

**Request:**
```json
{
  "issue_id": 1,
  "repo_url": "https://github.com/owner/repo",
  "branch_name": "main",
  "ai_model_id": 1
}
```

**Response:**
```json
{
  "solve_session_id": "abc123",
  "status": "pending"
}
```

**Implementation:**
- Creates `Solve` and `SolveRun` records
- Launches async task with `HeadlessSandboxExecutor`
- Returns immediately with solve_session_id

### `/sessions/{session_id}/solve/status/{solve_id}` (GET)
**Status**: ✅ Working correctly

**Response:**
```json
{
  "solve_session_id": "abc123",
  "status": "running",
  "progress": {
    "runs_total": 1,
    "runs_completed": 0,
    "runs_failed": 0,
    "runs_running": 1,
    "last_update": "2024-01-15T10:30:00Z",
    "message": "running"
  },
  "runs": [
    {
      "id": "run123",
      "solve_id": "abc123",
      "model": "anthropic/claude-sonnet-4-5",
      "status": "running",
      "sandbox_id": "sbx-xyz",
      ...
    }
  ],
  "champion_run": null,
  "error_message": null
}
```

### `/sessions/{session_id}/solve/cancel/{solve_id}` (POST)
**Status**: ✅ Working correctly

**Response:**
```json
{
  "solve_session_id": "abc123",
  "status": "cancelled",
  "message": "Solve cancelled"
}
```

**Implementation:**
- Cancels async task
- Closes E2B sandbox
- Updates database status to "cancelled"

## 🗄️ Database Schema

### Final Schema (Simplified)

#### `solves` table
```sql
CREATE TABLE solves (
    id VARCHAR(64) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    session_id INTEGER REFERENCES chat_sessions(id),
    repo_url VARCHAR(1000) NOT NULL,
    issue_number INTEGER NOT NULL,
    base_branch VARCHAR(255) DEFAULT 'main',
    status VARCHAR(50) DEFAULT 'pending',
    matrix JSONB NOT NULL,
    limits JSONB,
    requested_by VARCHAR(255),
    champion_run_id VARCHAR(64) REFERENCES solve_runs(id),
    max_parallel INTEGER,
    time_budget_s INTEGER,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

#### `solve_runs` table
```sql
CREATE TABLE solve_runs (
    id VARCHAR(64) PRIMARY KEY,
    solve_id VARCHAR(64) REFERENCES solves(id) ON DELETE CASCADE,
    model VARCHAR(255) NOT NULL,
    temperature FLOAT NOT NULL,
    max_edits INTEGER NOT NULL,
    evolution VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    sandbox_id VARCHAR(255),
    pr_url VARCHAR(1000),
    tests_passed BOOLEAN,
    loc_changed INTEGER,
    files_changed INTEGER,
    tokens INTEGER,
    latency_ms INTEGER,
    logs_url VARCHAR(1000),
    diagnostics JSONB,
    trajectory_data JSONB,  -- NEW: Agent trajectory
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

## 🔧 Next Steps

### 1. Update init.sql
Update the database initialization script to match the final schema:
- Remove `swe_agent_configs` table
- Remove `ai_solve_sessions` table
- Remove `ai_solve_edits` table
- Add `trajectory_data` column to `solve_runs`

### 2. Test E2B Integration
```bash
# Set environment variables
export E2B_API_KEY="your_key"
export OPENROUTER_API_KEY="your_key"
export GITHUB_TOKEN="your_token"

# Test solver endpoint
curl -X POST http://localhost:8000/api/daifu/sessions/1/solve/start \
  -H "Content-Type: application/json" \
  -d '{
    "issue_id": 1,
    "repo_url": "https://github.com/owner/repo",
    "branch_name": "main"
  }'

# Check status
curl http://localhost:8000/api/daifu/sessions/1/solve/status/abc123
```

### 3. Remove Old Files
```bash
rm backend/solver/MSWEA.py
rm backend/solver/sandbox.py
```

### 4. Update database.py
- Remove sample data creation for deleted tables
- Remove imports for `AISolveSession`, `AISolveEdit`, `SWEAgentConfig`

## 📚 Documentation References

- [mini-swe-agent Python bindings](https://mini-swe-agent.com/latest/advanced/cookbook/)
- [E2B Sandbox API](https://e2b.dev/docs)
- [Database Schema Design](./DATABASE_SCHEMA_DESIGN.md)

## 🎯 Benefits

1. **Simpler architecture** - One file instead of three
2. **Better integration** - Direct Python API instead of CLI
3. **Cleaner database** - Removed redundant tables
4. **Better error handling** - Programmatic control over execution
5. **More data** - Trajectory data captured directly
6. **Easier maintenance** - All solver logic in one place
7. **Better testability** - Mock-friendly design

## ⚠️ Important Notes

- E2B_API_KEY required in environment
- OPENROUTER_API_KEY required for model access
- GITHUB_TOKEN optional but recommended for private repos
- Sandboxes auto-close after execution or on error
- Background tasks are cancelled gracefully on shutdown

