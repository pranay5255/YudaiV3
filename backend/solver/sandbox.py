"""
Modal Sandbox operations for solver execution.

This module handles all sandbox-related operations including:
- Modal sandbox creation and lifecycle management
- Sandbox environment configuration
- Agent script and config artifact upload
- Sandbox command execution with streaming output support
- Result parsing and cleanup

Streaming Example:
    # Basic streaming with callbacks
    def on_stdout(chunk: str):
        print(f"Output: {chunk}")

    result = await sandbox.run_command(
        "python agent.py",
        on_stdout=on_stdout,
        on_stderr=lambda chunk: print(f"Error: {chunk}")
    )

    # Streaming with automatic logging
    result = await sandbox.run_command_with_logging(
        "python agent.py",
        logger=my_logger,
        log_prefix="[Agent] "
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import modal
from solver.agentScriptGen import AgentScriptParams, build_agent_script

from utils import utc_now

logger = logging.getLogger(__name__)

# Trajectory storage configuration
TRAJECTORY_STORAGE_DIR = Path(
    os.getenv("TRAJECTORY_STORAGE_DIR", "/tmp/yudai/trajectories")
)
TRAJECTORY_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Template and path constants
TFBD_TEMPLATE_PATH = Path(__file__).with_name("tfbd.yaml")
DEFAULT_TFBD_FALLBACK = """agent:
  system_template: "You are a helpful assistant that can interact with a computer."
model:
  model_name: "{model_name}"
  model_class: "openrouter"
  model_kwargs:
    temperature: 0.4
"""

REMOTE_TFBD_PATH = "/home/user/tfbd.yaml"
REMOTE_AGENT_SCRIPT_PATH = "/home/user/run_agent.py"
MINI_SWE_AGENT_PATH = "/home/user/mini-swe-agent"
MINI_SWE_AGENT_REPO = "https://github.com/pranay5255/yudai-swe-agent.git"
SOLVER_IMAGE = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "curl")
    .pip_install("requests", "pyyaml")
)

_modal_app: Optional[modal.App] = None
_modal_app_lock = asyncio.Lock()


async def _call_modal_async(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Call Modal APIs using async variants when available.

    Modal exposes `.aio` wrappers on many methods. We use them when present and
    fall back to a worker thread for sync-only methods.
    """

    aio_fn = getattr(fn, "aio", None)
    if aio_fn is not None:
        return await aio_fn(*args, **kwargs)
    return await asyncio.to_thread(fn, *args, **kwargs)


async def _get_modal_app() -> modal.App:
    """Lazily initialize and cache the Modal app for sandbox creation."""

    global _modal_app
    if _modal_app is not None:
        return _modal_app

    async with _modal_app_lock:
        if _modal_app is None:
            _modal_app = await _call_modal_async(
                modal.App.lookup,
                "yudai-solver",
                create_if_missing=True,
            )
    return _modal_app


# ============================================================================
# SANDBOX CONFIGURATION BUILDERS
# ============================================================================


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

    constraints: List[str] = []
    if small_change:
        constraints.append(
            "Limit code edits to minimal, targeted changes directly tied to the issue."
        )
    if best_effort:
        constraints.append(
            "Continue working toward a solution even if automated checks fail, documenting any failures."
        )

    return _inject_constraints(updated_template, constraints)


def _inject_constraints(template: str, constraints: List[str]) -> str:
    """Inject constraint guidance into the instance template section."""

    if not constraints:
        return template

    insertion_point = "    ## Recommended Workflow"

    constraint_lines = ["    ## Constraints", ""]
    constraint_lines.extend(f"    - {constraint}" for constraint in constraints)
    constraint_block = "\n".join(constraint_lines)

    if insertion_point in template:
        return template.replace(
            insertion_point, f"{constraint_block}\n\n{insertion_point}", 1
        )

    trailing_newline = "" if template.endswith("\n") else "\n"
    bullets = "\n".join(f"- {constraint}" for constraint in constraints)
    return f"{template.rstrip()}{trailing_newline}\n\n# Constraints\n{bullets}\n"


def build_tfbd_config(params: AgentScriptParams) -> str:
    """Create a tfbd.yaml configuration string from agent parameters."""

    return build_tfbd_template(
        model_name=params.model_name,
        small_change=params.small_change,
        best_effort=params.best_effort,
        max_iterations=params.max_iterations,
        max_cost=params.max_cost,
    )


def build_sandbox_env_bundle(
    *,
    openrouter_api_key: str,
    github_token: Optional[str],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Construct sandbox and command environments for Modal sandbox execution."""

    base_env: Dict[str, Any] = {"OPENROUTER_API_KEY": openrouter_api_key}
    if github_token:
        base_env["GITHUB_TOKEN"] = github_token

    sandbox_env = {
        key: value for key, value in base_env.items() if value not in (None, "")
    }
    command_env = sandbox_env.copy()
    return sandbox_env, command_env


# ============================================================================
# SANDBOX DATA MODELS
# ============================================================================


@dataclass
class TrajectoryMetadata:
    """Metadata extracted from trajectory file."""

    exit_status: Optional[str] = None
    submission: Optional[str] = None
    instance_cost: Optional[float] = None
    api_calls: Optional[int] = None
    mini_version: Optional[str] = None
    model_name: Optional[str] = None
    total_messages: Optional[int] = None


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
    local_trajectory_path: Optional[str] = None
    trajectory_metadata: Optional[TrajectoryMetadata] = None
    pr_url: Optional[str] = None
    tfbd_path: Optional[str] = None
    script_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class HeadlessSandboxRequest:
    """Request parameters for headless sandbox execution."""

    issue_url: str
    repo_url: str
    branch_name: str = "main"
    model_name: str = "anthropic/claude-sonnet-4-5-20250929"
    temperature: float = 0.1
    small_change: bool = False
    best_effort: bool = False
    max_iterations: int = 50
    max_cost: float = 10.0
    max_tokens: int = 4000
    solve_id: Optional[str] = None
    solve_run_id: Optional[str] = None
    issue_text: Optional[str] = None
    verbose: bool = False
    openrouter_call_delay: float = 0.0
    create_pr: bool = True
    timeout: int = 1800  # 30 minutes default for agent execution


class SandboxExecutionError(Exception):
    """Raised when sandbox execution fails."""

    def __init__(self, message: str, logs: str = ""):
        super().__init__(message)
        self.logs = logs


# ============================================================================
# ASYNC SANDBOX ADAPTER
# ============================================================================


@dataclass
class CommandResult:
    """Result object returned by sandbox command execution."""

    exit_code: int
    stdout: str
    stderr: str


def _coerce_stream_chunk(chunk: Any) -> str:
    """Normalize stream chunks to text."""

    if chunk is None:
        return ""
    if isinstance(chunk, bytes):
        return chunk.decode("utf-8", errors="replace")
    return str(chunk)


@dataclass
class SandboxClient:
    """Thin asynchronous adapter around the Modal Sandbox SDK."""

    _sandbox: modal.Sandbox

    @classmethod
    async def create(
        cls,
        *,
        envs: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, str]] = None,
        timeout: int = 1800,  # 30 minutes default for agent execution
    ) -> "SandboxClient":
        sanitized_envs = {
            key: value for key, value in (envs or {}).items() if value not in (None, "")
        }
        sanitized_metadata = {
            key: str(value)
            for key, value in (metadata or {}).items()
            if value not in (None, "")
        }
        logger.info(
            "Creating Modal sandbox with env=%s metadata=%s timeout=%ds",
            sanitized_envs,
            sanitized_metadata,
            timeout,
        )

        app = await _get_modal_app()
        sandbox = await _call_modal_async(
            modal.Sandbox.create,
            app=app,
            image=SOLVER_IMAGE,
            env=sanitized_envs or None,
            timeout=timeout,
        )
        client = cls(_sandbox=sandbox)
        if sanitized_metadata:
            await _call_modal_async(client._sandbox.set_tags, sanitized_metadata)
        return client

    async def _consume_stream(
        self,
        stream: Any,
        sink: List[str],
        callback: Optional[Callable[[str], None]],
    ) -> None:
        if stream is None:
            return

        if hasattr(stream, "__aiter__"):
            async for chunk in stream:
                text = _coerce_stream_chunk(chunk)
                if not text:
                    continue
                sink.append(text)
                if callback:
                    callback(text)
            return

        def _consume_sync() -> None:
            for chunk in stream:
                text = _coerce_stream_chunk(chunk)
                if not text:
                    continue
                sink.append(text)
                if callback:
                    callback(text)

        await asyncio.to_thread(_consume_sync)

    async def _resolve_return_code(self, process: Any) -> int:
        exit_code = getattr(process, "returncode", None)
        if isinstance(exit_code, int):
            return exit_code

        wait_fn = getattr(process, "wait", None)
        if callable(wait_fn):
            wait_result = await _call_modal_async(wait_fn)
            if isinstance(wait_result, int):
                return wait_result
            maybe_code = getattr(wait_result, "returncode", None)
            if isinstance(maybe_code, int):
                return maybe_code

        return 0

    async def run_command(
        self,
        command: str,
        *,
        envs: Optional[Dict[str, str]] = None,
        timeout: int = 0,  # 0 disables timeout for long-running agent commands
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
    ) -> CommandResult:
        """
        Run a command in the sandbox with optional streaming callbacks.

        Args:
            command: The command to execute
            envs: Environment variables for the command
            timeout: Command timeout (0 = disabled)
            on_stdout: Callback function for stdout streaming (receives str chunks)
            on_stderr: Callback function for stderr streaming (receives str chunks)
        """
        sanitized_envs = {
            key: value for key, value in (envs or {}).items() if value not in (None, "")
        }
        exec_kwargs: Dict[str, Any] = {"env": sanitized_envs or None}
        if timeout and timeout > 0:
            exec_kwargs["timeout"] = timeout

        process = await _call_modal_async(
            self._sandbox.exec,
            "bash",
            "-c",
            command,
            **exec_kwargs,
        )

        stdout_chunks: List[str] = []
        stderr_chunks: List[str] = []
        await asyncio.gather(
            self._consume_stream(
                getattr(process, "stdout", None),
                stdout_chunks,
                on_stdout,
            ),
            self._consume_stream(
                getattr(process, "stderr", None),
                stderr_chunks,
                on_stderr,
            ),
        )

        exit_code = await self._resolve_return_code(process)
        return CommandResult(
            exit_code=exit_code,
            stdout="".join(stdout_chunks),
            stderr="".join(stderr_chunks),
        )

    async def run_command_with_logging(
        self,
        command: str,
        *,
        envs: Optional[Dict[str, str]] = None,
        timeout: int = 0,
        logger: Optional[logging.Logger] = None,
        log_prefix: str = "",
    ) -> CommandResult:
        """
        Run a command with automatic stdout/stderr logging.

        Args:
            command: The command to execute
            envs: Environment variables for the command
            timeout: Command timeout (0 = disabled)
            logger: Logger instance to use (defaults to module logger)
            log_prefix: Prefix for log messages
        """
        if logger is None:
            logger = logging.getLogger(__name__)

        def log_stdout(chunk: str) -> None:
            if chunk.strip():
                logger.info("%sSTDOUT: %s", log_prefix, chunk.strip())

        def log_stderr(chunk: str) -> None:
            if chunk.strip():
                logger.warning("%sSTDERR: %s", log_prefix, chunk.strip())

        return await self.run_command(
            command,
            envs=envs,
            timeout=timeout,
            on_stdout=log_stdout,
            on_stderr=log_stderr,
        )

    async def write_file(self, path: str, content: str) -> None:
        def _write() -> None:
            handle = self._sandbox.open(path, "w")
            try:
                handle.write(content)
            finally:
                handle.close()

        await asyncio.to_thread(_write)

    async def read_file(self, path: str) -> bytes:
        """Read file content from sandbox."""

        def _read() -> bytes:
            handle = self._sandbox.open(path, "rb")
            try:
                return handle.read()
            finally:
                handle.close()

        return await asyncio.to_thread(_read)

    async def close(self) -> None:
        await _call_modal_async(self._sandbox.terminate)

    async def get_id(self) -> str:
        return str(self._sandbox.object_id)

    async def get_metadata(self) -> Dict[str, str]:
        tags = await _call_modal_async(self._sandbox.get_tags)
        if not isinstance(tags, dict):
            return {}
        return {str(key): str(value) for key, value in tags.items()}


# ============================================================================
# SANDBOX OPERATIONS
# ============================================================================


async def create_sandbox_instance(
    *,
    sandbox_env: Dict[str, str],
    metadata: Dict[str, str],
    timeout: int = 1800,  # 30 minutes default for agent execution
) -> SandboxClient:
    """Create a SandboxClient with the provided environment and metadata."""

    logger.info(
        "Requesting sandbox creation (env keys=%s, metadata=%s, timeout=%ds)",
        list(sandbox_env.keys()),
        metadata,
        timeout,
    )
    return await SandboxClient.create(
        envs=sandbox_env, metadata=metadata, timeout=timeout
    )


async def upload_solver_artifacts(
    *,
    sandbox: SandboxClient,
    params: AgentScriptParams,
) -> Tuple[str, str]:
    """Upload tfbd.yaml and agent runner script into the sandbox."""

    tfbd_config = build_tfbd_config(params)
    await sandbox.write_file(REMOTE_TFBD_PATH, tfbd_config)

    python_script = build_agent_script(params)
    await sandbox.write_file(REMOTE_AGENT_SCRIPT_PATH, python_script)

    return REMOTE_TFBD_PATH, REMOTE_AGENT_SCRIPT_PATH


def parse_trajectory_metadata(trajectory_data: Dict[str, Any]) -> TrajectoryMetadata:
    """Extract metadata from trajectory JSON."""

    info = trajectory_data.get("info", {})
    model_stats = info.get("model_stats", {})
    config = info.get("config", {})
    model_config = config.get("model", {})
    messages = trajectory_data.get("messages", [])

    return TrajectoryMetadata(
        exit_status=info.get("exit_status"),
        submission=info.get("submission"),
        instance_cost=model_stats.get("instance_cost"),
        api_calls=model_stats.get("api_calls"),
        mini_version=info.get("mini_version"),
        model_name=model_config.get("model_name"),
        total_messages=len(messages),
    )


async def download_trajectory_file(
    *,
    sandbox: SandboxClient,
    remote_path: str,
    solve_id: str,
    run_id: str,
    repo_url: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[TrajectoryMetadata]]:
    """
    Download trajectory file from sandbox and save locally.

    Args:
        sandbox: Active sandbox instance
        remote_path: Path to trajectory file in sandbox
        solve_id: Solve session identifier
        run_id: Run identifier
        repo_url: Repository URL for filename
        session_id: Session ID for filename

    Returns:
        Tuple of (local_path, metadata) or (None, None) if download fails
    """

    try:
        logger.info(f"Downloading trajectory from sandbox: {remote_path}")

        # Read file from sandbox
        trajectory_bytes = await sandbox.read_file(remote_path)

        # Create local storage path with sanitized repo URL
        repo_slug = "unknown"
        if repo_url:
            # Extract owner/repo from URL and sanitize
            repo_slug = repo_url.replace("https://", "").replace("http://", "")
            repo_slug = (
                repo_slug.replace("github.com/", "").replace("/", "_").replace(".", "_")
            )

        # Use session_id if provided, otherwise use run_id
        session_part = session_id if session_id else run_id
        local_filename = f"{repo_slug}_{solve_id}_{session_part}.traj.json"
        local_path = TRAJECTORY_STORAGE_DIR / local_filename

        # Write to local storage
        local_path.write_bytes(trajectory_bytes)
        logger.info(f"Trajectory saved to: {local_path}")

        # Parse metadata
        try:
            trajectory_data = json.loads(trajectory_bytes.decode("utf-8"))
            metadata = parse_trajectory_metadata(trajectory_data)
            logger.info(
                f"Trajectory metadata: exit_status={metadata.exit_status}, "
                f"cost={metadata.instance_cost}, api_calls={metadata.api_calls}"
            )
        except Exception as e:
            logger.warning(f"Failed to parse trajectory metadata: {e}")
            metadata = None

        return str(local_path), metadata

    except Exception as e:
        logger.error(f"Failed to download trajectory file: {e}")
        return None, None


# ============================================================================
# HEADLESS SANDBOX EXECUTOR
# ============================================================================


class HeadlessSandboxExecutor:
    """
    Executes mini-swe-agent in Modal sandboxes using Python bindings.

    This executor:
    1. Creates a Modal sandbox with required dependencies
    2. Generates execution artifacts (tfbd.yaml + runner script)
    3. Executes the uploaded script which performs repository setup and agent run
    4. Captures execution results and trajectory data
    5. Manages sandbox lifecycle and cleanup
    """

    def __init__(self):
        self._sandbox: Optional[SandboxClient] = None
        self._cancelled = False
        self._lock = asyncio.Lock()

    async def run(self, request: HeadlessSandboxRequest) -> SandboxRunResult:
        """
        Execute mini-swe-agent in Modal sandbox using Python bindings.

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

            sandbox_env, command_env = build_sandbox_env_bundle(
                openrouter_api_key=openrouter_api_key,
                github_token=github_token,
            )

            if request.openrouter_call_delay and request.openrouter_call_delay > 0:
                delay_str = f"{request.openrouter_call_delay:.2f}"
                sandbox_env["OPENROUTER_CALL_DELAY"] = delay_str
                command_env["OPENROUTER_CALL_DELAY"] = delay_str
                logger.info(
                    "Applying OpenRouter call delay of %ss to sandbox environment",
                    delay_str,
                )

            # Create Modal sandbox
            logger.info("Creating Modal sandbox with mini-swe-agent...")
            metadata = self._build_metadata(request)
            async with self._lock:
                if self._cancelled:
                    raise SandboxExecutionError("Execution cancelled before start")
                self._sandbox = await create_sandbox_instance(
                    sandbox_env=sandbox_env,
                    metadata=metadata,
                    timeout=request.timeout,
                )

            sandbox = self._sandbox
            if not sandbox:
                raise SandboxExecutionError("Failed to create sandbox")

            sandbox_id = await sandbox.get_id()
            logger.info(f"Sandbox created: {sandbox_id}")
            if metadata:
                logger.info("Sandbox metadata attached: %s", metadata)

            # Create tfbd.yaml config with the selected model and user options for traceability
            script_params = AgentScriptParams.from_payload(
                model_name=request.model_name,
                repo_url=request.repo_url,
                branch_name=request.branch_name,
                issue_url=request.issue_url,
                issue_text=request.issue_text,
                payload={
                    "temperature": request.temperature,
                    "max_tokens": request.max_tokens,
                    "max_iterations": request.max_iterations,
                    "max_cost": request.max_cost,
                    "small_change": request.small_change,
                    "best_effort": request.best_effort,
                    "create_pr": request.create_pr,
                },
                verbose=request.verbose,
            )
            tfbd_path, script_path = await upload_solver_artifacts(
                sandbox=sandbox,
                params=script_params,
            )
            logger.info(
                "Uploaded tfbd.yaml template to sandbox %s for model %s (small_change=%s, best_effort=%s)",
                sandbox_id,
                script_params.model_name,
                script_params.small_change,
                script_params.best_effort,
            )
            logger.info(
                "Uploaded headless execution script to sandbox %s",
                sandbox_id,
            )

            # Prepare mini-swe-agent dependencies
            await self._prepare_mini_swe_agent(
                sandbox=sandbox,
                envs=command_env,
            )

            # Execute the agent script with streaming output
            logger.info(
                "Executing mini-swe-agent in sandbox %s (repo=%s, issue=%s, model=%s)",
                sandbox_id,
                request.repo_url,
                request.issue_url,
                request.model_name,
            )
            result = await sandbox.run_command_with_logging(
                f"python {script_path}",
                envs=command_env,
                timeout=0,  # Disable command timeout for agent execution
                logger=logger,
                log_prefix=f"[Agent {sandbox_id}] ",
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

            # Download trajectory file from sandbox
            local_trajectory_path = None
            trajectory_metadata = None

            if trajectory_file and request.solve_id and request.solve_run_id:
                logger.info(
                    f"Attempting to download trajectory file: {trajectory_file}"
                )
                (
                    local_trajectory_path,
                    trajectory_metadata,
                ) = await download_trajectory_file(
                    sandbox=sandbox,
                    remote_path=trajectory_file,
                    solve_id=request.solve_id,
                    run_id=request.solve_run_id,
                    repo_url=request.repo_url,
                    session_id=None,  # Will be added when available in request
                )

                if local_trajectory_path:
                    logger.info(
                        f"Trajectory downloaded successfully: {local_trajectory_path}"
                    )
                else:
                    logger.warning("Failed to download trajectory file from sandbox")
            else:
                logger.info(
                    "Skipping trajectory download (missing trajectory_file=%s, solve_id=%s, run_id=%s)",
                    trajectory_file,
                    request.solve_id,
                    request.solve_run_id,
                )

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
                local_trajectory_path=local_trajectory_path,
                trajectory_metadata=trajectory_metadata,
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
                    await self._sandbox.close()
                    logger.info("Sandbox cancelled and closed")
                except Exception as e:
                    logger.warning(f"Failed to close sandbox during cancellation: {e}")
                finally:
                    self._sandbox = None

    async def _prepare_mini_swe_agent(
        self,
        *,
        sandbox: SandboxClient,
        envs: Dict[str, str],
    ) -> None:
        """Ensure mini-swe-agent and runtime dependencies are available in sandbox."""

        setup_commands = [
            ("if [ ! -d {path} ]; then git clone --depth 1 {repo} {path}; fi").format(
                path=MINI_SWE_AGENT_PATH, repo=MINI_SWE_AGENT_REPO
            ),
            f"python3 -m pip install --no-cache-dir -e {MINI_SWE_AGENT_PATH}",
        ]

        for command in setup_commands:
            logger.info("Running sandbox setup command: %s", command)
            await sandbox.run_command(command, envs=envs)

    def _build_metadata(self, request: HeadlessSandboxRequest) -> Dict[str, str]:
        metadata: Dict[str, Any] = {
            "solve_id": request.solve_id,
            "solve_run_id": request.solve_run_id,
            "issue_url": request.issue_url,
            "repo_url": request.repo_url,
            "branch_name": request.branch_name,
            "model_name": request.model_name,
            "small_change": request.small_change,
            "best_effort": request.best_effort,
        }
        metadata["created_at"] = utc_now().isoformat()
        return {
            key: str(value)
            for key, value in metadata.items()
            if value not in (None, "")
        }

    def _extract_pr_url(self, stdout: str) -> Optional[str]:
        """Extract PR URL from agent output."""
        # Look for GitHub PR URLs in output
        pr_pattern = r"https://github\.com/[\w-]+/[\w-]+/pull/\d+"
        matches = re.findall(pr_pattern, stdout)

        return matches[-1] if matches else None

    def _extract_trajectory_path(self, stdout: str) -> Optional[str]:
        """Extract trajectory file path from agent output."""
        if "Trajectory saved to" in stdout:
            match = re.search(r"Trajectory saved to (.+)", stdout)
            if match:
                return match.group(1).strip()
        # Fallback to the default output path used in run_agent.py
        return "/home/user/last_mini_run.traj.json"

    async def _cleanup_sandbox(self):
        """Clean up sandbox resources."""
        async with self._lock:
            if self._sandbox:
                try:
                    await self._sandbox.close()
                    logger.info("Sandbox closed")
                except Exception as e:
                    logger.warning(f"Failed to close sandbox: {e}")
                finally:
                    self._sandbox = None
