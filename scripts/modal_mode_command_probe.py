#!/usr/bin/env python3
"""Temporary Modal probe for controller-brokered mode command assembly."""

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

app = modal.App("yudai-mode-command-probe")


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


def _extract_probe_payload(stdout: str) -> dict:
    for raw_line in reversed(stdout.splitlines()):
        line = raw_line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("argv"), list):
            return payload
    raise RuntimeError(f"No command probe JSON payload found in stdout: {stdout[-1000:]}")


def _assert_probe_payload(
    *,
    mode: str,
    payload: dict,
    expected_model: str,
    expected_issue_number: str,
    expected_issue_url: str,
    expected_test_branch: str,
) -> None:
    argv = [str(item) for item in payload.get("argv") or []]
    if not argv or argv[0] != "mini":
        raise RuntimeError(f"{mode}: expected argv to start with mini, got {argv!r}")
    if "-c" not in argv or f"/app/mswea_mode_configs/{mode}/config.yaml" not in argv:
        raise RuntimeError(f"{mode}: expected mode config in argv, got {argv!r}")
    if "-y" not in argv:
        raise RuntimeError(f"{mode}: expected yolo flag in argv, got {argv!r}")
    if "-m" not in argv or expected_model not in argv:
        raise RuntimeError(f"{mode}: expected model {expected_model!r} in argv, got {argv!r}")
    if "-t" not in argv:
        raise RuntimeError(f"{mode}: expected task flag in argv, got {argv!r}")

    task_text = argv[argv.index("-t") + 1]
    context_file = str(payload.get("context_file") or "")
    if not context_file.endswith("/.yudai/context.md"):
        raise RuntimeError(f"{mode}: expected shared context file in payload, got {context_file!r}")
    if context_file not in task_text:
        raise RuntimeError(f"{mode}: expected context file in task text, got {task_text!r}")
    if f"#{expected_issue_number}" not in task_text:
        raise RuntimeError(f"{mode}: expected issue number in task text, got {task_text!r}")
    if expected_issue_url and expected_issue_url not in task_text:
        raise RuntimeError(f"{mode}: expected issue URL in task text, got {task_text!r}")
    if mode == "coder" and expected_test_branch not in task_text:
        raise RuntimeError(f"{mode}: expected test branch in task text, got {task_text!r}")


async def _run(args: argparse.Namespace) -> int:
    _load_env_file(Path(args.env_file))

    _require_env("MODAL_TOKEN_ID")
    _require_env("MODAL_TOKEN_SECRET")

    from realtime.modal_preflight import (  # noqa: WPS433
        run_modal_exec_smoke_test,
        validate_modal_exec_smoke_result,
        wait_for_sandbox_healthcheck,
    )
    from realtime.modal_sandbox import RealtimeModalSandbox  # noqa: WPS433
    from realtime.mode_orchestrator import SessionExecutionOrchestrator  # noqa: WPS433
    from realtime.sandbox_transport import run_sandbox_command  # noqa: WPS433

    controller_base_url = args.controller_base_url or _require_env("CONTROLLER_BASE_URL")
    session_public_id = args.session_id or f"probe_session_{uuid.uuid4().hex[:12]}"
    sandbox_db_id = args.sandbox_id or f"sbx_probe_{uuid.uuid4().hex[:12]}"
    pipeline_execution_id = args.pipeline_execution_id or f"probe_{uuid.uuid4().hex[:10]}"
    model_name = args.model_name or os.getenv("MSWEA_MODEL_NAME") or "openrouter/x-ai/grok-4-fast"
    github_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

    print(f"[mode-probe] env_file={args.env_file}")
    print(f"[mode-probe] controller_base_url={controller_base_url}")
    print(f"[mode-probe] sandbox_db_id={sandbox_db_id}")
    print(f"[mode-probe] session_public_id={session_public_id}")
    print("[mode-probe] step=provision_sandbox")

    sandbox = await RealtimeModalSandbox.create(
        sandbox_db_id=sandbox_db_id,
        controller_base_url=controller_base_url,
        github_token=github_token,
        session_public_id=session_public_id,
        repo_url=args.repo_url or None,
        repo_branch=args.repo_branch,
        env_inputs={"MODAL_SANDBOX_PREFLIGHT": "1"},
        timeout=args.sandbox_timeout,
    )

    print(f"[mode-probe] modal_sandbox_id={sandbox.modal_sandbox_id}")
    print(f"[mode-probe] tunnel_url={sandbox.tunnel_url}")

    try:
        print("[mode-probe] step=wait_healthz")
        healthcheck_url = await wait_for_sandbox_healthcheck(
            sandbox.tunnel_url,
            timeout_seconds=args.healthcheck_timeout,
        )
        print(f"[mode-probe] healthcheck_url={healthcheck_url}")

        print("[mode-probe] step=preflight_exec_smoke")
        smoke_result = await run_modal_exec_smoke_test(
            tunnel_url=sandbox.tunnel_url,
            session_public_id=session_public_id,
            timeout_seconds=args.exec_timeout,
        )
        validate_modal_exec_smoke_result(smoke_result)

        orchestrator = SessionExecutionOrchestrator(
            broker=object(),
            lifecycle=object(),
            ws_hub=object(),
        )
        modes = ("architect", "tester", "coder")
        summaries: list[dict] = []

        for mode in modes:
            print(f"[mode-probe] step=run_mode_probe mode={mode}")
            command = orchestrator._build_mswea_command(
                mode=mode,
                include_issue_number=True,
                include_test_branch=mode == "coder",
            )
            env = {
                "YUDAI_MSWEA_COMMAND_PROBE": "1",
                "WORKSPACE_PATH": args.workspace_path,
                "PIPELINE_EXECUTION_ID": pipeline_execution_id,
                "MSWEA_OBJECTIVE": f"Probe {mode} mode command arguments",
                "MSWEA_MODEL_NAME": model_name,
                "MSWEA_ISSUE_NUMBER": args.issue_number,
                "MSWEA_ISSUE_URL": args.issue_url,
                "REPO_BRANCH": args.repo_branch,
            }
            if args.repo_url:
                env["REPO_URL"] = args.repo_url
            if mode == "coder":
                env["MSWEA_TEST_BRANCH"] = args.test_branch

            result = await run_sandbox_command(
                tunnel_url=sandbox.tunnel_url,
                session_public_id=session_public_id,
                command=command,
                cwd=args.workspace_path,
                env=env,
                timeout_seconds=args.exec_timeout,
            )
            print(
                f"[mode-probe] mode={mode} exit_code={result.exit_code} duration_ms={result.duration_ms}"
            )
            if result.stderr.strip():
                print("[mode-probe] stderr:")
                print(result.stderr.rstrip())
            if result.exit_code != 0:
                raise RuntimeError(f"{mode} command probe failed with exit_code={result.exit_code}")

            payload = _extract_probe_payload(result.stdout)
            _assert_probe_payload(
                mode=mode,
                payload=payload,
                expected_model=model_name,
                expected_issue_number=args.issue_number,
                expected_issue_url=args.issue_url,
                expected_test_branch=args.test_branch,
            )
            summaries.append(
                {
                    "mode": mode,
                    "config_path": payload.get("config_path"),
                    "context_file": payload.get("context_file"),
                    "argv": payload.get("argv"),
                }
            )

        print("[mode-probe] step=success")
        print(json.dumps({"modes": summaries}, ensure_ascii=True, indent=2))

        if args.keep_sandbox:
            print("[mode-probe] keep_sandbox=true; sandbox left running for inspection")
            return 0

        print("[mode-probe] step=terminate_sandbox")
        await sandbox.terminate()
        return 0
    except Exception:
        if not args.keep_sandbox:
            try:
                print("[mode-probe] step=terminate_sandbox_after_failure")
                await sandbox.terminate()
            except Exception as terminate_exc:  # pragma: no cover
                print(f"[mode-probe] warning=terminate_failed detail={terminate_exc}", file=sys.stderr)
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Probe Modal sandbox mode command argv over the internal controller API.",
    )
    parser.add_argument("--env-file", default=str(BACKEND_ROOT / ".env.prod"))
    parser.add_argument("--controller-base-url", default=None)
    parser.add_argument("--session-id", default=None)
    parser.add_argument("--sandbox-id", default=None)
    parser.add_argument("--pipeline-execution-id", default=None)
    parser.add_argument("--repo-url", default=os.getenv("MODAL_PROBE_REPO_URL", ""))
    parser.add_argument("--repo-branch", default=os.getenv("MODAL_PROBE_REPO_BRANCH", "main"))
    parser.add_argument("--workspace-path", default="/workspace/repo")
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--issue-number", default="123")
    parser.add_argument("--issue-url", default="https://github.com/pranay5255/YudaiV3/issues/123")
    parser.add_argument("--test-branch", default="yudai/issue-123-tests")
    parser.add_argument(
        "--sandbox-timeout",
        type=int,
        default=int(os.getenv("MODAL_SANDBOX_PREFLIGHT_SANDBOX_TIMEOUT_SECONDS", "900")),
    )
    parser.add_argument(
        "--healthcheck-timeout",
        type=float,
        default=float(os.getenv("MODAL_SANDBOX_PREFLIGHT_HEALTHCHECK_TIMEOUT_SECONDS", "60")),
    )
    parser.add_argument(
        "--exec-timeout",
        type=int,
        default=int(os.getenv("MODAL_SANDBOX_PREFLIGHT_EXEC_TIMEOUT_SECONDS", "120")),
    )
    parser.add_argument("--keep-sandbox", action="store_true")
    return parser


async def _async_main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return await _run(args)


def main(argv: list[str] | None = None) -> int:
    try:
        return asyncio.run(_async_main(argv))
    except Exception as exc:
        print(f"[mode-probe] failed: {exc}", file=sys.stderr)
        return 1


@app.local_entrypoint()
def modal_main(
    env_file: str = str(BACKEND_ROOT / ".env.prod"),
    controller_base_url: str = "",
    repo_url: str = "",
    repo_branch: str = "main",
    model_name: str = "",
    keep_sandbox: bool = False,
) -> None:
    argv = ["--env-file", env_file, "--repo-branch", repo_branch]
    if controller_base_url:
        argv.extend(["--controller-base-url", controller_base_url])
    if repo_url:
        argv.extend(["--repo-url", repo_url])
    if model_name:
        argv.extend(["--model-name", model_name])
    if keep_sandbox:
        argv.append("--keep-sandbox")
    exit_code = main(argv)
    if exit_code:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    raise SystemExit(main())
