Perfect—let’s drop Anyscale entirely and still **steal the parallel-experiments pattern**. Below is a concrete, FastAPI-native plan that runs **mini-SWE-agent** inside **Prime RL sandboxes**, fanned out in parallel with simple Python concurrency (and optional workers) so every GitHub issue can spawn multiple experiments (different LLMs / prompts / "evolution" tweaks) at once.

---

# 1) Core architecture (no Ray/Anyscale)

**FastAPI (YudaiV3 backend)**

* `POST /solve`: accepts repo + issue + experiment matrix → enqueues a "Solve" record.
* `SolveRunner`: expands the matrix and launches **N parallel Prime RL sandboxes** (bounded by a concurrency limit) where each run executes **mini-SWE-agent** against that issue and validates with tests.
* `ResultReducer`: selects the best result (tests green, smallest diff, shortest latency), opens/links the PR, stores per-run metrics.

**Prime RL Sandboxes**

* Each experiment creates a fresh sandbox using the **Prime RL sandbox API** with custom Docker images (git, gh CLI, pytest/jest, build tools are available). You start/stop sandboxes, run shell commands, and read/write files via the Prime RL Python SDK. ([Prime RL Docs][1])

**mini-SWE-agent**

* Invoke via shell inside the sandbox; it’s intentionally tiny/portable and works anywhere with bash or a container runtime. ([mini-swe-agent.com][2])

---

# 2) Prime RL Docker image (one-time setup)

Create `Dockerfile` for your sandbox image:

```dockerfile
FROM python:3.11-slim
# essentials
RUN apt-get update && apt-get install -y git gh build-essential jq ripgrep curl && rm -rf /var/lib/apt/lists/*
# python & node test tooling (keep lean; rely on repo's lockfiles)
RUN pip install -U pip pytest && npm -g i npm && npm -g i pnpm
# (optional) install mini-swe-agent deps if any; otherwise just git-clone per run
```

Build & push your Docker image:
```bash
docker build -t your-registry/yudai-solver:latest .
docker push your-registry/yudai-solver:latest
```

Notes:

* Use standard Docker images as the base and include all tools you need for repo operations.
* You can pin Python/Node versions and include any necessary build tools.
* The **start command** can be set when creating sandboxes to run background processes.

---

# 3) FastAPI endpoints and job model

**Request**

```json
POST /solve
{
  "repo_url": "https://github.com/owner/repo",
  "issue_number": 123,
  "base_branch": "main",
  "matrix": {
    "models": ["gpt-4.1", "claude-3.7-sonnet", "local-solo"],
    "temps": [0.2, 0.6],
    "max_edits": [3, 5],
    "evolution": ["test-first","stacktrace-first","small-steps"]
  },
  "limits": {"max_parallel": 6, "time_budget_s": 1800}
}
```

**Data tables**

* `solves(id, repo, issue, base_branch, status, created_at, ...)`
* `solve_runs(id, solve_id, model, temp, max_edits, evolution, status, pr_url, tests_passed, loc_changed, files_changed, tokens, latency_ms, logs_url, ...)`

---

# 4) Parallel execution pattern (pure Python, no external queue required)

Use **`asyncio` + a semaphore** in your FastAPI worker to bound parallelism; each task controls its own Prime RL sandbox.

**Skeleton (Python)**

```python
import asyncio, os, time
from prime_sandboxes import AsyncSandboxClient, CreateSandboxRequest, APIError

DOCKER_IMAGE = os.environ["PRIME_SANDBOX_IMAGE"]  # your-registry/yudai-solver:latest

async def run_experiment(cfg, gh_token):
    t0 = time.time()
    async with AsyncSandboxClient() as sandbox_client:
        # Create sandbox
        request = CreateSandboxRequest(
            name=f"yudai-solver-{cfg.issue_number}-{cfg.run_id}",
            docker_image=DOCKER_IMAGE,
            start_command="tail -f /dev/null",
            cpu_cores=2,
            memory_gb=4,
            timeout_minutes=60,
        )
        sandbox = await sandbox_client.create(request)

        try:
            # Wait for sandbox to be ready
            await sandbox_client.wait_for_creation(sandbox.id, max_attempts=60)

            # 1) Set environment and pull repo
            await sandbox_client.execute_command(sandbox.id, f"export GITHUB_TOKEN={gh_token}")
            await sandbox_client.execute_command(sandbox.id, f"git clone {cfg.repo_url} repo && cd repo && git checkout {cfg.base_branch}")

            # 2) Install deps (python OR node auto-detect)
            await sandbox_client.execute_command(sandbox.id, "cd repo && if [ -f requirements.txt ]; then pip install -r requirements.txt; fi")
            await sandbox_client.execute_command(sandbox.id, "cd repo && if [ -f package.json ]; then npm ci || pnpm i; fi")

            # 3) Quick smoke tests
            smoke_result = await sandbox_client.execute_command(sandbox.id, "cd repo && (pytest -q || npm test --silent || true)")

            # 4) mini-SWE-agent: fetch & run
            await sandbox_client.execute_command(sandbox.id, "cd / && rm -rf mini && git clone https://github.com/SWE-agent/mini-swe-agent mini")
            cmd = (
                f'cd repo && ../mini/bin/mini-swe '
                f'--issue {cfg.issue_number} '
                f'--model "{cfg.model}" --temperature {cfg.temp} '
                f'--max-edits {cfg.max_edits} --strategy "{cfg.evolution}" '
                f'--base "{cfg.base_branch}" --branch "ai/fix-{cfg.issue_number}-{cfg.run_id}"'
            )
            agent_result = await sandbox_client.execute_command(sandbox.id, cmd)

            # 5) Validate
            test_result = await sandbox_client.execute_command(sandbox.id, "cd repo && (pytest -q || npm test --silent)")
            passed = test_result.exit_code == 0

            pr_url = ""
            if passed:
                # 6) Publish PR
                await sandbox_client.execute_command(sandbox.id, "cd repo && git config user.email bot@yudai.app && git config user.name yudai-bot")
                await sandbox_client.execute_command(sandbox.id, "cd repo && git add -A && git commit -m '[AI] Fix from mini-SWE-agent'")
                await sandbox_client.execute_command(sandbox.id, "cd repo && git push origin HEAD")
                pr_result = await sandbox_client.execute_command(sandbox.id, f'cd repo && gh pr create -t "[AI] Fix: #{cfg.issue_number}" -b "Automated fix" -B {cfg.base_branch}')
                pr_url = pr_result.stdout.strip()

            # 7) Get logs for debugging
            logs = await sandbox_client.get_logs(sandbox.id)

            # 8) Metrics
            return {
                "passed": passed, "pr_url": pr_url,
                "latency_ms": int((time.time()-t0)*1000),
                "logs": logs[-4000:]  # Last 4KB of logs
            }
        finally:
            # Cleanup sandbox
            await sandbox_client.delete(sandbox.id)
```

Key Prime RL behaviors used above: **create sandbox, wait for creation, execute commands, get logs, delete sandbox**—all first-class SDK features.

Then orchestrate runs:

```python
async def run_matrix(matrix, limit, gh_token):
    sem = asyncio.Semaphore(limit)
    async def guarded(cfg):
        async with sem:
            return await run_experiment(cfg, gh_token)
    tasks = [guarded(cfg) for cfg in expand_matrix(matrix)]
    return await asyncio.gather(*tasks, return_exceptions=False)
```

> This gives you simple, horizontally scalable fan-out without extra infra. If you prefer a queue, drop the same `run_experiment` into **Celery/RQ** workers later (identical sandbox flow).

---

# 5) mini-SWE-agent specifics

* The project is purposefully **minimal**—great for your evolutionary variants and per-run tweaks. It targets “solve a GitHub issue” and works anywhere with bash/container runtime. ([mini-swe-agent.com][2])
* For heavier features (multi-tool orchestration, broader config), you can later swap to **SWE-agent**; its CLI & docs cover config, PR automation, etc., but keep V1 on mini for speed. ([swe-agent.com][7])

---

# 6) Selecting the “champion” PR

Reducer heuristic (simple, effective):

1. tests pass; 2) **fewest files changed**; 3) **smallest diff**; 4) lowest latency.
   Tie? Prefer stable model (e.g., low-T GPT-4.1) and put the rest as “alternate attempts” on the Solve detail page.

---

# 7) Ops, security, and cost controls

* **Concurrency & TTL**: bound parallel sandboxes per user/solve; destroy sandboxes as soon as runs finish. Prime RL gives you precise lifecycle control with configurable timeouts.
* **Secrets**: inject GH / model keys as env at runtime; never bake into the Docker image.
* **Isolation**: sandboxes run as **isolated containers** with an exposed command API—ideal for untrusted, AI-generated code.
* **Monitoring**: store logs retrieved via `get_logs()` for smoke/tests/agent; when failures happen, show these in YudaiV3's UI.
* **Budgets**: enforce per-run timeouts with `timeout_minutes` parameter and per-solve max runtime.

---

# 8) “Experiment matrix” knobs (what to try first)

* **Models**: `gpt-4.1`, `claude-3.7-sonnet`, and your local Solo-Server model.
* **Temps**: `{0.2, 0.6}` (deterministic vs creative fix).
* **Max micro-edits**: `{3,5}`.
* **Evolution tags**: `test-first`, `stacktrace-first`, `small-steps` (used only to adjust a short strategy string your wrapper passes to mini-SWE-agent).

---

# 9) Prime RL SDK snippets you'll actually use

* **Create a sandbox**: `await sandbox_client.create(CreateSandboxRequest(...))`
* **Wait for creation**: `await sandbox_client.wait_for_creation(sandbox_id, max_attempts=60)`
* **Run a shell command**: `await sandbox_client.execute_command(sandbox_id, "git clone ...")`
* **Get logs**: `await sandbox_client.get_logs(sandbox_id)`
* **Delete sandbox**: `await sandbox_client.delete(sandbox_id)`
  All are documented in Prime RL's SDK documentation.

---

# 10) PR body template (helps reviewers)

Include a tiny scorecard:

```
### YudaiV3 Auto-Fix
- ✅ Tests: PASS
- ⏱️ Latency: {{latency_ms}} ms
- 🧠 Model: {{model}} (T={{temp}})
- 🧩 Files changed: {{n_files}} | LOC: {{loc}}
- 🧪 Command: {{test_cmd}}
- 🔁 Strategy: {{evolution}}
```

---

## TL;DR

* **FastAPI** receives "Solve" → **async fan-out** N experiments → each experiment spins a **Prime RL sandbox** → runs **mini-SWE-agent** → tests → publishes a PR if green → reducer picks a champion → YudaiV3 shows results.
* No Anyscale, no Ray—just **Prime RL** + **mini-SWE-agent** + a **lean asyncio semaphore** (and you can later drop the same runner into Celery/RQ if you outgrow a single node).
* Everything above is directly supported by Prime RL's SDK (create sandboxes, run commands, manage lifecycle, handle timeouts) and mini-SWE-agent's portability.

If you want, I can turn this into:

* a **FastAPI router** (`/solve`, `/solve/{id}/status`) and
* a **production-ready `SolveRunner` module** (with retries, timeouts, and metrics)
  —just say "code it (Python)."

[1]: https://docs.prime-rl.com "Prime RL Documentation"
[2]: https://mini-swe-agent.com/?utm_source=chatgpt.com "Overview - mini-SWE-agent documentation"
