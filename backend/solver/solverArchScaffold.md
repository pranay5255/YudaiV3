# Solver Architecture Scaffold - E2B Sandbox Integration

## Overview

The solver module implements an automated GitHub issue solving system using **mini-SWE-agent** running in **E2B sandboxes**. The architecture supports parallel experiments with different AI models and configurations, automatically selecting the best solution based on test results, diff size, and other metrics.

## Key Design Principles

1. **Headless Execution**: All solver runs execute in E2B sandboxes without terminal UI sessions. The current `InteractiveAgent` implementation triggers terminal UI, which is undesirable for automated execution.

2. **Async Sandbox Flow**: Use E2B Python SDK's async capabilities for efficient sandbox lifecycle management (create, execute, monitor, terminate).

3. **Parallel Experiments**: Support multiple concurrent experiments with different model/temperature/config combinations to find optimal solutions.

4. **Result Reduction**: Automatically select the best PR based on tests passing, diff size, and latency metrics.

5. **Concurrency Control**: Respect max_parallel limits and TTL constraints for sandbox management.

## Architecture Components

### 1. API Layer (`backend/api/solver.py`)

FastAPI router implementing three endpoints:

- **POST `/daifu/sessions/{sessionId}/solve/start`**
  - Accepts `StartSolveRequest` (issue_id, repo_url, branch_name, optional ai_model_id, swe_config_id)
  - Creates `Solve` record in database
  - Schedules async solve runs via solver manager
  - Returns `solve_session_id`

- **GET `/daifu/sessions/{sessionId}/solve/status/{solveSessionId}`**
  - Returns current status (pending, running, completed, failed)
  - Reads from `Solve`/`SolveRun` models
  - Includes progress summary, PR URL, error messages


### 2. Solver Manager (`backend/solver/manager.py`)

Orchestration service handling:

- **Validation**: Validates issue_id, repository URL, branch
- **Issue Fetching**: Retrieves GitHub issue text via GitHub API or IssueOps module
- **Sandbox Execution**: Calls `run_mswea_in_sandbox` for each experiment
- **Result Capture**: Captures logs, PR URLs, metrics (tests_passed, loc_changed, files_changed, tokens, latency_ms)
- **Database Updates**: Updates `SolveRun` entries and parent `Solve` status

**Extensibility Design** (for future features):
- **Abstract Base Class**: Use `ABC` and abstract methods for core operations
- **Strategy Pattern**: Separate concerns (validation, execution, result processing) into pluggable strategies


### 3. Sandbox Integration (`backend/solver/sandbox.py`)

**CRITICAL**: Current implementation uses `InteractiveAgent` which triggers terminal UI sessions via `prompt_toolkit` and `rich.console`. Must be refactored to:

- Use E2B Python SDK async sandbox flow (no terminal UI)
- Execute `MSWEA.py` in headless mode using `DefaultAgent` instead of `InteractiveAgent`
- Stream logs asynchronously without blocking
- Handle sandbox lifecycle (create, execute, monitor, terminate) asynchronously

**Key Changes Required**:

1. **MSWEA.py Refactoring**:
   - Add `--headless` flag to `MSWEA.py` argument parser
   - When `--headless` is set, use `DefaultAgent` instead of `InteractiveAgent`
   - Replace `from minisweagent.agents.interactive import InteractiveAgent` with conditional import
   - Remove `rich.console` usage for headless mode (use standard logging instead)
   - Set mode to "yolo" automatically in headless mode (no confirmations needed)

2. **E2B Async Patterns**:
   - Wrap `sandbox.commands.run()` in `asyncio.to_thread()` for async execution
   - Use `sandbox.logs.listen()` for real-time log streaming (if available)
   - Implement async context managers for sandbox lifecycle
   - Use `asyncio.gather()` for parallel experiment execution

3. **Log Streaming**:
   - Capture stdout/stderr from sandbox commands
   - Stream logs to database (`SolveRun.logs_url` or store in `diagnostics` JSON field)
   - Provide real-time log updates via WebSocket or polling (future enhancement)

4. **Environment Variables**:
   - Pass `OPENROUTER_API_KEY`, `GITHUB_TOKEN` via E2B sandbox `envs` parameter
   - Handle missing credentials gracefully with clear error messages

### 4. Database Models (`backend/models.py`)

Three primary models:

- **`Solve`**: Top-level solve job tracking fan-out of experiments
  - Fields: id, user_id, session_id, repo_url, issue_number, base_branch, status, matrix, limits, champion_run_id, max_parallel, time_budget_s, error_message, timestamps

- **`SolveRun`**: Individual experiment run executed in E2B sandbox
  - Fields: id, solve_id, model, temperature, max_edits, evolution, status, sandbox_id, pr_url, tests_passed, loc_changed, files_changed, tokens, latency_ms, logs_url, diagnostics, error_message, timestamps

- **`AISolveSession`**: AI solve sessions tracking solver progress
  - Fields: id, user_id, issue_id, ai_model_id, swe_config_id, status, repo_url, branch_name, trajectory_data, error_message, timestamps

### 5. Request/Response Models

**StartSolveRequest**:
```python
class StartSolveRequest(BaseModel):
    issue_id: int
    repo_url: str
    branch_name: str = "main"
    ai_model_id: Optional[int] = None
    swe_config_id: Optional[int] = None
```

**SolveStatusResponse**:
```python
class SolveStatusResponse(BaseModel):
    solve_session_id: str
    status: SolveStatus  # pending, running, completed, failed, cancelled
    progress: Dict[str, Any]  # runs_completed, runs_total, etc.
    champion_run: Optional[SolveRunOut] = None
    error_message: Optional[str] = None
```

## Implementation Details

### E2B Async Sandbox Flow

The E2B Python SDK provides async sandbox management. Key considerations:

1. **Sandbox Creation**: 
   - `Sandbox.create()` is synchronous but sandboxes are ready immediately
   - Use async context managers or wrap in `asyncio.to_thread()` for non-blocking creation
   - Example: `sandbox = await asyncio.to_thread(Sandbox.create, envs=env_vars)`

2. **Command Execution**: 
   - `sandbox.commands.run()` is synchronous and blocks until completion
   - Wrap in `asyncio.to_thread()` for async execution: `result = await asyncio.to_thread(sandbox.commands.run, command)`
   - For long-running commands, consider using `sandbox.process.start()` for better control

3. **Log Streaming**: 
   - Use `sandbox.logs.listen()` for real-time log streaming (async iterator)
   - Example: `async for log in sandbox.logs.listen(): process_log(log)`
   - Store logs in database or stream to client via WebSocket

4. **File Operations**: 
   - `sandbox.files.write()` and `sandbox.files.read()` are synchronous
   - Wrap in `asyncio.to_thread()` for async file operations
   - Upload MSWEA.py, config files, and .env before execution

5. **Sandbox Lifecycle**: 
   - Always close sandboxes: `await asyncio.to_thread(sandbox.close)`
   - Use try/finally blocks or async context managers
   - Handle cancellation by closing sandboxes immediately

**Important**: The current `sandbox.py` uses synchronous `sandbox.commands.run()`. For true async execution:
- Wrap all synchronous E2B calls in `asyncio.to_thread()`
- Use `asyncio.gather()` for parallel experiment execution
- Implement proper async/await patterns throughout
- Consider using E2B SDK's async context managers if available

### Headless Agent Execution

The `MSWEA.py` script currently uses `InteractiveAgent` which requires terminal UI. To run headlessly:

1. **Option 1**: Modify `MSWEA.py` to use `DefaultAgent` instead of `InteractiveAgent`
2. **Option 2**: Create a headless wrapper that suppresses interactive prompts
3. **Option 3**: Use environment variables or config flags to disable interactive mode

**Recommended**: Modify `MSWEA.py` to accept a `--headless` flag that:
- Uses `DefaultAgent` instead of `InteractiveAgent`
- Sets mode to "yolo" (no confirmation)
- Disables console output or redirects to log files
- Removes `prompt_toolkit` dependencies



### GitHub Integration

- Use GitHub App installation tokens for authentication
- Clone repositories with proper credentials
- Create PRs with appropriate metadata
- Fetch issue content via GitHub API
- Handle private repositories securely

## Current Implementation Status

### ✅ Completed
- Basic `sandbox.py` with E2B integration
- `MSWEA.py` script for running mini-SWE-agent
- Database models (`Solve`, `SolveRun`, `AISolveSession`)
- Route constants in `backend/config/routes.py`
- Frontend API paths in `src/config/api.ts`

### ❌ Issues to Address
1. **Terminal UI Session**: `InteractiveAgent` triggers terminal UI - must use headless execution
2. **Async Flow**: Current implementation uses synchronous E2B calls - need proper async patterns
3. **Missing Endpoints**: No FastAPI router implementation yet
4. **Missing Manager**: No solver manager service for orchestration
5. **Headless Mode**: `MSWEA.py` needs headless execution mode

### 🔄 In Progress
- Architecture documentation (this file)
- Task list creation

## Implementation Phases

### Phase 1: Next Release (Current Focus)
- Tasks 1-7: Core solver functionality (headless execution, async sandbox, manager, API endpoints, models, database, GitHub integration)
- Tasks 11-12: Error handling and environment variable integration
- Task 15: Deployment configuration

### Phase 2: Future Releases (Deferred)
- Task 8: Experiment matrix builder (parallel experiments with different configs)
- Task 9: Best solution selection logic (result reduction and comparison)
- Task 10: Cancellation logic (sandbox termination and cleanup)
- Task 13: Logging and monitoring (structured logging, metrics tracking)
- Task 14: Unit tests (comprehensive test coverage)

## SolverManager Extensibility Design

The `SolverManager` class should be designed with extensibility in mind:

```python
from abc import ABC, abstractmethod
from typing import Protocol, Optional

class ExperimentStrategy(Protocol):
    """Protocol for experiment execution strategies."""
    async def execute(self, solve_id: str, config: dict) -> dict: ...

class ResultEvaluator(Protocol):
    """Protocol for result evaluation and comparison."""
    def evaluate(self, runs: List[SolveRun]) -> Optional[SolveRun]: ...

class SolverManager(ABC):
    """Base solver manager with extensible architecture."""
    
    def __init__(
        self,
        db_session: Session,
        github_client: GitHubClient,
        e2b_client: E2BClient,
        experiment_strategy: Optional[ExperimentStrategy] = None,
        result_evaluator: Optional[ResultEvaluator] = None,
    ):
        self.db = db_session
        self.github = github_client
        self.e2b = e2b_client
        self.experiment_strategy = experiment_strategy or DefaultExperimentStrategy()
        self.result_evaluator = result_evaluator or DefaultResultEvaluator()
    
    @abstractmethod
    async def start_solve(self, request: StartSolveRequest) -> str: ...
    
    @abstractmethod
    async def get_status(self, solve_id: str) -> SolveStatusResponse: ...
    
    # Hook points for extensibility
    async def before_execution(self, solve_id: str) -> None: ...
    async def after_execution(self, solve_id: str, result: dict) -> None: ...
    async def on_error(self, solve_id: str, error: Exception) -> None: ...
```

This design allows:
- **Future matrix builder**: Implement as `ExperimentStrategy` plugin
- **Future result selection**: Implement as `ResultEvaluator` plugin
- **Custom hooks**: Override `before_execution`, `after_execution`, `on_error` for custom logic
- **Testing**: Easy to mock dependencies and test in isolation

---

## DEPLOYMENT CHECKS

This section provides comprehensive deployment verification procedures for the solver module in production.

### Deployment Prerequisites

Before deploying the solver module, ensure you have:

1. **Environment Variables**:
   - `E2B_API_KEY` - E2B sandbox API key (format: `e2b_...`)
   - `OPENROUTER_API_KEY` - OpenRouter API key for LLM access
   - `GITHUB_TOKEN` or GitHub App credentials for repository access
   - `DATABASE_URL` - PostgreSQL connection string
   - `SECRET_KEY` and `JWT_SECRET` - Authentication secrets

2. **Infrastructure**:
   - Docker and Docker Compose installed
   - PostgreSQL database with pgvector extension
   - SSL certificates for HTTPS (production)
   - Sufficient disk space for sandbox operations

3. **Accounts & Quotas**:
   - Active E2B account with sandbox quota
   - OpenRouter account with API credits
   - GitHub App installed with appropriate permissions

---

### Deployment Steps

Follow these steps to deploy the solver module to production:

#### 1. Update Configuration Files

**Update `.env.prod`** with solver-related variables:

```bash
# E2B Sandbox Configuration
E2B_API_KEY=e2b_your_api_key_here

# Solver Configuration
SOLVER_MAX_PARALLEL=3
SOLVER_TIME_BUDGET_SECONDS=5400
MAX_SOLVE_TIME_MINUTES=30
MAX_CONCURRENT_SOLVES=3
SOLVER_TIMEOUT_SECONDS=1800
```

**Verify `docker-compose.prod.yml`** includes:

```yaml
backend:
  environment:
    - E2B_API_KEY=${E2B_API_KEY}
    - SOLVER_MAX_PARALLEL=${SOLVER_MAX_PARALLEL:-3}
    - SOLVER_TIME_BUDGET_SECONDS=${SOLVER_TIME_BUDGET_SECONDS:-5400}
```

**Verify `backend/run_server.py`** includes solver router:

```python
from api.solver import router as solver_router
app.include_router(solver_router, prefix="/daifu", tags=["solver"])
```

#### 2. Run Deployment Script

```bash
# Make scripts executable
chmod +x deploy_solver.sh test_solver_deployment.sh

# Run deployment with all checks
./deploy_solver.sh

# Or skip build if images are already built
./deploy_solver.sh --skip-build

# Or skip automated tests
./deploy_solver.sh --skip-tests
```

The deployment script will:
- ✅ Validate environment variables
- ✅ Check file structure
- ✅ Verify database models
- ✅ Build Docker images
- ✅ Start services
- ✅ Wait for health checks
- ✅ Run automated tests

#### 3. Verify Deployment

After deployment, run the test suite:

```bash
./test_solver_deployment.sh
```

This runs 10 test suites covering:
- Container health checks
- Environment variables
- File structure
- Python dependencies
- Module imports
- Database connectivity
- API endpoint availability
- Solver manager functionality
- Configuration validation

---

### Manual Verification Checks

Use these `docker exec` commands to verify backend functionality:

#### Container Status Checks

```bash
# Check all containers are running
docker compose -f docker-compose.prod.yml ps

# Expected: yudai-be, yudai-db, yudai-fe all "Up (healthy)"

# Check backend health endpoint
docker exec yudai-be curl -f http://localhost:8000/health

# Expected: {"status": "healthy", "service": "yudai-v3-backend"}
```

#### Environment Variable Checks

```bash
# Verify E2B API key is set
docker exec yudai-be bash -c 'echo "E2B_API_KEY: ${E2B_API_KEY:0:10}..."'

# Verify OpenRouter API key is set
docker exec yudai-be bash -c 'echo "OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:0:10}..."'

# Verify database connection string
docker exec yudai-be bash -c 'echo $DATABASE_URL | grep -o "postgresql://[^@]*"'
```

#### Module Import Checks

```bash
# Test solver API module imports
docker exec yudai-be python -c "from api.solver import router; print('✓ Solver API imported')"

# Test solver manager imports
docker exec yudai-be python -c "from solver.manager import DefaultSolverManager; print('✓ Manager imported')"

# Test sandbox executor imports
docker exec yudai-be python -c "from solver.sandbox import HeadlessSandboxExecutor; print('✓ Sandbox imported')"

# Test database models imports
docker exec yudai-be python -c "from models import Solve, SolveRun, AISolveSession; print('✓ Models imported')"
```

#### Database Schema Checks

```bash
# Check solver tables exist
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT table_name 
FROM information_schema.tables 
WHERE table_name IN ('solves', 'solve_runs', 'ai_solve_sessions')
ORDER BY table_name;"

# Expected: All three tables listed

# Check Solve table schema
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\d solves"

# Check foreign key relationships
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 
    tc.table_name, 
    kcu.column_name, 
    ccu.table_name AS foreign_table
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
  AND tc.table_name IN ('solves', 'solve_runs')
ORDER BY tc.table_name;"
```

#### API Route Checks

```bash
# Verify solver routes are registered
docker exec yudai-be python -c "
from run_server import app
routes = [r.path for r in app.routes]
solver_routes = [r for r in routes if 'solve' in r]
print(f'Found {len(solver_routes)} solver routes:')
for route in solver_routes:
    print(f'  - {route}')
"

# Expected output:
# Found 3 solver routes:
#   - /daifu/sessions/{session_id}/solve/start
#   - /daifu/sessions/{session_id}/solve/status/{solve_id}
#   - /daifu/sessions/{session_id}/solve/cancel/{solve_id}

# Check API documentation is accessible
docker exec yudai-be curl -s http://localhost:8000/docs | grep -o "<title>.*</title>"

# Expected: <title>YudaiV3 Backend API - Swagger UI</title>
```

#### Dependency Checks

```bash
# Verify E2B package is installed
docker exec yudai-be python -c "import e2b; print(f'E2B version: {e2b.__version__}')"

# Verify required Python packages
docker exec yudai-be python -c "
import fastapi
import sqlalchemy
import pydantic
import asyncio
print('✓ All required packages installed')
"

# Check mini-swe-agent files exist
docker exec yudai-be test -f /app/solver/MSWEA.py && echo "✓ MSWEA.py exists"
docker exec yudai-be test -f /app/solver/tfbd.yaml && echo "✓ tfbd.yaml exists"
```

#### Database Connectivity Check

```bash
# Test database connection from backend
docker exec yudai-be python -c "
from db.database import SessionLocal
from models import User
db = SessionLocal()
try:
    count = db.query(User).count()
    print(f'✓ Database connected. Users: {count}')
finally:
    db.close()
"

# Test solver manager can access database
docker exec yudai-be python -c "
from solver.manager import DefaultSolverManager
from db.database import SessionLocal
manager = DefaultSolverManager(session_factory=SessionLocal)
print('✓ Solver manager initialized with database access')
"
```

#### Configuration File Validation

```bash
# Validate tfbd.yaml is valid YAML
docker exec yudai-be python -c "
import yaml
with open('/app/solver/tfbd.yaml') as f:
    config = yaml.safe_load(f)
    print(f'✓ tfbd.yaml valid. Keys: {list(config.keys())}')
"

# Validate MSWEA.py syntax
docker exec yudai-be python -m py_compile /app/solver/MSWEA.py && echo "✓ MSWEA.py syntax valid"

# Check MSWEA.py has headless flag support
docker exec yudai-be grep -q "headless" /app/solver/MSWEA.py && echo "✓ MSWEA.py supports headless mode"
```

#### Solver Manager Functionality Check

```bash
# Test SolverManager instantiation
docker exec yudai-be python -c "
from solver.manager import DefaultSolverManager
manager = DefaultSolverManager()
print(f'✓ SolverManager created')
print(f'  Max parallel: {manager._max_parallel}')
print(f'  Time budget: {manager._time_budget_s}s')
"

# Test HeadlessSandboxExecutor instantiation
docker exec yudai-be python -c "
from solver.sandbox import HeadlessSandboxExecutor
executor = HeadlessSandboxExecutor()
print('✓ HeadlessSandboxExecutor instantiated')
"
```

#### E2B Sandbox Connectivity Check (Optional)

**⚠️ WARNING**: This test creates an actual E2B sandbox and consumes quota/credits.

```bash
# Only run if you want to verify E2B connectivity
docker exec yudai-be python -c "
from e2b import Sandbox
import os

api_key = os.getenv('E2B_API_KEY')
if not api_key:
    print('✗ E2B_API_KEY not set')
    exit(1)

try:
    print('Creating E2B sandbox...')
    sandbox = Sandbox.create()
    info = sandbox.get_info()
    print(f'✓ Sandbox created: {info.sandbox_id}')
    
    result = sandbox.commands.run('echo \"Test\"')
    print(f'✓ Command executed: {result.stdout.strip()}')
    
    sandbox.close()
    print('✓ Sandbox closed')
except Exception as e:
    print(f'✗ E2B test failed: {e}')
"
```

---

### Monitoring and Logging

#### View Real-Time Logs

```bash
# View all backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# Filter for solver-specific logs
docker compose -f docker-compose.prod.yml logs -f backend | grep -i solve

# Filter for E2B-specific logs
docker compose -f docker-compose.prod.yml logs -f backend | grep -i e2b

# View database logs
docker compose -f docker-compose.prod.yml logs -f db
```

#### Query Solve Sessions

```bash
# Check recent solve sessions
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 
    id, 
    status, 
    issue_number, 
    repo_url,
    created_at,
    started_at,
    completed_at,
    error_message
FROM solves 
ORDER BY created_at DESC 
LIMIT 5;"

# Check solve runs for a specific solve
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 
    id,
    solve_id,
    model,
    status,
    sandbox_id,
    tests_passed,
    error_message
FROM solve_runs 
WHERE solve_id = 'your-solve-id-here';"
```

---

### Production Testing

#### Test Solver Endpoints via API

See `test_solver_manual.md` for comprehensive API testing guide, including:
- Authentication setup
- Creating solve sessions
- Checking solve status
- Cancelling solve sessions
- Monitoring solve progress

Quick test commands:

```bash
# Set variables
export AUTH_TOKEN="your-auth-token"
export SESSION_ID="1"
export ISSUE_ID="1"
export REPO_URL="https://github.com/owner/repo"

# Start solve
curl -X POST "https://yudai.app/api/daifu/sessions/${SESSION_ID}/solve/start" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"issue_id\": ${ISSUE_ID}, \"repo_url\": \"${REPO_URL}\", \"branch_name\": \"main\"}"

# Get status (replace SOLVE_ID with response from above)
export SOLVE_ID="abc123..."
curl -X GET "https://yudai.app/api/daifu/sessions/${SESSION_ID}/solve/status/${SOLVE_ID}" \
  -H "Authorization: Bearer ${AUTH_TOKEN}"

# Cancel solve
curl -X POST "https://yudai.app/api/daifu/sessions/${SESSION_ID}/solve/cancel/${SOLVE_ID}" \
  -H "Authorization: Bearer ${AUTH_TOKEN}"
```

---

### Troubleshooting Common Issues

#### 1. E2B API Key Invalid

**Symptoms**: `401 Unauthorized` errors from E2B

**Fix**:
```bash
# Verify key format
docker exec yudai-be bash -c 'echo $E2B_API_KEY | grep -q "^e2b_" && echo "✓ Format OK" || echo "✗ Invalid format"'

# Update .env.prod and restart
docker compose -f docker-compose.prod.yml restart backend
```

#### 2. Solver Routes Not Found

**Symptoms**: `404 Not Found` for `/api/daifu/sessions/{session_id}/solve/start`

**Fix**:
```bash
# Check router is imported and mounted
docker exec yudai-be grep -n "from api.solver import router" /app/run_server.py
docker exec yudai-be grep -n "solver_router" /app/run_server.py

# If missing, update run_server.py and restart
docker compose -f docker-compose.prod.yml restart backend
```

#### 3. Database Tables Missing

**Symptoms**: `relation "solves" does not exist`

**Fix**:
```bash
# Recreate tables
docker exec yudai-be python -c "
from db.database import init_db
init_db()
print('✓ Database initialized')
"
```

#### 4. Import Errors

**Symptoms**: `ModuleNotFoundError: No module named 'solver'`

**Fix**:
```bash
# Check PYTHONPATH
docker exec yudai-be bash -c 'echo $PYTHONPATH'

# Verify file structure
docker exec yudai-be ls -la /app/solver/
docker exec yudai-be ls -la /app/api/solver.py
```

#### 5. Sandbox Execution Fails

**Symptoms**: Solve status shows "failed" with errors

**Debug**:
```bash
# Check recent failed runs
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 
    id,
    status,
    error_message,
    diagnostics
FROM solve_runs 
WHERE status = 'failed'
ORDER BY created_at DESC 
LIMIT 1;"

# View backend logs for details
docker compose -f docker-compose.prod.yml logs backend | tail -100
```

---

### Deployment Checklist

Use this checklist to verify successful deployment:

- [ ] All containers running and healthy (backend, database, frontend)
- [ ] E2B_API_KEY environment variable set and valid
- [ ] OPENROUTER_API_KEY environment variable set
- [ ] Database tables created (solves, solve_runs, ai_solve_sessions)
- [ ] Solver router mounted in run_server.py
- [ ] All Python modules import successfully
- [ ] Solver routes registered and accessible
- [ ] E2B package installed and working
- [ ] MSWEA.py and tfbd.yaml files present
- [ ] Database connectivity from backend works
- [ ] API documentation accessible at /docs
- [ ] No critical errors in backend logs
- [ ] Manual API test successful (start/status/cancel)
- [ ] E2B sandbox test successful (optional)

---

### Post-Deployment

After successful deployment:

1. **Monitor Performance**:
   - Track solve session duration
   - Monitor E2B sandbox creation time
   - Watch database query performance
   - Monitor memory/CPU usage

2. **Cost Tracking**:
   - Monitor E2B sandbox usage
   - Track OpenRouter API costs
   - Set up billing alerts

3. **Error Tracking**:
   - Integrate with error tracking service (Sentry)
   - Set up log aggregation (ELK, DataDog)
   - Configure alerts for critical errors

4. **Documentation**:
   - Document production configuration
   - Create runbook for common issues
   - Update team on new endpoints

---

### Additional Resources

- **Deployment Script**: `deploy_solver.sh` - Automated deployment with validation
- **Test Suite**: `test_solver_deployment.sh` - Comprehensive automated tests
- **Manual Testing Guide**: `test_solver_manual.md` - Step-by-step API testing
- **Architecture Docs**: This file (solverArchScaffold.md) - Implementation details
- **E2B Documentation**: https://e2b.dev/docs
- **Mini-SWE-Agent Docs**: backend/solver/mswea/README.md

---

### Support Contacts

- **Backend Issues**: Check backend logs and database
- **E2B Issues**: Review E2B dashboard and quotas
- **Infrastructure**: Check Docker logs and container health
- **Database**: Review PostgreSQL logs and connection pool

