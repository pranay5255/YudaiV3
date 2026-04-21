"""
Helpers for generating the on-the-fly mini-swe-agent execution script.

Uses mini-swe-agent Python bindings directly:
- DefaultAgent.run(task) returns a dict {"exit_status": ..., "submission": ...}
- output_path= on DefaultAgent auto-saves trajectory after each step
- LocalEnvironment(cwd=..., env=...) sets working directory and env vars
- get_model(input_model_name=..., config=...) selects model class by name

The generated script loads mswea's builtin "mini" config for system/instance
templates, overrides step_limit and cost_limit from user params, then runs
the agent. PR creation is handled separately by build_pr_script (Phase 2 bash).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Mapping, Optional

# Stdout markers for controller-brokered solve streaming
# (consolidated from solve_stream_protocol.py)
TRAJECTORY_UPDATE_PREFIX = "__YUDAI_TRAJECTORY_UPDATE__"
SOLVE_RESULT_PREFIX = "__YUDAI_SOLVE_RESULT__"


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class AgentScriptParams:
    """
    Fully normalized parameters required to render the agent script.

    These values typically come from the StartSolveRequest payload (solve/start
    endpoint) but can be constructed from any mapping (e.g. persisted Solve.matrix).
    """

    model_name: str
    repo_url: str
    branch_name: str
    issue_url: str
    issue_text: Optional[str] = None
    issue_title: Optional[str] = None
    issue_body: Optional[str] = None
    verbose: bool = False
    temperature: float = 0.1
    max_tokens: int = 4000
    max_iterations: int = 50
    max_cost: float = 10.0
    small_change: bool = False
    best_effort: bool = False

    @classmethod
    def from_payload(
        cls,
        *,
        model_name: str,
        repo_url: str,
        branch_name: str,
        issue_url: str,
        issue_text: Optional[str] = None,
        payload: Optional[Mapping[str, Any]] = None,
        verbose: bool = False,
    ) -> "AgentScriptParams":
        payload = payload or {}
        return cls(
            model_name=model_name,
            repo_url=repo_url,
            branch_name=branch_name,
            issue_url=issue_url,
            issue_text=issue_text if isinstance(issue_text, str) else None,
            issue_title=payload.get("issue_title") if isinstance(payload.get("issue_title"), str) else None,
            issue_body=payload.get("issue_body") if isinstance(payload.get("issue_body"), str) else None,
            verbose=verbose,
            temperature=_safe_float(payload.get("temperature"), 0.1),
            max_tokens=_safe_int(payload.get("max_tokens"), 4000),
            max_iterations=_safe_int(payload.get("max_iterations"), 50),
            max_cost=_safe_float(payload.get("max_cost"), 10.0),
            small_change=_safe_bool(payload.get("small_change")),
            best_effort=_safe_bool(payload.get("best_effort")),
        )

    @classmethod
    def from_env(
        cls,
        *,
        model_name: str,
        repo_url: str,
        branch_name: str,
        issue_url: str,
        issue_text: Optional[str] = None,
        env: Optional[Mapping[str, Any]] = None,
        verbose: bool = False,
    ) -> "AgentScriptParams":
        env = env or {}
        normalized_payload = {
            "temperature": env.get("TEMPERATURE"),
            "max_tokens": env.get("MAX_TOKENS"),
            "max_iterations": env.get("MAX_ITERATIONS"),
            "max_cost": env.get("MAX_COST"),
            "small_change": env.get("SMALL_CHANGE"),
            "best_effort": env.get("BEST_EFFORT"),
        }
        return cls.from_payload(
            model_name=model_name,
            repo_url=repo_url,
            branch_name=branch_name,
            issue_url=issue_url,
            issue_text=issue_text,
            payload=normalized_payload,
            verbose=verbose,
        )

    @property
    def log_level(self) -> str:
        return "DEBUG" if self.verbose else "INFO"

    @property
    def task_literal(self) -> str:
        """JSON literal keeps the script ASCII-safe regardless of the issue text."""
        if not self.issue_text:
            return "None"
        return json.dumps(self.issue_text, ensure_ascii=True)

    @property
    def owner(self) -> str:
        parts = self.repo_url.split("github.com/")[-1].strip("/").replace(".git", "").split("/")
        return parts[0] if len(parts) >= 2 else ""

    @property
    def repo_name(self) -> str:
        parts = self.repo_url.split("github.com/")[-1].strip("/").replace(".git", "").split("/")
        return parts[1] if len(parts) >= 2 else ""

    @property
    def issue_number(self) -> str:
        return self.issue_url.rstrip("/").split("/")[-1] if self.issue_url else "0"

    def substitutions(self) -> Mapping[str, Any]:
        return {
            "log_level": self.log_level,
            "task_literal": self.task_literal,
            "model_name": self.model_name,
            "repo_literal": json.dumps(self.repo_url, ensure_ascii=True),
            "branch_literal": json.dumps(self.branch_name, ensure_ascii=True),
            "issue_url_literal": json.dumps(self.issue_url, ensure_ascii=True),
            "temperature": f"{self.temperature:.3f}",
            "max_tokens": str(self.max_tokens),
            "step_limit": str(self.max_iterations),
            "cost_limit": f"{self.max_cost:.2f}",
            "small_change": "True" if self.small_change else "False",
            "best_effort": "True" if self.best_effort else "False",
            "trajectory_update_prefix_literal": json.dumps(
                TRAJECTORY_UPDATE_PREFIX, ensure_ascii=True
            ),
            "solve_result_prefix_literal": json.dumps(
                SOLVE_RESULT_PREFIX, ensure_ascii=True
            ),
        }


# ---------------------------------------------------------------------------
# Script template — uses the correct mini-swe-agent Python bindings:
#
#   agent.run(task)  →  dict {"exit_status": str, "submission": str}
#   exit_status == "Submitted"  means the agent completed successfully
#   output_path= on DefaultAgent auto-saves trajectory after every step
#   get_model(input_model_name=..., config=...)  selects the model class
#   LocalEnvironment(cwd=..., env=...)  sets working dir and env vars
# ---------------------------------------------------------------------------

_SCRIPT_TEMPLATE = """\
#!/usr/bin/env python3
'''
Mini-SWE-Agent execution script for headless sandbox execution.
Generated automatically by YudaiV3 solver manager.

API contract (mini-swe-agent Python bindings):
  agent.run(task)  ->  dict with "exit_status" and "submission"
  exit_status == "Submitted"  on success (agent echoed COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT)
  exit_status == "LimitsExceeded"  if step/cost limit hit
  output_path on DefaultAgent  auto-saves trajectory after each step
'''
import json
import logging
import os
import contextlib
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

import requests

logging.basicConfig(
    level=logging.%(log_level)s,
    format="[%%(levelname)s] %%(message)s",
)
logger = logging.getLogger("yudai.solver.script")

# === Injected parameters ===
REPO_URL         = %(repo_literal)s
BRANCH_NAME      = %(branch_literal)s
ISSUE_URL        = %(issue_url_literal)s
MODEL_NAME       = "%(model_name)s"
ISSUE_TEXT_GIVEN = %(task_literal)s
TEMPERATURE      = %(temperature)s
MAX_TOKENS       = %(max_tokens)s
STEP_LIMIT       = %(step_limit)s   # 0 = unlimited
COST_LIMIT       = %(cost_limit)s
SMALL_CHANGE     = %(small_change)s
BEST_EFFORT      = %(best_effort)s

TRAJECTORY_UPDATE_PREFIX = %(trajectory_update_prefix_literal)s
SOLVE_RESULT_PREFIX     = %(solve_result_prefix_literal)s
WORKSPACE_PATH          = Path(os.getenv("WORKSPACE_PATH", "/workspace/repo"))
OUTPUT_PATH             = Path(
    os.getenv("TRAJECTORY_PATH", "/workspace/trajectory.json")
)

# Env vars forwarded into every subshell the agent runs
_AGENT_ENV = {
    "PAGER": "cat",
    "MANPAGER": "cat",
    "LESS": "-R",
    "PIP_PROGRESS_BAR": "off",
    "TQDM_DISABLE": "1",
}


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

def emit_marker(prefix: str, payload: dict) -> None:
    print(prefix + json.dumps(payload, ensure_ascii=True), flush=True)


def _load_trajectory() -> Optional[dict]:
    if not OUTPUT_PATH.exists():
        return None
    data = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def start_trajectory_watcher() -> tuple[threading.Event, threading.Thread]:
    stop_event = threading.Event()
    state = {"message_count": 0, "fingerprint": None}

    def publish(force: bool = False) -> None:
        trajectory = _load_trajectory()
        if not trajectory:
            return

        messages = trajectory.get("messages", [])
        info = trajectory.get("info", {})
        if not isinstance(messages, list):
            messages = []
        if not isinstance(info, dict):
            info = {}

        current_count = len(messages)
        try:
            fingerprint = (OUTPUT_PATH.stat().st_mtime_ns, current_count)
        except FileNotFoundError:
            return

        if not force and fingerprint == state["fingerprint"]:
            return

        start_index = state["message_count"]
        if current_count < start_index:
            start_index = 0

        new_messages = messages[start_index:]
        if not new_messages and not force:
            state["fingerprint"] = fingerprint
            return

        emit_marker(
            TRAJECTORY_UPDATE_PREFIX,
            {
                "messages": new_messages,
                "info": info,
                "message_count": current_count,
                "new_message_start_index": start_index,
            },
        )
        state["message_count"] = current_count
        state["fingerprint"] = fingerprint

    def _watch_loop() -> None:
        while not stop_event.wait(0.25):
            with contextlib.suppress(Exception):
                publish()
        with contextlib.suppress(Exception):
            publish(force=True)

    thread = threading.Thread(
        target=_watch_loop,
        name="trajectory-watcher",
        daemon=True,
    )
    thread.start()
    return stop_event, thread


# ---------------------------------------------------------------------------
# Repository setup
# ---------------------------------------------------------------------------

def _setup_git_credentials() -> None:
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token or "github.com" not in REPO_URL:
        return
    netrc = Path.home() / ".netrc"
    netrc.write_text(f"machine github.com login x-token password {github_token}\\n")
    netrc.chmod(0o600)


def clone_repository() -> None:
    _setup_git_credentials()

    if (WORKSPACE_PATH / ".git").exists():
        # Sandbox reuse: repo already cloned from a previous solve run.
        # Fetch latest and reset to the target branch.
        logger.info("Repo exists at %%s — fetching and resetting to %%s", WORKSPACE_PATH, BRANCH_NAME)
        fetch = subprocess.run(
            ["git", "fetch", "--all", "--prune"],
            cwd=str(WORKSPACE_PATH), capture_output=True, text=True,
        )
        if fetch.returncode != 0:
            logger.warning("git fetch failed: %%s", fetch.stderr)

        # Clean working tree and reset to branch HEAD
        subprocess.run(["git", "checkout", "-f", BRANCH_NAME or "main"],
                        cwd=str(WORKSPACE_PATH), capture_output=True, text=True)
        subprocess.run(["git", "reset", "--hard", f"origin/{BRANCH_NAME or 'main'}"],
                        cwd=str(WORKSPACE_PATH), capture_output=True, text=True)
        subprocess.run(["git", "clean", "-fdx"],
                        cwd=str(WORKSPACE_PATH), capture_output=True, text=True)
        logger.info("Workspace reset to origin/%%s", BRANCH_NAME or "main")
        return

    repo_url = REPO_URL
    clone_cmd = ["git", "clone", "--depth", "1"]
    if BRANCH_NAME:
        clone_cmd.extend(["--branch", BRANCH_NAME])
    if not repo_url.endswith(".git"):
        repo_url += ".git"
    WORKSPACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    clone_cmd.extend([repo_url, str(WORKSPACE_PATH)])

    logger.info("Cloning repository: %%s", REPO_URL)
    result = subprocess.run(clone_cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Failed to clone repository: {result.stderr}")
    logger.info("Repository cloned to %%s", WORKSPACE_PATH)


# ---------------------------------------------------------------------------
# Issue text resolution
# ---------------------------------------------------------------------------

def fetch_github_issue(issue_url: str) -> str:
    api_url = issue_url.replace("github.com", "api.github.com/repos")
    headers = {"Accept": "application/vnd.github.v3+json"}
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers["Authorization"] = f"token {github_token}"
    resp = requests.get(api_url, headers=headers, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    title = data.get("title", "No title")
    body = data.get("body", "")
    return f"GitHub Issue: {title}\\n\\n{body}"


def resolve_task() -> str:
    if ISSUE_TEXT_GIVEN:
        logger.info("Using provided issue text")
        return ISSUE_TEXT_GIVEN
    if ISSUE_URL:
        logger.info("Fetching GitHub issue from: %%s", ISSUE_URL)
        return fetch_github_issue(ISSUE_URL)
    raise RuntimeError("No task or issue URL provided")


# ---------------------------------------------------------------------------
# Constraint injection (appended to instance_template before agent init)
# ---------------------------------------------------------------------------

def _build_constraint_block() -> str:
    lines = []
    if SMALL_CHANGE:
        lines.append("- Limit code edits to minimal, targeted changes directly tied to the issue.")
    if BEST_EFFORT:
        lines.append("- Continue working toward a solution even if automated checks fail, documenting any failures.")
    if not lines:
        return ""
    return "\\n\\n## Constraints\\n\\n" + "\\n".join(lines)


# ---------------------------------------------------------------------------
# Main execution using mini-swe-agent Python bindings
# ---------------------------------------------------------------------------

def main() -> int:
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError("OPENROUTER_API_KEY environment variable required")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    clone_repository()
    task = resolve_task()
    stop_event, watcher = start_trajectory_watcher()

    # --- Load builtin mini-swe-agent config for system/instance templates ---
    from minisweagent.run.utilities.config import get_config_from_spec
    config = get_config_from_spec("mini")

    agent_cfg   = config.get("agent", {})
    env_cfg     = config.get("environment", {}).get("env", {})
    model_cfg   = config.get("model", {})

    # Merge our env additions on top of the builtin env
    merged_env = {**env_cfg, **_AGENT_ENV}

    # Append constraint block to instance_template if needed
    instance_template = agent_cfg.get("instance_template", "")
    constraint_block  = _build_constraint_block()
    if constraint_block:
        instance_template = instance_template.rstrip() + constraint_block

    # --- Model ---
    # get_model selects OpenRouterModel when model_class="openrouter"
    # The config dict (minus model_class) is forwarded to the constructor.
    from minisweagent.models import get_model

    model_init_cfg = {
        "model_class": "openrouter",
        # model_kwargs are passed through to the OpenRouter API call
        "model_kwargs": {
            "temperature": TEMPERATURE,
            "max_tokens": MAX_TOKENS,
        },
        **{k: v for k, v in model_cfg.items() if k not in ("model_name", "model_class", "model_kwargs")},
    }
    model = get_model(input_model_name=MODEL_NAME, config=model_init_cfg)
    logger.info("Model initialised: %%s", MODEL_NAME)

    # --- Environment ---
    from minisweagent.environments.local import LocalEnvironment

    env = LocalEnvironment(
        cwd=str(WORKSPACE_PATH),
        env=merged_env,
    )
    logger.info("LocalEnvironment cwd=%%s", WORKSPACE_PATH)

    # --- Agent ---
# output_path causes DefaultAgent.save() to be called after every step,
# so the trajectory file is written incrementally and the watcher thread
# can emit controller-consumable trajectory markers during the run.
    from minisweagent.agents.default import DefaultAgent

    agent = DefaultAgent(
        model,
        env,
        system_template=agent_cfg.get("system_template", "You are a helpful assistant."),
        instance_template=instance_template,
        step_limit=STEP_LIMIT,    # 0 = unlimited
        cost_limit=COST_LIMIT,
        output_path=OUTPUT_PATH,  # auto-save after each step
    )
    logger.info("Agent initialised (step_limit=%%s cost_limit=%%s)", STEP_LIMIT, COST_LIMIT)

    # --- Run ---
    # agent.run() returns {"exit_status": str, "submission": str}
    # "Submitted"     -> agent echoed COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT (success)
    # "LimitsExceeded"-> step or cost limit hit
    # Any exception class name -> unhandled error
    logger.info("Executing agent...")
    try:
        result = agent.run(task)
    finally:
        stop_event.set()
        watcher.join(timeout=2)

    exit_status = result.get("exit_status", "")
    submission = result.get("submission", "")
    emit_marker(
        SOLVE_RESULT_PREFIX,
        {
            "exit_status": exit_status,
            "submission": submission,
            "trajectory_path": str(OUTPUT_PATH),
        },
    )

    logger.info("Agent finished: exit_status=%%s", exit_status)

    succeeded = exit_status == "Submitted"
    if succeeded:
        print(f"\\n✓ Agent completed successfully")
        print(f"Submission: {submission}")
        print(f"Trajectory saved to: {OUTPUT_PATH}")
        return 0
    else:
        print(f"\\n✗ Agent finished with status: {exit_status}")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        logger.error("Script failed: %%s", exc, exc_info=True)
        sys.exit(1)
"""


def build_agent_script(params: AgentScriptParams) -> str:
    """Render the agent execution script with the given parameters."""
    return _SCRIPT_TEMPLATE % params.substitutions()


def build_pr_script(params: AgentScriptParams) -> str:
    """
    Generate a bash script that creates a PR with issue context, diff stats,
    and trajectory metadata (Phase 2, runs in the same sandbox after agent completes).
    """
    owner        = params.owner
    repo         = params.repo_name
    issue_number = params.issue_number
    branch_name  = params.branch_name
    model_name   = params.model_name
    issue_url    = params.issue_url
    repo_url     = params.repo_url

    fallback_title = (params.issue_title or "").replace("'", "'\\''")
    fallback_body  = (params.issue_body or "").replace("'", "'\\''")[:500]

    timestamp = int(time.time())
    pr_branch = f"yudai/fix-issue-{issue_number}-{timestamp}"

    return f"""\
#!/usr/bin/env bash
set -euo pipefail

OWNER='{owner}'
REPO='{repo}'
ISSUE_NUMBER='{issue_number}'
BASE_BRANCH='{branch_name}'
MODEL_NAME='{model_name}'
ISSUE_URL='{issue_url}'
REPO_URL='{repo_url}'
PR_BRANCH='{pr_branch}'
TESTBED='${{WORKSPACE_PATH:-/workspace/repo}}'
TRAJ_PATH='${{TRAJECTORY_PATH:-/workspace/trajectory.json}}'

FALLBACK_TITLE='{fallback_title}'
FALLBACK_BODY='{fallback_body}'

cd "$TESTBED"

# ── Step 1: Authenticate gh CLI ──
echo "$GITHUB_TOKEN" | gh auth login --with-token 2>/dev/null || true

# ── Step 2: Fetch issue context via gh ──
ISSUE_JSON=$(gh issue view "$ISSUE_NUMBER" --repo "$OWNER/$REPO" \\
    --json title,body,comments,labels 2>/dev/null || echo '{{}}')

ISSUE_TITLE=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
print(data.get('title', '${{FALLBACK_TITLE}}'))
" <<< "$ISSUE_JSON" 2>/dev/null || echo "$FALLBACK_TITLE")

ISSUE_BODY_EXCERPT=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
body = data.get('body', '${{FALLBACK_BODY}}') or ''
print(body[:500])
" <<< "$ISSUE_JSON" 2>/dev/null || echo "$FALLBACK_BODY")

ISSUE_LABELS=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
labels = data.get('labels', [])
names = [l.get('name', '') for l in labels if isinstance(l, dict)]
print(', '.join(names) if names else 'none')
" <<< "$ISSUE_JSON" 2>/dev/null || echo "none")

TOP_COMMENTS=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
comments = data.get('comments', [])[:3]
for c in comments:
    author = c.get('author', {{}}).get('login', 'unknown')
    body = (c.get('body', '') or '')[:200]
    print(f'> **@{{author}}**: {{body}}')
    print()
" <<< "$ISSUE_JSON" 2>/dev/null || echo "")

# ── Step 3: Diff statistics ──
DIFF_STAT=$(git diff --stat 2>/dev/null || echo "No changes")
DIFF_FILES=$(git diff --name-only 2>/dev/null || echo "")
DIFF_SHORT=$(git diff --shortstat 2>/dev/null || echo "0 files changed")
FILES_CHANGED_COUNT=$(echo "$DIFF_FILES" | grep -c '.' 2>/dev/null || echo "0")

# ── Step 4: Trajectory metadata ──
TRAJ_STATS=$(python3 -c "
import json, sys
try:
    with open('$TRAJ_PATH', 'r') as f:
        data = json.load(f)
    info = data.get('info', {{}})
    model_stats = info.get('model_stats', {{}})
    messages = data.get('messages', [])
    print(f'Exit status: {{info.get(\"exit_status\", \"unknown\")}}')
    print(f'API calls: {{model_stats.get(\"api_calls\", \"N/A\")}}')
    print(f'Cost: \\${{model_stats.get(\"instance_cost\", \"N/A\")}}')
    print(f'Total messages: {{len(messages)}}')
except Exception as e:
    print(f'Trajectory parsing failed: {{e}}')
" 2>/dev/null || echo "Trajectory data unavailable")

# ── Step 5: Check for changes ──
if [ -z "$(git status --porcelain)" ]; then
    echo "ERROR: No changes detected. Nothing to commit."
    exit 1
fi

# ── Step 6: Git config, branch, commit ──
git config user.name "Yudai Agent"
git config user.email "agent@yudai.dev"

git checkout -b "$PR_BRANCH"
git add -A

COMMIT_MSG="fix: resolve #${{ISSUE_NUMBER}} — ${{ISSUE_TITLE}}

Automated fix generated by Yudai Agent (${{MODEL_NAME}}).
Issue: ${{ISSUE_URL}}

${{DIFF_SHORT}}"

git commit -m "$COMMIT_MSG"

# ── Step 7: Push using .netrc credential (no token in URL) ──
git push -u origin "$PR_BRANCH"

# ── Step 8: Create PR ──
PR_BODY="## Summary

fix: resolve #${{ISSUE_NUMBER}} — ${{ISSUE_TITLE}}

### Issue Context

**Title:** ${{ISSUE_TITLE}}
**Labels:** ${{ISSUE_LABELS}}

${{ISSUE_BODY_EXCERPT}}

### Top Comments
${{TOP_COMMENTS}}

### Diff Statistics

\\`\\`\\`
${{DIFF_STAT}}
\\`\\`\\`

**Files changed:** ${{FILES_CHANGED_COUNT}}
${{DIFF_SHORT}}

### Agent Trajectory

\\`\\`\\`
${{TRAJ_STATS}}
\\`\\`\\`

**Model:** ${{MODEL_NAME}}

---
*This PR was automatically generated by [Yudai](https://github.com/pranay5255/YudaiV3)*"

gh pr create \\
    --repo "$OWNER/$REPO" \\
    --title "fix: resolve #${{ISSUE_NUMBER}} — ${{ISSUE_TITLE}}" \\
    --body "$PR_BODY" \\
    --base "$BASE_BRANCH" \\
    --head "$PR_BRANCH"

echo "Phase 2: PR creation complete."
"""
