from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def run_agent_command(args: list[str]) -> str:
    """Run the swe-agent CLI with the provided arguments.

    This function logs the invocation and any errors so that agent
    interactions can be monitored.
    """
    import subprocess

    logger.info("running swe-agent", args=args)
    try:
        result = subprocess.run(
            ["sweagent", *args],
            capture_output=True,
            text=True,
            timeout=600,
        )
        logger.debug(
            "swe-agent finished",
            returncode=result.returncode,
        )
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        logger.error("swe-agent timed out")
        return "Timeout"
    except Exception as exc:  # noqa: BLE001
        logger.exception("swe-agent execution failed", exc=exc)
        return f"Error: {exc}"


def apply_patch_with_agent(patch: str, repo_path: str = ".") -> str:
    """Apply a patch using swe-agent if available."""
    try:
        from sweagent.agent.apply_patch import apply_patch  # type: ignore

        logger.info("applying patch via swe-agent", repo=repo_path)
        apply_patch(repo_path, patch)
        logger.debug("patch applied")
        return patch
    except Exception as exc:  # noqa: BLE001
        logger.warning("swe-agent apply failed, returning original patch", exc=exc)
        return patch
