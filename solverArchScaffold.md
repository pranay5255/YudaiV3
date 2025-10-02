# Solver Architecture Scaffold - Consolidated 2-File Implementation

> Consolidated implementation path for adding the parallel solver service backed by e2b sandboxes and the mini-swe-agent. All logic consolidated into 2 files with maximum code reuse from existing functions.

## Implementation Overview
**ONLY 2 FILES TO CREATE:**
1. `backend/solver/ai_solver.py` - Core solver logic with e2b integration
2. `backend/solver/solver_templates.py` - Template management and sandbox orchestration

**REUSE EXISTING CODE:**
- Session management from `session_routes.py` (already has solver endpoints)
- Database models from `models.py` (AISolveSession, AIModel, SWEAgentConfig already exist)
- GitHub operations from `githubOps.py`
- Chat integration from `ChatOps.py`
- Repository processing from `services/` (RepositorySnapshotService, FactsAndMemoriesService)

## 0. Prerequisites & Baseline Validation (Day 0)
- [x] FastAPI backend (`backend/run_server.py`) can reach Redis/Postgres
- [x] Session routes already have solver endpoints in `session_routes.py`
- [x] Database models already exist (AISolveSession, AIModel, SWEAgentConfig)
- [x] GitHub credentials handled in `backend/github`
- [ ] Add missing dependencies to `backend/requirements.txt`

## 1. Dependency Updates (Day 1 Morning)
**File: `backend/requirements.txt`**
- Add `e2b==0.8.0` (official SDK)
- Add `mini-swe-agent==0.1.0` (or current version)
- Add `redis==5.0.1` (for job queue)
- Add `rq==1.15.1` (Redis Queue worker)
- Add `tenacity==8.2.3` (retry logic)

## 2. Core Solver Implementation (Day 1 Afternoon)
**File: `backend/solver/ai_solver.py`**
```python
# Consolidated AI Solver with e2b integration
class AISolverAdapter:
    def __init__(self, db: Session):
        self.db = db
        self.e2b_client = E2BClient(api_key=settings.E2B_API_KEY)
    
    async def run_solver(self, issue_id, user_id, repo_url, branch, issue_content, issue_title, ai_model_id, swe_config_id):
        # Reuse existing session validation from session_routes.py
        # Create AISolveSession record (model already exists)
        # Launch e2b sandbox with template
        # Run mini-swe-agent
        # Stream results back to chat via ChatOps
        # Update session status
    
    async def cancel_session(self, solve_session_id, user_id):
        # Cancel running solver session
    
    def get_session_status(self, solve_session_id):
        # Get solver session statistics
```

**Key Functions to Implement:**
- `_launch_sandbox()` - e2b sandbox creation with template
- `_prepare_repository()` - Clone repo into sandbox (reuse GitHubOps)
- `_run_agent()` - Execute mini-swe-agent in sandbox
- `_collect_artifacts()` - Fetch results from sandbox
- `_cleanup_sandbox()` - Clean up resources

## 3. Template Management (Day 2 Morning)
**File: `backend/solver/solver_templates.py`**
```python
# Template management and sandbox orchestration
class SolverTemplateManager:
    def __init__(self):
        self.template_id = settings.E2B_TEMPLATE_ID
    
    def create_sandbox_template(self):
        # Create e2b template with Python environment
        # Add mini-swe-agent installation
        # Add repository cloning scripts
        # Add result collection scripts
    
    def prepare_sandbox_environment(self, sandbox, repo_url, branch, issue_data):
        # Clone repository using GitHubOps
        # Install dependencies
        # Set up issue context
        # Prepare mini-swe-agent configuration
```

**Template Scripts to Generate:**
- `prepare_repo.sh` - Clone repository (reuse GitHubOps logic)
- `install_deps.sh` - Install project dependencies
- `run_solver.py` - Execute mini-swe-agent (reuse existing agent logic)
- `collect_results.py` - Package results for retrieval

## 4. Integration with Existing Services (Day 2 Afternoon)
**Reuse Existing Code:**
- **Session Management**: Use existing `SessionService` from `session_service.py`
- **GitHub Operations**: Use existing `GitHubOps` from `githubOps.py`
- **Chat Integration**: Use existing `ChatOps` from `ChatOps.py`
- **Repository Processing**: Use existing `RepositorySnapshotService` from `services/`
- **Facts & Memories**: Use existing `FactsAndMemoriesService` from `services/`

**Modify Existing Files:**
- **`session_routes.py`**: Fix missing `await solver.run_solver()` call (line 1588)
- **`ChatOps.py`**: Add `append_solver_status()` method for real-time updates
- **`IssueOps.py`**: Add solver result integration after completion

## 5. Queue & Background Processing (Day 3 Morning)
**Reuse Existing Background Task Pattern:**
- Use existing `BackgroundTasks` from FastAPI (already in session_routes.py)
- Use existing `_index_repository_for_session_background()` pattern
- Implement `_run_solver_background()` following same pattern

**Redis Queue Integration:**
- Use existing Redis connection from database config
- Implement `enqueue_solver_job()` and `process_solver_job()`
- Reuse existing error handling and logging patterns

## 6. Real-time Updates & Chat Integration (Day 3 Afternoon)
**Reuse Existing Chat System:**
- Use existing `ChatOps.process_chat_message()` for status updates
- Use existing `ChatMessage` model for solver status messages
- Use existing WebSocket patterns from chat endpoints

**Status Update Flow:**
1. Solver starts → Post "Solver started" message via ChatOps
2. Sandbox created → Post "Environment prepared" message
3. Agent running → Post "Analyzing issue" message
4. Results ready → Post "Solution generated" message with results

## 7. Error Handling & Observability (Day 4)
**Reuse Existing Error Patterns:**
- Use existing `create_standardized_error()` from session_routes.py
- Use existing logging patterns from `utils.py`
- Use existing database transaction patterns

**Health Checks:**
- Reuse existing health check pattern from session_routes.py
- Add e2b connectivity check
- Add mini-swe-agent availability check

## 8. Testing Strategy (Day 5)
**Reuse Existing Test Patterns:**
- Use existing test database setup
- Mock e2b client (similar to existing GitHub API mocks)
- Use existing session test patterns from session_routes.py

## 9. Deployment & Configuration (Day 6)
**Reuse Existing Config:**
- Use existing environment variable patterns
- Use existing Docker configuration
- Use existing database migration patterns

**New Environment Variables:**
- `E2B_API_KEY` - e2b API key
- `E2B_TEMPLATE_ID` - e2b template ID
- `REDIS_URL` - Redis connection for job queue

## 10. Detailed Implementation Tasks

### File 1: `backend/solver/ai_solver.py` - Core Solver Logic

**Class Structure:**
```python
class AISolverAdapter:
    def __init__(self, db: Session)
    async def run_solver(self, issue_id, user_id, repo_url, branch, issue_content, issue_title, ai_model_id, swe_config_id)
    async def cancel_session(self, solve_session_id, user_id)
    def get_session_status(self, solve_session_id)
    async def _launch_sandbox(self, template_id, metadata)
    async def _prepare_repository(self, sandbox, repo_url, branch, user_id)
    async def _run_agent(self, sandbox, issue_data, ai_model_id, swe_config_id)
    async def _stream_results(self, sandbox, session_id, user_id)
    async def _collect_artifacts(self, sandbox, solve_session_id)
    async def _cleanup_sandbox(self, sandbox_id)
    def _update_session_status(self, solve_session_id, status, error_message=None)
    async def _post_status_to_chat(self, session_id, user_id, message, status_type)
```

**Step-by-Step Implementation:**

**Step 1: Basic Class Setup**
- [ ] Import required dependencies (e2b, redis, existing models)
- [ ] Initialize E2B client with API key from settings
- [ ] Add database session handling
- [ ] Add error handling and logging setup

**Step 2: run_solver() Method**
- [ ] Validate session exists and belongs to user (reuse from session_routes.py)
- [ ] Create AISolveSession record in database
- [ ] Launch e2b sandbox with template
- [ ] Prepare repository in sandbox (clone, install deps)
- [ ] Run mini-swe-agent with issue data
- [ ] Stream results back to chat
- [ ] Collect artifacts and update database
- [ ] Clean up sandbox resources
- [ ] Update session status to completed/failed

**Step 3: cancel_session() Method**
- [ ] Validate solve session exists and belongs to user
- [ ] Update session status to cancelled
- [ ] Terminate e2b sandbox if running
- [ ] Post cancellation message to chat
- [ ] Clean up resources

**Step 4: get_session_status() Method**
- [ ] Query AISolveSession from database
- [ ] Return comprehensive status including:
  - Current status (pending/running/completed/failed/cancelled)
  - Progress percentage
  - Error messages if any
  - Artifact URLs if completed
  - Execution time statistics

**Step 5: Helper Methods**
- [ ] `_launch_sandbox()` - Create e2b sandbox with metadata
- [ ] `_prepare_repository()` - Clone repo, install dependencies
- [ ] `_run_agent()` - Execute mini-swe-agent with proper configuration
- [ ] `_stream_results()` - Stream logs to chat via ChatOps
- [ ] `_collect_artifacts()` - Fetch results from sandbox
- [ ] `_cleanup_sandbox()` - Clean up e2b resources
- [ ] `_update_session_status()` - Update database record
- [ ] `_post_status_to_chat()` - Post status updates to chat

### File 2: `backend/solver/solver_templates.py` - Template Management

**Class Structure:**
```python
class SolverTemplateManager:
    def __init__(self)
    async def create_sandbox_template(self)
    async def prepare_sandbox_environment(self, sandbox, repo_url, branch, issue_data, user_id)
    def _generate_prepare_repo_script(self, repo_url, branch, github_token)
    def _generate_install_deps_script(self, project_type)
    def _generate_run_solver_script(self, issue_data, ai_model_id, swe_config_id)
    def _generate_collect_results_script(self)
    async def _clone_repository(self, sandbox, repo_url, branch, github_token)
    async def _install_dependencies(self, sandbox, project_type)
    async def _setup_issue_context(self, sandbox, issue_data)
    async def _configure_agent(self, sandbox, ai_model_id, swe_config_id)
```

**Step-by-Step Implementation:**

**Step 1: Template Creation**
- [ ] Create e2b template with Python environment
- [ ] Install mini-swe-agent and dependencies
- [ ] Add repository cloning scripts
- [ ] Add dependency installation scripts
- [ ] Add result collection scripts
- [ ] Configure environment variables

**Step 2: Sandbox Environment Preparation**
- [ ] Clone repository using GitHub token (reuse GitHubOps logic)
- [ ] Install project dependencies (detect type: Python/Node.js/etc.)
- [ ] Set up issue context files
- [ ] Configure mini-swe-agent with proper settings
- [ ] Prepare execution environment

**Step 3: Script Generation**
- [ ] `_generate_prepare_repo_script()` - Clone repo with proper authentication
- [ ] `_generate_install_deps_script()` - Install dependencies based on project type
- [ ] `_generate_run_solver_script()` - Execute mini-swe-agent with issue data
- [ ] `_generate_collect_results_script()` - Package results for retrieval

**Step 4: Repository Operations**
- [ ] `_clone_repository()` - Use GitHubOps for repository access
- [ ] `_install_dependencies()` - Detect and install project dependencies
- [ ] `_setup_issue_context()` - Create issue context files
- [ ] `_configure_agent()` - Set up mini-swe-agent configuration

### Integration Tasks

**Fix session_routes.py (Line 1588):**
- [ ] Fix missing `await solver.run_solver()` call
- [ ] Add proper error handling for solver failures
- [ ] Add background task integration

**Add ChatOps Integration:**
- [ ] Add `append_solver_status()` method to ChatOps
- [ ] Add real-time status updates during solver execution
- [ ] Add result posting when solver completes

**Add IssueOps Integration:**
- [ ] Add solver result integration after completion
- [ ] Add diff summary attachment to issues
- [ ] Add commit suggestion generation

**Add Redis Queue Processing:**
- [ ] Implement `enqueue_solver_job()` function
- [ ] Implement `process_solver_job()` worker
- [ ] Add job status tracking
- [ ] Add retry logic for failed jobs

**Add Health Checks:**
- [ ] Add e2b connectivity check
- [ ] Add mini-swe-agent availability check
- [ ] Add Redis queue health check
- [ ] Add database connectivity check

## Key Implementation Details

### Code Reuse Strategy:
1. **Database Models**: Use existing AISolveSession, AIModel, SWEAgentConfig
2. **Session Management**: Reuse SessionService patterns
3. **GitHub Operations**: Reuse GitHubOps for repository access
4. **Chat Integration**: Reuse ChatOps for real-time updates
5. **Background Tasks**: Reuse existing BackgroundTasks pattern
6. **Error Handling**: Reuse existing error response patterns
7. **Logging**: Reuse existing logging configuration

### File Structure:
```
backend/
├── solver/
│   ├── __init__.py
│   ├── ai_solver.py          # Core solver logic (NEW)
│   └── solver_templates.py   # Template management (NEW)
├── daifuUserAgent/
│   ├── session_routes.py      # Already has solver endpoints
│   ├── ChatOps.py            # Add solver status methods
│   └── IssueOps.py            # Add solver result integration
└── models.py                  # Already has solver models
```

### API Endpoints (Already Implemented):
- `POST /sessions/{session_id}/solve/start`
- `GET /sessions/{session_id}/solve/sessions/{solve_session_id}`
- `GET /sessions/{session_id}/solve/sessions/{solve_session_id}/stats`
- `POST /sessions/{session_id}/solve/sessions/{solve_session_id}/cancel`
- `GET /sessions/{session_id}/solve/sessions`
- `GET /sessions/{session_id}/solve/health`

> This consolidated approach maximizes code reuse while implementing the full solver functionality in just 2 new files.
