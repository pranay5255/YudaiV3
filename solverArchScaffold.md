Perfect—let’s drop Anyscale entirely and still **steal the parallel-experiments pattern**. Below is a concrete, FastAPI-native plan that runs **mini-SWE-agent** inside **Prime Sandboxes**, fanned out in parallel with simple Python concurrency (and optional workers) so every GitHub issue can spawn multiple experiments (different LLMs / prompts / “evolution” tweaks) at once. ([Prime Sandboxes Overview][1])

---

# 1) Core architecture (no Ray/Anyscale)

**FastAPI (YudaiV3 backend)**

* `POST /solve`: accepts repo + issue + experiment matrix → enqueues a “Solve” record.
* `SolveRunner`: expands the matrix and launches **N parallel Prime Sandboxes** (bounded by a concurrency limit) where each run executes **mini-SWE-agent** against that issue and validates with tests.
* `ResultReducer`: selects the best result (tests green, smallest diff, shortest latency), opens/links the PR, stores per-run metrics.

**Prime Sandboxes**

* Each experiment creates a fresh sandbox using the **Prime CLI** (disposable Docker environment). You create/list/run/delete sandboxes via CLI and execute arbitrary commands inside them. Example:

```
# Create
prime sandbox create python:3.11-slim --timeout-minutes 120

# See what is active
prime sandbox list

# Try a quick command
prime sandbox run <sandbox-id> "python --version"

# Clean up when you're done
prime sandbox delete <sandbox-id>
```

See pricing (CPU/mem/disk) and current GPU status in docs. ([Prime Sandboxes Overview][1])

**mini-SWE-agent**

* Invoke via shell inside the sandbox; it’s intentionally tiny/portable and works anywhere with bash or a container runtime. ([mini-swe-agent.com][2])

---

# 2) Prime Sandbox setup (one-time)

Prime Sandboxes are disposable Docker environments. Use an image like `python:3.11-slim` and install needed tools per run. Ensure you have an API key and are logged in (`prime login`). Pricing at the time of writing: CPU $0.05/core/hr, Memory $0.01/GB/hr, Disk $0.001/GB/hr; GPU support is on the roadmap. ([Prime Sandboxes Overview][1])

Minimal bootstrap inside a newly created sandbox:

```bash
prime sandbox run <sandbox-id> "bash -lc 'apt-get update && apt-get install -y git gh build-essential jq ripgrep curl && rm -rf /var/lib/apt/lists/*'"
prime sandbox run <sandbox-id> "bash -lc 'python -m pip install -U pip pytest'"
prime sandbox run <sandbox-id> "bash -lc 'npm -g i npm && npm -g i pnpm || true'"
```

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

Use **`asyncio` + a semaphore** in your FastAPI worker to bound parallelism; each task controls its own Prime Sandbox via the Prime CLI.

**Skeleton (Python, using Prime CLI)**

```python
import asyncio, os, time, json, shlex

PRIME_BIN = os.environ.get("PRIME_BIN", "prime")  # path to prime CLI

async def run_shell(cmd: str) -> dict:
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return {"code": proc.returncode, "out": stdout.decode(), "err": stderr.decode()}

async def prime_create(image: str, timeout_minutes: int) -> str:
    res = await run_shell(f"{PRIME_BIN} sandbox create {shlex.quote(image)} --timeout-minutes {timeout_minutes}")
    if res["code"] != 0:
        raise RuntimeError(f"prime create failed: {res['err'] or res['out']}")
    # assume last non-empty line contains the sandbox id
    lines = [l.strip() for l in res["out"].splitlines() if l.strip()]
    return lines[-1]

async def prime_run(sbx_id: str, command: str) -> dict:
    return await run_shell(f"{PRIME_BIN} sandbox run {shlex.quote(sbx_id)} \"bash -lc {shlex.quote(command)}\"")

async def prime_delete(sbx_id: str) -> None:
    await run_shell(f"{PRIME_BIN} sandbox delete {shlex.quote(sbx_id)}")

async def run_experiment(cfg, gh_token: str, timeout_minutes: int = 120) -> dict:
    t0 = time.time()
    sbx_id = await prime_create("python:3.11-slim", timeout_minutes)
    try:
        # bootstrap tools
        await prime_run(sbx_id, "apt-get update && apt-get install -y git gh build-essential jq ripgrep curl && rm -rf /var/lib/apt/lists/*")
        await prime_run(sbx_id, "python -m pip install -U pip pytest")
        await prime_run(sbx_id, "bash -lc 'command -v npm >/dev/null 2>&1 || curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs' || true")
        await prime_run(sbx_id, "npm -g i npm && npm -g i pnpm || true")

        # clone repo and prepare
        await prime_run(sbx_id, f"git clone {shlex.quote(cfg.repo_url)} repo && cd repo && git checkout {shlex.quote(cfg.base_branch)}")
        await prime_run(sbx_id, "cd repo && if [ -f requirements.txt ]; then pip install -r requirements.txt; fi")
        await prime_run(sbx_id, "cd repo && if [ -f package.json ]; then (pnpm i || npm ci); fi")

        # smoke tests
        smoke = await prime_run(sbx_id, "cd repo && (pytest -q || npm test --silent || true)")

        # mini-SWE-agent
        await prime_run(sbx_id, "cd / && rm -rf mini && git clone https://github.com/SWE-agent/mini-swe-agent mini && cd mini && pip install -e .")
        agent_cmd = (
            "cd repo && "
            "MSWEA_MODEL_NAME=\"%s\" "
            "GITHUB_TOKEN=\"%s\" "
            "../mini/bin/mini -m \"%s\" -- "
            "--issue %s --base \"%s\" --branch \"ai/fix-%s-%s\""
        ) % (cfg.model, gh_token, cfg.model, cfg.issue_number, cfg.base_branch, cfg.issue_number, cfg.run_id)
        agent_res = await prime_run(sbx_id, agent_cmd)

        # validate
        tests = await prime_run(sbx_id, "cd repo && (pytest -q || npm test --silent)")
        passed = tests["code"] == 0
        pr_url = ""
        if passed:
            await prime_run(sbx_id, "cd repo && git config user.email bot@yudai.app && git config user.name yudai-bot")
            await prime_run(sbx_id, "cd repo && git add -A && git commit -m '[AI] Fix from mini-SWE-agent' || true")
            await prime_run(sbx_id, "cd repo && git push origin HEAD")
            pr = await prime_run(sbx_id, f"cd repo && gh pr create -t '[AI] Fix: #{cfg.issue_number}' -b 'Automated fix' -B {shlex.quote(cfg.base_branch)}")
            pr_url = (pr["out"].strip() if pr["out"].strip() else pr["err"].strip())

        return {
            "passed": passed,
            "pr_url": pr_url,
            "latency_ms": int((time.time() - t0) * 1000),
            "logs": {
                "smoke": smoke["out"][-2000:],
                "agent": agent_res["out"][-4000:] or agent_res["err"][-4000:],
                "tests": tests["out"][-2000:] or tests["err"][-2000:],
            },
        }
    finally:
        await prime_delete(sbx_id)

async def run_matrix(matrix, limit: int, gh_token: str):
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

### Simple mini-SWE-agent script and plan

Plan:

1. Install and configure mini-SWE-agent defaults once (`mini-extra config setup`) and set `MSWEA_MODEL_NAME` or pass `-m` per run. ([mini-swe-agent quickstart][10])
2. Provide a tiny script that clones the repo, runs mini against a GitHub issue, and exits non-zero if tests fail.
3. Use the script inside each Prime Sandbox run to standardize invocation.

Script (bash):

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_URL="$1"          # e.g., https://github.com/owner/repo
ISSUE_NUMBER="$2"      # e.g., 123
BASE_BRANCH="${3:-main}"
MODEL_NAME="${4:-${MSWEA_MODEL_NAME:-openai/gpt-5-mini}}"

echo "[mini-run] repo=$REPO_URL issue=$ISSUE_NUMBER base=$BASE_BRANCH model=$MODEL_NAME"

git clone "$REPO_URL" repo
cd repo
git checkout "$BASE_BRANCH"

if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
if [ -f package.json ]; then (pnpm i || npm ci); fi

cd /
rm -rf mini && git clone https://github.com/SWE-agent/mini-swe-agent mini && cd mini && pip install -e .

cd /repo
../mini/bin/mini -m "$MODEL_NAME" -- --issue "$ISSUE_NUMBER" --base "$BASE_BRANCH" --branch "ai/fix-$ISSUE_NUMBER-$(date +%s)"

# Validate
cd /repo
pytest -q || npm test --silent
```

---

# 6) Selecting the “champion” PR

Reducer heuristic (simple, effective):

1. tests pass; 2) **fewest files changed**; 3) **smallest diff**; 4) lowest latency.
   Tie? Prefer stable model (e.g., low-T GPT-4.1) and put the rest as “alternate attempts” on the Solve detail page.

---

# 7) Ops, security, and cost controls

* **Concurrency & TTL**: bound parallel sandboxes per user/solve; destroy sandboxes as soon as runs finish. Prime sandboxes are billed while running; keep TTLs tight. ([Prime Sandboxes Overview][1])
* **Secrets**: inject GH / model keys as env at runtime; never bake into the template.
* **Isolation**: sandboxes are disposable Docker environments—ideal for untrusted, AI-generated code. ([Prime Sandboxes Overview][1])
* **Monitoring**: store the last N KB of stdout/stderr for smoke/tests/agent; when failures happen, show these in YudaiV3’s UI.
* **Budgets**: enforce per-run timeouts via sandbox `--timeout-minutes` and job-level deadlines. ([Prime Sandboxes Overview][1])
* **Pricing/GPU**: CPU $0.05/core/hr; Memory $0.01/GB/hr; Disk $0.001/GB/hr. GPU support is on the roadmap; current sandboxes are CPU-only. ([Prime Sandboxes Overview][1])

---

# 8) “Experiment matrix” knobs (what to try first)

* **Models**: `gpt-4.1`, `claude-3.7-sonnet`, and your local Solo-Server model.
* **Temps**: `{0.2, 0.6}` (deterministic vs creative fix).
* **Max micro-edits**: `{3,5}`.
* **Evolution tags**: `test-first`, `stacktrace-first`, `small-steps` (used only to adjust a short strategy string your wrapper passes to mini-SWE-agent).

---

# 9) Prime CLI snippets you’ll actually use

* **Create a sandbox**: `prime sandbox create python:3.11-slim --timeout-minutes 120`
* **List sandboxes**: `prime sandbox list`
* **Run a shell command**: `prime sandbox run <sandbox-id> "bash -lc 'git clone ...'"`
* **Delete a sandbox**: `prime sandbox delete <sandbox-id>`
  See the Sandboxes Overview and CLI guide links there. ([Prime Sandboxes Overview][1])

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

* **FastAPI** receives “Solve” → **async fan-out** N experiments → each experiment spins a **Prime Sandbox** → runs **mini-SWE-agent** → tests → publishes a PR if green → reducer picks a champion → YudaiV3 shows results.
* No Anyscale, no Ray—just **Prime Sandboxes (CLI)** + **mini-SWE-agent** + a **lean asyncio semaphore** (and you can later drop the same runner into Celery/RQ if you outgrow a single node).
* Everything above is directly supported by Prime’s Sandboxes (create/list/run/delete via CLI) and mini-SWE-agent’s portability. ([Prime Sandboxes Overview][1])

If you want, I can turn this into:

* a **FastAPI router** (`/solve`, `/solve/{id}/status`) and
* a **production-ready `SolveRunner` module** (with retries, timeouts, and metrics)
  —just say “code it (Python).”

[1]: https://docs.primeintellect.ai/sandboxes/overview "Prime Sandboxes Overview"
[2]: https://mini-swe-agent.com/?utm_source=chatgpt.com "Overview - mini-SWE-agent documentation"
[7]: https://swe-agent.com/latest/usage/?utm_source=chatgpt.com "User guides"
[10]: https://mini-swe-agent.com/latest/models/quickstart/#__tabbed_1_3 "Model setup quickstart - mini-SWE-agent"
