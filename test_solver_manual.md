# YudaiV3 Solver Module - Manual Testing Guide

This guide provides step-by-step instructions for manually testing the solver module after deployment.

## Prerequisites

- Deployed YudaiV3 application with solver module
- Valid authentication token
- Access to a GitHub repository with issues
- E2B API key configured
- OpenRouter API key configured

## Table of Contents

1. [Environment Verification](#environment-verification)
2. [Backend Health Checks](#backend-health-checks)
3. [Database Verification](#database-verification)
4. [API Endpoint Testing](#api-endpoint-testing)
5. [E2B Sandbox Testing](#e2b-sandbox-testing)
6. [End-to-End Solver Test](#end-to-end-solver-test)
7. [Troubleshooting](#troubleshooting)

---

## 1. Environment Verification

### Check Container Status

```bash
# List all running containers
docker compose -f docker-compose.prod.yml ps

# Expected output:
# NAME       IMAGE           STATUS        PORTS
# yudai-be   ...             Up (healthy)  8000->8000
# yudai-db   ...             Up (healthy)  5432
# yudai-fe   ...             Up (healthy)  80->80, 443->443
```

### Verify Environment Variables

```bash
# Check E2B API key is set
docker exec yudai-be bash -c 'echo "E2B_API_KEY: ${E2B_API_KEY:0:10}..."'

# Check OpenRouter API key is set
docker exec yudai-be bash -c 'echo "OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:0:10}..."'

# Check database connection
docker exec yudai-be bash -c 'echo $DATABASE_URL'
```

---

## 2. Backend Health Checks

### Check Backend Health Endpoint

```bash
# From host machine
docker exec yudai-be curl -s http://localhost:8000/health | jq

# Expected output:
# {
#   "status": "healthy",
#   "service": "yudai-v3-backend"
# }
```

### Check API Documentation

```bash
# Access API docs (from host)
docker exec yudai-be curl -s http://localhost:8000/docs

# Should return HTML content with "YudaiV3 Backend API"
```

### Verify Solver Router is Loaded

```bash
# Check if solver routes are registered
docker exec yudai-be python -c "
from run_server import app
routes = [r.path for r in app.routes]
solver_routes = [r for r in routes if 'solve' in r]
print('Solver routes found:', len(solver_routes))
for route in solver_routes:
    print(f'  - {route}')
"

# Expected output:
# Solver routes found: 3
#   - /daifu/sessions/{session_id}/solve/start
#   - /daifu/sessions/{session_id}/solve/status/{solve_id}
#   - /daifu/sessions/{session_id}/solve/cancel/{solve_id}
```

---

## 3. Database Verification

### Check Database Tables

```bash
# Connect to database and check tables
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('solves', 'solve_runs', 'ai_solve_sessions')
ORDER BY table_name;
"

# Expected output:
#     table_name     
# -------------------
#  ai_solve_sessions
#  solve_runs
#  solves
```

### Verify Table Schemas

```bash
# Check Solve table schema
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
\d solves
"

# Check SolveRun table schema
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
\d solve_runs
"

# Check relationships
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' 
  AND tc.table_name IN ('solves', 'solve_runs')
ORDER BY tc.table_name;
"
```

---

## 4. API Endpoint Testing

### Test Imports and Module Loading

```bash
# Test solver API imports
docker exec yudai-be python -c "
from api.solver import router
print('✓ Solver API imported successfully')
"

# Test solver manager imports
docker exec yudai-be python -c "
from solver.manager import DefaultSolverManager
manager = DefaultSolverManager()
print('✓ Solver manager instantiated successfully')
"

# Test sandbox executor imports
docker exec yudai-be python -c "
from solver.sandbox import HeadlessSandboxExecutor, HeadlessSandboxRequest
executor = HeadlessSandboxExecutor()
print('✓ Sandbox executor instantiated successfully')
"

# Test models imports
docker exec yudai-be python -c "
from models import Solve, SolveRun, AISolveSession, StartSolveRequest
print('✓ All solver models imported successfully')
"
```

### Test Database Connectivity

```bash
# Test database connection from backend
docker exec yudai-be python -c "
from db.database import SessionLocal
from models import User
db = SessionLocal()
try:
    count = db.query(User).count()
    print(f'✓ Database connected. Users in database: {count}')
finally:
    db.close()
"
```

---

## 5. E2B Sandbox Testing

### Test E2B Package Installation

```bash
# Check E2B package is installed
docker exec yudai-be python -c "
import e2b
print(f'✓ E2B package version: {e2b.__version__}')
"
```

### Test E2B API Key Validation

```bash
# Validate E2B API key format
docker exec yudai-be python -c "
import os
api_key = os.getenv('E2B_API_KEY')
if not api_key:
    print('✗ E2B_API_KEY not set')
    exit(1)
if not api_key.startswith('e2b_'):
    print(f'⚠ Warning: E2B_API_KEY does not start with e2b_ (got: {api_key[:10]}...)')
else:
    print(f'✓ E2B_API_KEY format valid: {api_key[:10]}...')
"
```

### Test E2B Sandbox Creation (Optional - Costs Quota)

**WARNING**: This test creates an actual E2B sandbox and may consume quota/credits.

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
    
    # Test command execution
    result = sandbox.commands.run('echo \"Hello from E2B\"')
    print(f'✓ Command executed: {result.stdout.strip()}')
    
    # Close sandbox
    sandbox.close()
    print('✓ Sandbox closed')
except Exception as e:
    print(f'✗ E2B sandbox test failed: {e}')
    exit(1)
"
```

---

## 6. End-to-End Solver Test

### Prepare Test Data

First, you need:
1. A valid auth token
2. A session ID
3. An issue ID from the database

```bash
# Get auth token (replace with your actual login)
# curl -X POST https://yudai.app/api/auth/api/login ...

# Get or create a session ID
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT id, title FROM chat_sessions ORDER BY created_at DESC LIMIT 5;
"

# Get or create an issue ID
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT id, number, title FROM issues ORDER BY created_at DESC LIMIT 5;
"
```

### Test Start Solve Endpoint

```bash
# Set your test variables
export AUTH_TOKEN="your-auth-token-here"
export SESSION_ID="1"
export ISSUE_ID="1"
export REPO_URL="https://github.com/owner/repo"

# Start a solve session
curl -X POST "https://yudai.app/api/daifu/sessions/${SESSION_ID}/solve/start" \
  -H "Authorization: Bearer ${AUTH_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"issue_id\": ${ISSUE_ID},
    \"repo_url\": \"${REPO_URL}\",
    \"branch_name\": \"main\"
  }"

# Expected response:
# {
#   "solve_session_id": "abc123...",
#   "status": "pending"
# }
```

### Test Get Status Endpoint

```bash
# Get status (replace SOLVE_ID with the solve_session_id from above)
export SOLVE_ID="abc123..."

curl -X GET "https://yudai.app/api/daifu/sessions/${SESSION_ID}/solve/status/${SOLVE_ID}" \
  -H "Authorization: Bearer ${AUTH_TOKEN}"

# Expected response:
# {
#   "solve_session_id": "abc123...",
#   "status": "running",
#   "progress": {
#     "runs_total": 1,
#     "runs_completed": 0,
#     "runs_failed": 0,
#     "runs_running": 1,
#     "message": "running"
#   },
#   "runs": [...],
#   "champion_run": null
# }
```

### Test Cancel Solve Endpoint

```bash
# Cancel a solve session
curl -X POST "https://yudai.app/api/daifu/sessions/${SESSION_ID}/solve/cancel/${SOLVE_ID}" \
  -H "Authorization: Bearer ${AUTH_TOKEN}"

# Expected response:
# {
#   "solve_session_id": "abc123...",
#   "status": "cancelled",
#   "message": "Solve cancelled"
# }
```

### Monitor Solve Progress

```bash
# Watch solve progress in real-time
watch -n 5 "curl -s -X GET \"https://yudai.app/api/daifu/sessions/${SESSION_ID}/solve/status/${SOLVE_ID}\" \
  -H \"Authorization: Bearer ${AUTH_TOKEN}\" | jq '.status, .progress'"
```

---

## 7. Troubleshooting

### View Backend Logs

```bash
# View all backend logs
docker compose -f docker-compose.prod.yml logs -f backend

# Filter for solver-related logs
docker compose -f docker-compose.prod.yml logs -f backend | grep -i solve

# Filter for E2B-related logs
docker compose -f docker-compose.prod.yml logs -f backend | grep -i e2b
```

### Check Database Records

```bash
# Check recent solve sessions
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 
    id, 
    status, 
    issue_number, 
    created_at,
    started_at,
    completed_at,
    error_message
FROM solves 
ORDER BY created_at DESC 
LIMIT 5;
"

# Check solve runs for a specific solve
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 
    id,
    solve_id,
    model,
    status,
    sandbox_id,
    error_message,
    created_at,
    completed_at
FROM solve_runs 
WHERE solve_id = 'your-solve-id-here'
ORDER BY created_at DESC;
"
```

### Common Issues

#### 1. E2B API Key Invalid

**Error**: `E2B API key is invalid` or `401 Unauthorized`

**Solution**:
```bash
# Verify E2B_API_KEY in .env.prod
grep E2B_API_KEY .env.prod

# Update and restart
docker compose -f docker-compose.prod.yml restart backend
```

#### 2. Solver Router Not Found

**Error**: `404 Not Found` for solver endpoints

**Solution**:
```bash
# Check if solver router is mounted
docker exec yudai-be python -c "
from run_server import app
print([r.path for r in app.routes if 'solve' in r.path])
"

# If empty, check run_server.py has:
# from api.solver import router as solver_router
# app.include_router(solver_router, prefix="/daifu", tags=["solver"])
```

#### 3. Database Tables Missing

**Error**: `relation "solves" does not exist`

**Solution**:
```bash
# Recreate database tables
docker exec yudai-be python -c "
from db.database import init_db
init_db()
print('✓ Database tables created')
"
```

#### 4. Import Errors

**Error**: `ModuleNotFoundError: No module named 'solver'`

**Solution**:
```bash
# Check PYTHONPATH
docker exec yudai-be bash -c 'echo $PYTHONPATH'

# Should be: /app

# Check file structure
docker exec yudai-be ls -la /app/solver/
docker exec yudai-be ls -la /app/api/
```

#### 5. Sandbox Execution Fails

**Error**: Solve status shows "failed" with sandbox errors

**Solution**:
```bash
# Check solve run diagnostics
docker exec yudai-db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "
SELECT 
    id,
    status,
    error_message,
    diagnostics
FROM solve_runs 
WHERE status = 'failed'
ORDER BY created_at DESC 
LIMIT 1;
"

# Check E2B sandbox logs (if sandbox_id is available)
# Review error_message and diagnostics JSON for specific error
```

---

## Summary Checklist

- [ ] All containers are running and healthy
- [ ] Environment variables are set correctly
- [ ] Database tables exist with correct schema
- [ ] Solver API imports work
- [ ] E2B package is installed
- [ ] Solver routes are registered
- [ ] Can create solve session via API
- [ ] Can check solve status via API
- [ ] Can cancel solve session via API
- [ ] Logs show no critical errors

---

## Next Steps

1. **Production Monitoring**: Set up monitoring for solver endpoints
2. **Load Testing**: Test with multiple concurrent solve sessions
3. **Error Tracking**: Integrate with error tracking service (Sentry)
4. **Performance Optimization**: Monitor sandbox creation/execution times
5. **Cost Tracking**: Monitor E2B sandbox usage and costs

---

## Support

If you encounter issues not covered in this guide:
1. Check backend logs: `docker compose -f docker-compose.prod.yml logs backend`
2. Check database for error messages in `solves` and `solve_runs` tables
3. Verify E2B account quota and billing status
4. Review solverArchScaffold.md for architecture details

