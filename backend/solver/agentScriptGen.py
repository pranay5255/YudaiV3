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
from textwrap import dedent
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
        }


SCRIPT_TEMPLATE = Template(
    dedent(
        """\
        #!/usr/bin/env python3
        '''
        Mini-SWE-Agent execution script using Python bindings.
        Generated automatically by YudaiV3 solver manager.
        '''
        import contextlib
        import json
        import logging
        import os
        import shutil
        import subprocess
        import sys
        from pathlib import Path
        from typing import Dict, List, Optional

        from minisweagent.agents.default import DefaultAgent
        from minisweagent.environments.local import LocalEnvironment
        from minisweagent.models import get_model
        from minisweagent.run.utils.save import save_traj
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        logging.basicConfig(
            level=logging.$log_level,
            format="[%(levelname)s] %(message)s"
        )

        LOG_LEVEL = logging.$log_level
        TFBD_PATH = Path("/home/user/tfbd.yaml")
        TESTBED_PATH = Path("/home/user/testbed")
        MINI_SWE_ROOT = Path("/home/user/mini-swe-agent")
        TRAJECTORY_PATH = Path("/home/user/trajectory.json")

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

        SOLVE_PAYLOAD = {
            "small_change": SMALL_CHANGE,
            "best_effort": BEST_EFFORT,
            "max_iterations": MAX_ITERATIONS,
            "max_cost": MAX_COST,
        }

        logger = logging.getLogger("yudai.solver.script")


        def _log_command_output(result: subprocess.CompletedProcess) -> None:
            stdout = (result.stdout or "").strip()
            if stdout:
                logger.debug("stdout:\\n%s", stdout)
            stderr = (result.stderr or "").strip()
            if stderr:
                logger.debug("stderr:\\n%s", stderr)


        def _run_command(
            command: List[str],
            *,
            cwd: Optional[Path] = None,
        ) -> subprocess.CompletedProcess:
            logger.info("Running command: %s", " ".join(command))
            result = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=False,
            )
            _log_command_output(result)
            if result.returncode != 0:
                raise RuntimeError(
                    f"Command {' '.join(command)} failed with exit code {result.returncode}"
                )
            return result


        def _prepare_clone_url(repo_url: str, token: Optional[str]) -> str:
            sanitized = repo_url.rstrip("/")
            if token and "github.com" in sanitized:
                repo_path = sanitized.split("github.com/", 1)[-1]
                if repo_path.endswith(".git"):
                    repo_path = repo_path[:-4]
                return f"https://x-access-token:{token}@github.com/{repo_path}.git"
            if sanitized.endswith(".git"):
                return sanitized
            return f"{sanitized}.git"


        def _install_mini_swe_agent() -> None:
            logger.info("Ensuring mini-swe-agent repository is available")
            if not MINI_SWE_ROOT.exists():
                _run_command(
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "https://github.com/pranay5255/yudai-swe-agent.git",
                        str(MINI_SWE_ROOT),
                    ],
                    cwd=MINI_SWE_ROOT.parent,
                )
            _run_command(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-cache-dir",
                    "-e",
                    ".",
                ],
                cwd=MINI_SWE_ROOT,
            )


        def _clone_repository(
            *,
            repo_url: str,
            branch_name: str,
            token: Optional[str],
        ) -> None:
            if TESTBED_PATH.exists():
                shutil.rmtree(TESTBED_PATH)
            clone_url = _prepare_clone_url(repo_url, token)
            command = ["git", "clone", "--depth", "1"]
            if branch_name:
                command.extend(["--branch", branch_name])
            command.extend([clone_url, str(TESTBED_PATH)])
            _run_command(command, cwd=TESTBED_PATH.parent)


        def _fetch_issue_text(issue_url: str, token: Optional[str]) -> Optional[str]:
            if not issue_url:
                return None
            api_url = issue_url.replace(
                "https://github.com/", "https://api.github.com/repos/"
            )
            headers = {"Accept": "application/vnd.github+json"}
            if token:
                headers["Authorization"] = f"token {token}"
            request = Request(api_url, headers=headers)
            try:
                with urlopen(request, timeout=30) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                logger.warning("Failed to fetch GitHub issue: %s", exc)
                return None
            title = payload.get("title", "No title")
            body = payload.get("body", "")
            return f"GitHub Issue: {title}\\n\\n{body}"


        def _resolve_issue_text(token: Optional[str]) -> str:
            if isinstance(ISSUE_TEXT_LITERAL, str) and ISSUE_TEXT_LITERAL.strip():
                return ISSUE_TEXT_LITERAL
            fetched = _fetch_issue_text(ISSUE_URL, token)
            if fetched:
                return fetched
            raise RuntimeError("Issue text not available for mini-swe-agent execution")


        def _assert_capacity() -> None:
            if not os.getenv("OPENROUTER_API_KEY"):
                raise RuntimeError("OPENROUTER_API_KEY environment variable required")
            if not TFBD_PATH.exists():
                raise RuntimeError(f"Expected tfbd.yaml at {TFBD_PATH}")


        def _select_models(model_name: str) -> Dict[str, str]:
            if not model_name:
                raise RuntimeError("Model name missing")
            logger.info("Selected model: %s", model_name)
            return {"model_name": model_name}


        def _record_success(result: Dict[str, str]) -> None:
            payload = {
                "exit_status": result["exit_status"],
                "result": result["result"],
                "trajectory_file": str(TRAJECTORY_PATH),
                "tfbd_path": str(TFBD_PATH),
                "repository_path": str(TESTBED_PATH),
                "solve_payload": SOLVE_PAYLOAD,
            }
            Path("/home/user/solve_success.json").write_text(
                json.dumps(payload, indent=2)
            )
            logger.info("Recorded success payload to /home/user/solve_success.json")


        def _record_failure(error: Exception) -> Dict[str, str]:
            payload = {"error": str(error)}
            Path("/home/user/solve_failure.json").write_text(
                json.dumps(payload, indent=2)
            )
            logger.error("Solve run failed: %s", error)
            return payload


        def _finalize_solve_if_complete(payload: Dict[str, int]) -> None:
            summary = {
                "exit_code": payload["exit_code"],
                "completed": payload["exit_code"] == 0,
            }
            Path("/home/user/solve_final_state.json").write_text(
                json.dumps(summary, indent=2)
            )
            logger.info("Solve final state written to /home/user/solve_final_state.json")


        @contextlib.contextmanager
        def _workspace(path: Path):
            if not path.exists():
                raise RuntimeError(f"Workspace missing at {path}")
            original = Path.cwd()
            os.chdir(path)
            try:
                yield
            finally:
                os.chdir(original)


        def _execute_run(
            *,
            issue_text: str,
            model_name: str,
        ) -> Dict[str, str]:
            if not issue_text:
                raise RuntimeError("Issue text required for execution")
            config = {
                "model_name": model_name,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
            }
            agent_config = {
                "mode": "yolo",
                "max_iterations": MAX_ITERATIONS,
                "max_cost": MAX_COST,
            }
            with _workspace(TESTBED_PATH):
                agent = DefaultAgent(
                    get_model(model_name=model_name, config=config),
                    LocalEnvironment(),
                    **agent_config,
                )
                exit_status, result = agent.run(issue_text)
                save_traj(agent, TRAJECTORY_PATH, exit_status=exit_status, result=result)
            logger.info("Trajectory saved to %s", TRAJECTORY_PATH)
            serialized_result = (
                result
                if isinstance(result, str)
                else json.dumps(result, ensure_ascii=True)
            )
            return {
                "exit_status": exit_status,
                "result": serialized_result,
            }


        def main():
            '''Execute mini-swe-agent on the GitHub issue.'''

            logging.getLogger().setLevel(LOG_LEVEL)
            logging.info("Solve payload: %s", SOLVE_PAYLOAD)
            github_token = os.getenv("GITHUB_TOKEN")
            try:
                _assert_capacity()
                model_context = _select_models(MODEL_NAME)
                _install_mini_swe_agent()
                _clone_repository(
                    repo_url=REPO_URL,
                    branch_name=BRANCH_NAME,
                    token=github_token,
                )
                issue_text = _resolve_issue_text(github_token)

                logging.info("Starting mini-swe-agent execution...")
                execution = _execute_run(
                    issue_text=issue_text,
                    model_name=model_context["model_name"],
                )
                _record_success(execution)

                exit_code = 0 if execution["exit_status"] == "finished" else 1
                _finalize_solve_if_complete({"exit_code": exit_code})

                if exit_code == 0:
                    print("\\n✓ Agent completed successfully")
                    print(f"Result: {execution['result']}")
                    return 0

                print("\\n✗ Agent failed with status:", execution["exit_status"])
                print(f"Result: {execution['result']}")
                return exit_code

            except KeyboardInterrupt:
                logging.warning("Execution interrupted")
                _record_failure(RuntimeError("Execution interrupted"))
                return 130
            except Exception as exc:  # pragma: no cover - safety net on remote sandbox
                logging.error("Agent execution failed: %s", exc, exc_info=True)
                _record_failure(exc)
                return 1


        if __name__ == "__main__":
            sys.exit(main())
        """
    )
)


def build_agent_script(params: AgentScriptParams) -> str:
    """
    Render the agent script by substituting the normalized parameters into the template.
    """

    return SCRIPT_TEMPLATE.substitute(params.substitutions())
