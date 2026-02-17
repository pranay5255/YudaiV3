# YudaiV3 Modal Sandbox Architecture & Flow

## Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [Data Flow Diagrams](#data-flow-diagrams)
3. [State Machine](#state-machine)
4. [Demo Scripts Explained](#demo-scripts-explained)
5. [Trajectory Streaming Flow](#trajectory-streaming-flow)

---

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          YudaiV3 Full Stack                              │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ FRONTEND (React + TypeScript + Vite)                                    │
│ Location: /home/pranay5255/Documents/YudaiV3/src/                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────┐    ┌──────────────────┐    ┌─────────────────┐   │
│  │  SolveIssues.tsx │───▶│ IssueModal       │───▶│ Start Solve     │   │
│  │  (Issue list)    │    │ (Configure solve)│    │ Request         │   │
│  └──────────────────┘    └──────────────────┘    └─────────┬───────┘   │
│                                                              │           │
│  ┌──────────────────┐    ┌──────────────────┐              │           │
│  │ TrajectoryViewer │◀───│ SolveProgressModal│◀─────────────┘           │
│  │ (Agent execution │    │ (Status polling) │                           │
│  │  messages)       │    │ (Every 3s)       │                           │
│  └──────────────────┘    └──────────────────┘                           │
│                                                                          │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ HTTP/REST
                                 │
┌────────────────────────────────▼─────────────────────────────────────────┐
│ BACKEND (FastAPI + PostgreSQL)                                          │
│ Location: /home/pranay5255/Documents/YudaiV3/backend/                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ FastAPI Endpoints (solver/solver.py)                            │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │ POST /api/daifu/sessions/{id}/solve/start                       │   │
│  │ GET  /api/daifu/solve/status/{solveId}  (polled every 3s)      │   │
│  │ POST /api/daifu/solve/cancel/{solveId}                          │   │
│  └────────────────┬─────────────────────────────────────────────────┘   │
│                   │                                                      │
│  ┌────────────────▼─────────────────────────────────────────────────┐   │
│  │ DefaultSolverManager (solver/manager.py - 863 lines)            │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │ • Creates Solve + SolveRun database records                     │   │
│  │ • Generates agent script artifacts (tfbd.yaml + run_agent.py)   │   │
│  │ • Spawns HeadlessSandboxExecutor for each run                   │   │
│  │ • Manages parallel/sequential execution                         │   │
│  │ • Determines champion (first successful run)                    │   │
│  └────────────────┬─────────────────────────────────────────────────┘   │
│                   │                                                      │
│  ┌────────────────▼─────────────────────────────────────────────────┐   │
│  │ AgentScriptParams (solver/agentScriptGen.py - 752 lines)        │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │ • Takes config (model, repo, issue, constraints)                │   │
│  │ • Generates tfbd.yaml (agent instructions)                      │   │
│  │ • Generates run_agent.py (execution script)                     │   │
│  │ • Pure string template substitution (NO ML)                     │   │
│  └────────────────┬─────────────────────────────────────────────────┘   │
│                   │                                                      │
│  ┌────────────────▼─────────────────────────────────────────────────┐   │
│  │ HeadlessSandboxExecutor (solver/sandbox.py - 812 lines)         │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │ • Creates Modal sandbox via modal.Sandbox.create()              │   │
│  │ • Uploads tfbd.yaml + run_agent.py to sandbox                   │   │
│  │ • Executes: python /home/user/run_agent.py                      │   │
│  │ • Streams stdout/stderr via SSE                                 │   │
│  │ • Downloads trajectory.json when complete                       │   │
│  │ • Updates SolveRun.status, trajectory_data, pr_url              │   │
│  └────────────────┬─────────────────────────────────────────────────┘   │
│                   │                                                      │
│  ┌────────────────▼─────────────────────────────────────────────────┐   │
│  │ PostgreSQL Database Tables                                      │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │ Solve: id, status, repo_url, issue_number, champion_run_id     │   │
│  │ SolveRun: id, solve_id, model, status, pr_url, trajectory_data │   │
│  │ AIModel: id, name, provider, model_id, pricing                 │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │ Modal SDK (modal.Sandbox.create)
                                 │
┌────────────────────────────────▼─────────────────────────────────────────┐
│ MODAL SANDBOX (Cloud-based ephemeral container)                         │
│ Created per solve run, destroyed after completion                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Container Image: Debian slim + Python 3.11 + git + curl               │
│  Environment: OPENROUTER_API_KEY, GITHUB_TOKEN                          │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │ /home/user/                                                      │   │
│  │ ├─ tfbd.yaml              (uploaded by backend)                 │   │
│  │ ├─ run_agent.py           (uploaded by backend)                 │   │
│  │ ├─ mini-swe-agent/        (cloned from GitHub)                  │   │
│  │ ├─ testbed/               (cloned target repo)                  │   │
│  │ ├─ trajectory.json        (written incrementally)               │   │
│  │ └─ last_mini_run.traj.json (final output)                       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  Execution Flow:                                                        │
│  1. python run_agent.py                                                 │
│  2.   └─ fetch_github_issue(ISSUE_URL)                                  │
│  3.   └─ clone_repository(REPO_URL) → /home/user/testbed/               │
│  4.   └─ install_mini_swe_agent() → /home/user/mini-swe-agent/          │
│  5.   └─ load_config(/home/user/tfbd.yaml)                              │
│  6.   └─ Run DefaultAgent(config, model, environment)                   │
│  7.       └─ Agent iterates (up to MAX_ITERATIONS):                     │
│  8.           ├─ Think (LLM call via OpenRouter)                        │
│  9.           ├─ Act (execute bash command in testbed/)                 │
│  10.          ├─ Observe (capture command output)                       │
│  11.          ├─ Append to trajectory.json                              │
│  12.          └─ Repeat until "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"   │
│  13.  └─ Create PR (if create_pr=True)                                  │
│  14.  └─ save_trajectory() → last_mini_run.traj.json                    │
│  15.  └─ Exit (code 0 = success, non-zero = failure)                    │
│                                                                          │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
                    OpenRouter API (LLM inference)
                    GitHub API (issue fetch, PR creation)
```

---

## Data Flow Diagrams

### Flow 1: Start Solve Request

```
USER                 FRONTEND              BACKEND                  MODAL               GITHUB
 │                      │                     │                      │                    │
 │ Click "Solve Issue" │                     │                      │                    │
 ├──────────────────────▶                     │                      │                    │
 │                      │ POST /solve/start   │                      │                    │
 │                      ├─────────────────────▶                      │                    │
 │                      │  {                  │                      │                    │
 │                      │    session_id,      │                      │                    │
 │                      │    issue_url,       │                      │                    │
 │                      │    ai_model_id,     │                      │                    │
 │                      │    temperature,     │                      │                    │
 │                      │    small_change     │                      │                    │
 │                      │  }                  │                      │                    │
 │                      │                     │                      │                    │
 │                      │                     │ 1. Create Solve DB   │                    │
 │                      │                     │    record            │                    │
 │                      │                     │ ┌──────────────────┐ │                    │
 │                      │                     │ │ Solve            │ │                    │
 │                      │                     │ │ ├─ id: 123       │ │                    │
 │                      │                     │ │ ├─ status: PENDING│                    │
 │                      │                     │ │ ├─ repo_url      │ │                    │
 │                      │                     │ │ └─ issue_number  │ │                    │
 │                      │                     │ └──────────────────┘ │                    │
 │                      │                     │                      │                    │
 │                      │                     │ 2. Create SolveRun   │                    │
 │                      │                     │    record(s)         │                    │
 │                      │                     │ ┌──────────────────┐ │                    │
 │                      │                     │ │ SolveRun         │ │                    │
 │                      │                     │ │ ├─ id: 456       │ │                    │
 │                      │                     │ │ ├─ solve_id: 123 │ │                    │
 │                      │                     │ │ ├─ status: QUEUED│ │                    │
 │                      │                     │ │ ├─ model: sonnet │ │                    │
 │                      │                     │ │ └─ temperature   │ │                    │
 │                      │                     │ └──────────────────┘ │                    │
 │                      │                     │                      │                    │
 │                      │                     │ 3. Generate artifacts│                    │
 │                      │                     │    via agentScriptGen│                    │
 │                      │                     │ ┌──────────────────┐ │                    │
 │                      │                     │ │ tfbd.yaml        │ │                    │
 │                      │                     │ │ run_agent.py     │ │                    │
 │                      │                     │ └──────────────────┘ │                    │
 │                      │                     │                      │                    │
 │                      │                     │ 4. Create Modal      │                    │
 │                      │                     │    Sandbox           │                    │
 │                      │                     ├──────────────────────▶                    │
 │                      │                     │ modal.Sandbox.create()                    │
 │                      │                     │                      │                    │
 │                      │                     │ 5. Upload artifacts  │                    │
 │                      │                     ├──────────────────────▶                    │
 │                      │                     │ sandbox.write_file() │                    │
 │                      │                     │                      │                    │
 │                      │                     │ 6. Execute script    │                    │
 │                      │                     ├──────────────────────▶                    │
 │                      │                     │ sandbox.run_command()│                    │
 │                      │                     │ "python run_agent.py"│                    │
 │                      │                     │                      │                    │
 │                      │  { solve_id: 123 }  │                      │ fetch_issue()      │
 │                      │◀─────────────────────                      ├────────────────────▶
 │                      │                     │                      │                    │
 │ { solve_id: 123 }   │                     │                      │ clone_repo()       │
 │◀──────────────────────                     │                      ├────────────────────▶
 │                      │                     │                      │                    │
 │                      │                     │                      │ (Agent starts...)  │
 │                      │                     │                      │                    │
```

### Flow 2: Status Polling (Every 3 seconds)

```
FRONTEND              BACKEND                  DATABASE              MODAL
   │                     │                         │                   │
   │ GET /solve/status/123                         │                   │
   ├─────────────────────▶                         │                   │
   │                     │ SELECT * FROM Solve     │                   │
   │                     │  WHERE id = 123         │                   │
   │                     ├─────────────────────────▶                   │
   │                     │                         │                   │
   │                     │ SELECT * FROM SolveRun  │                   │
   │                     │  WHERE solve_id = 123   │                   │
   │                     ├─────────────────────────▶                   │
   │                     │                         │                   │
   │                     │ {                       │                   │
   │                     │   runs: [               │                   │
   │  {                  │     { id: 456,          │                   │
   │    status: RUNNING, │       status: RUNNING,  │                   │
   │    progress: {      │       pr_url: null,     │                   │
   │      total: 1,      │       trajectory_data   │                   │
   │      running: 1,    │     }                   │                   │
   │      completed: 0   │   ]                     │                   │
   │    }                │ }                       │                   │
   │  }                  │                         │                   │
   │◀─────────────────────                         │                   │
   │                     │                         │                   │
   │ [Wait 3 seconds]    │                         │                   │
   │                     │                         │                   │
   │ GET /solve/status/123 (again)                 │                   │
   ├─────────────────────▶                         │                   │
   │                     │                         │                   │
   ...                  ...                       ...                 ...
```

### Flow 3: Trajectory Streaming (Future - MSWEA Arena)

```
FRONTEND              BACKEND                  MODAL SANDBOX
   │                     │                         │
   │ Start polling every 2s                        │
   │                     │                         │
   │ GET /trajectories/456                         │
   ├─────────────────────▶                         │
   │                     │ sandbox.read_file(      │
   │                     │   "/home/user/          │
   │                     │    trajectory.json"     │
   │                     │ )                       │
   │                     ├─────────────────────────▶
   │                     │                         │
   │                     │ {                       │
   │  {                  │   messages: [           │ (File growing in
   │    messages: [      │     {role: system,...}, │  real-time as
   │      {...},         │     {role: user,...},   │  agent executes)
   │      {...},         │     {role: assistant,...│
   │      {...}          │   ],                    │
   │    ],               │   info: {               │
   │    info: {          │     exit_status: null   │
   │      complete: false│   }                     │
   │    }                │ }                       │
   │  }                  │                         │
   │◀─────────────────────                         │
   │                     │                         │
   │ [Update TrajectoryViewer]                     │
   │ [Append new messages]                         │
   │                     │                         │
   │ [Wait 2 seconds]    │                         │
   │                     │                         │
   │ GET /trajectories/456 (fetch updates)         │
   ├─────────────────────▶                         │
   │                     │                         │
   ...                  ...                       ...
```

---

## State Machine

### Solve State Transitions

```
                    ┌─────────────────┐
                    │   User clicks   │
                    │  "Solve Issue"  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     PENDING     │◀──┐
                    │  (Solve created)│   │
                    └────────┬─────────┘   │
                             │             │
                    Create SolveRun        │
                             │             │
                             ▼             │
                    ┌─────────────────┐   │
                    │     QUEUED      │   │
                    │  (Awaiting exec)│   │
                    └────────┬─────────┘   │
                             │             │
                    Sandbox starts         │
                             │             │
                             ▼             │
                    ┌─────────────────┐   │
              ┌────▶│     RUNNING     │   │
              │     │ (Agent executing)│  │
              │     └────────┬─────────┘   │
              │              │             │
              │         ┌────┴────┐        │
              │         │         │        │
    Retry on error   Success   Failure    │
              │         │         │        │
              │         ▼         ▼        │
              │    ┌─────────┐  ┌─────────┐
              └────│COMPLETED│  │ FAILED  │
                   │(PR created)  │(Error) │
                   └─────────┘  └────┬────┘
                                     │
                                     └─────┘
                                      (End)
```

### SolveRun State Details

```
QUEUED → RUNNING → COMPLETED
   │        │           │
   │        │           └─ pr_url populated
   │        │           └─ trajectory_data saved
   │        │           └─ tests_passed = true/false
   │        │
   │        └─ FAILED
   │            └─ error message in diagnostics
   │            └─ partial trajectory_data if any
   │
   └─ Can transition directly to CANCELLED
```

---

## Demo Scripts Explained

### demo_script.py Flow

```
┌─────────────────────────────────────────────────────────────┐
│ demo_script.py                                              │
│ Purpose: Generate agent artifacts WITHOUT running Modal     │
└─────────────────────────────────────────────────────────────┘

Step 1: build_demo_params()
┌──────────────────────────────────────────────────────────┐
│ AgentScriptParams {                                      │
│   model_name: "minimax/minimax-m2:free"                  │
│   repo_url: "https://github.com/example/repo"            │
│   issue_url: "https://github.com/example/repo/issues/123"│
│   temperature: 0.2                                       │
│   max_iterations: 40                                     │
│   max_cost: 7.5                                          │
│   small_change: True                                     │
│ }                                                         │
└──────────────────────┬───────────────────────────────────┘
                       │
        ┌──────────────┴─────────────┐
        │                            │
        ▼                            ▼
Step 2a: build_tfbd_config()   Step 2b: build_agent_script()
┌──────────────────────┐      ┌────────────────────────────┐
│ Read tfbd.yaml       │      │ Use SCRIPT_TEMPLATE        │
│ template             │      │ from agentScriptGen.py     │
│                      │      │                            │
│ Replace:             │      │ Substitute variables:      │
│ - model_name         │      │ - $repo_url                │
│                      │      │ - $issue_url               │
│ Add constraints:     │      │ - $model_name              │
│ - small_change       │      │ - $temperature             │
│                      │      │ - $max_iterations          │
│ Return YAML string   │      │                            │
│ (5.2 KB)             │      │ Return Python string       │
│                      │      │ (13 KB)                    │
└──────────┬───────────┘      └────────────┬───────────────┘
           │                               │
           │                               │
           └───────────┬───────────────────┘
                       │
                       ▼
Step 3: create_demo_artifacts()
┌──────────────────────────────────────────────────────────┐
│ Write to disk:                                           │
│                                                          │
│ sandbox_demo_artifacts/                                  │
│ ├─ tfbd.yaml        (YAML config)                        │
│ └─ run_agent.py     (Python script)                      │
│                                                          │
│ These are TEXT FILES, not code execution!               │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
Step 4: display_preview()
┌──────────────────────────────────────────────────────────┐
│ Print first 24 lines of each file                       │
│ Show file sizes                                          │
│ Done!                                                    │
└──────────────────────────────────────────────────────────┘

KEY INSIGHT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This script ONLY does string manipulation and file writing.
NO Modal, NO LLM, NO PyTorch, NO agent execution!

The artifacts it creates are INPUTS for the Modal sandbox.
```

### e2b_standalone_demo.py Flow

```
┌─────────────────────────────────────────────────────────────┐
│ e2b_standalone_demo.py                                      │
│ Purpose: Full end-to-end Modal execution                    │
└─────────────────────────────────────────────────────────────┘

Step 1: validate_environment()
┌──────────────────────────────────────────────────────────┐
│ Check env vars:                                          │
│ ✓ OPENROUTER_API_KEY (required)                          │
│ ✓ MODAL_TOKEN_ID (required)                              │
│ ✓ MODAL_TOKEN_SECRET (required)                          │
│ ⚠ GITHUB_TOKEN (optional)                                │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
Step 2: build_demo_request()
┌──────────────────────────────────────────────────────────┐
│ HeadlessSandboxRequest {                                 │
│   issue_url: USER_CONFIG["issue_url"]                    │
│   repo_url: USER_CONFIG["repo_url"]                      │
│   model_name: USER_CONFIG["model_name"]                  │
│   temperature: 0.1                                       │
│   max_iterations: 40                                     │
│   create_pr: True                                        │
│ }                                                         │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
Step 3: HeadlessSandboxExecutor().run(request)
┌──────────────────────────────────────────────────────────┐
│ Creates Modal sandbox                                    │
│ Generates tfbd.yaml + run_agent.py (like demo_script)    │
│ Uploads to sandbox                                       │
│ Executes: python /home/user/run_agent.py                 │
│ Streams output                                           │
│ Downloads trajectory when complete                       │
│ Returns SandboxRunResult                                 │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
Step 4: display_result()
┌──────────────────────────────────────────────────────────┐
│ Show:                                                    │
│ - Sandbox ID                                             │
│ - Exit code                                              │
│ - Duration                                               │
│ - PR URL (if created)                                    │
│ - Trajectory file path                                   │
│ - Cost, API calls, message count                         │
│ - Last 2000 chars of stdout/stderr                       │
└──────────────────────┬───────────────────────────────────┘
                       │
                       ▼
Step 5: save_result_to_file()
┌──────────────────────────────────────────────────────────┐
│ Write to:                                                │
│ demo_results/demo_result_{sandbox_id}.json               │
│                                                          │
│ Contains full execution metadata                         │
└──────────────────────────────────────────────────────────┘

KEY INSIGHT:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
This script DOES execute the agent in Modal sandbox.
It creates a real sandbox, runs the AI agent, makes code
changes, and creates a GitHub PR. This is a FULL TEST.
```

---

## Trajectory Streaming Flow

### Current Implementation (Polling)

```
┌────────────────────────────────────────────────────────────────┐
│ CURRENT: Download trajectory AFTER completion                  │
└────────────────────────────────────────────────────────────────┘

TIME ──▶

Agent Start                       Agent Complete
    │                                    │
    │  ┌──────────────────────────────┐ │
    │  │ Modal Sandbox                │ │
    │  │                              │ │
    ├──▶ trajectory.json (growing)    │ │
    │  │ {                            │ │
    │  │   messages: [                │ │
    │  │     {msg1},  ◀─ append       │ │
    │  │     {msg2},  ◀─ append       │ │
    │  │     {msg3},  ◀─ append       │ │
    │  │     ...                      │ │
    │  │   ]                          │ │
    │  │ }                            │ │
    │  └──────────────────────────────┘ │
    │                                    │
    │ (Frontend cannot see this yet!)   │
    │                                    │
    │                                    ▼
    │                         sandbox.download_file()
    │                                    │
    │                                    ▼
    │                         /tmp/yudai/trajectories/
    │                         repo_123_456.traj.json
    │                                    │
    │                                    ▼
    │                         Update SolveRun.trajectory_data
    │                                    │
    │                                    ▼
    │                         Frontend GET /solve/status/123
    │                                    │
    │                                    ▼
    │                         TrajectoryViewer shows FINAL result
```

### Planned Implementation (SSE Streaming - MSWEA Arena)

```
┌────────────────────────────────────────────────────────────────┐
│ PLANNED: Stream trajectory during execution (every 2s)         │
└────────────────────────────────────────────────────────────────┘

TIME ──▶

Agent Start           t=2s      t=4s      t=6s      Agent Complete
    │                  │         │         │              │
    │  ┌───────────────┴─────────┴─────────┴────────────┐ │
    │  │ Modal Sandbox                                   │ │
    │  │ /home/user/trajectory.json (growing)            │ │
    │  │                                                 │ │
    ├──▶ {messages: [{msg1}]}                            │ │
    │  │      ▲                                          │ │
    │  │      │ sandbox.read_file() ← Poll every 2s     │ │
    │  │      ▼                                          │ │
    │  │ Frontend fetches partial trajectory             │ │
    │  │ TrajectoryViewer.append([msg1])                 │ │
    │  │                                                 │ │
    │  │ {messages: [{msg1}, {msg2}, {msg3}]}           │ │
    │  │      ▲                                          │ │
    │  │      │ sandbox.read_file() ← Poll every 2s     │ │
    │  │      ▼                                          │ │
    │  │ Frontend fetches new messages                   │ │
    │  │ TrajectoryViewer.append([msg2, msg3])           │ │
    │  │                                                 │ │
    │  │ ...                                             │ │
    │  │                                                 │ │
    │  │ {messages: [...], info: {exit_status: "done"}} │ │
    │  │      ▲                                          │ │
    │  │      │ Final read                               │ │
    │  │      ▼                                          │ │
    │  │ Frontend shows complete trajectory              │ │
    │  └─────────────────────────────────────────────────┘ │
    │                                                       │
    └───────────────────────────────────────────────────────┘

New Endpoint Needed:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GET /api/daifu/solve/trajectories/{solve_run_id}
  - While status=RUNNING: read partial trajectory from sandbox
  - When status=COMPLETED: return cached trajectory from DB
  - Return: { messages: [...], complete: boolean }
```

---

## Summary

### Component Responsibilities

| Component | Responsibility | State | I/O |
|-----------|---------------|-------|-----|
| **Frontend** | UI, polling, display | React state + TanStack Query cache | HTTP requests |
| **Backend API** | Request handling, DB operations | PostgreSQL records | FastAPI endpoints |
| **SolverManager** | Orchestration, artifact generation | Solve + SolveRun DB | Calls HeadlessSandboxExecutor |
| **AgentScriptGen** | String template substitution | Stateless | Params → (tfbd.yaml, run_agent.py) |
| **HeadlessSandboxExecutor** | Modal sandbox lifecycle | Ephemeral sandbox | Modal SDK calls |
| **Modal Sandbox** | Isolated agent execution | Container filesystem | run_agent.py execution |
| **run_agent.py** | Agent execution orchestration | Mini-swe-agent state | Writes trajectory.json |

### Key State Transitions

```
User Intent
    ↓
Frontend State (local)
    ↓
Backend API Request
    ↓
Database State (Solve.status, SolveRun.status)
    ↓
Modal Sandbox State (created → running → destroyed)
    ↓
Trajectory File State (growing → complete)
    ↓
Database State (trajectory_data, pr_url updated)
    ↓
Frontend Poll Response
    ↓
UI Update (TrajectoryViewer)
```

### Data Flow Layers

```
Layer 1: User Interaction
  └─▶ React components (clicks, forms)

Layer 2: Client State
  └─▶ Zustand stores, TanStack Query cache

Layer 3: HTTP Transport
  └─▶ REST API (JSON payloads)

Layer 4: Server Business Logic
  └─▶ FastAPI routes, SolverManager

Layer 5: Database Persistence
  └─▶ PostgreSQL (Solve, SolveRun, AIModel tables)

Layer 6: Cloud Execution
  └─▶ Modal sandbox (ephemeral)

Layer 7: External APIs
  └─▶ OpenRouter (LLM), GitHub (issues, PRs)
```

---

**END OF ARCHITECTURE FLOW DOCUMENTATION**
