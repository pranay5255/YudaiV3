# Quick Reference - Solver Refactoring

## 📦 What Changed

| Item | Before | After |
|------|--------|-------|
| **Files** | 4 files (solver.py, manager.py, sandbox.py, MSWEA.py) | 2 files (solver.py, manager.py) |
| **Integration** | CLI-based (subprocess) | Python bindings (Direct API) |
| **Database Tables** | 6 solver tables | 3 solver tables |
| **Architecture** | Fragmented across multiple files | Consolidated in manager.py |

## 🗂️ Deleted Files

- ❌ `backend/solver/MSWEA.py` → Moved to `manager.py::HeadlessSandboxExecutor._generate_agent_script()`
- ❌ `backend/solver/sandbox.py` → Moved to `manager.py::HeadlessSandboxExecutor`

## 🗄️ Database Changes

### Removed Tables
- ❌ `swe_agent_configs` (not needed)
- ❌ `ai_solve_sessions` (redundant)
- ❌ `ai_solve_edits` (in trajectory data)

### Added Column
- ✅ `solve_runs.trajectory_data` (JSONB) - Agent execution trajectory

### Kept Tables
- ✅ `solves` - Top-level orchestration
- ✅ `solve_runs` - Individual runs
- ✅ `ai_models` - Model configurations

## 🔑 Key Classes

### HeadlessSandboxExecutor
```python
# Creates E2B sandbox, installs mini-swe-agent, executes agent
executor = HeadlessSandboxExecutor()
result = await executor.run(HeadlessSandboxRequest(...))
```

### DefaultSolverManager
```python
# Orchestrates solve sessions, manages database
manager = DefaultSolverManager()
response = await manager.start_solve(session_id, request, user)
```

## 🌐 API Endpoints

```bash
# Start solve
POST /api/daifu/sessions/{session_id}/solve/start
Body: {"issue_id": 1, "repo_url": "...", "branch_name": "main"}

# Check status
GET /api/daifu/sessions/{session_id}/solve/status/{solve_id}

# Cancel solve
POST /api/daifu/sessions/{session_id}/solve/cancel/{solve_id}
```

## 🔧 Environment Variables

```bash
# Required
export E2B_API_KEY="your_e2b_api_key"
export OPENROUTER_API_KEY="your_openrouter_api_key"

# Optional
export GITHUB_TOKEN="your_github_token"
```

## 🧪 Quick Test

```bash
# 1. Set environment variables
export E2B_API_KEY="..."
export OPENROUTER_API_KEY="..."

# 2. Start solve
curl -X POST http://localhost:8000/api/daifu/sessions/1/solve/start \
  -H "Content-Type: application/json" \
  -d '{"issue_id": 1, "repo_url": "https://github.com/owner/repo", "branch_name": "main"}'

# Response: {"solve_session_id": "abc123", "status": "pending"}

# 3. Check status
curl http://localhost:8000/api/daifu/sessions/1/solve/status/abc123

# 4. Verify in database
psql -d yudai -c "SELECT id, status FROM solves WHERE id = 'abc123';"
```

## 📊 Database Schema (Simplified)

```sql
-- solves: Top-level solve orchestration
CREATE TABLE solves (
    id VARCHAR(64) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    repo_url VARCHAR(1000) NOT NULL,
    issue_number INTEGER NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    champion_run_id VARCHAR(64) REFERENCES solve_runs(id),
    ...
);

-- solve_runs: Individual experiment runs
CREATE TABLE solve_runs (
    id VARCHAR(64) PRIMARY KEY,
    solve_id VARCHAR(64) REFERENCES solves(id),
    model VARCHAR(255) NOT NULL,
    sandbox_id VARCHAR(255),
    trajectory_data JSONB,  -- NEW
    pr_url VARCHAR(1000),
    status VARCHAR(50) DEFAULT 'pending',
    ...
);

-- ai_models: Model configurations
CREATE TABLE ai_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    provider VARCHAR(100) NOT NULL,
    model_id VARCHAR(255) NOT NULL,
    config JSONB,
    is_active BOOLEAN DEFAULT TRUE
);
```

## 🎯 Mini-SWE-Agent Integration

### Before (CLI)
```python
# Old approach: Shell out to CLI
result = subprocess.run(
    ["python", "MSWEA.py", issue_url, "--mode", "yolo"],
    capture_output=True
)
```

### After (Python Bindings)
```python
# New approach: Direct Python API
from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment

agent = DefaultAgent(
    get_model(model_name="anthropic/claude-sonnet-4-5"),
    LocalEnvironment(),
    mode="yolo"
)
exit_status, result = agent.run(task)
```

## 🔄 Workflow

```
API Request → DefaultSolverManager → HeadlessSandboxExecutor
                                              ↓
                                    Create E2B Sandbox
                                              ↓
                                    Install mini-swe-agent
                                              ↓
                                    Clone Repository
                                              ↓
                                    Execute DefaultAgent
                                              ↓
                                    Capture Results
                                              ↓
                                    Update Database
                                              ↓
                                    Close Sandbox
```

## 📚 Documentation Files

- 📖 `DATABASE_SCHEMA_DESIGN.md` - Schema design rationale
- 📖 `REFACTORING_SUMMARY.md` - Detailed changes
- 📖 `TESTING_VALIDATION_GUIDE.md` - Testing instructions
- 📖 `IMPLEMENTATION_COMPLETE.md` - Implementation status
- 📖 `QUICK_REFERENCE.md` - This file

## ⚠️ TODO Before Production

1. Update `backend/db/init.sql` to match new schema
2. Run database migration
3. Test all API endpoints
4. Verify E2B integration
5. Test cancellation workflow
6. Set up monitoring

## 🐛 Common Issues

| Issue | Solution |
|-------|----------|
| Missing E2B_API_KEY | Set environment variable |
| Missing OPENROUTER_API_KEY | Set environment variable |
| Table not found | Update database schema |
| Column not found | Add trajectory_data column |
| Sandbox creation fails | Check E2B_API_KEY validity |

## 📞 Need Help?

1. Check `TESTING_VALIDATION_GUIDE.md` for troubleshooting
2. Review logs for error messages
3. Verify environment variables
4. Check E2B dashboard
5. Refer to mini-swe-agent cookbook

---

**Last Updated**: 2024-11-09  
**Status**: ✅ Implementation Complete

