from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from .agentScriptGen import AgentScriptParams, build_agent_script

ARTIFACT_DIR = Path(__file__).with_name("sandbox_demo_artifacts")
ISSUE_DEMO_PATH = Path(__file__).with_name("issue_demo.txt")
TFBD_TEMPLATE_PATH = Path(__file__).with_name("tfbd.yaml")

DEFAULT_TFBD_FALLBACK = """agent:
  system_template: "You are a helpful assistant that can interact with a computer."
model:
  model_name: "{model_name}"
  model_class: "openrouter"
  model_kwargs:
    temperature: 0.4
"""


def build_demo_params() -> AgentScriptParams:
    payload = {
        "temperature": 0.2,
        "max_tokens": 6000,
        "max_iterations": 40,
        "max_cost": 7.5,
        "small_change": True,
        "best_effort": False,
    }
    issue_text = ISSUE_DEMO_PATH.read_text().strip() if ISSUE_DEMO_PATH.exists() else ""
    params = AgentScriptParams.from_payload(
        model_name="minimax/minimax-m2:free",
        repo_url="https://github.com/example/repo",
        branch_name="main",
        issue_url="https://github.com/example/repo/issues/123",
        issue_text=issue_text,
        payload=payload,
        verbose=True,
    )
    if not params.issue_text:
        params.issue_text = (
            "Update onboarding tests to handle international phone numbers."
        )
    return params


def build_tfbd_config(params: AgentScriptParams) -> str:
    try:
        base_template = TFBD_TEMPLATE_PATH.read_text()
    except FileNotFoundError:
        return DEFAULT_TFBD_FALLBACK.format(model_name=params.model_name)

    updated_template, replacements = re.subn(
        r'model_name:\s*"[^"]+"',
        f'model_name: "{params.model_name}"',
        base_template,
        count=1,
    )

    if replacements == 0:
        appended_block = (
            f"\nmodel:\n"
            f'    model_name: "{params.model_name}"\n'
            f'    model_class: "openrouter"\n'
            f"    model_kwargs:\n"
            f"        temperature: 0.4\n"
        )
        updated_template = base_template.rstrip() + appended_block

    constraints: List[str] = []
    if params.small_change:
        constraints.append(
            "Limit code edits to minimal, targeted changes directly tied to the issue."
        )
    if params.best_effort:
        constraints.append(
            "Continue working toward a solution even if automated checks fail, documenting any failures."
        )

    return _inject_constraints(updated_template, constraints)


def _inject_constraints(template: str, constraints: List[str]) -> str:
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
