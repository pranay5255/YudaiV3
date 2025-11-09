# Solve Issues Tab Implementation

This document explains the implementation of the "Solve Issues" tab in YudaiV3, which allows users to solve GitHub issues using AI-powered agents.

## Overview

The Solve Issues feature enables users to:
1. View all GitHub issues from the selected repository
2. Filter issues by source (Yudai-generated vs. others)
3. Select issues and configure solving parameters
4. Start AI-powered solve sessions
5. Monitor solve progress in real-time
6. View and access generated pull requests

## Architecture

### Frontend Components

#### 1. **SolveIssues.tsx** - Main Component
Location: `src/components/SolveIssues.tsx`

**Features:**
- Fetches and displays GitHub issues in a card grid layout
- Filters issues by type (All, Yudai-generated, Others)
- Distinguishes Yudai-generated issues via `chat-generated` label
- Manages issue selection and solve configuration
- Polls solve status every 3 seconds when active
- Displays solve progress with detailed run information

**Key Components:**
- `SolveIssues` - Main container component
- `IssueModal` - Configuration modal for solving an issue
- `SolveProgressModal` - Real-time progress monitoring

#### 2. **Sidebar.tsx** - Navigation
Updated to include "Solve Issues" tab with Zap icon

#### 3. **App.tsx** - Routing
Updated to:
- Import SolveIssues component
- Add 'solve' to valid tab types
- Render SolveIssues component when tab is active

### Backend Endpoints

#### 1. **GitHub Issues Endpoint**
```
GET /daifu/github/repositories/{owner}/{repo}/issues
```

**Purpose:** Fetch GitHub issues for a repository and store them in the database

**Features:**
- Fetches issues from GitHub API via GitHubOps
- Stores issues in the database with proper relationships
- Returns issues with database IDs for solving
- Supports pagination (default 100 issues)

**Response:**
```typescript
Array<{
  id: number,           // Database ID (required for solving)
  number: number,       // GitHub issue number
  title: string,
  body: string,
  state: string,
  html_url: string,
  labels: string[],
  comments: number,
  created_at: string,
  updated_at: string
}>
```

#### 2. **AI Models Endpoint**
```
GET /daifu/ai-models
```

**Purpose:** Get list of available AI models for solving

**Response:**
```typescript
Array<{
  id: number,
  name: string,
  provider: string,
  model_id: string,
  description?: string
}>
```

#### 3. **Solver Endpoints** (existing, updated)

**Start Solve:**
```
POST /daifu/sessions/{session_id}/solve/start
```

**Request Body:**
```typescript
{
  issue_id: number,           // Database issue ID
  ai_model_id: number,        // Selected AI model
  repo_url: string,           // Repository URL
  branch_name: string,        // Branch to work on (default: "main")
  small_change: boolean,      // Limit scope to minimal changes
  best_effort: boolean,       // Continue even if tests fail
  max_iterations: number,     // Max agent iterations (default: 50)
  max_cost: number           // Max cost in USD (default: 10.0)
}
```

**Response:**
```typescript
{
  solve_session_id: string,
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "CANCELLED"
}
```

**Get Status:**
```
GET /daifu/sessions/{session_id}/solve/status/{solve_id}
```

**Response:**
```typescript
{
  solve_session_id: string,
  status: string,
  progress: {
    runs_total: number,
    runs_completed: number,
    runs_failed: number,
    runs_running: number,
    last_update: string,
    message: string
  },
  runs: Array<{
    id: string,
    model: string,
    status: string,
    started_at?: string,
    completed_at?: string,
    pr_url?: string,
    error_message?: string
  }>,
  champion_run?: {...},
  error_message?: string
}
```

**Cancel Solve:**
```
POST /daifu/sessions/{session_id}/solve/cancel/{solve_id}
```

### Backend Updates

#### 1. **manager.py** - Enhanced Configuration

**New Functions:**

**`build_tfbd_template()`** - Updated
```python
def build_tfbd_template(
    model_name: str,
    small_change: bool = False,
    best_effort: bool = False,
    max_iterations: int = 50,
    max_cost: float = 10.0,
) -> str
```
Generates YAML configuration with user-specified options.

**`generate_agent_config()`** - New
```python
def generate_agent_config(
    small_change: bool = False,
    best_effort: bool = False,
    max_iterations: int = 50,
    max_cost: float = 10.0,
) -> str
```
Creates agent configuration block based on user options.

**`generate_solve_config_file()`** - New
```python
def generate_solve_config_file(
    model_name: str,
    issue_url: str,
    repo_url: str,
    branch_name: str = "main",
    small_change: bool = False,
    best_effort: bool = False,
    max_iterations: int = 50,
    max_cost: float = 10.0,
) -> Dict[str, str]
```
Generates complete configuration files including YAML and metadata.

**Configuration Options:**

1. **Small Change Mode:**
   - Reduces max_iterations to 20 (from default 50)
   - Reduces max_cost to 5.0 (from default 10.0)
   - Instructs agent to make minimal code changes

2. **Best Effort Mode:**
   - Sets agent mode to "best_effort"
   - Allows agent to continue even if tests fail
   - Useful for exploratory fixes

**YAML Configuration Example:**
```yaml
agent:
  mode: "yolo"  # or "best_effort"
  max_iterations: 50
  max_cost: 10.0
  small_change: false
  best_effort: false
```

#### 2. **models.py** - Updated Request Model

**StartSolveRequest** - Enhanced
```python
class StartSolveRequest(BaseModel):
    issue_id: int
    repo_url: str
    branch_name: str = "main"
    ai_model_id: Optional[int] = None
    ai_model_ids: Optional[List[int]] = None
    small_change: bool = False
    best_effort: bool = False
    max_iterations: int = 50
    max_cost: float = 10.0
```

#### 3. **session_routes.py** - New Endpoints

Added three new endpoints:
1. List repository issues
2. Get available AI models
3. Solver endpoints (integrated via router)

### Data Flow

#### Starting a Solve Session

```
1. User clicks on issue card
   ↓
2. IssueModal opens with configuration options
   ↓
3. User selects:
   - AI Model
   - Small Change option
   - Best Effort option
   ↓
4. User clicks "Start Solve"
   ↓
5. Frontend sends POST to /sessions/{session_id}/solve/start
   ↓
6. Backend:
   - Validates issue and session
   - Creates Solve record in database
   - Generates custom YAML config based on options
   - Creates E2B sandbox
   - Installs mini-swe-agent
   - Clones repository
   - Starts agent execution
   ↓
7. Frontend receives solve_session_id
   ↓
8. Frontend opens SolveProgressModal
   ↓
9. Frontend polls /solve/status/{solve_id} every 3 seconds
   ↓
10. Backend returns current status, progress, and runs
   ↓
11. Frontend displays progress in real-time
   ↓
12. When complete:
    - Shows champion run
    - Displays PR URL
    - Allows closing or viewing results
```

#### Progress Monitoring

```
Every 3 seconds:
1. Frontend polls GET /sessions/{session_id}/solve/status/{solve_id}
2. Backend queries database for latest status
3. Returns:
   - Overall status (PENDING/RUNNING/COMPLETED/FAILED/CANCELLED)
   - Progress metrics (total, completed, failed, running)
   - Individual run details
   - Champion run (if completed)
   - Error messages (if any)
4. Frontend updates UI:
   - Progress bars
   - Status indicators
   - Run details
   - PR links
```

## User Interface

### Issue Cards
- Grid layout with 3 columns (responsive)
- Each card shows:
  - Issue number
  - Title
  - Description preview
  - Labels (with special badge for Yudai-generated)
  - Creation date
  - Comment count

### Filter Buttons
- **All Issues:** Shows all repository issues
- **Yudai Generated:** Shows only issues with `chat-generated` label
- **Other Issues:** Shows issues without `chat-generated` label

### Issue Configuration Modal
- Issue details (title, description, labels)
- AI Model dropdown (populated from available models)
- Small Change checkbox
- Best Effort checkbox
- Cancel and Start Solve buttons

### Progress Modal
- Overall status indicator with animation
- Progress statistics (total, completed, failed, running)
- Individual run details with status icons
- Champion run highlight (green border)
- PR links (when available)
- Cancel button (for active solves)
- Close button (for completed solves)

## Styling

Uses Tailwind CSS with custom theme:
- `bg` - Background colors
- `bg-secondary` - Secondary background
- `fg` - Foreground/text colors
- `accent` - Accent color (for buttons, links)
- `border` - Border colors
- `muted` - Muted text

## Error Handling

### Frontend
- Displays error messages in red banners
- Handles API failures gracefully
- Shows loading states during operations
- Prevents duplicate solve starts

### Backend
- Validates session ownership
- Checks issue existence
- Verifies model availability
- Handles sandbox failures
- Logs errors comprehensively

## Database Schema

### Updated Tables

**Solve Table:**
- Added fields for user options in `matrix` JSON column:
  - `small_change`
  - `best_effort`
  - `max_iterations`
  - `max_cost`

**Issue Table:**
- Stores GitHub issues with:
  - `github_issue_id` (unique)
  - `repository_id` (foreign key)
  - `number`, `title`, `body`
  - `state`, `html_url`
  - `author_username`
  - `github_created_at`, `github_updated_at`

## Configuration

### Environment Variables
- `OPENROUTER_API_KEY` - Required for AI model access
- `GITHUB_TOKEN` - Optional, for private repository access
- `SOLVER_MAX_PARALLEL` - Max concurrent solves (default: 3)
- `SOLVER_TIME_BUDGET_SECONDS` - Max solve time (default: 5400)

## Testing

### Manual Testing Steps

1. **Issue Display:**
   - Select a repository
   - Navigate to "Solve Issues" tab
   - Verify issues load correctly
   - Test filter buttons

2. **Issue Selection:**
   - Click on an issue card
   - Verify modal opens with correct details
   - Check AI model dropdown populates

3. **Solve Configuration:**
   - Select different AI models
   - Toggle Small Change checkbox
   - Toggle Best Effort checkbox
   - Verify UI updates correctly

4. **Solve Execution:**
   - Click "Start Solve"
   - Verify progress modal opens
   - Check status updates every 3 seconds
   - Monitor run progress

5. **Solve Completion:**
   - Wait for solve to complete
   - Verify champion run displays
   - Check PR link works
   - Test close button

6. **Error Scenarios:**
   - Try starting solve without session
   - Test canceling active solve
   - Verify error messages display

## Future Enhancements

1. **Solve History:** View past solves for comparison
2. **Batch Solving:** Solve multiple issues simultaneously
3. **Custom Templates:** Save and reuse configuration templates
4. **Cost Tracking:** Display cumulative costs for solves
5. **Notifications:** Alert when solve completes
6. **Advanced Filters:** Filter by label, assignee, date range
7. **Issue Preview:** Show issue content before selecting
8. **PR Integration:** Auto-merge successful PRs with approval

## Troubleshooting

### Issues Not Loading
- Check repository selection
- Verify GitHub token permissions
- Check backend logs for API errors

### Solve Not Starting
- Verify session is active
- Check OPENROUTER_API_KEY is set
- Ensure issue has database ID
- Check backend logs

### Progress Not Updating
- Verify solve_session_id is valid
- Check polling interval (should be 3 seconds)
- Look for network errors in browser console

### E2B Sandbox Errors
- Check E2B API key configuration
- Verify sandbox template exists
- Check mini-swe-agent installation logs

## Security Considerations

1. **Authentication:** All endpoints require authenticated user
2. **Session Ownership:** Solves are scoped to user's sessions
3. **Repository Access:** Respects GitHub token permissions
4. **Cost Limits:** Max cost enforced to prevent runaway expenses
5. **Rate Limiting:** GitHub API requests are rate-limited
6. **Sandbox Isolation:** Each solve runs in isolated E2B sandbox

## Performance Optimization

1. **Issue Caching:** Issues cached in database after first fetch
2. **Polling Interval:** 3-second interval balances updates vs. load
3. **Lazy Loading:** Issues load on tab activation
4. **Database Indexing:** Issues indexed by repository and number
5. **Parallel Solves:** Configurable max parallel solves (default: 3)

## Deployment Checklist

- [ ] Set OPENROUTER_API_KEY environment variable
- [ ] Configure GitHub token for private repos
- [ ] Set solver limits (max_parallel, time_budget)
- [ ] Test issue fetching with public and private repos
- [ ] Verify E2B sandbox configuration
- [ ] Test solve execution end-to-end
- [ ] Monitor costs and set alerts
- [ ] Configure logging and monitoring

## API Reference Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/daifu/github/repositories/{owner}/{repo}/issues` | GET | Fetch repository issues |
| `/daifu/ai-models` | GET | Get available AI models |
| `/daifu/sessions/{session_id}/solve/start` | POST | Start solve session |
| `/daifu/sessions/{session_id}/solve/status/{solve_id}` | GET | Get solve status |
| `/daifu/sessions/{session_id}/solve/cancel/{solve_id}` | POST | Cancel solve |

## File Changes Summary

### New Files
- `src/components/SolveIssues.tsx` - Main component

### Modified Files
- `src/App.tsx` - Added solve tab rendering
- `src/components/Sidebar.tsx` - Added solve tab button
- `src/types/sessionTypes.ts` - Added 'solve' to TabType
- `backend/daifuUserAgent/session_routes.py` - Added endpoints
- `backend/solver/manager.py` - Added config generation functions
- `backend/models.py` - Updated StartSolveRequest model

## Support

For issues or questions:
1. Check backend logs: `backend/logs/`
2. Check frontend console: Browser DevTools
3. Verify environment variables are set
4. Review E2B sandbox logs
5. Check GitHub API rate limits

## License

Same as YudaiV3 project license.

---

**Implementation Date:** November 2025
**Version:** 1.0.0
**Author:** YudaiV3 Development Team

