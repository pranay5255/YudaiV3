from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from solver.agentScriptGen import AgentScriptParams, build_agent_script
from solver.manager import build_tfbd_config

ARTIFACT_DIR = Path(__file__).with_name("sandbox_demo_artifacts")
ISSUE_DEMO_PATH = Path(__file__).with_name("issue_demo.txt")


def build_demo_params() -> AgentScriptParams:
    payload = {
        "temperature": 0.2,
        "max_tokens": 6000,
        "max_iterations": 40,
        "max_cost": 7.5,
        "small_change": True,
        "best_effort": False,
    }
    issue_text = ISSUE_DEMO_PATH.read_text() if ISSUE_DEMO_PATH.exists() else ""
    return AgentScriptParams.from_payload(
        model_name="anthropic/claude-sonnet-4-5-20250929",
        repo_url="https://github.com/example/repo",
        branch_name="main",
        issue_url="https://github.com/example/repo/issues/123",
        issue_text=issue_text,
        payload=payload,
        verbose=True,
    )


def create_demo_artifacts(*, config: Dict[str, Any]) -> Dict[str, Path]:
    output_dir: Path = config["output_dir"]
    params: AgentScriptParams = config["params"]

    output_dir.mkdir(parents=True, exist_ok=True)

    tfbd_content = build_tfbd_config(params)
    script_content = build_agent_script(params)

    tfbd_path = output_dir / "tfbd.yaml"
    script_path = output_dir / "run_agent.py"

    tfbd_path.write_text(tfbd_content)
    script_path.write_text(script_content)

    return {"tfbd_path": tfbd_path, "script_path": script_path}


def display_preview(*, artifacts: Dict[str, Path], max_lines: int = 24) -> None:
    for name, path in artifacts.items():
        header = f"=== {name} ({path}) ==="
        print(header)
        print("-" * len(header))
        content = path.read_text()
        lines = content.splitlines()
        preview = "\n".join(lines[:max_lines])
        print(preview)
        if len(lines) > max_lines:
            print(f"... ({len(lines) - max_lines} more lines)")
        print()


def main() -> None:
    params = build_demo_params()
    artifacts = create_demo_artifacts(
        config={"output_dir": ARTIFACT_DIR, "params": params}
    )
    display_preview(artifacts=artifacts)


if __name__ == "__main__":
    main()
