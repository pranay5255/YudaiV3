import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

import requests
import yaml
from rich.console import Console

# Add mswea/src to Python path for local imports
script_dir = Path(__file__).parent
mswea_src_path = script_dir / "mswea" / "src"
if mswea_src_path.exists() and str(mswea_src_path) not in sys.path:
    sys.path.insert(0, str(mswea_src_path))

from minisweagent.agents.interactive import InteractiveAgent
from minisweagent.config import get_config_path
from minisweagent.environments.local import LocalEnvironment
from minisweagent.models import get_model
from minisweagent.run.extra.config import configure_if_first_time
from minisweagent.run.utils.save import save_traj

console = Console(highlight=False)


def parse_issue_url(issue_url: str) -> Tuple[str, str, str]:
    pattern = r"^https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)(?:/.*)?$"
    match = re.match(pattern, issue_url)
    if not match:
        raise ValueError(
            "Issue URL must be like https://github.com/<owner>/<repo>/issues/<number>"
        )
    return match.group(1), match.group(2), match.group(3)


def fetch_github_issue(issue_url: str) -> str:
    """Fetch GitHub issue text from the URL."""
    # Convert GitHub issue URL to API URL
    api_url = issue_url.replace("github.com", "api.github.com/repos").replace(
        "/issues/", "/issues/"
    )

    headers = {}
    if github_token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"token {github_token}"

    response = requests.get(api_url, headers=headers)
    response.raise_for_status()
    issue_data = response.json()

    title = issue_data["title"]
    body = issue_data["body"] or ""

    return f"GitHub Issue: {title}\n\n{body}"


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run mini-SWE-agent to solve a GitHub issue",
    )
    parser.add_argument(
        "issue_url",
        help="GitHub issue URL (https://github.com/<owner>/<repo>/issues/<number>)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to mini config YAML (default: tfbd.yaml in script directory)",
    )
    parser.add_argument("--model", help="Model name to use (overrides config file)")
    parser.add_argument(
        "--model-class",
        help="Model class to use (e.g., 'anthropic' or 'minisweagent.models.anthropic.AnthropicModel')",
    )
    parser.add_argument(
        "--mode",
        choices=["yolo", "confirm", "human"],
        default="confirm",
        help="Start mode (default: confirm)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("traj.json"),
        help="Output trajectory file (default: traj.json)",
    )

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )

    try:
        parse_issue_url(args.issue_url)
    except ValueError as e:
        logging.error(str(e))
        return 2

    configure_if_first_time()

    # Resolve config path - default to tfbd.yaml in script directory
    if args.config:
        config_path = get_config_path(args.config)
    else:
        script_dir = Path(__file__).parent
        default_config = script_dir / "tfbd.yaml"
        if default_config.exists():
            config_path = default_config
        else:
            config_path = get_config_path("tfbd.yaml")

    console.print(f"Loading agent config from [bold green]'{config_path}'[/bold green]")
    _config = yaml.safe_load(config_path.read_text())
    _agent_config = _config.setdefault("agent", {})

    # Set mode
    if args.mode == "yolo":
        _agent_config["mode"] = "yolo"
    elif args.mode == "human":
        _agent_config["mode"] = "human"
    else:
        _agent_config["mode"] = "confirm"

    # Set model class if provided
    if args.model_class is not None:
        _config.setdefault("model", {})["model_class"] = args.model_class

    # Fetch GitHub issue content
    try:
        task = fetch_github_issue(args.issue_url)
    except requests.RequestException as e:
        logging.error(f"Failed to fetch GitHub issue: {e}")
        return 3

    # Create agent
    agent = InteractiveAgent(
        get_model(args.model, _config.get("model", {})),
        LocalEnvironment(**_config.get("environment", {})),
        **_agent_config,
    )

    # Clone repository to local directory
    repo_url = args.issue_url.split("/issues/")[0]
    if github_token := os.getenv("GITHUB_TOKEN"):
        repo_url = (
            repo_url.replace(
                "https://github.com/", f"https://{github_token}@github.com/"
            )
            + ".git"
        )
    else:
        repo_url = repo_url + ".git"

    # Use testbed directory in current working directory
    testbed_dir = Path.cwd() / "testbed"
    if testbed_dir.exists():
        logging.info(f"Testbed directory already exists: {testbed_dir}")
    else:
        result = agent.env.execute(f"git clone {repo_url} testbed", cwd=str(Path.cwd()))
        if result["returncode"] != 0:
            logging.error(f"Failed to clone repository: {result['output']}")
            return 4

    # Run agent in testbed directory
    exit_status, result = None, None
    original_cwd = os.getcwd()
    try:
        # Set working directory to testbed for agent execution
        os.chdir(str(testbed_dir))
        exit_status, result = agent.run(task)
    except KeyboardInterrupt:
        console.print("\n[bold red]KeyboardInterrupt -- goodbye[/bold red]")
        return 130
    except Exception as e:
        logging.error(f"Agent execution failed: {e}", exc_info=args.verbose)
        return 1
    finally:
        os.chdir(original_cwd)
        save_traj(agent, args.output, exit_status=exit_status, result=result)

    return 0 if exit_status == "finished" else 1


if __name__ == "__main__":
    sys.exit(main())
