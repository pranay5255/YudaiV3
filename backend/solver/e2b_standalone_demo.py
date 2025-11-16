#!/usr/bin/env python3
"""
Standalone E2B Sandbox Demo Script

This script demonstrates the full end-to-end execution of mini-swe-agent in an E2B sandbox
without requiring database operations or the full manager infrastructure.

Usage:
    1. Set environment variables:
       - OPENROUTER_API_KEY (required)
       - E2B_API_KEY (required)
       - GITHUB_TOKEN (optional, but recommended for private repos)

    2. Modify the USER_CONFIG section below with your repo details

    3. Run: python e2b_standalone_demo.py
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from solver.sandbox import (
    HeadlessSandboxExecutor,
    HeadlessSandboxRequest,
    SandboxExecutionError,
    SandboxRunResult,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ============================================================================
# USER CONFIGURATION - Modify these values for your demo
# ============================================================================

USER_CONFIG = {
    # Repository details
    "repo_url": "https://github.com/satavisha/TFBDMap3",
    "branch_name": "main",
    # Issue details (provide either issue_url OR issue_text)
    "issue_url": "https://github.com/satavisha/TFBDMap3/issues/22",
    "issue_text": None,  # Optional: provide issue text directly instead of URL
    # Model configuration
    "model_name": "deepseek/deepseek-v3.2-exp",  # Free model for testing
    # Alternative models:
    # "anthropic/claude-sonnet-4-5-20250929"
    # "openai/gpt-4-turbo",
    # "google/gemini-pro-1.5"
    # Agent behavior configuration
    "temperature": 0.1,
    "max_tokens": 8000,
    "max_iterations": 40,
    "max_cost": 7.5,
    "small_change": True,  # Limit to minimal targeted changes
    "best_effort": False,  # Continue even if tests fail
    # Rate limiting safeguards
    "openrouter_call_delay": 5.0,  # Seconds to sleep between OpenRouter requests
    # Execution settings
    "verbose": True,
}


# ============================================================================
# DEMO EXECUTION FUNCTIONS
# ============================================================================


def validate_environment() -> tuple[str, Optional[str]]:
    """
    Validate required environment variables are set.

    Returns:
        Tuple of (openroutevalidate_environmentr_api_key, github_token)

    Raises:
        SystemExit if required variables are missing
    """
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    e2b_api_key = os.getenv("E2B_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")

    missing = []
    if not openrouter_api_key:
        missing.append("OPENROUTER_API_KEY")
    if not e2b_api_key:
        missing.append("E2B_API_KEY")

    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        logger.error("Please set the following environment variables:")
        for var in missing:
            logger.error("  export %s=your_%s_here", var, var.lower())
        sys.exit(1)

    if not github_token:
        logger.warning(
            "GITHUB_TOKEN not set. This may limit access to private repositories "
            "and can cause rate limiting issues."
        )

    return openrouter_api_key, github_token


def display_config(config: dict):
    """Display the demo configuration."""
    logger.info("=" * 80)
    logger.info("E2B Sandbox Demo Configuration")
    logger.info("=" * 80)
    for key in (
        "repo_url",
        "branch_name",
        "issue_url",
        "model_name",
        "temperature",
        "max_iterations",
        "max_cost",
        "small_change",
        "best_effort",
        "openrouter_call_delay",
    ):
        logger.info("%s: %s", key.replace("_", " ").title(), config.get(key))
    logger.info("=" * 80)


def display_result(result: SandboxRunResult):
    """Display execution results in a formatted way."""
    logger.info("=" * 80)
    logger.info("Execution Results")
    logger.info("=" * 80)
    logger.info("Sandbox ID: %s", result.sandbox_id)
    logger.info("Exit Code: %d", result.exit_code)
    logger.info("Duration: %.2f seconds", result.duration_ms / 1000)
    logger.info("Status: %s", "SUCCESS" if result.exit_code == 0 else "FAILED")

    if result.pr_url:
        logger.info("Pull Request: %s", result.pr_url)

    if result.trajectory_file:
        logger.info("Trajectory File (Remote): %s", result.trajectory_file)

    if result.local_trajectory_path:
        logger.info("Trajectory File (Local): %s", result.local_trajectory_path)

    if result.trajectory_metadata:
        logger.info("Trajectory Metadata:")
        logger.info("  Exit Status: %s", result.trajectory_metadata.exit_status)
        logger.info(
            "  Instance Cost: $%.4f", result.trajectory_metadata.instance_cost or 0
        )
        logger.info("  API Calls: %d", result.trajectory_metadata.api_calls or 0)
        logger.info(
            "  Total Messages: %d", result.trajectory_metadata.total_messages or 0
        )

    if result.error:
        logger.error("Error: %s", result.error)

    logger.info("=" * 80)
    logger.info("Standard Output (last 2000 chars):")
    logger.info("-" * 80)
    logger.info("%s", result.stdout[-2000:] if result.stdout else "(empty)")

    if result.stderr:
        logger.info("=" * 80)
        logger.info("Standard Error (last 2000 chars):")
        logger.info("-" * 80)
        logger.info("%s", result.stderr[-2000:])

    logger.info("=" * 80)


def build_demo_request(config: dict) -> HeadlessSandboxRequest:
    """Build a HeadlessSandboxRequest from the user config."""

    return HeadlessSandboxRequest(
        issue_url=config["issue_url"],
        repo_url=config["repo_url"],
        branch_name=config["branch_name"],
        model_name=config["model_name"],
        temperature=config["temperature"],
        max_tokens=config["max_tokens"],
        max_iterations=config["max_iterations"],
        max_cost=config["max_cost"],
        small_change=config["small_change"],
        best_effort=config["best_effort"],
        issue_text=config.get("issue_text"),
        verbose=config["verbose"],
        openrouter_call_delay=config.get("openrouter_call_delay", 0.0),
        solve_id="demo_solve",
        solve_run_id="demo_run",
    )


async def run_demo(config: dict) -> SandboxRunResult:
    """
    Execute the e2b sandbox demo with the provided configuration.

    Args:
        config: Configuration dictionary with repo, issue, and model details

    Returns:
        SandboxRunResult with execution details

    Raises:
        SandboxExecutionError: If execution fails
    """
    request = build_demo_request(config)

    # Create executor and run
    logger.info("Creating sandbox executor...")
    executor = HeadlessSandboxExecutor()

    logger.info("Starting sandbox execution...")
    logger.info("This may take several minutes depending on the issue complexity...")

    try:
        result = await executor.run(request)
        return result
    except SandboxExecutionError as e:
        logger.error("Sandbox execution failed: %s", str(e))
        if e.logs:
            logger.error("Execution logs:")
            logger.error("%s", e.logs[-2000:])  # Last 2000 chars
        raise


def save_result_to_file(result: SandboxRunResult, output_dir: Path):
    """Save execution result to a JSON file for analysis."""
    output_dir.mkdir(parents=True, exist_ok=True)

    result_data = {
        "sandbox_id": result.sandbox_id,
        "exit_code": result.exit_code,
        "duration_ms": result.duration_ms,
        "completed_at": result.completed_at.isoformat(),
        "command": result.command,
        "pr_url": result.pr_url,
        "trajectory_file": result.trajectory_file,
        "local_trajectory_path": result.local_trajectory_path,
        "tfbd_path": result.tfbd_path,
        "script_path": result.script_path,
        "error": result.error,
        "stdout_preview": result.stdout[-1000:] if result.stdout else None,
        "stderr_preview": result.stderr[-1000:] if result.stderr else None,
    }

    if result.trajectory_metadata:
        result_data["trajectory_metadata"] = {
            "exit_status": result.trajectory_metadata.exit_status,
            "submission": result.trajectory_metadata.submission,
            "instance_cost": result.trajectory_metadata.instance_cost,
            "api_calls": result.trajectory_metadata.api_calls,
            "mini_version": result.trajectory_metadata.mini_version,
            "model_name": result.trajectory_metadata.model_name,
            "total_messages": result.trajectory_metadata.total_messages,
        }

    output_file = output_dir / f"demo_result_{result.sandbox_id}.json"
    output_file.write_text(json.dumps(result_data, indent=2))
    logger.info("Result saved to: %s", output_file)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


async def main():
    """Main execution function."""
    try:
        # Validate environment
        logger.info("Validating environment...")
        validate_environment()

        # Display configuration
        display_config(USER_CONFIG)

        # Run the demo
        result = await run_demo(USER_CONFIG)

        # Display results
        display_result(result)

        # Save results to file
        output_dir = Path(__file__).parent / "demo_results"
        save_result_to_file(result, output_dir)

        # Exit with appropriate code
        exit_code = 0 if result.exit_code == 0 else 1
        if exit_code == 0:
            logger.info("✓ Demo completed successfully!")
        else:
            logger.warning("✗ Demo completed with errors")

        return exit_code

    except SandboxExecutionError as e:
        logger.error("Sandbox execution failed: %s", str(e))
        return 1
    except KeyboardInterrupt:
        logger.warning("Demo interrupted by user")
        return 130
    except Exception as e:
        logger.exception("Unexpected error during demo: %s", str(e))
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
