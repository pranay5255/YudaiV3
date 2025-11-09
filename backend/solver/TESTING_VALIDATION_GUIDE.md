# Testing & Validation Guide for Solver Refactoring

## ✅ Completed Tasks

### 1. Code Consolidation
- ✅ All functionality from `MSWEA.py` moved to `manager.py`
- ✅ All functionality from `sandbox.py` moved to `manager.py`
- ✅ Deleted `MSWEA.py` and `sandbox.py`
- ✅ Created `HeadlessSandboxExecutor` class with Python bindings integration
- ✅ Updated `DefaultSolverManager` to use new executor

### 2. Database Schema Updates
- ✅ Added `trajectory_data` column to `solve_runs` table in models
- ✅ Removed `SWEAgentConfig` model (not needed)
- ✅ Removed `AISolveSession` model (redundant with `solves`)
- ✅ Removed `AISolveEdit` model (tracked in trajectory data)
- ✅ Updated `database.py` to remove sample data for deleted models

### 3. Mini-SWE-Agent Integration
- ✅ Using Python bindings instead of CLI
- ✅ `DefaultAgent` for headless execution
- ✅ `LocalEnvironment` for command execution
- ✅ `get_model` for automatic model selection
- ✅ Trajectory data capture

## 🔧 TODO: Update init.sql

The `init.sql` file needs to be updated to match the simplified schema. Here's what needs to be changed:

### Remove These Tables
```sql
-- DELETE THESE:
DROP TABLE IF EXISTS swe_agent_configs;
DROP TABLE IF EXISTS ai_solve_edits;
DROP TABLE IF EXISTS ai_solve_sessions;
```

### Update solve_runs Table
```sql
-- ADD trajectory_data column:
ALTER TABLE solve_runs ADD COLUMN trajectory_data JSONB;

-- Or better, update the CREATE TABLE statement:
CREATE TABLE IF NOT EXISTS solve_runs (
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
    diagnostics JSON,
    trajectory_data JSON,  -- NEW FIELD
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

### Remove These Indexes
```sql
-- DELETE THESE:
DROP INDEX IF EXISTS idx_swe_agent_configs_is_default;
DROP INDEX IF EXISTS idx_ai_solve_sessions_user_id;
DROP INDEX IF EXISTS idx_ai_solve_sessions_issue_id;
DROP INDEX IF EXISTS idx_ai_solve_sessions_status;
DROP INDEX IF EXISTS idx_ai_solve_edits_session_id;
```

### Remove These Triggers
```sql
-- DELETE THESE:
DROP TRIGGER IF EXISTS update_swe_agent_configs_updated_at ON swe_agent_configs;
DROP TRIGGER IF EXISTS update_ai_solve_sessions_updated_at ON ai_solve_sessions;
DROP TRIGGER IF EXISTS update_ai_solve_edits_updated_at ON ai_solve_edits;
```

## 🧪 Testing Checklist

### 1. Environment Variables
Ensure these are set before testing:
```bash
export E2B_API_KEY="your_e2b_api_key"
export OPENROUTER_API_KEY="your_openrouter_api_key"
export GITHUB_TOKEN="your_github_token"  # Optional but recommended
export DATABASE_URL="postgresql://user:password@localhost:5432/yudai"
```

### 2. Database Migration
```bash
# Option 1: Drop and recreate (development only)
cd backend
python -c "from db.database import engine, Base; Base.metadata.drop_all(engine); Base.metadata.create_all(engine)"

# Option 2: Use init.sql (after updating it)
psql -U your_user -d yudai -f db/init.sql

# Option 3: Create sample data
python -c "from db.database import create_sample_data; create_sample_data()"
```

### 3. API Endpoint Tests

#### Test 1: Start Solve
```bash
curl -X POST http://localhost:8000/api/daifu/sessions/1/solve/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "issue_id": 1,
    "repo_url": "https://github.com/owner/repo",
    "branch_name": "main",
    "ai_model_id": 1
  }'

# Expected Response:
{
  "solve_session_id": "abc123...",
  "status": "pending"
}
```

#### Test 2: Check Status
```bash
curl http://localhost:8000/api/daifu/sessions/1/solve/status/abc123 \
  -H "Authorization: Bearer YOUR_TOKEN"

# Expected Response:
{
  "solve_session_id": "abc123...",
  "status": "running",  # or "completed", "failed", etc.
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
      "id": "run123...",
      "solve_id": "abc123...",
      "model": "anthropic/claude-sonnet-4-5-20250929",
      "temperature": 0.1,
      "status": "running",
      "sandbox_id": "sbx-xyz...",
      ...
    }
  ],
  "champion_run": null,
  "error_message": null
}
```

#### Test 3: Cancel Solve
```bash
curl -X POST http://localhost:8000/api/daifu/sessions/1/solve/cancel/abc123 \
  -H "Authorization: Bearer YOUR_TOKEN"

# Expected Response:
{
  "solve_session_id": "abc123...",
  "status": "cancelled",
  "message": "Solve cancelled"
}
```

### 4. Database Validation

After a successful solve run, verify database records:

```sql
-- Check solve record
SELECT id, status, champion_run_id, started_at, completed_at
FROM solves
WHERE id = 'abc123...';

-- Check solve_run record
SELECT 
    id, status, sandbox_id, pr_url, 
    tests_passed, latency_ms, 
    trajectory_data IS NOT NULL as has_trajectory
FROM solve_runs
WHERE solve_id = 'abc123...';

-- Verify trajectory data was captured
SELECT trajectory_data
FROM solve_runs
WHERE id = 'run123...'
AND trajectory_data IS NOT NULL;
```

### 5. E2B Sandbox Validation

Monitor E2B sandbox logs during execution:

1. Check E2B dashboard for sandbox creation
2. Verify mini-swe-agent installation
3. Verify repository cloning
4. Monitor agent execution
5. Confirm sandbox cleanup after completion

### 6. Logs Validation

Check application logs for:

```bash
# Expected log sequence:
[INFO] Creating E2B sandbox with mini-swe-agent...
[INFO] Sandbox created: sbx-xyz...
[INFO] Installing mini-swe-agent from source...
[INFO] mini-swe-agent installed: 0.x.x
[INFO] Cloning repository: https://github.com/...
[INFO] Repository cloned successfully
[INFO] Fetching GitHub issue: https://github.com/.../issues/123
[INFO] Executing mini-swe-agent in sandbox...
[INFO] Sandbox execution completed: exit_code=0, duration=45000ms
[INFO] Sandbox closed
```

## 🐛 Common Issues & Solutions

### Issue 1: E2B_API_KEY not found
```
Error: E2B_API_KEY environment variable required
```
**Solution**: Set E2B_API_KEY environment variable

### Issue 2: OPENROUTER_API_KEY not found
```
SandboxExecutionError: OPENROUTER_API_KEY environment variable required
```
**Solution**: Set OPENROUTER_API_KEY environment variable

### Issue 3: mini-swe-agent installation fails
```
Failed to install mini-swe-agent
```
**Solution**: 
- Check if yudai-swe-agent repository is accessible
- Verify E2B sandbox has internet access
- Check pip install logs in diagnostics

### Issue 4: Repository clone fails
```
Failed to clone repository: https://github.com/...
```
**Solution**:
- Verify repository URL is correct
- For private repos, ensure GITHUB_TOKEN is set
- Check GitHub API rate limits

### Issue 5: Database column not found
```
Column 'trajectory_data' does not exist
```
**Solution**: Update database schema to add trajectory_data column

### Issue 6: Model references deleted tables
```
sqlalchemy.exc.NoSuchTableError: swe_agent_configs
```
**Solution**: 
- Remove references to deleted models in code
- Drop the tables from database
- Recreate database with updated schema

## 📊 Success Criteria

A successful test run should:

1. ✅ Create solve and solve_run records in database
2. ✅ Launch E2B sandbox successfully
3. ✅ Install mini-swe-agent from source
4. ✅ Clone target repository
5. ✅ Execute mini-swe-agent with Python bindings
6. ✅ Capture execution results (exit_code, stdout, stderr)
7. ✅ Store trajectory data in database
8. ✅ Update solve status to "completed" or "failed"
9. ✅ Close sandbox and cleanup resources
10. ✅ Return correct status via API endpoints

## 🔬 Advanced Testing

### Test with Real GitHub Issue
```bash
# Use a real, simple GitHub issue for testing
curl -X POST http://localhost:8000/api/daifu/sessions/1/solve/start \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "issue_id": 1,
    "repo_url": "https://github.com/your-test-org/test-repo",
    "branch_name": "main",
    "ai_model_id": 1
  }'
```

### Monitor Sandbox Execution
```python
# Add debug logging to manager.py
logger.setLevel(logging.DEBUG)

# Or set environment variable
export LOG_LEVEL=DEBUG
```

### Verify Trajectory Data Structure
```sql
-- Query trajectory data
SELECT 
    id,
    trajectory_data->>'exit_status' as exit_status,
    jsonb_array_length(trajectory_data->'steps') as step_count
FROM solve_runs
WHERE trajectory_data IS NOT NULL;
```

## 📝 Next Steps

After successful testing:

1. ✅ Update `init.sql` with simplified schema
2. ✅ Run database migration
3. ✅ Test all three API endpoints
4. ✅ Verify E2B integration
5. ✅ Validate database records
6. ✅ Check logs for errors
7. ✅ Test cancellation workflow
8. ✅ Document any edge cases discovered

## 🚀 Production Deployment Checklist

Before deploying to production:

- [ ] All tests passing
- [ ] Database schema updated
- [ ] Environment variables configured
- [ ] E2B API key valid
- [ ] OPENROUTER API key valid
- [ ] GitHub token configured (if needed)
- [ ] Logs configured properly
- [ ] Error monitoring setup (Sentry, etc.)
- [ ] Rate limiting configured
- [ ] Timeout settings configured
- [ ] Resource limits set (max_parallel, time_budget_s)
- [ ] Backup strategy in place

