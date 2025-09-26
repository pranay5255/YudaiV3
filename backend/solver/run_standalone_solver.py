"""Standalone script to derive solver models from config.yaml."""

from __future__ import annotations

import argparse
import json
import sys
import types
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.solver.config_utils import build_solver_artifacts, load_solver_config


def _ensure_repo_root_on_path(script_path: Path) -> Path:
    """Allow running as a standalone script by injecting the repo root."""

    repo_root = script_path.resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.append(str(repo_root))
    backend_root = repo_root / "backend"
    if backend_root.exists() and str(backend_root) not in sys.path:
        sys.path.append(str(backend_root))
    return repo_root


REPO_ROOT = _ensure_repo_root_on_path(Path(__file__))

if "pgvector.sqlalchemy" not in sys.modules:
    pgvector_mod = types.ModuleType("pgvector")
    pgvector_sqlalchemy = types.ModuleType("pgvector.sqlalchemy")
    setattr(pgvector_sqlalchemy, "Vector", object)
    pgvector_mod.sqlalchemy = pgvector_sqlalchemy
    sys.modules["pgvector"] = pgvector_mod
    sys.modules["pgvector.sqlalchemy"] = pgvector_sqlalchemy




def _default_repo() -> str:
    return "https://github.com/example/repo.git"


def _isoformat(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _print_section(title: str, payload: dict) -> None:
    print(f"\n== {title} ==")
    print(json.dumps(payload, indent=2, default=_isoformat))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect ai_solver config without backend dependencies",
    )
    parser.add_argument(
        "--config",
        default="backend/solver/config.yaml",
        help="Path to SWE-agent config.yaml",
    )
    parser.add_argument(
        "--repo-url",
        default=_default_repo(),
        help="Repository URL to embed in the generated models",
    )
    parser.add_argument(
        "--branch-name",
        default="main",
        help="Branch name for the simulated run",
    )
    parser.add_argument(
        "--issue-id",
        type=int,
        default=1,
        help="Identifier for the referenced issue",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="Identifier for the requesting user",
    )
    parser.add_argument(
        "--issue-title",
        default="Standalone AI Solver Dry Run",
        help="Title for the GitHub issue context",
    )
    parser.add_argument(
        "--session-id",
        type=int,
        default=1,
        help="Session identifier to inject into responses",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    config = load_solver_config(str(config_path))

    artifacts = build_solver_artifacts(
        config=config,
        config_path=str(config_path),
        issue_id=args.issue_id,
        user_id=args.user_id,
        repo_url=args.repo_url,
        branch_name=args.branch_name,
        session_id=args.session_id,
        issue_title=args.issue_title,
    )

    print("Loaded config from", artifacts.config_path)

    _print_section("AIModelOut", artifacts.ai_model.model_dump())
    _print_section("SWEAgentConfigOut", artifacts.swe_config.model_dump())
    _print_section("StartSolveRequest", artifacts.start_request.model_dump())
    _print_section("StartSolveResponse", artifacts.start_response.model_dump())
    _print_section("SolveSessionOut", artifacts.session.model_dump())
    _print_section("SolveSessionStatsOut", artifacts.session_stats.model_dump())
    _print_section("SolverTrajectoryOut", artifacts.trajectory.model_dump())


if __name__ == "__main__":
    main()
