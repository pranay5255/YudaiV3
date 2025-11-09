# Solver Database Schema Design

## Overview
This document outlines the database schema requirements for the YudaiV3 solver system based on the actual workflow and data we need to track.

## Core Entities

### 1. `solves` Table (Top-level solve orchestration)
**Purpose**: Tracks a solve session that may spawn multiple experiment runs

```sql
CREATE TABLE solves (
    -- Primary key
    id VARCHAR(64) PRIMARY KEY,  -- UUID for solve session
    
    -- Foreign keys
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_id INTEGER REFERENCES chat_sessions(id),  -- Optional: link to chat session
    
    -- Solve configuration
    repo_url VARCHAR(1000) NOT NULL,  -- Target repository
    issue_number INTEGER NOT NULL,     -- GitHub issue number
    base_branch VARCHAR(255) DEFAULT 'main',
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    
    -- Experiment matrix (JSON)
    matrix JSONB NOT NULL,  -- Configuration for multiple experiment runs
    limits JSONB,           -- Resource limits (max_parallel, time_budget_s, etc.)
    
    -- Metadata
    requested_by VARCHAR(255),
    champion_run_id VARCHAR(64) REFERENCES solve_runs(id),  -- Best performing run
    max_parallel INTEGER,
    time_budget_s INTEGER,
    error_message TEXT,
    
    -- Timestamps
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Indexes**:
```sql
CREATE INDEX idx_solves_user_id ON solves(user_id);
CREATE INDEX idx_solves_session_id ON solves(session_id);
CREATE INDEX idx_solves_status ON solves(status);
CREATE INDEX idx_solves_created_at ON solves(created_at);
```

---

### 2. `solve_runs` Table (Individual experiment executions)
**Purpose**: Tracks individual mini-swe-agent runs in E2B sandboxes

```sql
CREATE TABLE solve_runs (
    -- Primary key
    id VARCHAR(64) PRIMARY KEY,  -- UUID for run
    
    -- Foreign key
    solve_id VARCHAR(64) REFERENCES solves(id) ON DELETE CASCADE,
    
    -- Run configuration
    model VARCHAR(255) NOT NULL,         -- Model used (e.g., "anthropic/claude-sonnet-4")
    temperature FLOAT NOT NULL,          -- Model temperature
    max_edits INTEGER NOT NULL,          -- Maximum edits allowed
    evolution VARCHAR(255) NOT NULL,     -- Evolution strategy (baseline, etc.)
    
    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending',  -- pending, running, completed, failed, cancelled
    
    -- Execution results
    sandbox_id VARCHAR(255),             -- E2B sandbox identifier
    pr_url VARCHAR(1000),                -- Pull request URL if created
    tests_passed BOOLEAN,                -- Whether tests passed
    loc_changed INTEGER,                 -- Lines of code changed
    files_changed INTEGER,               -- Number of files changed
    tokens INTEGER,                      -- Total tokens used
    latency_ms INTEGER,                  -- Execution duration in milliseconds
    logs_url VARCHAR(1000),             -- URL to full execution logs
    
    -- Diagnostics and trajectory
    diagnostics JSONB,                   -- Execution diagnostics (stdout/stderr previews, etc.)
    trajectory_data JSONB,               -- Agent trajectory data
    error_message TEXT,
    
    -- Timestamps
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Indexes**:
```sql
CREATE INDEX idx_solve_runs_solve_id ON solve_runs(solve_id);
CREATE INDEX idx_solve_runs_status ON solve_runs(status);
CREATE INDEX idx_solve_runs_created_at ON solve_runs(created_at);
```

---

### 3. `ai_models` Table (Model configurations)
**Purpose**: Stores available AI model configurations

```sql
CREATE TABLE ai_models (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,          -- Display name
    provider VARCHAR(100) NOT NULL,      -- Provider (e.g., "openrouter", "anthropic")
    model_id VARCHAR(255) NOT NULL,      -- Model identifier for API
    config JSONB,                        -- Model-specific config (temperature, max_tokens, etc.)
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

**Indexes**:
```sql
CREATE INDEX idx_ai_models_is_active ON ai_models(is_active);
CREATE INDEX idx_ai_models_provider ON ai_models(provider);
```

---

## Relationships

```
users (1) ──→ (N) solves
chat_sessions (1) ──→ (N) solves  [optional]
solves (1) ──→ (N) solve_runs
solves (1) ──→ (1) solve_runs [champion_run_id - best performing run]
ai_models (1) ──→ (N) solve_runs [via model field]
```

---

## Data Flow

### 1. Start Solve Request
```
POST /sessions/{session_id}/solve/start
↓
Create Solve record (status: pending)
↓
Create SolveRun record(s) (status: pending)
↓
Launch async task (HeadlessSandboxExecutor)
↓
Update Solve (status: running)
Update SolveRun (status: running)
```

### 2. Execution in E2B Sandbox
```
Create E2B sandbox
↓
Install mini-swe-agent
↓
Clone repository
↓
Execute DefaultAgent with Python bindings
↓
Capture results (stdout, stderr, exit_code, trajectory)
↓
Close sandbox
```

### 3. Record Results
```
SolveRun updates:
- status: completed/failed
- exit_code, sandbox_id
- tests_passed, loc_changed, files_changed
- tokens, latency_ms
- diagnostics (stdout/stderr previews)
- trajectory_data
- pr_url (if created)

Solve updates:
- status: completed/failed
- champion_run_id (if successful)
- completed_at
```

### 4. Status Polling
```
GET /sessions/{session_id}/solve/status/{solve_id}
↓
Query Solve + SolveRuns
↓
Calculate progress metrics
↓
Return status response
```

---

## What We DON'T Need

Based on the actual workflow, we can **remove** these unused models:

1. **`swe_agent_configs`** - Not needed; configuration is embedded in code
2. **`ai_solve_sessions`** - Redundant with `solves` table
3. **`ai_solve_edits`** - Not needed; edits are tracked in trajectory data
4. **`FileAnalysis`** - Not related to solver

---

## Simplified Schema Summary

### Tables to KEEP:
- ✅ `solves` - Top-level solve orchestration
- ✅ `solve_runs` - Individual experiment runs
- ✅ `ai_models` - Model configurations
- ✅ `users` - User management
- ✅ `chat_sessions` - Session context
- ✅ `issues` - GitHub issues

### Tables to REMOVE:
- ❌ `swe_agent_configs` - Configuration is in code
- ❌ `ai_solve_sessions` - Redundant with `solves`
- ❌ `ai_solve_edits` - Tracked in trajectory data

---

## Migration Plan

1. ✅ Update `models.py` to match this schema
2. ✅ Keep `solves` and `solve_runs` tables with correct fields
3. ✅ Remove unused models from `models.py`
4. ✅ Update `init.sql` to match final schema
5. ✅ Test with actual solver workflow

---

## Example JSON Data

### Solve.matrix (experiment configurations)
```json
{
  "experiments": [
    {
      "run_id": "abc123",
      "model": "anthropic/claude-sonnet-4-5",
      "temperature": 0.1,
      "mode": "yolo"
    }
  ]
}
```

### SolveRun.diagnostics (execution diagnostics)
```json
{
  "command": "python /home/user/run_agent.py",
  "stdout_tail": "... last 2000 chars of stdout ...",
  "stderr_tail": "... last 2000 chars of stderr ...",
  "trajectory_file": "/home/user/trajectory.json"
}
```

### SolveRun.trajectory_data (agent trajectory)
```json
{
  "exit_status": "finished",
  "total_steps": 15,
  "steps": [
    {"action": "read_file", "file": "src/main.py", "timestamp": "..."},
    {"action": "edit_file", "file": "src/main.py", "timestamp": "..."}
  ]
}
```

