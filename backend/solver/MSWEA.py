import argparse
import logging
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple


def parse_issue_url(issue_url: str) -> Tuple[str, str, str]:
    pattern = r"^https?://github\.com/([^/]+)/([^/]+)/issues/(\d+)(?:/.*)?$"
    match = re.match(pattern, issue_url)
    if not match:
        raise ValueError("Issue URL must be like https://github.com/<owner>/<repo>/issues/<number>")
    return match.group(1), match.group(2), match.group(3)


def build_task(issue_url: str) -> str:
    owner, repo, number = parse_issue_url(issue_url)
    return (
        f"Fix GitHub issue #{number} for {owner}/{repo}.\n"
        f"Issue: {issue_url}\n"
        "Follow the recommended mini workflow: analyze, reproduce, edit, verify, test, submit."
    )


def find_mini_command() -> list[str]:
    if shutil.which("mini"):
        return ["mini"]
    return [sys.executable, "-m", "minisweagent.run.mini"]


def ensure_repo_cloned(repo_owner: str, repo_name: str, dest_dir: Path, repo_url: Optional[str] = None) -> Path:
    dest_dir = dest_dir.expanduser().resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)
    repo_path = dest_dir / repo_name
    if repo_path.exists():
        return repo_path
    url = repo_url or f"https://github.com/{repo_owner}/{repo_name}.git"
    subprocess.run(["git", "clone", url, str(repo_path)], check=True)
    return repo_path


def run_mini(
    *,
    task: str,
    model_name: Optional[str],
    config_path: Optional[str],
    start_mode: str,
    working_dir: Optional[Path],
) -> int:
    cmd: list[str] = find_mini_command()
    cmd += ["-t", task]
    if model_name:
        cmd += ["-m", model_name]
    if config_path:
        cmd += ["-c", config_path]
    if start_mode == "yolo":
        cmd += ["-y"]

    logging.info("Running: %s", " ".join(shlex.quote(c) for c in cmd))
    try:
        proc = subprocess.run(cmd, cwd=str(working_dir) if working_dir else None)
        return proc.returncode
    except FileNotFoundError as exc:
        logging.error("mini-swe-agent not found. Install with: pip install mini-swe-agent")
        logging.debug("FileNotFoundError: %s", exc)
        return 127


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run mini-SWE-agent to solve a GitHub issue",
    )
    parser.add_argument("issue_url", help="GitHub issue URL (https://github.com/<owner>/<repo>/issues/<number>)")
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path("/tmp/mswea_repos"),
        help="Destination directory to clone repositories into (if cloning)",
    )
    parser.add_argument("--no-clone", action="store_true", help="Do not clone the repository")
    parser.add_argument("--repo-url", help="Override repository URL for cloning (optional)")
    parser.add_argument("--model", help="Model name to use (overrides config file)")
    parser.add_argument(
        "--config", 
        default="tfbd.yaml",
        help="Path to mini config YAML (default: tfbd.yaml)"
    )
    parser.add_argument(
        "--mode",
        choices=["yolo", "confirm", "human"],
        default="confirm",
        help="Start mode (default: confirm from tfbd.yaml config)",
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        help="Explicit working directory to run mini from (overrides clone dir)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="[%(levelname)s] %(message)s")

    # Resolve config path relative to script directory
    script_dir = Path(__file__).parent
    config_path = script_dir / args.config
    if not config_path.exists():
        logging.error(f"Config file not found: {config_path}")
        return 1

    try:
        owner, repo, _ = parse_issue_url(args.issue_url)
    except ValueError as e:
        logging.error(str(e))
        return 2

    working_dir: Optional[Path] = args.cwd
    if not working_dir and not args.no_clone:
        try:
            working_dir = ensure_repo_cloned(owner, repo, args.dest, args.repo_url)
        except subprocess.CalledProcessError as e:
            logging.error("git clone failed: %s", e)
            return e.returncode or 128

    task = build_task(args.issue_url)
    return run_mini(
        task=task,
        model_name=args.model,
        config_path=str(config_path),
        start_mode=args.mode,
        working_dir=working_dir,
    )


if __name__ == "__main__":
    sys.exit(main())


