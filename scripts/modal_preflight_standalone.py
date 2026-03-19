#!/usr/bin/env python3
"""Standalone runner for the repo's Modal sandbox preflight flow."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys
import uuid

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


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

    controller_base_url = args.controller_base_url or _require_env("CONTROLLER_BASE_URL")
    session_public_id = args.session_id or f"mock_session_{uuid.uuid4().hex[:12]}"
    sandbox_db_id = args.sandbox_id or f"sbx_mock_preflight_{uuid.uuid4().hex[:12]}"

    print(f"[standalone] env_file={args.env_file}")
    print(f"[standalone] controller_base_url={controller_base_url}")
    print(f"[standalone] sandbox_db_id={sandbox_db_id}")
    print(f"[standalone] session_public_id={session_public_id}")
    print("[standalone] step=provision_sandbox")

    sandbox = await RealtimeModalSandbox.create(
        sandbox_db_id=sandbox_db_id,
        controller_base_url=controller_base_url,
        session_public_id=session_public_id,
        env_inputs={"MODAL_SANDBOX_PREFLIGHT": "1"},
        timeout=args.sandbox_timeout,
    )

    print(f"[standalone] modal_sandbox_id={sandbox.modal_sandbox_id}")
    print(f"[standalone] tunnel_url={sandbox.tunnel_url}")

    try:
        print("[standalone] step=wait_healthz")
        healthcheck_url = await wait_for_sandbox_healthcheck(
            sandbox.tunnel_url,
            timeout_seconds=args.healthcheck_timeout,
        )
        print(f"[standalone] healthcheck_url={healthcheck_url}")

        print("[standalone] step=exec_smoke_command")
        exec_result = await run_modal_exec_smoke_test(
            tunnel_url=sandbox.tunnel_url,
            session_public_id=session_public_id,
            timeout_seconds=args.exec_timeout,
        )
        validate_modal_exec_smoke_result(exec_result)

        print("[standalone] step=success")
        print(f"[standalone] exec_exit_code={exec_result.exit_code}")
        print(f"[standalone] exec_duration_ms={exec_result.duration_ms}")
        if exec_result.stdout.strip():
            print("[standalone] stdout:")
            print(exec_result.stdout.rstrip())
        if exec_result.stderr.strip():
            print("[standalone] stderr:")
            print(exec_result.stderr.rstrip())

        if args.keep_sandbox:
            print("[standalone] keep_sandbox=true; sandbox left running for inspection")
            return 0

        print("[standalone] step=terminate_sandbox")
        await sandbox.terminate()
        return 0
    except Exception:
        if not args.keep_sandbox:
            try:
                print("[standalone] step=terminate_sandbox_after_failure")
                await sandbox.terminate()
            except Exception as terminate_exc:  # pragma: no cover - defensive
                print(f"[standalone] warning=terminate_failed detail={terminate_exc}", file=sys.stderr)
        raise


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the repo's Modal sandbox preflight against a mock session.",
    )
    parser.add_argument(
        "--env-file",
        default=str(BACKEND_ROOT / ".env.prod"),
        help="Path to the env file to load before calling Modal.",
    )
    parser.add_argument(
        "--controller-base-url",
        default=None,
        help="Override CONTROLLER_BASE_URL for the temporary sandbox.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Mock session public id to use for the internal exec websocket path.",
    )
    parser.add_argument(
        "--sandbox-id",
        default=None,
        help="Mock sandbox db id to assign to the temporary Modal sandbox.",
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
        default=int(os.getenv("MODAL_SANDBOX_PREFLIGHT_EXEC_TIMEOUT_SECONDS", "45")),
        help="How long to wait for the internal bash smoke command.",
    )
    parser.add_argument(
        "--keep-sandbox",
        action="store_true",
        help="Leave the temporary sandbox running after success or failure for debugging.",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        return asyncio.run(_run(args))
    except Exception as exc:
        print(f"[standalone] failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
