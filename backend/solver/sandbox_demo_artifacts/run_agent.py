#!/usr/bin/env python3
"""
Mini-SWE-Agent execution script for headless sandbox execution.
Generated automatically by YudaiV3 solver manager.
"""

import json
import logging
import os
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Dict

import requests
import yaml
from minisweagent.agents.default import DefaultAgent
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models import get_model
from minisweagent.run.utils.save import save_traj

logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")

CONFIG_DIR = Path("/home/user/config_mswea")
TFBD_PATH = Path("/home/user/tfbd.yaml")
TESTBED_PATH = Path("/home/user/testbed")
MINI_SWE_ROOT = Path("/home/user/mini-swe-agent")
TRAJECTORY_PATH = Path("/home/user/trajectory.json")
OUTPUT_PATH = Path("/home/user/last_mini_run.traj.json")

REPO_URL = "https://github.com/example/repo"
BRANCH_NAME = "main"
ISSUE_URL = "https://github.com/example/repo/issues/123"
MODEL_NAME = "minimax/minimax-m2:free"
ISSUE_TEXT_LITERAL = "# Add a Simple Button to the React UI\n\n## Problem Description\nThe user wants to add a basic button to the React-based user interface in the project. This is a common UI enhancement request to enable user interactions, such as logging a click event.\n\n## Context from Conversation\nIn the chat session, the user asked: \"How do I add a simple button to UI in React?\" The response provided a basic example of implementing a button component in React, including an event handler for clicks. This issue captures that intent to integrate such a feature into the `tfbdmap3` repository, which appears to be a React application (based on the file analysis of 25 files, likely including React components).\n\nNo specific component or location in the codebase was mentioned, so this should be added to a relevant UI section, such as a main dashboard or map interface (inferred from the repo name `tfbdmap3`, possibly related to mapping).\n\n## Relevant Files and Code Sections\n- The project uses React (inferred from the query and repo structure with ~25 files, estimated 75.6k tokens).\n- Potential files to modify: Look for existing React components (e.g., `App.js`, `Dashboard.js`, or similar entry points in `src/components/`).\n- No exact file paths provided in the conversation, but integrate into an existing functional component.\n\n## Implementation Suggestions\nUse the provided example code as a starting point. Create or update a component to include a button with an `onClick` handler that logs a message to the console (or triggers a relevant action in the app, like toggling a map feature).\n\nHere's the suggested code snippet to incorporate:\n\n```jsx\nimport React from 'react';\n\nfunction MyComponent() {\n  const handleClick = () => {\n    console.log('Button clicked!');\n  };\n\n  return (\n    <div>\n      <button onClick={handleClick}>\n        Click Me\n      </button>\n    </div>\n  );\n}\n\nexport default MyComponent;\n```\n\n- Import and render this in the parent component (e.g., `App.js`).\n- Style the button if needed using existing CSS or inline styles for consistency with the project's UI.\n- Ensure it fits the app's theme, perhaps labeling it something context-specific like \"Toggle Map View\" if relevant to `tfbdmap3`.\n\n## Acceptance Criteria\n- [ ] A button element is added to at least one React component in the UI.\n- [ ] The button includes an `onClick` event handler that logs a message to the console (or performs a simple action).\n- [ ] The button renders correctly without errors in the browser.\n- [ ] Code is integrated into the existing codebase (e.g., via a new or updated component file).\n- [ ] Basic testing: Button click triggers the handler (verifiable via browser console).\n- [ ] No breaking changes to existing functionality.\n\nThis enhancement is marked as medium priority and should improve user interactivity in the React app.\n\n## Repository\n- **Name**: satavisha/TFBDMap3\n- **Branch**: main\n- **URL**: https://github.com/satavisha/TFBDMap3\n\n## Recent Conversation\n- **assistant**: To add a simple button to your React UI, import React and use the `<button>` element in your component. Here's a basic example:\n\n```jsx\nimport React from 'react';\n\nfunction MyComponent() {\n  const handleClick = () => {\n    console.log('Button clic...\n- **user**: How do i add a simple button to UI in react ?\n\n---\n*Issue generated with DAifu session context.*"

TEMPERATURE = 0.200
MAX_TOKENS = 6000
MAX_ITERATIONS = 40
MAX_COST = 7.50
SMALL_CHANGE = True
BEST_EFFORT = False

SOLVE_PAYLOAD = {
    "small_change": SMALL_CHANGE,
    "best_effort": BEST_EFFORT,
    "max_iterations": MAX_ITERATIONS,
    "max_cost": MAX_COST,
}

logger = logging.getLogger("yudai.solver.script")


def fetch_github_issue(issue_url: str) -> str:
    """Fetch GitHub issue text from the URL."""
    if not issue_url:
        raise ValueError("GitHub issue URL is required")

    api_url = issue_url.replace("github.com", "api.github.com/repos").replace(
        "/issues/", "/issues/"
    )

    headers = {"Accept": "application/vnd.github.v3+json"}
    if github_token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"token {github_token}"

    try:
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        issue_data = response.json()
    except Exception as exc:
        logger.warning("Failed to fetch GitHub issue: %s", exc)
        raise ValueError(f"Failed to fetch GitHub issue: {exc}")

    title = issue_data.get("title", "No title")
    body = issue_data.get("body", "")

    return f"GitHub Issue: {title}\n\n{body}"


def load_config() -> Dict[str, Any]:
    """Load agent configuration from tfbd.yaml."""
    if not TFBD_PATH.exists():
        raise RuntimeError(f"Config file not found at {TFBD_PATH}")

    logger.info("Loading agent config from '%s'", TFBD_PATH)
    config = yaml.safe_load(TFBD_PATH.read_text())

    # Apply runtime overrides

    config.setdefault("agent", {})["cost_limit"] = MAX_COST

    config.setdefault("model", {})["temperature"] = TEMPERATURE
    config.setdefault("model", {})["max_tokens"] = MAX_TOKENS

    return config


def clone_repository() -> None:
    """Clone the target repository into testbed directory."""
    if TESTBED_PATH.exists():
        logger.info("Testbed already exists at %s", TESTBED_PATH)
        return

    repo_url = REPO_URL
    if github_token := os.getenv("GITHUB_TOKEN"):
        if "github.com" in repo_url:
            repo_url = repo_url.replace(
                "https://github.com/", f"https://{github_token}@github.com/"
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
        raise RuntimeError(f"Failed to clone repository: {result.stderr}")

    logger.info("Repository cloned successfully to %s", TESTBED_PATH)


def install_mini_swe_agent() -> None:
    """Install mini-swe-agent if not already available."""
    logger.info("Ensuring mini-swe-agent is available")

    if not MINI_SWE_ROOT.exists():
        logger.info("Cloning mini-swe-agent repository")
        result = subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
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
    """Record successful execution results."""
    payload = {
        "exit_status": exit_status,
        "result": str(result) if result else None,
        "trajectory_file": str(OUTPUT_PATH),
        "tfbd_path": str(TFBD_PATH),
        "repository_path": str(TESTBED_PATH),
        "solve_payload": SOLVE_PAYLOAD,
    }
    Path("/home/user/solve_success.json").write_text(json.dumps(payload, indent=2))
    logger.info("Recorded success to /home/user/solve_success.json")


def record_failure(error: Exception) -> None:
    """Record execution failure."""
    payload = {
        "error": str(error),
        "traceback": traceback.format_exc(),
    }
    Path("/home/user/solve_failure.json").write_text(json.dumps(payload, indent=2))
    logger.error("Recorded failure: %s", error)


def finalize_execution(exit_code: int) -> None:
    """Write final execution state."""
    summary = {
        "exit_code": exit_code,
        "completed": exit_code == 0,
    }
    Path("/home/user/solve_final_state.json").write_text(json.dumps(summary, indent=2))
    logger.info("Execution finalized with exit code %d", exit_code)


def main() -> int:
    """Execute mini-swe-agent on the GitHub issue."""

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
            extra_info=extra_info,
        )
        logger.info("Trajectory saved to: %s", OUTPUT_PATH)

        # Record success
        record_success(exit_status, result)

        # Determine exit code
        exit_code = 0 if exit_status == "finished" else 1
        finalize_execution(exit_code)

        if exit_code == 0:
            print("\n✓ Agent completed successfully")
            print(f"Result: {result}")
        else:
            print(f"\n✗ Agent finished with status: {exit_status}")
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
            if OUTPUT_PATH and "agent" in locals():
                save_traj(
                    agent,
                    OUTPUT_PATH,
                    exit_status=exit_status,
                    result=result,
                    extra_info=extra_info,
                )
        except Exception:
            pass

        record_failure(exc)
        finalize_execution(1)
        return 1


if __name__ == "__main__":
    sys.exit(main())
