# Parallel Agent Execution — Sandbox Design & Provisioning

## Date
March 6, 2026

## Scope

Design and implementation details for running two coordinated mini-swe-agent instances
(Tester + Coder) inside a Modal sandbox, including:

- Sandbox provisioning fixes required to run the server
- Git worktree isolation strategy for parallel agents
- Agent config design for each role
- Execution pipeline and handoff mechanism
- Template variable injection model

---

## 1. Sandbox Provisioning Fixes

### Problem: Missing packages in Modal image

The sandbox runs `run_sandbox_server.py` inside a Modal container built from
`_get_realtime_sandbox_image()` in `backend/realtime/modal_sandbox.py`.

`run_sandbox_server.py` imports `db.database` → `db/__init__.py` imports `models.py`
→ `models.py` line 38 does `from pgvector.sqlalchemy import Vector`.

The original Modal image only installed 10 packages and was missing `pgvector`
and `psycopg2-binary`, causing an immediate crash on container startup before
uvicorn could bind.

**Fix applied to `_get_realtime_sandbox_image()`:**

```python
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "curl", "libpq-dev", "gcc")   # libpq-dev + gcc added
    .pip_install(
        "fastapi",
        "uvicorn[standard]",
        "httpx",
        "sqlalchemy",
        "pydantic",
        "pyyaml",
        "requests",
        "websockets",
        "python-jose[cryptography]",
        "passlib",
        "pgvector",           # added — required by models.py
        "psycopg2-binary",    # added — required by SQLAlchemy + PostgreSQL
    )
    .env({"PYTHONPATH": "/app/backend"})
)
```

### Problem: DATABASE_URL not forwarded to sandbox

`db/database.py` raises a `ValueError` at module load time if neither
`DATABASE_URL` nor `CONTROLLER_DATABASE_URL` is set. The sandbox env dict never
forwarded the DB connection string from the controller host.

**Fix applied to `RealtimeModalSandbox.create()`:**

```python
controller_database_url = os.getenv("DATABASE_URL") or os.getenv("CONTROLLER_DATABASE_URL")
if controller_database_url:
    sandbox_env["CONTROLLER_DATABASE_URL"] = controller_database_url
```

The sandbox server picks it up via `db/database.py`:
```python
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("CONTROLLER_DATABASE_URL")
```

---

## 2. Two-Agent Architecture

### Roles

| Agent | Role | Input | Output |
|---|---|---|---|
| **Tester** | Write/extend test suite | GitHub issue | Test files committed to `tester/{issue_num}` branch |
| **Coder** | Implement to pass tests + fulfill issue | GitHub issue + test diff | Implementation committed to `coder/{issue_num}` branch |

### Why not truly parallel?

The Coder depends on the Tester's output. Running both simultaneously would require
the Coder to either start without tests (weakening TDD guarantees) or poll/wait for
the Tester's branch. The wall-clock difference between chained and truly-parallel is
minimal because the Tester completes fast (test writing only). The pipeline is:

```
Tester runs ──────────────────▶ Handoff ──▶ Coder runs
  (fast, ~5-15 min)                           (longer, ~20-45 min)

Total = Tester + Coder
vs.
Truly parallel = max(Tester, Coder)   ← saves ~5-15 min at high complexity cost
```

The complexity cost of true parallelism (branch polling, mid-run merges, conflict
resolution) is not worth the small time saving at this stage.

---

## 3. Git Worktree Isolation

Multiple agent instances cannot safely share the same working directory. Concurrent
`git add/commit`, file edits, and test runs on the same path cause race conditions and
git state corruption.

**Solution: one git worktree per agent.**

Git worktrees share the `.git` object store (deduplication of blobs/trees) but give
each agent a fully independent working tree, index, and HEAD.

### Filesystem layout inside the sandbox

```
/workspace/
  repo/                         ← primary clone (main branch, read-only reference)
  worktrees/
    tester-{session_id}/        ← branch: tester/{issue_number}
    coder-{session_id}/         ← branch: coder/{issue_number}
```

### Setup commands

```bash
# Clone once
git clone {repo_url} /workspace/repo --branch {base_branch}

# Create isolated worktrees
git -C /workspace/repo worktree add /workspace/worktrees/tester-{id} -b tester/{issue_num}
git -C /workspace/repo worktree add /workspace/worktrees/coder-{id}  -b coder/{issue_num}
```

### What each agent owns

| Resource | Shared | Per-agent |
|---|---|---|
| `.git` object store (blobs, trees, commits) | ✅ | |
| Working tree files | | ✅ |
| Git index | | ✅ |
| HEAD / branch ref | | ✅ |
| Trajectory output file | | ✅ |

---

## 4. Execution Pipeline

```
POST /sandbox/solve-issue
  { session_id, issue_number, issue_title, issue_body, repo_url, repo_branch }
  │
  ▼
SETUP
  ├── clone repo → /workspace/repo
  ├── create tester worktree → /workspace/worktrees/tester-{id}
  └── create coder worktree  → /workspace/worktrees/coder-{id}
  │
  ▼
TESTER PHASE  (async subprocess)
  ├── spawn: mini -y -c tester.yaml
  │     env: MSWEA_MODEL_NAME, ANTHROPIC_API_KEY
  │     runtime override: environment.cwd=/workspace/worktrees/tester-{id}
  │     python api: agent.run(task="", issue_number=N, issue_title=..., issue_body=...)
  ├── stream stdout → WebSocket → client
  └── detect: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
  │
  ▼
HANDOFF
  ├── git diff main...tester/{issue_num} -- > /tmp/test.diff
  ├── git -C /workspace/worktrees/coder-{id} merge tester/{issue_num} --no-edit
  └── read /tmp/test.diff → inject as {{test_diff}} template var
  │
  ▼
CODER PHASE  (async subprocess)
  ├── spawn: mini -y -c coder.yaml
  │     runtime override: environment.cwd=/workspace/worktrees/coder-{id}
  │     python api: agent.run(task="", issue_number=N, issue_title=...,
  │                           issue_body=..., test_diff=<diff_string>)
  ├── stream stdout → WebSocket → client
  └── detect: echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT
  │
  ▼
PR CREATION
  ├── push branch: coder/{issue_num}
  ├── gh pr create --base {base_branch} --head coder/{issue_num}
  └── emit pr_url → WebSocket → client
  │
  ▼
CLEANUP
  ├── git worktree remove /workspace/worktrees/tester-{id}
  └── git worktree remove /workspace/worktrees/coder-{id}
```

### WebSocket event stream

```json
{ "phase": "setup",   "event": "worktrees_ready" }
{ "phase": "tester",  "event": "running", "stdout": "..." }
{ "phase": "tester",  "event": "complete", "commit": "abc123" }
{ "phase": "handoff", "event": "tests_merged", "test_diff": "..." }
{ "phase": "coder",   "event": "running", "stdout": "..." }
{ "phase": "coder",   "event": "complete", "commit": "def456" }
{ "phase": "pr",      "event": "opened", "pr_url": "https://github.com/..." }
```

---

## 5. Agent Config Design

Config files live at `backend/configs/tester.yaml` and `backend/configs/coder.yaml`.

### Action format

Both configs use the `mswea_bash_command` backtick block format (from `mini.yaml`
style, not tool-call style). This works universally across all model classes and
with both the CLI and Python API.

```
```mswea_bash_command
your_command_here
```
```

### Template variable injection

Custom variables are passed via the Python API at runtime. `{{cwd}}` is provided
automatically by `LocalEnvironment.get_template_vars()`.

```python
# Tester
agent.run(
    task="",
    issue_number=42,
    issue_title="Add rate limiting to /api/users",
    issue_body="...",
)

# Coder
agent.run(
    task="",
    issue_number=42,
    issue_title="Add rate limiting to /api/users",
    issue_body="...",
    test_diff="...",   # git diff output from tester branch
)
```

### Tester config key decisions

| Decision | Rationale |
|---|---|
| Hard constraints before workflow | LLMs weight early content; constraints must come first |
| "Tests fail because impl is missing, NOT because of SyntaxError" | Most common failure mode — tester writes tests that error out instead of failing cleanly |
| Git stage verification before commit | Forces `git diff --name-only` check so agent can't accidentally commit source changes |
| `step_limit: 80, cost_limit: 2.5` | Tester only writes tests — 80 steps is generous, $2.50 cap keeps it cheap |
| `timeout: 120` | Test runs and pip installs exceed default 30s timeout |

### Coder config key decisions

| Decision | Rationale |
|---|---|
| Anti-cheat rules are exhaustive and explicit | Covers every known cheating pattern: delete, skip, xfail, comment assertions, mock behavior |
| "Note it in commit message but do NOT change it" escape valve | Prevents deadlock if tester wrote a genuinely wrong test |
| Test diff shown as context, not instructions | Tests are already merged — diff is for reading, not applying |
| Incremental test loop: run one test at a time | Saves steps and cost vs running full suite on every change |
| Full suite run at the end for regression check | Ensures no pre-existing passing tests were broken |
| `step_limit: 150, cost_limit: 6.0` | Implementation is longer work; higher limits prevent premature cutoff |

### `observation_template` design

Both configs use XML tags (`<output>`, `<returncode>`, `<exception>`) which Claude
handles better than JSON or raw text. Hard truncation at 10,000 chars with head
(5,000) + tail (5,000) display prevents the agent burning steps on giant test outputs.

---

## 6. Files Created / Modified

| File | Change |
|---|---|
| `backend/realtime/modal_sandbox.py` | Added `pgvector`, `psycopg2-binary`, `libpq-dev`, `gcc` to Modal image; forwarded `CONTROLLER_DATABASE_URL` to sandbox env |
| `backend/configs/tester.yaml` | New — Tester agent config |
| `backend/configs/coder.yaml` | New — Coder agent config |

### Pending implementation

| File | Purpose |
|---|---|
| `backend/realtime/solve_runner.py` | Orchestrator: worktree setup, subprocess spawning, handoff, cleanup |
| `backend/realtime/sandbox_routes.py` | `POST /sandbox/solve-issue` endpoint + WebSocket status stream |
| `backend/realtime/modal_sandbox.py` | Add `mini-swe-agent` (forked) to Modal image pip_install |

---

## 7. Open Questions

1. **Fork integration**: The forked mini-swe-agent will be installed from its git URL.
   The Modal image will need `pip install git+https://github.com/{fork}/mini-swe-agent.git`
   instead of the PyPI package. The image rebuild is triggered on any config change.

2. **GitHub token scope**: The Coder needs push access to create branches and the PR.
   `GITHUB_TOKEN` is already forwarded to the sandbox env from `modal_sandbox.py`.

3. **Test framework detection**: Both configs assume Python/pytest. If the repo uses
   a different test framework (jest, go test, cargo test), the configs need
   framework-specific variants or a detection step in the `instance_template`.

4. **Conflict on merge**: If the tester's changes conflict with something in the coder's
   worktree (unlikely since they start from the same base), the handoff step needs
   a conflict resolution strategy.

5. **Cost tracking**: Each agent run generates separate trajectory JSON files.
   These should be stored as `SessionArtifact` records against the session.
