Perfect—let’s drop Anyscale entirely and still **steal the parallel-experiments pattern**. Below is a concrete, FastAPI-native plan that runs **mini-SWE-agent** inside **E2B sandboxes**, fanned out in parallel with simple Python concurrency (and optional workers) so every GitHub issue can spawn multiple experiments (different LLMs / prompts / “evolution” tweaks) at once.

---

# 1) Core architecture (no Ray/Anyscale)

**FastAPI (YudaiV3 backend)**

* `POST /solve`: accepts repo + issue + experiment matrix → enqueues a “Solve” record.
* `SolveRunner`: expands the matrix and launches **N parallel E2B sandboxes** (bounded by a concurrency limit) where each run executes **mini-SWE-agent** against that issue and validates with tests.
* `ResultReducer`: selects the best result (tests green, smallest diff, shortest latency), opens/links the PR, stores per-run metrics.

**E2B Sandboxes**

* Each experiment creates a fresh sandbox from your **custom E2B template** built on `e2bdev/code-interpreter` (so git, gh CLI, pytest/jest, build tools are available). You start/stop sandboxes, run shell commands, and read/write files via the E2B Python SDK. ([E2B][1])

**mini-SWE-agent**

* Invoke via shell inside the sandbox; it’s intentionally tiny/portable and works anywhere with bash or a container runtime. ([mini-swe-agent.com][2])

---

# 2) E2B template (one-time setup)

Create `e2b.Dockerfile`:

```dockerfile
FROM e2bdev/code-interpreter:latest
# essentials
RUN apt-get update && apt-get install -y git gh build-essential jq ripgrep curl && rm -rf /var/lib/apt/lists/*
# python & node test tooling (keep lean; rely on repo’s lockfiles)
RUN pip install -U pip pytest && npm -g i npm && npm -g i pnpm
# (optional) install mini-swe-agent deps if any; otherwise just git-clone per run
```

Build & publish your template (E2B turns this image into a micro-VM template):
`e2b template build -c "/root/.jupyter/start-up.sh"` ([GitHub][3])

Notes:

* `e2bdev/code-interpreter` is the official base and exposes the SDK entrypoints/filesystem/commands you need. ([GitHub][4])
* You can pin a Python variant image like `python-3.12.8` if you need. ([Docker Hub][5])
* A **start command** is supported if you want background processes running on spawn. ([E2B][6])

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

Use **`asyncio` + a semaphore** in your FastAPI worker to bound parallelism; each task controls its own E2B sandbox.

**Skeleton (Python)**

```python
import asyncio, os, time
from e2b_code_interpreter import Sandbox  # pip install e2b-code-interpreter
E2B_API_KEY = os.environ["E2B_API_KEY"]  # set from env per docs

async def run_experiment(cfg, gh_token, template_id):
    t0 = time.time()
    sbx = await Sandbox.create(template_id=template_id, api_key=E2B_API_KEY)  # spawn sandbox
    try:
        await sbx.files.write("/root/.env", f"GITHUB_TOKEN={gh_token}")
        # 1) pull repo/checkout
        await sbx.commands.run(f"git clone {cfg.repo_url} repo && cd repo && git checkout {cfg.base_branch}")
        # 2) install deps (python OR node auto-detect)
        await sbx.commands.run("cd repo && if [ -f requirements.txt ]; then pip install -r requirements.txt; fi")
        await sbx.commands.run("cd repo && if [ -f package.json ]; then npm ci || pnpm i; fi")
        # 3) quick smoke tests
        smoke = await sbx.commands.run("cd repo && (pytest -q || npm test --silent || true)")
        # 4) mini-SWE-agent: fetch & run
        await sbx.commands.run("cd / && rm -rf mini && git clone https://github.com/SWE-agent/mini-swe-agent mini")
        cmd = (
          f'cd repo && ../mini/bin/mini-swe '
          f'--issue {cfg.issue_number} '
          f'--model "{cfg.model}" --temperature {cfg.temp} '
          f'--max-edits {cfg.max_edits} --strategy "{cfg.evolution}" '
          f'--base "{cfg.base_branch}" --branch "ai/fix-{cfg.issue_number}-{cfg.run_id}"'
        )
        agent_res = await sbx.commands.run(cmd)
        # 5) validate
        tests = await sbx.commands.run("cd repo && (pytest -q || npm test --silent)")
        passed = tests.exit_code == 0
        pr_url = ""
        if passed:
            # 6) publish PR
            await sbx.commands.run("cd repo && git config user.email bot@yudai.app && git config user.name yudai-bot")
            await sbx.commands.run("cd repo && git add -A && git commit -m '[AI] Fix from mini-SWE-agent'")
            await sbx.commands.run("cd repo && git push origin HEAD")
            pr = await sbx.commands.run(f'cd repo && gh pr create -t "[AI] Fix: #{cfg.issue_number}" -b "Automated fix" -B {cfg.base_branch}')
            pr_url = pr.stdout.strip()
        # 7) metrics
        return {
            "passed": passed, "pr_url": pr_url,
            "latency_ms": int((time.time()-t0)*1000),
            "logs": {"smoke": smoke.stdout[-2000:], "agent": agent_res.stdout[-4000:], "tests": tests.stdout[-2000:]}
        }
    finally:
        await sbx.close()
```

Key E2B behaviors used above: **create sandbox, run commands, read/write files, kill/timeouts if needed**—all first-class SDK features. ([E2B][1])

Then orchestrate runs:

```python
async def run_matrix(matrix, limit, gh_token, template_id):
    sem = asyncio.Semaphore(limit)
    async def guarded(cfg):
        async with sem:
            return await run_experiment(cfg, gh_token, template_id)
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

* **Concurrency & TTL**: bound parallel sandboxes per user/solve; destroy sandboxes as soon as runs finish. E2B gives you precise lifecycle control. ([E2B][8])
* **Secrets**: inject GH / model keys as env at runtime; never bake into the template.
* **Isolation**: sandboxes run as **isolated micro-VMs** with an exposed filesystem/command API—ideal for untrusted, AI-generated code. ([E2B][1])
* **Monitoring**: store the last N KB of stdout/stderr for smoke/tests/agent; when failures happen, show these in YudaiV3’s UI.
* **Budgets**: enforce per-run timeouts (E2B lets you kill commands by PID) and per-solve max runtime. ([E2B][9])

---

# 8) “Experiment matrix” knobs (what to try first)

* **Models**: `gpt-4.1`, `claude-3.7-sonnet`, and your local Solo-Server model.
* **Temps**: `{0.2, 0.6}` (deterministic vs creative fix).
* **Max micro-edits**: `{3,5}`.
* **Evolution tags**: `test-first`, `stacktrace-first`, `small-steps` (used only to adjust a short strategy string your wrapper passes to mini-SWE-agent).

---

# 9) E2B SDK snippets you’ll actually use

* **Create a sandbox**: `Sandbox.create(template_id="tmpl_...")`
* **Run a shell command**: `await sbx.commands.run("git clone ...")`
* **Write files**: `await sbx.files.write(path, content)`
* **Run Python code directly** (optional): `await sbx.run_code("print('hi')")`
  All are documented in E2B’s quickstart, commands, python-SDK, and language pages. ([E2B][8])

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

* **FastAPI** receives “Solve” → **async fan-out** N experiments → each experiment spins an **E2B sandbox** → runs **mini-SWE-agent** → tests → publishes a PR if green → reducer picks a champion → YudaiV3 shows results.
* No Anyscale, no Ray—just **E2B** + **mini-SWE-agent** + a **lean asyncio semaphore** (and you can later drop the same runner into Celery/RQ if you outgrow a single node).
* Everything above is directly supported by E2B’s SDK (create sandboxes, run commands, manage files, kill long-running commands) and mini-SWE-agent’s portability. ([E2B][1])

If you want, I can turn this into:

* a **FastAPI router** (`/solve`, `/solve/{id}/status`) and
* a **production-ready `SolveRunner` module** (with retries, timeouts, and metrics)
  —just say “code it (Python).”

[1]: https://e2b.dev/docs?utm_source=chatgpt.com "E2B Documentation - Code Interpreting for AI apps"
[2]: https://mini-swe-agent.com/?utm_source=chatgpt.com "Overview - mini-SWE-agent documentation"
[3]: https://github.com/e2b-dev/code-interpreter/blob/main/template/README.md?utm_source=chatgpt.com "code-interpreter/template/README.md at main - GitHub"
[4]: https://github.com/e2b-dev/code-interpreter?utm_source=chatgpt.com "e2b-dev/code-interpreter: Python & JS/TS SDK for running ... - GitHub"
[5]: https://hub.docker.com/layers/e2bdev/code-interpreter/python-3.12.8/images/sha256-9d5f81fff62a6ada2fcb1b7fcf14d08f6f2fcfd4706476057af7c4905eba614f?utm_source=chatgpt.com "Image Layer Details - e2bdev/code-interpreter:python ... - Docker Hub"
[6]: https://e2b.dev/docs/sandbox-template/start-cmd?utm_source=chatgpt.com "Start command - E2B - Code Interpreting for AI apps"
[7]: https://swe-agent.com/latest/usage/?utm_source=chatgpt.com "User guides"
[8]: https://e2b.dev/docs/quickstart?utm_source=chatgpt.com "Running your first Sandbox"
[9]: https://e2b.dev/docs/sdk-reference/python-sdk/v1.0.2/sandbox_sync?utm_source=chatgpt.com "E2B - Code Interpreting for AI apps"
