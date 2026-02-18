"""
Helpers for generating the on-the-fly mini-swe-agent execution script.

The solver endpoint accepts a payload (StartSolveRequest) that determines how the
agent should behave (small change mode, best effort, max iterations, etc).
This module takes that payload, normalizes the values, and renders the final
Python script by parameterizing a template with those values.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from string import Template
from typing import Any, Mapping, Optional


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
    create_pr: bool = True

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
        """
        Build params from an arbitrary payload (StartSolveRequest, Solve.matrix, env).
        """

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
            create_pr=_safe_bool(payload.get("create_pr"), default=True),
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
        """
        Convenience helper for HeadlessSandboxRequest env payloads.
        """

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
        """Extract repository owner from repo_url."""
        parts = self.repo_url.split("github.com/")[-1].strip("/").replace(".git", "").split("/")
        return parts[0] if len(parts) >= 2 else ""

    @property
    def repo_name(self) -> str:
        """Extract repository name from repo_url."""
        parts = self.repo_url.split("github.com/")[-1].strip("/").replace(".git", "").split("/")
        return parts[1] if len(parts) >= 2 else ""

    @property
    def issue_number(self) -> str:
        """Extract issue number from issue_url."""
        return self.issue_url.rstrip("/").split("/")[-1] if self.issue_url else "0"

    def substitutions(self) -> Mapping[str, Any]:
        """Values passed into the final Template.substitute call."""

        return {
            "log_level": self.log_level,
            "task_literal": self.task_literal,
            "model_name": self.model_name,
            "repo_literal": json.dumps(self.repo_url, ensure_ascii=True),
            "branch_literal": json.dumps(self.branch_name, ensure_ascii=True),
            "issue_url_literal": json.dumps(self.issue_url, ensure_ascii=True),
            "temperature": f"{self.temperature:.3f}",
            "max_tokens": str(self.max_tokens),
            "max_iterations": str(self.max_iterations),
            "max_cost": f"{self.max_cost:.2f}",
            "small_change": "True" if self.small_change else "False",
            "best_effort": "True" if self.best_effort else "False",
            "create_pr": "True" if self.create_pr else "False",
        }


_SCRIPT_TEMPLATE_STR = """#!/usr/bin/env python3
'''
Mini-SWE-Agent execution script for headless sandbox execution.
Generated automatically by YudaiV3 solver manager.
'''
import json
import logging
import os
import subprocess
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

import requests
import yaml
from minisweagent.agents.default import DefaultAgent
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models import get_model
from minisweagent.run.utils.save import save_traj

logging.basicConfig(
    level=logging.$log_level,
    format="[%(levelname)s] %(message)s"
)

CONFIG_DIR = Path("/home/user/config_mswea")
TFBD_PATH = Path("/home/user/tfbd.yaml")
TESTBED_PATH = Path("/home/user/testbed")
MINI_SWE_ROOT = Path("/home/user/mini-swe-agent")
TRAJECTORY_PATH = Path("/home/user/trajectory.json")
OUTPUT_PATH = Path("/home/user/last_mini_run.traj.json")

REPO_URL = $repo_literal
BRANCH_NAME = $branch_literal
ISSUE_URL = $issue_url_literal
MODEL_NAME = "$model_name"
ISSUE_TEXT_LITERAL = $task_literal

TEMPERATURE = $temperature
MAX_TOKENS = $max_tokens
MAX_ITERATIONS = $max_iterations
MAX_COST = $max_cost
SMALL_CHANGE = $small_change
BEST_EFFORT = $best_effort
CREATE_PR = $create_pr

SOLVE_PAYLOAD = {
    "small_change": SMALL_CHANGE,
    "best_effort": BEST_EFFORT,
    "max_iterations": MAX_ITERATIONS,
    "max_cost": MAX_COST,
    "create_pr": CREATE_PR,
}

logger = logging.getLogger("yudai.solver.script")


def _parse_openrouter_delay(value: Optional[str]) -> float:
    \"\"\"Parse OPENROUTER_CALL_DELAY from environment.\"\"\"
    if not value:
        return 0.0
    try:
        delay = float(value)
        if delay < 0:
            logger.warning(
                "OPENROUTER_CALL_DELAY must be non-negative, ignoring %s", value
            )
            return 0.0
        return delay
    except (TypeError, ValueError):
        logger.warning(
            "Invalid OPENROUTER_CALL_DELAY value '%s'; ignoring delay override", value
        )
        return 0.0


OPENROUTER_CALL_DELAY = _parse_openrouter_delay(os.getenv("OPENROUTER_CALL_DELAY"))


def fetch_github_issue(issue_url: str) -> str:
    \"\"\"Fetch GitHub issue text from the URL.\"\"\"
    if not issue_url:
        raise ValueError("GitHub issue URL is required")
    
    api_url = issue_url.replace(
        "github.com", "api.github.com/repos"
    ).replace("/issues/", "/issues/")
    
    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"token {github_token}"
    
    try:
        response = requests.get(api_url, headers=headers, timeout=60)
        response.raise_for_status()
        issue_data = response.json()
    except Exception as exc:
        logger.warning("Failed to fetch GitHub issue: %s", exc)
        raise ValueError(f"Failed to fetch GitHub issue: {exc}")
    
    title = issue_data.get("title", "No title")
    body = issue_data.get("body", "")
    
    return f"GitHub Issue: {title}\\n\\n{body}"


def load_config() -> Dict[str, Any]:
    \"\"\"Load agent configuration from tfbd.yaml.\"\"\"
    if not TFBD_PATH.exists():
        raise RuntimeError(f"Config file not found at {TFBD_PATH}")
    
    logger.info("Loading agent config from '%s'", TFBD_PATH)
    config = yaml.safe_load(TFBD_PATH.read_text())
    
    # Apply runtime overrides
    config.setdefault("agent", {})["cost_limit"] = MAX_COST
    
    # Set temperature and max_tokens inside model_kwargs (required by OpenRouterModelConfig)
    config.setdefault("model", {}).setdefault("model_kwargs", {})["temperature"] = TEMPERATURE
    config.setdefault("model", {}).setdefault("model_kwargs", {})["max_tokens"] = MAX_TOKENS

    
    return config


def clone_repository() -> None:
    \"\"\"Clone the target repository into testbed directory.\"\"\"
    if TESTBED_PATH.exists():
        logger.info("Testbed already exists at %s", TESTBED_PATH)
        return
    
    repo_url = REPO_URL
    if github_token := os.getenv("GITHUB_TOKEN"):
        if "github.com" in repo_url:
            repo_url = repo_url.replace(
                "https://github.com/", 
                f"https://{github_token}@github.com/"
            )
    
    if not repo_url.endswith(".git"):
        repo_url += ".git"
    
    clone_cmd = ["git", "clone", "--depth", "1"]
    if BRANCH_NAME:
        clone_cmd.extend(["--branch", BRANCH_NAME])
    clone_cmd.extend([repo_url, str(TESTBED_PATH)])
    
    logger.info("Cloning repository: %s", REPO_URL)
    result = subprocess.run(
        clone_cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to clone repository: {result.stderr}"
        )
    
    logger.info("Repository cloned successfully to %s", TESTBED_PATH)


def install_mini_swe_agent() -> None:
    \"\"\"Install mini-swe-agent if not already available.\"\"\"
    logger.info("Ensuring mini-swe-agent is available")
    
    if not MINI_SWE_ROOT.exists():
        logger.info("Cloning mini-swe-agent repository")
        result = subprocess.run(
            [
                "git", "clone", "--depth", "1",
                "https://github.com/pranay5255/yudai-swe-agent.git",
                str(MINI_SWE_ROOT),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to clone mini-swe-agent: {result.stderr}")
    
    logger.info("Installing mini-swe-agent")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-cache-dir", "-e", "."],
        cwd=MINI_SWE_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Failed to install mini-swe-agent: {result.stderr}")
    
    logger.info("mini-swe-agent installed successfully")


def record_success(exit_status: str, result: Any) -> None:
    \"\"\"Record successful execution results.\"\"\"
    payload = {
        "exit_status": exit_status,
        "result": str(result) if result else None,
        "trajectory_file": str(OUTPUT_PATH),
        "tfbd_path": str(TFBD_PATH),
        "repository_path": str(TESTBED_PATH),
        "solve_payload": SOLVE_PAYLOAD,
    }
    Path("/home/user/solve_success.json").write_text(
        json.dumps(payload, indent=2)
    )
    logger.info("Recorded success to /home/user/solve_success.json")


def record_failure(error: Exception) -> None:
    \"\"\"Record execution failure.\"\"\"
    payload = {
        "error": str(error),
        "traceback": traceback.format_exc(),
    }
    Path("/home/user/solve_failure.json").write_text(
        json.dumps(payload, indent=2)
    )
    logger.error("Recorded failure: %s", error)


def finalize_execution(exit_code: int) -> None:
    \"\"\"Write final execution state.\"\"\"
    summary = {
        "exit_code": exit_code,
        "completed": exit_code == 0,
    }
    Path("/home/user/solve_final_state.json").write_text(
        json.dumps(summary, indent=2)
    )
    logger.info("Execution finalized with exit code %d", exit_code)


def apply_openrouter_delay(delay: float) -> None:
    \"\"\"Apply optional throttling between OpenRouter API calls.\"\"\"
    if delay <= 0:
        return

    try:
        from minisweagent.models import openrouter_model
    except Exception as exc:
        logger.warning("Unable to apply OpenRouter delay: %s", exc)
        return

    if getattr(openrouter_model.OpenRouterModel, "_yudai_delay_wrapped", False):
        return

    original_query = openrouter_model.OpenRouterModel._query

    def delayed_query(self, *args, **kwargs):
        logger.debug(
            "Sleeping %.2fs before OpenRouter API request to avoid rate limits",
            delay,
        )
        time.sleep(delay)
        return original_query(self, *args, **kwargs)

    openrouter_model.OpenRouterModel._query = delayed_query
    setattr(openrouter_model.OpenRouterModel, "_yudai_delay_wrapped", True)
    logger.info(
        "OpenRouter API throttling enabled: %.2fs delay between calls", delay
    )


def extract_repo_info(repo_url: str) -> tuple[str, str]:
    \"\"\"Extract owner and repo name from GitHub URL.\"\"\"
    # Handle both https://github.com/owner/repo and git@github.com:owner/repo
    if "github.com/" in repo_url:
        parts = repo_url.split("github.com/")[1].strip("/").replace(".git", "").split("/")
    elif "github.com:" in repo_url:
        parts = repo_url.split("github.com:")[1].strip("/").replace(".git", "").split("/")
    else:
        raise ValueError(f"Unable to parse GitHub repo URL: {repo_url}")

    if len(parts) < 2:
        raise ValueError(f"Invalid GitHub repo URL format: {repo_url}")

    return parts[0], parts[1]


def create_pull_request(issue_url: str) -> Optional[str]:
    \"\"\"
    Create a pull request for the changes made by the agent.

    Returns:
        PR URL if successful, None otherwise
    \"\"\"
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logger.warning("GITHUB_TOKEN not set, skipping PR creation")
        return None

    try:
        # Extract owner and repo
        owner, repo = extract_repo_info(REPO_URL)
        logger.info(f"Creating PR for {owner}/{repo}")

        # Extract issue number from issue URL
        issue_number = issue_url.split("/")[-1] if issue_url else "unknown"

        # Generate unique branch name
        timestamp = int(time.time())
        branch_name = f"yudai/fix-issue-{issue_number}-{timestamp}"

        # Configure git
        logger.info("Configuring git...")
        subprocess.run(
            ["git", "config", "user.name", "Yudai Agent"],
            cwd=TESTBED_PATH,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "agent@yudai.dev"],
            cwd=TESTBED_PATH,
            check=True,
            capture_output=True,
        )

        # Check if there are any changes
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=TESTBED_PATH,
            capture_output=True,
            text=True,
            check=True,
        )

        if not status_result.stdout.strip():
            logger.warning("No changes detected, skipping PR creation")
            return None

        logger.info(f"Changes detected:\\n{status_result.stdout}")

        # Create and checkout new branch
        logger.info(f"Creating branch: {branch_name}")
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=TESTBED_PATH,
            check=True,
            capture_output=True,
        )

        # Stage all changes
        logger.info("Staging changes...")
        subprocess.run(
            ["git", "add", "-A"],
            cwd=TESTBED_PATH,
            check=True,
            capture_output=True,
        )

        # Create commit
        commit_message = f\"\"\"Fix issue #{issue_number}

Automated fix generated by Yudai Agent
Model: {MODEL_NAME}
Issue: {issue_url}

Changes made by the agent to resolve the reported issue.
\"\"\"
        logger.info("Creating commit...")
        subprocess.run(
            ["git", "commit", "-m", commit_message],
            cwd=TESTBED_PATH,
            check=True,
            capture_output=True,
        )

        # Push to remote
        remote_url = REPO_URL
        if "github.com" in remote_url and not remote_url.startswith("https://"):
            remote_url = f"https://github.com/{owner}/{repo}.git"

        # Add token to URL for authentication
        auth_url = remote_url.replace(
            "https://github.com/",
            f"https://{github_token}@github.com/"
        )

        logger.info(f"Pushing branch to remote...")
        push_result = subprocess.run(
            ["git", "push", "-u", auth_url, branch_name],
            cwd=TESTBED_PATH,
            capture_output=True,
            text=True,
            check=False,
        )

        if push_result.returncode != 0:
            logger.error(f"Failed to push branch: {push_result.stderr}")
            return None

        logger.info("Branch pushed successfully")

        # Create PR using GitHub API
        logger.info("Creating pull request via GitHub API...")
        pr_title = f"Fix: Resolve issue #{issue_number}"
        pr_body = f\"\"\"## Description
This PR contains automated fixes generated by Yudai Agent to resolve issue #{issue_number}.

## Issue
{issue_url}

## Model Used
{MODEL_NAME}

## Agent Configuration
- Small Change Mode: {SMALL_CHANGE}
- Best Effort: {BEST_EFFORT}
- Max Iterations: {MAX_ITERATIONS}

## Changes
The agent analyzed the issue and made targeted changes to resolve it. Please review the changes carefully before merging.

---
*This PR was automatically generated by [Yudai](https://github.com/pranay5255/YudaiV3)*
\"\"\"

        api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {github_token}",
        }
        data = {
            "title": pr_title,
            "body": pr_body,
            "head": branch_name,
            "base": BRANCH_NAME,
        }

        response = requests.post(api_url, headers=headers, json=data, timeout=30)

        if response.status_code == 201:
            pr_data = response.json()
            pr_url = pr_data.get("html_url")
            logger.info(f"Pull request created successfully: {pr_url}")
            print(f"\\n\\nPull Request Created: {pr_url}\\n\\n")
            return pr_url
        else:
            logger.error(f"Failed to create PR: {response.status_code} - {response.text}")
            return None

    except Exception as exc:
        logger.error(f"Error creating pull request: {exc}", exc_info=True)
        return None


def main() -> int:
    \"\"\"Execute mini-swe-agent on the GitHub issue.\"\"\"
    
    logger.info("Starting mini-swe-agent execution")
    logger.info("Solve configuration: %s", SOLVE_PAYLOAD)
    
    exit_status, result, extra_info = None, None, None
    
    try:
        # Verify API key is available
        if not os.getenv("OPENROUTER_API_KEY"):
            raise RuntimeError("OPENROUTER_API_KEY environment variable required")
        
        # Install mini-swe-agent
        install_mini_swe_agent()
        
        # Clone target repository
        clone_repository()
        
        # Determine task text
        task = None
        if ISSUE_TEXT_LITERAL and isinstance(ISSUE_TEXT_LITERAL, str):
            logger.info("Using provided issue text")
            task = ISSUE_TEXT_LITERAL
        elif ISSUE_URL:
            logger.info("Fetching GitHub issue from: %s", ISSUE_URL)
            task = fetch_github_issue(ISSUE_URL)
        else:
            raise RuntimeError("No task or issue URL provided")
        
        logger.info("Task loaded successfully")
        
        # Load configuration
        config = load_config()
        logger.info("Configuration loaded successfully")

        # Optionally slow down OpenRouter requests to mitigate rate limiting
        apply_openrouter_delay(OPENROUTER_CALL_DELAY)
        
        # Initialize model
        model = get_model(MODEL_NAME, config.get("model", {}))
        logger.info("Model initialized: %s", MODEL_NAME)
        
        # Initialize environment (LocalEnvironment for headless execution)
        env = LocalEnvironment(**config.get("env", {}))
        logger.info("Environment initialized: LocalEnvironment")
        
        # Initialize agent in yolo mode (non-interactive)
        agent_config = config.get("agent", {})
        agent = DefaultAgent(model, env, **agent_config)
        logger.info("Agent initialized with config: %s", agent_config)
        
        # Run the agent
        logger.info("Executing agent on task...")
        exit_status, result = agent.run(task)
        logger.info("Agent execution completed: %s", exit_status)
        
        # Save trajectory
        save_traj(
            agent,
            OUTPUT_PATH,
            exit_status=exit_status,
            result=result,
            extra_info=extra_info
        )
        logger.info("Trajectory saved to: %s", OUTPUT_PATH)

        # Create pull request if enabled and agent succeeded
        pr_url = None
        if CREATE_PR and exit_status == "finished":
            logger.info("Attempting to create pull request...")
            pr_url = create_pull_request(ISSUE_URL)
            if pr_url:
                logger.info(f"Pull request created: {pr_url}")
            else:
                logger.warning("Failed to create pull request")
        elif not CREATE_PR:
            logger.info("PR creation disabled, skipping...")
        else:
            logger.info("Agent did not finish successfully, skipping PR creation")

        # Record success
        record_success(exit_status, result)

        # Determine exit code
        exit_code = 0 if exit_status == "finished" else 1
        finalize_execution(exit_code)

        if exit_code == 0:
            print("\\n✓ Agent completed successfully")
            print(f"Result: {result}")
            if pr_url:
                print(f"Pull Request: {pr_url}")
        else:
            print(f"\\n✗ Agent finished with status: {exit_status}")
            print(f"Result: {result}")

        return exit_code
        
    except KeyboardInterrupt:
        logger.warning("Execution interrupted by user")
        record_failure(RuntimeError("Execution interrupted"))
        finalize_execution(130)
        return 130
        
    except Exception as exc:
        logger.error("Agent execution failed: %s", exc, exc_info=True)
        exit_status = type(exc).__name__
        result = str(exc)
        extra_info = {"traceback": traceback.format_exc()}
        
        # Attempt to save trajectory even on failure
        try:
            if OUTPUT_PATH and 'agent' in locals():
                save_traj(agent, OUTPUT_PATH, exit_status=exit_status, result=result, extra_info=extra_info)
        except Exception:
            pass
        
        record_failure(exc)
        finalize_execution(1)
        return 1


if __name__ == "__main__":
    sys.exit(main())
"""

SCRIPT_TEMPLATE = Template(_SCRIPT_TEMPLATE_STR)


def build_agent_script(params: AgentScriptParams) -> str:
    """
    Render the agent script by substituting the normalized parameters into the template.
    """

    return SCRIPT_TEMPLATE.substitute(params.substitutions())


def build_pr_script(params: AgentScriptParams) -> str:
    """
    Generate a bash script that creates a deep PR with issue context, diff stats,
    and trajectory metadata.

    This script is designed to run in the same sandbox after the agent has made
    code changes (Phase 2). It inspects the GitHub issue via `gh`, reads the diff,
    parses trajectory data, then creates a single commit + detailed PR.

    Parameters are substituted at generation time from AgentScriptParams.
    The script uses $GITHUB_TOKEN from the sandbox environment.
    """

    owner = params.owner
    repo = params.repo_name
    issue_number = params.issue_number
    branch_name = params.branch_name
    model_name = params.model_name
    issue_url = params.issue_url
    repo_url = params.repo_url

    # Escape fallback strings for safe embedding in bash
    fallback_title = (params.issue_title or "").replace("'", "'\\''")
    fallback_body = (params.issue_body or "").replace("'", "'\\''")[:500]

    import time as _time
    timestamp = int(_time.time())
    pr_branch = f"yudai/fix-issue-{issue_number}-{timestamp}"

    script = f"""#!/usr/bin/env bash
set -euo pipefail

OWNER='{owner}'
REPO='{repo}'
ISSUE_NUMBER='{issue_number}'
BASE_BRANCH='{branch_name}'
MODEL_NAME='{model_name}'
ISSUE_URL='{issue_url}'
REPO_URL='{repo_url}'
PR_BRANCH='{pr_branch}'
TESTBED='/home/user/testbed'
TRAJ_PATH='/home/user/last_mini_run.traj.json'

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

# ── Step 3: Capture diff statistics ──
DIFF_STAT=$(git diff --stat 2>/dev/null || echo "No changes")
DIFF_FILES=$(git diff --name-only 2>/dev/null || echo "")
DIFF_SHORT=$(git diff --shortstat 2>/dev/null || echo "0 files changed")
FILES_CHANGED_COUNT=$(echo "$DIFF_FILES" | grep -c '.' 2>/dev/null || echo "0")

# ── Step 4: Parse trajectory metadata ──
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
    echo "ERROR: No changes detected in testbed. Nothing to commit."
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

# ── Step 7: Push ──
AUTH_URL=$(echo "$REPO_URL" | sed "s|https://github.com/|https://${{GITHUB_TOKEN}}@github.com/|")
if [[ ! "$AUTH_URL" == *.git ]]; then
    AUTH_URL="${{AUTH_URL}}.git"
fi
git push -u "$AUTH_URL" "$PR_BRANCH"

# ── Step 8: Create PR ──
PR_BODY=$(cat <<'PRBODYEOF'
## Summary

fix: resolve #ISSUE_NUM_PLACEHOLDER — ISSUE_TITLE_PLACEHOLDER

PRBODYEOF
)

# Build the full PR body dynamically
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

echo "Phase 2: Deep PR creation complete."
"""

    return script
