# MSWEA Arena MVP: Diagrams & State Flows

Last updated: 2026-02-12  
Scope: current MVP implementation (parallel contestants, winner selection, 2s trajectory polling, docker-compose prod deployment)

## 1) System Topology

```mermaid
flowchart LR
    U[User]
    FE[React UI<br/>SolveIssues + TrajectoryViewer]
    API[FastAPI Router<br/>/api/daifu/sessions/*/solve/*]
    MGR[DefaultSolverManager]
    DB[(PostgreSQL<br/>Solve / SolveRun / AuthToken)]
    EXE[HeadlessSandboxExecutor<br/>per run]
    E2B[E2B Sandbox]
    GH[GitHub API]
    OR[OpenRouter API]
    RT[/Sandbox Trajectory<br/>/home/user/last_mini_run.traj.json/]
    LT[/Local Trajectory Cache<br/>/tmp/yudai/trajectories/]

    U --> FE
    FE --> API
    API --> MGR
    MGR --> DB
    MGR --> EXE
    EXE --> E2B
    E2B --> GH
    E2B --> OR
    E2B --> RT
    EXE --> LT
    API --> DB
```

## 2) Arena Start + Parallel Execution + Polling

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as Solve Router
    participant MGR as SolverManager
    participant DB as PostgreSQL
    participant EX as Sandbox Executor(s)
    participant E2B as E2B Sandboxes

    User->>FE: Start Arena (issue + models + strategies)
    FE->>API: POST /solve/start
    API->>MGR: start_solve()
    MGR->>DB: Create Solve + SolveRun rows
    MGR-->>API: solve_id (pending)
    API-->>FE: StartSolveResponse

    par Contestant Run A
        MGR->>EX: _execute_run(run A)
        EX->>E2B: Create sandbox + run agent
    and Contestant Run B
        MGR->>EX: _execute_run(run B)
        EX->>E2B: Create sandbox + run agent
    and Contestant Run N
        MGR->>EX: _execute_run(run N)
        EX->>E2B: Create sandbox + run agent
    end

    loop Every 2s (while solve active)
        FE->>API: GET /solve/status/{solve_id}
        API->>MGR: get_status()
        MGR->>DB: Read solve/runs/champion
        API-->>FE: SolveStatusResponse

        FE->>API: GET /solve/trajectory/{solve_id}/{run_id}
        API->>MGR: get_trajectory()
        MGR->>EX: read_live_trajectory() if run running
        MGR->>DB: fallback metadata/local path
        API-->>FE: SolveTrajectoryResponse
    end
```

## 3) Solve Session State Machine

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> running: first run starts
    pending --> cancelled: user cancel

    running --> running: some runs still pending/running
    running --> completed: all runs resolved AND champion exists
    running --> failed: all runs resolved AND no champion
    running --> cancelled: user cancel

    completed --> [*]
    failed --> [*]
    cancelled --> [*]
```

## 4) SolveRun State Machine (per contestant)

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> running: executor launched
    pending --> cancelled: user cancel before start

    running --> completed: exit_code == 0
    running --> failed: sandbox error OR exit_code != 0
    running --> cancelled: user cancel

    completed --> [*]
    failed --> [*]
    cancelled --> [*]
```

## 5) Trajectory Source Resolution Flow

```mermaid
flowchart TD
    A[GET /solve/trajectory/{solve_id}/{run_id}] --> B{Run status is pending/running?}
    B -- No --> F{Local trajectory exists?}
    B -- Yes --> C{Live executor present?}
    C -- Yes --> D{Live read succeeds?}
    D -- Yes --> E[Return source=live_sandbox<br/>is_live=true]
    D -- No --> F
    C -- No --> F
    F -- Yes --> G[Load local file<br/>source=local_cache]
    F -- No --> H[Return empty trajectory<br/>source=none]
```

## 6) Champion Selection (MVP Heuristic)

```mermaid
flowchart TD
    A[Run finishes] --> B{exit_code == 0 ?}
    B -- No --> C[Mark run failed]
    B -- Yes --> D[Mark run completed]
    D --> E{solve.champion_run_id exists?}
    E -- No --> F[Set champion_run_id = this run]
    E -- Yes --> G[Keep existing champion]
    C --> H[Finalize solve if all runs done]
    F --> H
    G --> H
```

## 7) Cancellation Flow

```mermaid
sequenceDiagram
    actor User
    participant FE as Frontend
    participant API as Solve Router
    participant MGR as SolverManager
    participant EX as Active Executors
    participant DB as PostgreSQL

    User->>FE: Cancel solve
    FE->>API: POST /solve/cancel/{solve_id}
    API->>MGR: cancel_solve()
    MGR->>EX: cancel() all active executors
    MGR->>DB: Mark solve + unresolved runs cancelled
    API-->>FE: CancelSolveResponse
```

## 8) docker-compose.prod Runtime Flow

```mermaid
flowchart LR
    Client[Browser]
    Nginx[Frontend Container<br/>nginx]
    Backend[Backend Container<br/>FastAPI]
    DB[(DB Container<br/>PostgreSQL)]
    Ext1[E2B API]
    Ext2[OpenRouter API]
    Ext3[GitHub API]

    Client -->|HTTPS 443| Nginx
    Nginx -->|/api/*| Backend
    Backend --> DB
    Backend --> Ext1
    Backend --> Ext2
    Backend --> Ext3
```

## 9) Operational Notes for Reading the Flows

- UI polling cadence for both solve status and trajectory is 2 seconds.
- Live trajectory can be partial while sandbox is still writing JSON.
- If live sandbox read is unavailable, API falls back to local cached trajectory.
- Arena is parallelized with bounded concurrency (`SOLVER_MAX_PARALLEL` and arena run caps).
- Winner logic in MVP is first successful run to set champion.
