"""
Solver manager orchestrating asynchronous mini-swe-agent executions inside E2B sandboxes.

This module consolidates all solver functionality including:
- Solve session orchestration and lifecycle management
- E2B sandbox creation and execution using mini-swe-agent Python bindings
- Direct mini-swe-agent integration via DefaultAgent
- Database updates and state tracking
- Async task management and cleanup
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from db.database import SessionLocal
from e2b import Sandbox
from fastapi import HTTPException, status
from models import (
    AIModel,
    CancelSolveResponse,
    ChatSession,
    Issue,
    Solve,
    SolveProgress,
    SolveRun,
    SolveRunOut,
    SolveStatus,
    SolveStatusResponse,
    StartSolveRequest,
    StartSolveResponse,
    User,
)
from sqlalchemy.orm import Session

from utils import utc_now

logger = logging.getLogger(__name__)
TFBD_TEMPLATE_PATH = Path(__file__).with_name("tfbd.yaml")
DEFAULT_TFBD_FALLBACK = """agent:
  system_template: "You are a helpful assistant that can interact with a computer."
model:
  model_name: "{model_name}"
  model_class: "openrouter"
  model_kwargs:
    temperature: 0.4
"""


def build_tfbd_template(
    model_name: str,
    small_change: bool = False,
    best_effort: bool = False,
    max_iterations: int = 50,
    max_cost: float = 10.0,
) -> str:
    """
    Build a tfbd.yaml-style template with the requested model and options.

    The sandbox expects both the execution script and the YAML control file,
    so we lazily load the repository template, update the model stanza, and
    fall back to a minimal configuration when the template is missing.

    Args:
        model_name: Model identifier for the solver
        small_change: Limit scope to minimal code changes
        best_effort: Continue solving even if tests fail
        max_iterations: Maximum iterations for the agent
        max_cost: Maximum cost in USD for the solve session
    """

    try:
        base_template = TFBD_TEMPLATE_PATH.read_text()
    except FileNotFoundError:
        logger.warning(
            "tfbd.yaml template missing at %s. Using fallback definition.",
            TFBD_TEMPLATE_PATH,
        )
        return DEFAULT_TFBD_FALLBACK.format(model_name=model_name)

    updated_template, replacements = re.subn(
        r'model_name:\s*"[^"]+"',
        f'model_name: "{model_name}"',
        base_template,
        count=1,
    )

    if replacements == 0:
        # Append a model block if the template did not contain one.
        appended_block = (
            f"\nmodel:\n"
            f'    model_name: "{model_name}"\n'
            f'    model_class: "openrouter"\n'
            f"    model_kwargs:\n"
            f"        temperature: 0.4\n"
        )
        updated_template = base_template.rstrip() + appended_block

    # Add agent configuration based on user options
    agent_config = generate_agent_config(
        small_change=small_change,
        best_effort=best_effort,
        max_iterations=max_iterations,
        max_cost=max_cost,
    )

    # Append agent configuration
    updated_template = updated_template.rstrip() + "\n" + agent_config

    return updated_template


def generate_agent_config(
    small_change: bool = False,
    best_effort: bool = False,
    max_iterations: int = 50,
    max_cost: float = 10.0,
) -> str:
    """
    Generate agent configuration YAML block based on user options.

    Args:
        small_change: Limit scope to minimal code changes
        best_effort: Continue solving even if tests fail
        max_iterations: Maximum iterations for the agent
        max_cost: Maximum cost in USD for the solve session

    Returns:
        YAML configuration string for agent settings
    """

    # Adjust iterations based on small_change option
    if small_change:
        max_iterations = min(max_iterations, 20)
        max_cost = min(max_cost, 5.0)

    # Configure mode based on best_effort option
    mode = "best_effort" if best_effort else "yolo"

    config = f"""
agent:
  mode: "{mode}"
  max_iterations: {max_iterations}
  max_cost: {max_cost}
  small_change: {str(small_change).lower()}
  best_effort: {str(best_effort).lower()}
"""

    return config


def generate_solve_config_file(
    model_name: str,
    issue_url: str,
    repo_url: str,
    branch_name: str = "main",
    small_change: bool = False,
    best_effort: bool = False,
    max_iterations: int = 50,
    max_cost: float = 10.0,
) -> Dict[str, str]:
    """
    Generate complete configuration files for a solve session.

    Args:
        model_name: Model identifier for the solver
        issue_url: GitHub issue URL to solve
        repo_url: Repository URL
        branch_name: Branch to work on
        small_change: Limit scope to minimal code changes
        best_effort: Continue solving even if tests fail
        max_iterations: Maximum iterations for the agent
        max_cost: Maximum cost in USD for the solve session

    Returns:
        Dictionary containing file paths and contents for configuration files
    """

    # Generate YAML configuration
    yaml_config = build_tfbd_template(
        model_name=model_name,
        small_change=small_change,
        best_effort=best_effort,
        max_iterations=max_iterations,
        max_cost=max_cost,
    )

    # Generate metadata file
    metadata = {
        "issue_url": issue_url,
        "repo_url": repo_url,
        "branch_name": branch_name,
        "model_name": model_name,
        "small_change": small_change,
        "best_effort": best_effort,
        "max_iterations": max_iterations,
        "max_cost": max_cost,
        "created_at": utc_now().isoformat(),
    }

    return {
        "tfbd.yaml": yaml_config,
        "solve_metadata.json": json.dumps(metadata, indent=2),
    }


# ============================================================================
# SANDBOX EXECUTION DATA MODELS
# ============================================================================


@dataclass
class SandboxRunResult:
    """Result from a completed sandbox execution."""

    sandbox_id: str
    exit_code: int
    stdout: str
    stderr: str
    command: str
    duration_ms: int
    completed_at: datetime
    trajectory_file: Optional[str] = None
    pr_url: Optional[str] = None
    tfbd_path: Optional[str] = None
    script_path: Optional[str] = None
    error: Optional[str] = None


class SandboxExecutionError(Exception):
    """Raised when sandbox execution fails."""

    def __init__(self, message: str, logs: str = ""):
        super().__init__(message)
        self.logs = logs


@dataclass
class HeadlessSandboxRequest:
    """Request parameters for headless sandbox execution."""

    issue_url: str
    repo_url: str
    branch_name: str = "main"
    model_name: str = "anthropic/claude-sonnet-4-5-20250929"
    env: Optional[Dict[str, str]] = None
    verbose: bool = False


# ============================================================================
# SANDBOX EXECUTOR - MINI-SWE-AGENT INTEGRATION
# ============================================================================


class HeadlessSandboxExecutor:
    """
    Executes mini-swe-agent in E2B sandboxes using Python bindings.

    This executor:
    1. Creates an E2B sandbox with required dependencies
    2. Clones the repository into the sandbox
    3. Uses mini-swe-agent Python bindings (DefaultAgent) directly
    4. Captures execution results and trajectory data
    5. Manages sandbox lifecycle and cleanup
    """

    def __init__(self):
        self._sandbox: Optional[Sandbox] = None
        self._cancelled = False
        self._lock = asyncio.Lock()

    async def run(self, request: HeadlessSandboxRequest) -> SandboxRunResult:
        """
        Execute mini-swe-agent in E2B sandbox using Python bindings.

        Args:
            request: Sandbox execution request with issue URL, repo, model, etc.

        Returns:
            SandboxRunResult with execution details

        Raises:
            SandboxExecutionError: If execution fails
        """
        start_time = utc_now()

        try:
            # Get required environment variables
            openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
            github_token = os.getenv("GITHUB_TOKEN")

            if not openrouter_api_key:
                raise SandboxExecutionError(
                    "OPENROUTER_API_KEY environment variable required"
                )

            # Prepare environment variables for sandbox
            env_vars = {
                "OPENROUTER_API_KEY": openrouter_api_key,
                **(request.env or {}),
            }

            if github_token:
                env_vars["GITHUB_TOKEN"] = github_token

            # Create E2B sandbox
            logger.info("Creating E2B sandbox with mini-swe-agent...")
            async with self._lock:
                if self._cancelled:
                    raise SandboxExecutionError("Execution cancelled before start")
                self._sandbox = Sandbox.create(envs=env_vars)

            sandbox_id = self._sandbox.get_info().sandbox_id
            logger.info(f"Sandbox created: {sandbox_id}")

            # Install mini-swe-agent from source
            await self._install_mini_swe_agent()

            # Clone repository into sandbox
            await self._clone_repository(
                request.repo_url, request.branch_name, github_token
            )

            # Fetch GitHub issue content
            issue_text = await self._fetch_github_issue(request.issue_url, github_token)

            # Create tfbd.yaml config with the selected model and user options for traceability
            tfbd_path = "/home/user/tfbd.yaml"
            tfbd_config = build_tfbd_template(
                model_name=request.model_name,
                small_change=request.env.get("SMALL_CHANGE", "false").lower() == "true",
                best_effort=request.env.get("BEST_EFFORT", "false").lower() == "true",
                max_iterations=int(request.env.get("MAX_ITERATIONS", "50")),
                max_cost=float(request.env.get("MAX_COST", "10.0")),
            )
            self._sandbox.files.write(tfbd_path, tfbd_config)
            logger.info(
                "Uploaded tfbd.yaml template to sandbox %s for model %s (small_change=%s, best_effort=%s)",
                sandbox_id,
                request.model_name,
                request.env.get("SMALL_CHANGE", "false"),
                request.env.get("BEST_EFFORT", "false"),
            )

            # Create mini-swe-agent Python script using bindings
            python_script = self._generate_agent_script(
                issue_text=issue_text,
                model_name=request.model_name,
                verbose=request.verbose,
            )

            # Upload script to sandbox
            script_path = "/home/user/run_agent.py"
            self._sandbox.files.write(script_path, python_script)
            logger.info(
                "Uploaded headless execution script to sandbox %s",
                sandbox_id,
            )

            # Execute the agent script
            logger.info(
                "Executing mini-swe-agent in sandbox %s (repo=%s, issue=%s, model=%s)",
                sandbox_id,
                request.repo_url,
                request.issue_url,
                request.model_name,
            )
            result = self._sandbox.commands.run(
                f"cd /home/user/testbed && python {script_path}"
            )

            # Calculate duration
            end_time = utc_now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            # Check for cancellation
            async with self._lock:
                if self._cancelled:
                    raise SandboxExecutionError("Execution cancelled")

            # Parse output for PR URL and trajectory data
            pr_url = self._extract_pr_url(result.stdout)
            trajectory_file = self._extract_trajectory_path(result.stdout)

            logger.info(
                f"Sandbox execution completed: exit_code={result.exit_code}, "
                f"duration={duration_ms}ms"
            )

            return SandboxRunResult(
                sandbox_id=sandbox_id,
                exit_code=result.exit_code,
                stdout=result.stdout,
                stderr=result.stderr,
                command=f"python {script_path}",
                duration_ms=duration_ms,
                completed_at=end_time,
                trajectory_file=trajectory_file,
                pr_url=pr_url,
                tfbd_path=tfbd_path,
                script_path=script_path,
                error=None if result.exit_code == 0 else "Agent execution failed",
            )

        except SandboxExecutionError:
            raise
        except Exception as e:
            logger.exception("Sandbox execution failed")
            raise SandboxExecutionError(
                f"Sandbox execution failed: {str(e)}",
                logs=getattr(e, "logs", str(e)),
            )
        finally:
            await self._cleanup_sandbox()

    async def cancel(self):
        """Cancel the running sandbox execution."""
        async with self._lock:
            self._cancelled = True
            if self._sandbox:
                try:
                    self._sandbox.close()
                    logger.info("Sandbox cancelled and closed")
                except Exception as e:
                    logger.warning(f"Failed to close sandbox during cancellation: {e}")

    async def _install_mini_swe_agent(self):
        """Install mini-swe-agent from source in the sandbox."""
        logger.info("Installing mini-swe-agent from source...")

        # Clone mini-swe-agent repository
        clone_result = self._sandbox.commands.run(
            "cd /home/user && git clone https://github.com/pranay5255/yudai-swe-agent.git mini-swe-agent"
        )
        if clone_result.exit_code != 0:
            raise SandboxExecutionError(
                "Failed to clone mini-swe-agent repository",
                logs=clone_result.stderr,
            )

        # Install mini-swe-agent
        install_result = self._sandbox.commands.run(
            "cd /home/user/mini-swe-agent && pip install --no-cache-dir -e ."
        )
        if install_result.exit_code != 0:
            raise SandboxExecutionError(
                "Failed to install mini-swe-agent",
                logs=install_result.stderr,
            )

        # Verify installation
        verify_result = self._sandbox.commands.run(
            "python -c 'import minisweagent; print(minisweagent.__version__)'"
        )
        if verify_result.exit_code != 0:
            logger.warning("Could not verify mini-swe-agent installation")
        else:
            logger.info(f"mini-swe-agent installed: {verify_result.stdout.strip()}")

    async def _clone_repository(
        self, repo_url: str, branch_name: str, github_token: Optional[str]
    ):
        """Clone the target repository into the sandbox."""
        logger.info(f"Cloning repository: {repo_url}")

        # Add GitHub token to URL if available
        if github_token and "github.com" in repo_url:
            repo_path = repo_url.rstrip("/").replace("https://github.com/", "")
            if repo_path.endswith(".git"):
                repo_path = repo_path[:-4]
            clone_url = (
                f"https://x-access-token:{github_token}@github.com/{repo_path}.git"
            )
        else:
            clone_url = repo_url if repo_url.endswith(".git") else f"{repo_url}.git"

        # Clone repository
        clone_cmd = f"cd /home/user && git clone {clone_url} testbed"
        if branch_name and branch_name != "main":
            clone_cmd += f" --branch {branch_name}"

        result = self._sandbox.commands.run(clone_cmd)
        if result.exit_code != 0:
            raise SandboxExecutionError(
                f"Failed to clone repository: {repo_url}",
                logs=result.stderr,
            )

        logger.info("Repository cloned successfully")

    async def _fetch_github_issue(
        self, issue_url: str, github_token: Optional[str]
    ) -> str:
        """Fetch GitHub issue content from API."""
        logger.info(f"Fetching GitHub issue: {issue_url}")

        # Convert GitHub issue URL to API URL
        api_url = issue_url.replace("github.com", "api.github.com/repos").replace(
            "/issues/", "/issues/"
        )

        # Build curl command with optional auth
        headers = ""
        if github_token:
            headers = f'-H "Authorization: token {github_token}"'

        curl_cmd = f"curl -s {headers} {api_url}"
        result = self._sandbox.commands.run(curl_cmd)

        if result.exit_code != 0:
            raise SandboxExecutionError(
                "Failed to fetch GitHub issue",
                logs=result.stderr,
            )

        try:
            issue_data = json.loads(result.stdout)
            title = issue_data.get("title", "No title")
            body = issue_data.get("body", "")
            return f"GitHub Issue: {title}\n\n{body}"
        except json.JSONDecodeError as e:
            raise SandboxExecutionError(
                f"Failed to parse GitHub issue response: {e}",
                logs=result.stdout,
            )

    def _generate_agent_script(
        self, issue_text: str, model_name: str, verbose: bool
    ) -> str:
        """
        Generate Python script using mini-swe-agent bindings.

        This uses the Python API directly instead of CLI:
        - DefaultAgent for headless execution
        - LocalEnvironment for executing commands
        - get_model for automatic model selection
        """
        script = f'''#!/usr/bin/env python3
"""
Mini-SWE-Agent execution script using Python bindings.
Generated automatically by YudaiV3 solver manager.
"""
import sys
import logging
from pathlib import Path

from minisweagent.agents.default import DefaultAgent
from minisweagent.models import get_model
from minisweagent.environments.local import LocalEnvironment
from minisweagent.run.utils.save import save_traj

# Configure logging
logging.basicConfig(
    level=logging.{"DEBUG" if verbose else "INFO"},
    format="[%(levelname)s] %(message)s"
)

def main():
    """Execute mini-swe-agent on the GitHub issue."""
    
    # Task description from GitHub issue
    task = """
{issue_text}
"""
    
    # Configuration
    model_name = "{model_name}"
    config = {{
        "model_name": model_name,
        "temperature": 0.1,
        "max_tokens": 4000,
    }}
    
    agent_config = {{
        "mode": "yolo",  # Headless mode without confirmation
        "max_iterations": 50,
        "max_cost": 10.0,
    }}
    
    environment_config = {{}}
    
    try:
        # Create agent using Python bindings
        agent = DefaultAgent(
            get_model(model_name=model_name, config=config),
            LocalEnvironment(**environment_config),
            **agent_config,
        )
        
        # Run agent on task
        logging.info("Starting mini-swe-agent execution...")
        exit_status, result = agent.run(task)
        
        # Save trajectory
        output_path = Path("/home/user/trajectory.json")
        save_traj(agent, output_path, exit_status=exit_status, result=result)
        logging.info(f"Trajectory saved to {{output_path}}")
        
        # Print result
        if exit_status == "finished":
            print(f"\\n✓ Agent completed successfully")
            print(f"Result: {{result}}")
            return 0
        else:
            print(f"\\n✗ Agent failed with status: {{exit_status}}")
            print(f"Result: {{result}}")
            return 1
            
    except KeyboardInterrupt:
        logging.warning("Execution interrupted")
        return 130
    except Exception as e:
        logging.error(f"Agent execution failed: {{e}}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
'''
        return script

    def _extract_pr_url(self, stdout: str) -> Optional[str]:
        """Extract PR URL from agent output."""
        import re

        # Look for GitHub PR URLs in output
        pr_pattern = r"https://github\.com/[\w-]+/[\w-]+/pull/\d+"
        matches = re.findall(pr_pattern, stdout)

        return matches[-1] if matches else None

    def _extract_trajectory_path(self, stdout: str) -> Optional[str]:
        """Extract trajectory file path from agent output."""
        if "Trajectory saved to" in stdout:
            import re

            match = re.search(r"Trajectory saved to (.+)", stdout)
            if match:
                return match.group(1).strip()
        return "/home/user/trajectory.json"

    async def _cleanup_sandbox(self):
        """Clean up sandbox resources."""
        async with self._lock:
            if self._sandbox:
                try:
                    self._sandbox.close()
                    logger.info("Sandbox closed")
                except Exception as e:
                    logger.warning(f"Failed to close sandbox: {e}")
                finally:
                    self._sandbox = None


# ============================================================================
# SOLVER MANAGER - ORCHESTRATION & DATABASE MANAGEMENT
# ============================================================================


@dataclass
class SolveTaskState:
    """Tracks background task metadata for running solves."""

    solve_id: str
    run_ids: List[str]
    executors: Dict[str, HeadlessSandboxExecutor]
    task: asyncio.Task


@dataclass
class ModelRunPlan:
    """Plan for executing a single model configuration inside a solve."""

    run_id: str
    ai_model_id: int
    model_identifier: str
    temperature: float


class SolverManager(ABC):
    """Base interface describing solver manager operations."""

    @abstractmethod
    async def start_solve(
        self, *, session_id: str, request: StartSolveRequest, user: User
    ) -> StartSolveResponse: ...

    @abstractmethod
    async def get_status(
        self, *, session_id: str, solve_id: str, user: User
    ) -> SolveStatusResponse: ...

    @abstractmethod
    async def cancel_solve(
        self, *, session_id: str, solve_id: str, user: User
    ) -> CancelSolveResponse: ...


class DefaultSolverManager(SolverManager):
    """Concrete solver manager that runs one experiment per solve session."""

    def __init__(
        self, session_factory=SessionLocal, *, max_parallel: Optional[int] = None
    ):
        self._session_factory = session_factory
        self._tasks: Dict[str, SolveTaskState] = {}
        self._lock = asyncio.Lock()
        self._max_parallel = max_parallel or int(os.getenv("SOLVER_MAX_PARALLEL", "3"))
        self._time_budget_s = int(os.getenv("SOLVER_TIME_BUDGET_SECONDS", "5400"))

    async def start_solve(
        self, *, session_id: str, request: StartSolveRequest, user: User
    ) -> StartSolveResponse:
        await self._assert_capacity()

        solve_id = uuid.uuid4().hex
        model_run_plans: List[ModelRunPlan] = []
        issue_url: Optional[str] = None

        db = self._session_factory()
        try:
            chat_session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id, ChatSession.user_id == user.id
                )
                .first()
            )
            if not chat_session:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Session not found for user"
                )

            issue = db.query(Issue).filter(Issue.id == request.issue_id).first()
            if not issue:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Issue not found")
            issue_url = issue.html_url

            ai_models = self._select_models(
                db,
                ai_model_id=request.ai_model_id,
                ai_model_ids=request.ai_model_ids,
            )
            logger.info(
                "Starting solve %s with %d model(s): %s",
                solve_id,
                len(ai_models),
                ", ".join(model.model_id for model in ai_models),
            )

            repo_url = request.repo_url or getattr(issue.repository, "repo_url", None)
            if not repo_url:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="Repository URL is required for solver execution",
                )

            experiments = []
            model_run_plans: List[ModelRunPlan] = []
            solve_runs: List[SolveRun] = []

            for current_model in ai_models:
                run_id = uuid.uuid4().hex
                temperature = self._extract_temperature(current_model)
                experiments.append(
                    {
                        "run_id": run_id,
                        "model": current_model.model_id,
                        "temperature": temperature,
                        "mode": "yolo",
                        "ai_model_id": current_model.id,
                    }
                )
                solve_runs.append(
                    SolveRun(
                        id=run_id,
                        solve_id=solve_id,
                        model=current_model.model_id,
                        temperature=temperature,
                        max_edits=5,
                        evolution="baseline",
                        status=SolveStatus.PENDING.value,
                    )
                )
                model_run_plans.append(
                    ModelRunPlan(
                        run_id=run_id,
                        ai_model_id=current_model.id,
                        model_identifier=current_model.model_id,
                        temperature=temperature,
                    )
                )

            max_parallel = max(len(model_run_plans), 1)
            max_parallel = min(max_parallel, self._max_parallel)

            solve = Solve(
                id=solve_id,
                user_id=user.id,
                session_id=chat_session.id,
                repo_url=repo_url,
                issue_number=issue.number,
                base_branch=request.branch_name,
                status=SolveStatus.PENDING.value,
                matrix={
                    "experiments": experiments,
                    "small_change": request.small_change,
                    "best_effort": request.best_effort,
                    "max_iterations": request.max_iterations,
                    "max_cost": request.max_cost,
                },
                limits={
                    "max_parallel": max_parallel,
                    "time_budget_s": self._time_budget_s,
                },
                requested_by=user.github_username or user.email or "unknown",
                max_parallel=max_parallel,
                time_budget_s=self._time_budget_s,
            )

            # Store user options as attributes for easy access
            solve.small_change = request.small_change
            solve.best_effort = request.best_effort
            solve.max_iterations = request.max_iterations
            solve.max_cost = request.max_cost

            db.add(solve)
            for solve_run in solve_runs:
                db.add(solve_run)
            db.commit()
        finally:
            db.close()

        run_ids = [plan.run_id for plan in model_run_plans]
        executor_registry: Dict[str, HeadlessSandboxExecutor] = {}

        task = asyncio.create_task(
            self._execute_runs(
                solve_id=solve_id,
                run_plans=model_run_plans,
                issue_url=issue_url or "",
                repo_url=repo_url,
                branch_name=request.branch_name,
                executor_registry=executor_registry,
            ),
            name=f"solve-{solve_id}",
        )

        task.add_done_callback(
            lambda t, sid=solve_id: asyncio.create_task(self._cleanup_task(sid))
        )

        async with self._lock:
            self._tasks[solve_id] = SolveTaskState(
                solve_id=solve_id,
                run_ids=run_ids,
                executors=executor_registry,
                task=task,
            )

        return StartSolveResponse(
            solve_session_id=solve_id,
            status=SolveStatus.PENDING,
        )

    async def _execute_runs(
        self,
        *,
        solve_id: str,
        run_plans: List[ModelRunPlan],
        issue_url: str,
        repo_url: str,
        branch_name: str,
        executor_registry: Dict[str, HeadlessSandboxExecutor],
    ):
        """Execute each requested run sequentially inside its own sandbox."""

        if not run_plans:
            logger.error("No run plans available for solve %s", solve_id)
            return

        try:
            for plan in run_plans:
                if plan.run_id in executor_registry:
                    logger.warning(
                        "Run %s already has an executor registered. Skipping duplicate.",
                        plan.run_id,
                    )
                    continue

                executor = HeadlessSandboxExecutor()
                executor_registry[plan.run_id] = executor
                logger.info(
                    "Launching run %s for solve %s with model %s",
                    plan.run_id,
                    solve_id,
                    plan.model_identifier,
                )

                try:
                    await self._execute_run(
                        solve_id=solve_id,
                        run_id=plan.run_id,
                        issue_url=issue_url,
                        repo_url=repo_url,
                        branch_name=branch_name,
                        model_name=plan.model_identifier,
                        executor=executor,
                    )
                finally:
                    executor_registry.pop(plan.run_id, None)
        except asyncio.CancelledError:
            logger.info("Solve %s execution loop cancelled", solve_id)
            raise

    async def get_status(
        self, *, session_id: str, solve_id: str, user: User
    ) -> SolveStatusResponse:
        db = self._session_factory()
        try:
            # Look up ChatSession by string session_id
            chat_session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id, ChatSession.user_id == user.id
                )
                .first()
            )
            if not chat_session:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Session not found for user"
                )

            # Query Solve using integer chat_session.id
            solve = (
                db.query(Solve)
                .filter(
                    Solve.id == solve_id,
                    Solve.session_id == chat_session.id,
                    Solve.user_id == user.id,
                )
                .first()
            )
            if not solve:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Solve session not found"
                )

            runs_out = [SolveRunOut.model_validate(run) for run in solve.runs]
            progress = self._build_progress(solve, runs_out)

            champion = (
                SolveRunOut.model_validate(solve.champion_run)
                if solve.champion_run
                else None
            )

            return SolveStatusResponse(
                solve_session_id=solve.id,
                status=SolveStatus(solve.status),
                progress=progress,
                runs=runs_out,
                champion_run=champion,
                error_message=solve.error_message,
            )
        finally:
            db.close()

    async def cancel_solve(
        self, *, session_id: str, solve_id: str, user: User
    ) -> CancelSolveResponse:
        state: Optional[SolveTaskState] = None
        async with self._lock:
            state = self._tasks.get(solve_id)

        if state:
            for executor in list(state.executors.values()):
                await executor.cancel()
            state.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await state.task

        db = self._session_factory()
        try:
            # Look up ChatSession by string session_id
            chat_session = (
                db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id, ChatSession.user_id == user.id
                )
                .first()
            )
            if not chat_session:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Session not found for user"
                )

            # Query Solve using integer chat_session.id
            solve = (
                db.query(Solve)
                .filter(
                    Solve.id == solve_id,
                    Solve.session_id == chat_session.id,
                    Solve.user_id == user.id,
                )
                .first()
            )
            if not solve:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND, detail="Solve session not found"
                )

            timestamp = utc_now()
            if solve.status not in {
                SolveStatus.COMPLETED.value,
                SolveStatus.CANCELLED.value,
                SolveStatus.FAILED.value,
            }:
                solve.status = SolveStatus.CANCELLED.value
                solve.error_message = "Solve cancelled by user"
                solve.completed_at = timestamp

            for run in solve.runs:
                if run.status not in {
                    SolveStatus.COMPLETED.value,
                    SolveStatus.CANCELLED.value,
                    SolveStatus.FAILED.value,
                }:
                    run.status = SolveStatus.CANCELLED.value
                    run.error_message = "Cancelled by user"
                    run.completed_at = timestamp

            db.commit()
        finally:
            db.close()

        await self._cleanup_task(solve_id)
        return CancelSolveResponse(
            solve_session_id=solve_id,
            status=SolveStatus.CANCELLED,
            message="Solve cancelled",
        )

    async def _execute_run(
        self,
        *,
        solve_id: str,
        run_id: str,
        issue_url: str,
        repo_url: str,
        branch_name: str,
        model_name: str,
        executor: HeadlessSandboxExecutor,
    ):
        db = self._session_factory()
        try:
            solve = db.query(Solve).filter(Solve.id == solve_id).first()
            run = db.query(SolveRun).filter(SolveRun.id == run_id).first()
            if not solve or not run:
                logger.warning("Solve or run record missing for %s", solve_id)
                return

            logger.info(
                "Preparing run %s for solve %s (model=%s, issue=%s)",
                run_id,
                solve_id,
                model_name,
                issue_url,
            )

            now = utc_now()
            solve.status = SolveStatus.RUNNING.value
            solve.started_at = solve.started_at or now
            run.status = SolveStatus.RUNNING.value
            run.started_at = now
            db.commit()

            request = HeadlessSandboxRequest(
                issue_url=issue_url,
                repo_url=repo_url,
                branch_name=branch_name,
                model_name=model_name,
                env={
                    "SOLVE_ID": solve_id,
                    "SOLVE_RUN_ID": run_id,
                    "SMALL_CHANGE": str(getattr(solve, "small_change", False)),
                    "BEST_EFFORT": str(getattr(solve, "best_effort", False)),
                    "MAX_ITERATIONS": str(getattr(solve, "max_iterations", 50)),
                    "MAX_COST": str(getattr(solve, "max_cost", 10.0)),
                },
                verbose=True,
            )

            try:
                result = await executor.run(request)
                self._record_success(db, solve, run, result)
            except SandboxExecutionError as exc:
                self._record_failure(
                    db,
                    solve,
                    run,
                    error_message=str(exc),
                    logs=exc.logs,
                )
            except asyncio.CancelledError:
                self._record_cancelled(db, solve, run)
                raise
            except Exception as exc:  # pragma: no cover - defensive programming
                logger.exception("Solver run failed: %s", exc)
                self._record_failure(
                    db,
                    solve,
                    run,
                    error_message=str(exc),
                    logs="",
                )
        finally:
            db.close()

    def _record_success(
        self, db: Session, solve: Solve, run: SolveRun, result: SandboxRunResult
    ):
        timestamp = result.completed_at
        succeeded = result.exit_code == 0
        run.status = (
            SolveStatus.COMPLETED.value if succeeded else SolveStatus.FAILED.value
        )
        run.completed_at = timestamp
        run.tests_passed = succeeded
        run.latency_ms = result.duration_ms
        run.sandbox_id = result.sandbox_id
        run.pr_url = result.pr_url
        run.error_message = None if succeeded else "Agent execution failed"
        if result.trajectory_file:
            run.trajectory_data = {"file_path": result.trajectory_file}
        preview_length = 2000
        run.diagnostics = {
            "command": result.command,
            "stdout_tail": (result.stdout or "")[-preview_length:],
            "stderr_tail": (result.stderr or "")[-preview_length:],
            "tfbd_path": result.tfbd_path,
            "script_path": result.script_path,
            "trajectory_file": result.trajectory_file,
        }

        if succeeded and not solve.champion_run_id:
            solve.champion_run_id = run.id
            solve.error_message = None

        logger.info(
            "Run %s for solve %s completed (exit_code=%s, success=%s)",
            run.id,
            solve.id,
            result.exit_code,
            succeeded,
        )

        self._finalize_solve_if_complete(db, solve, completed_at=timestamp)
        db.commit()

    def _record_failure(
        self,
        db: Session,
        solve: Solve,
        run: SolveRun,
        *,
        error_message: str,
        logs: str,
    ):
        timestamp = utc_now()
        run.status = SolveStatus.FAILED.value
        run.completed_at = timestamp
        run.error_message = error_message
        run.diagnostics = {"error_logs": logs[-4000:]}

        if not solve.error_message:
            solve.error_message = error_message

        logger.warning(
            "Run %s for solve %s failed: %s", run.id, solve.id, error_message
        )

        self._finalize_solve_if_complete(db, solve, completed_at=timestamp)
        db.commit()

    def _record_cancelled(self, db: Session, solve: Solve, run: SolveRun):
        timestamp = utc_now()
        run.status = SolveStatus.CANCELLED.value
        run.completed_at = timestamp
        run.error_message = "Cancelled by user"

        solve.status = SolveStatus.CANCELLED.value
        solve.error_message = "Cancelled by user"
        solve.completed_at = timestamp

        logger.info("Run %s for solve %s cancelled", run.id, solve.id)

        self._finalize_solve_if_complete(db, solve, completed_at=timestamp)
        db.commit()

    async def _cleanup_task(self, solve_id: str):
        async with self._lock:
            self._tasks.pop(solve_id, None)

    async def _assert_capacity(self):
        async with self._lock:
            if len(self._tasks) >= self._max_parallel:
                raise HTTPException(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Maximum number of concurrent solves reached",
                )

    def _finalize_solve_if_complete(
        self, db: Session, solve: Solve, *, completed_at: Optional[datetime] = None
    ):
        """Mark the parent solve complete once all runs are resolved."""

        if solve.status == SolveStatus.CANCELLED.value:
            return

        pending_statuses = {
            SolveStatus.PENDING.value,
            SolveStatus.RUNNING.value,
        }
        pending_runs = (
            db.query(SolveRun)
            .filter(
                SolveRun.solve_id == solve.id,
                SolveRun.status.in_(pending_statuses),
            )
            .count()
        )

        if pending_runs > 0:
            solve.status = SolveStatus.RUNNING.value
            return

        finish_time = completed_at or utc_now()
        solve.completed_at = solve.completed_at or finish_time

        if solve.champion_run_id:
            solve.status = SolveStatus.COMPLETED.value
            solve.error_message = None
        else:
            solve.status = SolveStatus.FAILED.value
            solve.error_message = solve.error_message or "All runs failed"

    def _select_models(
        self,
        db: Session,
        *,
        ai_model_id: Optional[int],
        ai_model_ids: Optional[List[int]],
    ) -> List[AIModel]:
        """Resolve requested models, preserving caller ordering."""

        base_query = db.query(AIModel).filter(AIModel.is_active.is_(True))

        if ai_model_ids:
            models = base_query.filter(AIModel.id.in_(ai_model_ids)).all()
            found_by_id = {model.id: model for model in models}
            ordered_models: List[AIModel] = []
            missing_ids: List[int] = []
            for requested_id in ai_model_ids:
                model = found_by_id.get(requested_id)
                if model:
                    ordered_models.append(model)
                else:
                    missing_ids.append(requested_id)

            if missing_ids:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail=f"AI models not found: {', '.join(map(str, missing_ids))}",
                )

            if not ordered_models:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail="No active AI models available for the requested IDs",
                )

            return ordered_models

        if ai_model_id:
            model = (
                base_query.filter(AIModel.id == ai_model_id)
                .order_by(AIModel.id.asc())
                .first()
            )
            if not model:
                raise HTTPException(
                    status.HTTP_404_NOT_FOUND,
                    detail="AI model not found or inactive",
                )
            return [model]

        default_model = base_query.order_by(AIModel.id.asc()).first()
        if not default_model:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="No active AI models configured",
            )
        return [default_model]

    @staticmethod
    def _extract_temperature(model: AIModel) -> float:
        try:
            return float((model.config or {}).get("temperature", 0.1))
        except (TypeError, ValueError):
            return 0.1

    @staticmethod
    def _build_progress(solve: Solve, runs: list[SolveRunOut]) -> SolveProgress:
        runs_total = len(runs)
        runs_completed = sum(1 for run in runs if run.status == SolveStatus.COMPLETED)
        runs_failed = sum(1 for run in runs if run.status == SolveStatus.FAILED)
        runs_running = sum(1 for run in runs if run.status == SolveStatus.RUNNING)

        return SolveProgress(
            runs_total=runs_total,
            runs_completed=runs_completed,
            runs_failed=runs_failed,
            runs_running=runs_running,
            last_update=solve.updated_at or utc_now(),
            message=solve.status,
        )
