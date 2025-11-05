"""
E2B Sandbox integration for running MSWEA.py pipeline.

This module provides functionality to execute GitHub issue solving
using mini-SWE-agent in isolated E2B sandboxes.

"""

import asyncio
import json
import logging
import os
import shlex
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from e2b import Sandbox
except ImportError:
    raise ImportError(
        "e2b is required. Install with: pip install e2b\n"
        "See https://e2b.dev/docs for setup instructions."
    )

# Load environment variables from .env file if available
if load_dotenv:
    load_dotenv()


logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def run_mswea_in_sandbox(
    issue_url: str,
    *,
    model_name: Optional[str] = None,
    mode: str = "confirm",
    repo_url: Optional[str] = None,
    verbose: bool = False,
    keep_sandbox: bool = False,
) -> dict:
    """
    Run MSWEA.py in an E2B sandbox to solve a GitHub issue.

    Args:
        issue_url: GitHub issue URL (e.g., https://github.com/owner/repo/issues/123)
        model_name: Optional model name to override config
        mode: Start mode (yolo, confirm, human) - default: confirm
        repo_url: Optional repository URL override for cloning
        verbose: Enable verbose logging
        timeout_minutes: Sandbox timeout in minutes (E2B handles this automatically)
        keep_sandbox: If True, don't close sandbox after execution (for inspection)

    Returns:
        Dictionary with execution results including:
        - sandbox_id: Sandbox identifier
        - exit_code: Exit code from MSWEA execution
        - stdout: Standard output from command
        - stderr: Standard error from command
        - logs: Full execution logs (combined stdout/stderr)
        - command: Command that was executed
        - error: Error message if execution failed
    """
    solver_dir = Path(__file__).parent
    mswea_script = solver_dir / "MSWEA.py"
    config_file = solver_dir / "tfbd.yaml"
    env_file = solver_dir / ".env"

    if not mswea_script.exists():
        raise FileNotFoundError(f"MSWEA.py not found at {mswea_script}")
    if not config_file.exists():
        raise FileNotFoundError(f"tfbd.yaml not found at {config_file}")

    # Prepare environment variables for sandbox
    env_vars: dict[str, str] = {}

    # Get OPENROUTER_API_KEY from environment
    openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_api_key:
        env_vars["OPENROUTER_API_KEY"] = openrouter_api_key
        logger.info("OPENROUTER_API_KEY found, will set in sandbox environment")
    else:
        logger.warning("OPENROUTER_API_KEY not found in environment variables")
        logger.warning("mini-swe-agent may fail if API key is required")

    # Read .env file if it exists and add to environment variables
    env_loaded = False
    if env_file.exists():
        logger.info("Reading .env file...")
        try:
            from dotenv import dotenv_values

            env_dict = dotenv_values(env_file)
            env_vars.update({k: v for k, v in env_dict.items() if v is not None})
            env_loaded = True
            logger.info(".env file loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to read .env file: {e}")
            logger.warning("Will use environment variables only")
    else:
        logger.info(".env file not found in solver directory, skipping")

    logger.info("Creating E2B sandbox...")

    # Create E2B sandbox with environment variables
    # E2B sandboxes are ready immediately, no need to wait
    sandbox = Sandbox.create(envs=env_vars)
    logger.info(f"Sandbox created: {sandbox.get_info()}")

    try:
        # Clone mini-swe-agent repository from source
        logger.info("Cloning mini-swe-agent repository from source...")
        clone_result = sandbox.commands.run(
            "cd /home/user && git clone https://github.com/pranay5255/yudai-swe-agent.git mini-swe-agent"
        )
        if clone_result.exit_code != 0:
            logger.error(f"Failed to clone repository: {clone_result.stderr}")
            return {
                "sandbox_id": sandbox.get_info().sandbox_id,
                "exit_code": clone_result.exit_code,
                "logs": clone_result.stderr,
                "output": clone_result.stdout,
                "error": "Failed to clone mini-swe-agent repository",
            }

        # Install mini-swe-agent from source
        logger.info("Installing mini-swe-agent from source...")
        install_result = sandbox.commands.run(
            "cd /home/user/mini-swe-agent && pip install --no-cache-dir -e ."
        )
        if install_result.exit_code != 0:
            logger.error(
                f"Failed to install mini-swe-agent from source: {install_result.stderr}"
            )
            logger.info(f"Install stdout: {install_result.stdout}")
            return {
                "sandbox_id": sandbox.get_info(),
                "exit_code": install_result.exit_code,
                "logs": install_result.stderr,
                "output": install_result.stdout,
                "error": "Failed to install mini-swe-agent from source",
            }

        # Verify installation by checking if mini command is available
        logger.info("Verifying mini-swe-agent installation...")
        verify_result = sandbox.commands.run(
            "which mini || python -m minisweagent.run.mini --help 2>&1 | head -n 1"
        )
        if verify_result.exit_code != 0:
            logger.warning(f"Could not verify mini command: {verify_result.stderr}")
        else:
            logger.info(f"mini-swe-agent verified: {verify_result.stdout.strip()}")

        # Read MSWEA.py script content
        logger.info("Reading MSWEA.py...")
        mswea_content = mswea_script.read_text()

        # Read config file content
        logger.info("Reading tfbd.yaml...")
        config_content = config_file.read_text()

        # Upload MSWEA.py script to sandbox
        logger.info("Uploading MSWEA.py...")
        sandbox.files.write("/home/user/MSWEA.py", mswea_content)

        # Upload config file to sandbox
        logger.info("Uploading tfbd.yaml...")
        sandbox.files.write("/home/user/tfbd.yaml", config_content)

        # Upload .env file if it exists
        if env_loaded and env_file.exists():
            logger.info("Uploading .env file...")
            try:
                env_content = env_file.read_text()
                sandbox.files.write("/home/user/.env", env_content)
                logger.info(".env file uploaded successfully")

                # Install python-dotenv in sandbox to load .env file
                logger.info("Installing python-dotenv to load .env file...")
                dotenv_result = sandbox.commands.run(
                    "pip install --no-cache-dir python-dotenv"
                )
                if dotenv_result.exit_code != 0:
                    logger.warning(
                        f"Failed to install python-dotenv: {dotenv_result.stderr}"
                    )
                    logger.warning(
                        "Will fall back to environment variables (already set)"
                    )
            except Exception as e:
                logger.warning(f"Failed to upload .env file: {e}")
                logger.warning("Will use environment variables (already set)")

        # Build command parts as list (for subprocess.run) and string (for shell execution)
        cmd_parts_list = ["python", "/home/user/MSWEA.py", issue_url]
        cmd_parts_list.extend(["--config", "/home/user/tfbd.yaml"])
        cmd_parts_list.extend(["--mode", mode])
        cmd_parts_list.extend(["--dest", "/tmp/mswea_repos"])

        if model_name:
            cmd_parts_list.extend(["--model", model_name])
        if repo_url:
            cmd_parts_list.extend(["--repo-url", repo_url])
        if verbose:
            cmd_parts_list.append("--verbose")

        # Build shell command string with proper quoting for display/logging
        cmd_parts_quoted = [shlex.quote(arg) for arg in cmd_parts_list]
        cmd_str = " ".join(cmd_parts_quoted)

        # If .env file is loaded, wrap command to load environment variables
        # Otherwise, environment variables are already set via envs parameter
        if env_loaded:
            # Create a Python wrapper that loads .env and executes the command
            # Use proper JSON encoding for the command to avoid escaping issues
            wrapper_code = (
                "import os, sys, subprocess; "
                "from dotenv import load_dotenv; "
                "load_dotenv('/home/user/.env'); "
                f"sys.exit(subprocess.run({json.dumps(cmd_parts_list)}).returncode)"
            )
            command = f"python -c {shlex.quote(wrapper_code)}"
        else:
            # Environment variables are already set via envs parameter
            command = cmd_str

        # Log command without sensitive information
        logger.info(f"Executing: {cmd_str}")
        if env_loaded:
            logger.info("(with .env file loaded)")
        elif openrouter_api_key:
            logger.info("(with OPENROUTER_API_KEY set via environment)")

        # Execute MSWEA script (this may take a while)
        logger.info("Running MSWEA script (this may take several minutes)...")
        result = sandbox.commands.run(command)

        logger.info(f"MSWEA execution completed with exit code: {result.exit_code}")

        # Combine stdout and stderr as logs
        logs = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"

        return {
            "sandbox_id": sandbox.get_info(),
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "logs": logs,
            "command": command,
        }

    except Exception as e:
        logger.error(f"Error during execution: {e}", exc_info=True)
        # Try to get result if available
        result_stdout = ""
        result_stderr = ""
        try:
            if "result" in locals():
                result_stdout = getattr(result, "stdout", "")
                result_stderr = getattr(result, "stderr", "")
        except Exception:
            pass

        logs = f"Error: {str(e)}\n\nSTDOUT:\n{result_stdout or 'N/A'}\n\nSTDERR:\n{result_stderr or 'N/A'}"

        return {
            "sandbox_id": sandbox.get_info(),
            "exit_code": -1,
            "error": str(e),
            "logs": logs,
        }

    finally:
        # Clean up sandbox unless keep_sandbox is True
        if not keep_sandbox:
            logger.info(f"Closing sandbox {sandbox.get_info()}...")
            try:
                sandbox.close()
                logger.info("Sandbox closed")
            except Exception as e:
                logger.warning(f"Failed to close sandbox: {e}")
        else:
            logger.info(
                f"Sandbox {sandbox.get_info()} kept for inspection (will auto-close after timeout)"
            )


async def demo_run(
    issue_url: Optional[str] = None,
    mode: str = "confirm",
    model_name: Optional[str] = None,
    repo_url: Optional[str] = None,
    verbose: bool = True,
    keep_sandbox: bool = False,
):
    """
    Demo function to test sandbox execution with a GitHub issue.

    Args:
        issue_url: GitHub issue URL (defaults to example if not provided)
        mode: Start mode (yolo, confirm, human)
        model_name: Optional model name override
        repo_url: Optional repository URL override
        verbose: Enable verbose logging
        keep_sandbox: If True, don't delete sandbox after execution
    """
    if not issue_url:
        # Example GitHub issue URL - replace with a real one for testing
        issue_url = "https://github.com/octocat/Hello-World/issues/1"
        logger.warning(f"No issue URL provided, using example: {issue_url}")

    logger.info("=" * 60)
    logger.info("E2B Sandbox Demo - MSWEA Execution")
    logger.info("=" * 60)
    logger.info(f"Issue URL: {issue_url}")
    logger.info(f"Mode: {mode}")
    if model_name:
        logger.info(f"Model: {model_name}")
    logger.info("")

    try:
        result = await run_mswea_in_sandbox(
            issue_url,
            model_name=model_name,
            mode=mode,
            repo_url=repo_url,
            verbose=verbose,
            keep_sandbox=keep_sandbox,
        )

        logger.info("")
        logger.info("=" * 60)
        logger.info("Execution Results")
        logger.info("=" * 60)
        logger.info(f"Sandbox ID: {result.get('sandbox_id')}")
        logger.info(f"Exit Code: {result.get('exit_code')}")

        if result.get("error"):
            logger.error(f"Error: {result.get('error')}")

        if result.get("stdout"):
            logger.info("\n--- STDOUT (first 1000 chars) ---")
            logger.info(result.get("stdout")[:1000])
            if len(result.get("stdout", "")) > 1000:
                logger.info(
                    f"... ({len(result.get('stdout', '')) - 1000} more characters)"
                )

        if result.get("stderr"):
            logger.info("\n--- STDERR (first 1000 chars) ---")
            logger.info(result.get("stderr")[:1000])
            if len(result.get("stderr", "")) > 1000:
                logger.info(
                    f"... ({len(result.get('stderr', '')) - 1000} more characters)"
                )

        if result.get("logs"):
            logger.info("\n--- LOGS (last 500 chars) ---")
            logs = result.get("logs", "")
            logger.info(logs[-500:] if len(logs) > 500 else logs)

        if keep_sandbox:
            logger.info(f"\n⚠ Sandbox {result.get('sandbox_id')} kept for inspection")

        return result

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run MSWEA in E2B sandbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with example issue
  python sandbox.py
  
  # Run with specific issue
  python sandbox.py https://github.com/owner/repo/issues/123
  
  # Run in yolo mode (no confirmation)
  python sandbox.py https://github.com/owner/repo/issues/123 --mode yolo
  
  # Keep sandbox for inspection
  python sandbox.py https://github.com/owner/repo/issues/123 --keep-sandbox
        """,
    )
    parser.add_argument(
        "issue_url",
        nargs="?",
        help="GitHub issue URL (e.g., https://github.com/owner/repo/issues/123)",
    )
    parser.add_argument(
        "--mode",
        choices=["yolo", "confirm", "human"],
        default="confirm",
        help="Start mode (default: confirm)",
    )
    parser.add_argument("--model", help="Model name to override config")
    parser.add_argument("--repo-url", help="Override repository URL for cloning")
    parser.add_argument(
        "--keep-sandbox",
        action="store_true",
        help="Keep sandbox after execution for inspection",
    )
    parser.add_argument("--quiet", action="store_true", help="Reduce logging verbosity")

    args = parser.parse_args()

    if args.quiet:
        logging.getLogger().setLevel(logging.WARNING)

    asyncio.run(
        demo_run(
            issue_url=args.issue_url,
            mode=args.mode,
            model_name=args.model,
            repo_url=args.repo_url,
            verbose=not args.quiet,
            keep_sandbox=args.keep_sandbox,
        )
    )
