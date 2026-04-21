#!/usr/bin/env python3
"""Provision a Modal sandbox, run a command workflow, and download artifacts."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import uuid

import modal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

app = modal.App("yudai-modal-workflow-standalone")


def _load_env_file(env_file: Path) -> None:
    if not env_file.is_file():
        raise FileNotFoundError(f"Env file not found: {env_file}")

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _default_commands() -> list[str]:
    summary_json = json.dumps(
        {
            "workflow": "3-mode-mock",
            "modes": ["architect", "tester", "coder"],
            "status": "complete",
        },
        ensure_ascii=True,
    )
    return [
        "\n".join(
            [
                "set -euo pipefail",
                "workspace=\"${WORKSPACE_PATH:-/workspace/repo}\"",
                "mkdir -p \"$workspace/workflow-output\"",
                "printf 'architect complete\\n' > \"$workspace/workflow-output/architect.txt\"",
                "printf 'created issue #123\\n' > \"$workspace/workflow-output/architect-summary.txt\"",
            ]
        ),
        "\n".join(
            [
                "set -euo pipefail",
                "workspace=\"${WORKSPACE_PATH:-/workspace/repo}\"",
                "mkdir -p \"$workspace/workflow-output/tests\"",
                "printf 'tester complete\\n' > \"$workspace/workflow-output/tester.txt\"",
                "printf 'def test_mock_workflow():\\n    assert True\\n' > \"$workspace/workflow-output/tests/test_mock_workflow.py\"",
            ]
        ),
        "\n".join(
            [
                "set -euo pipefail",
                "workspace=\"${WORKSPACE_PATH:-/workspace/repo}\"",
                "mkdir -p \"$workspace/workflow-output\"",
                "printf 'coder complete\\n' > \"$workspace/workflow-output/coder.txt\"",
                f"printf '%s\\n' {summary_json!r} > \"$workspace/workflow-output/workflow-summary.json\"",
            ]
        ),
    ]


async def _run(args: argparse.Namespace) -> int:
    _load_env_file(Path(args.env_file))

    _require_env("MODAL_TOKEN_ID")
    _require_env("MODAL_TOKEN_SECRET")
    controller_base_url = args.controller_base_url or _require_env("CONTROLLER_BASE_URL")
    session_public_id = args.session_id or f"mock_workflow_{uuid.uuid4().hex[:12]}"
    sandbox_db_id = args.sandbox_id or f"sbx_mock_workflow_{uuid.uuid4().hex[:12]}"
    commands = args.command or _default_commands()
    artifact_paths = args.artifact_path or ["workflow-output"]

    from yudai.realtime.modal_preflight import (
        run_modal_exec_smoke_test,
        validate_modal_exec_smoke_result,
        wait_for_sandbox_healthcheck,
    )
    from yudai.realtime.modal_sandbox import RealtimeModalSandbox
    from yudai.realtime.cache_store import SandboxArtifactStore, download_sandbox_artifact_bundle
    from yudai.realtime.sandbox_transport import run_sandbox_command

    print(f"[workflow] env_file={args.env_file}")
    print(f"[workflow] controller_base_url={controller_base_url}")
    print(f"[workflow] sandbox_db_id={sandbox_db_id}")
    print(f"[workflow] session_public_id={session_public_id}")
    print(f"[workflow] artifact_root={args.artifact_root or os.getenv('SANDBOX_ARTIFACT_ROOT', '/data/sandbox_artifacts')}")
    print("[workflow] step=provision_sandbox")

    sandbox = await RealtimeModalSandbox.create(
        sandbox_db_id=sandbox_db_id,
        controller_base_url=controller_base_url,
        session_public_id=session_public_id,
        env_inputs={"MODAL_SANDBOX_PREFLIGHT": "1"},
        timeout=args.sandbox_timeout,
    )

    print(f"[workflow] modal_sandbox_id={sandbox.modal_sandbox_id}")
    print(f"[workflow] tunnel_url={sandbox.tunnel_url}")

    try:
        print("[workflow] step=wait_healthz")
        healthcheck_url = await wait_for_sandbox_healthcheck(
            sandbox.tunnel_url,
            timeout_seconds=args.healthcheck_timeout,
        )
        print(f"[workflow] healthcheck_url={healthcheck_url}")

        print("[workflow] step=preflight_exec_smoke")
        smoke_result = await run_modal_exec_smoke_test(
            tunnel_url=sandbox.tunnel_url,
            session_public_id=session_public_id,
            timeout_seconds=args.exec_timeout,
        )
        validate_modal_exec_smoke_result(smoke_result)

        for index, command in enumerate(commands, start=1):
            print(f"[workflow] step=run_command index={index}")
            result = await run_sandbox_command(
                tunnel_url=sandbox.tunnel_url,
                session_public_id=session_public_id,
                command=command,
                cwd=args.cwd,
                env={"WORKSPACE_PATH": args.cwd or "/workspace/repo"},
                timeout_seconds=args.exec_timeout,
            )
            print(
                f"[workflow] command index={index} exit_code={result.exit_code} duration_ms={result.duration_ms}"
            )
            if result.stdout.strip():
                print("[workflow] stdout:")
                print(result.stdout.rstrip())
            if result.stderr.strip():
                print("[workflow] stderr:")
                print(result.stderr.rstrip())
            if result.exit_code != 0:
                raise RuntimeError(f"Command {index} failed with exit_code={result.exit_code}")

        print("[workflow] step=download_artifacts")
        store = SandboxArtifactStore(root=args.artifact_root)
        bundle = await download_sandbox_artifact_bundle(
            tunnel_url=sandbox.tunnel_url,
            session_public_id=session_public_id,
            store=store,
            workflow_name=args.workflow_name,
            archive_name=args.archive_name,
            source_paths=artifact_paths,
            timeout_seconds=args.exec_timeout,
            cwd=args.cwd,
            env={"WORKSPACE_PATH": args.cwd or "/workspace/repo"},
        )
        print(f"[workflow] bundle_path={bundle.bundle_path}")
        print(f"[workflow] metadata_path={bundle.metadata_path}")
        print(f"[workflow] checksum_sha256={bundle.checksum_sha256}")
        print(f"[workflow] byte_size={bundle.byte_size}")

        if args.keep_sandbox:
            print("[workflow] keep_sandbox=true; sandbox left running for inspection")
            return 0

        print("[workflow] step=terminate_sandbox")
        await sandbox.terminate()
        return 0
    except Exception:
        if not args.keep_sandbox:
            try:
                print("[workflow] step=terminate_sandbox_after_failure")
                await sandbox.terminate()
            except Exception as terminate_exc:  # pragma: no cover
                print(f"[workflow] warning=terminate_failed detail={terminate_exc}", file=sys.stderr)
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a standalone Modal sandbox workflow and pull artifacts locally.",
    )
    parser.add_argument(
        "--env-file",
        default=str(BACKEND_ROOT / ".env.prod"),
        help="Path to env file loaded before provisioning the sandbox.",
    )
    parser.add_argument(
        "--controller-base-url",
        default=None,
        help="Override CONTROLLER_BASE_URL for the temporary sandbox.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Mock session id used for the internal exec websocket path.",
    )
    parser.add_argument(
        "--sandbox-id",
        default=None,
        help="Temporary sandbox db id for this standalone run.",
    )
    parser.add_argument(
        "--command",
        action="append",
        default=None,
        help="Bash command to execute inside the sandbox. Repeat for multiple commands.",
    )
    parser.add_argument(
        "--artifact-path",
        action="append",
        default=None,
        help="Path inside the sandbox to include in the downloaded artifact bundle.",
    )
    parser.add_argument(
        "--workflow-name",
        default="mode-workflow",
        help="Logical workflow name used for the local artifact bundle directory.",
    )
    parser.add_argument(
        "--archive-name",
        default="sandbox-workflow.tar.gz",
        help="Filename for the downloaded artifact bundle.",
    )
    parser.add_argument(
        "--artifact-root",
        default=None,
        help="Override SANDBOX_ARTIFACT_ROOT for local bundle storage.",
    )
    parser.add_argument(
        "--cwd",
        default="/workspace/repo",
        help="Working directory for workflow commands inside the sandbox.",
    )
    parser.add_argument(
        "--sandbox-timeout",
        type=int,
        default=int(os.getenv("MODAL_SANDBOX_PREFLIGHT_SANDBOX_TIMEOUT_SECONDS", "900")),
        help="Modal sandbox timeout in seconds.",
    )
    parser.add_argument(
        "--healthcheck-timeout",
        type=float,
        default=float(os.getenv("MODAL_SANDBOX_PREFLIGHT_HEALTHCHECK_TIMEOUT_SECONDS", "60")),
        help="How long to wait for /healthz before failing.",
    )
    parser.add_argument(
        "--exec-timeout",
        type=int,
        default=int(os.getenv("MODAL_SANDBOX_PREFLIGHT_EXEC_TIMEOUT_SECONDS", "300")),
        help="How long to wait for each command and artifact download.",
    )
    parser.add_argument(
        "--keep-sandbox",
        action="store_true",
        help="Leave the temporary sandbox running for inspection.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except Exception as exc:
        print(f"[workflow] failed: {exc}", file=sys.stderr)
        return 1


@app.local_entrypoint()
def modal_main(
    env_file: str = str(BACKEND_ROOT / ".env.prod"),
    controller_base_url: str = "",
    artifact_root: str = "",
    keep_sandbox: bool = False,
) -> None:
    argv = ["--env-file", env_file]
    if controller_base_url:
        argv.extend(["--controller-base-url", controller_base_url])
    if artifact_root:
        argv.extend(["--artifact-root", artifact_root])
    if keep_sandbox:
        argv.append("--keep-sandbox")
    exit_code = main(argv)
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
