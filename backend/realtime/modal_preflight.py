"""Live Modal sandbox preflight checks for backend deployment."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional
import uuid

import httpx

from config.realtime_flags import RealtimeFeatureFlags, get_realtime_feature_flags

from .modal_sandbox import RealtimeModalSandbox
from .sandbox_transport import run_sandbox_command

TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}

MODAL_PREFLIGHT_IMPORT_MARKER = "modal-preflight-import-ok"
MODAL_PREFLIGHT_BASH_MARKER = "modal-preflight-bash-ok"


@dataclass(frozen=True)
class ModalExecSmokeResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int


@dataclass(frozen=True)
class ModalPreflightResult:
    sandbox_db_id: str
    modal_sandbox_id: str
    tunnel_url: str
    healthcheck_url: str
    exec_result: ModalExecSmokeResult


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in TRUE_VALUES


def should_run_modal_preflight(flags: Optional[RealtimeFeatureFlags] = None) -> bool:
    flags = flags or get_realtime_feature_flags()
    if not flags.modal_provisioning_enabled:
        return False
    return _env_bool("MODAL_SANDBOX_PREFLIGHT_ENABLED", True)


def _require_modal_credentials() -> None:
    missing = [
        name
        for name in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET")
        if not os.getenv(name, "").strip()
    ]
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"Missing Modal credentials for sandbox preflight: {joined}")


def build_modal_exec_smoke_command() -> str:
    return " && ".join(
        [
            (
                "python -c "
                f"\"import minisweagent; print('{MODAL_PREFLIGHT_IMPORT_MARKER}')\""
            ),
            f"printf '{MODAL_PREFLIGHT_BASH_MARKER}\\n'",
            "command -v bash >/dev/null",
        ]
    )


def validate_modal_exec_smoke_result(result: ModalExecSmokeResult) -> None:
    if result.exit_code != 0:
        stderr_tail = result.stderr.strip()[-1000:]
        raise RuntimeError(
            f"Modal sandbox bash smoke command failed with exit code {result.exit_code}: "
            f"{stderr_tail or 'no stderr output'}"
        )
    if MODAL_PREFLIGHT_IMPORT_MARKER not in result.stdout:
        raise RuntimeError("Modal sandbox smoke command did not import minisweagent successfully")
    if MODAL_PREFLIGHT_BASH_MARKER not in result.stdout:
        raise RuntimeError("Modal sandbox smoke command did not complete bash execution successfully")

async def wait_for_sandbox_healthcheck(
    tunnel_url: str,
    *,
    timeout_seconds: float = 60.0,
) -> str:
    healthcheck_url = f"{tunnel_url.rstrip('/')}/healthz"
    deadline = time.monotonic() + timeout_seconds
    last_error = "sandbox healthcheck did not become ready"

    while time.monotonic() < deadline:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(healthcheck_url)
            if response.status_code == 200:
                return healthcheck_url
            last_error = f"unexpected healthz status {response.status_code}"
        except Exception as exc:  # pragma: no cover - defensive
            last_error = str(exc)
        await asyncio.sleep(1)

    raise RuntimeError(
        f"Timed out waiting for Modal sandbox healthcheck at {healthcheck_url}: {last_error}"
    )


async def run_modal_exec_smoke_test(
    *,
    tunnel_url: str,
    session_public_id: str,
    timeout_seconds: int = 45,
) -> ModalExecSmokeResult:
    result = await run_sandbox_command(
        tunnel_url=tunnel_url,
        session_public_id=session_public_id,
        command=build_modal_exec_smoke_command(),
        env={"MODAL_SANDBOX_PREFLIGHT": "1"},
        timeout_seconds=timeout_seconds,
    )

    return ModalExecSmokeResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_ms=result.duration_ms,
    )


async def run_modal_preflight() -> ModalPreflightResult:
    _require_modal_credentials()

    sandbox_db_id = f"sbx_preflight_{uuid.uuid4().hex[:12]}"
    session_public_id = f"preflight_{uuid.uuid4().hex[:12]}"
    controller_base_url = os.getenv("CONTROLLER_BASE_URL", "http://localhost:8000")
    sandbox_timeout = int(os.getenv("MODAL_SANDBOX_PREFLIGHT_SANDBOX_TIMEOUT_SECONDS", "900"))
    healthcheck_timeout = float(os.getenv("MODAL_SANDBOX_PREFLIGHT_HEALTHCHECK_TIMEOUT_SECONDS", "60"))
    exec_timeout = int(os.getenv("MODAL_SANDBOX_PREFLIGHT_EXEC_TIMEOUT_SECONDS", "45"))

    sandbox = await RealtimeModalSandbox.create(
        sandbox_db_id=sandbox_db_id,
        controller_base_url=controller_base_url,
        session_public_id=session_public_id,
        env_inputs={"MODAL_SANDBOX_PREFLIGHT": "1"},
        timeout=sandbox_timeout,
    )

    try:
        healthcheck_url = await wait_for_sandbox_healthcheck(
            sandbox.tunnel_url,
            timeout_seconds=healthcheck_timeout,
        )
        exec_result = await run_modal_exec_smoke_test(
            tunnel_url=sandbox.tunnel_url,
            session_public_id=session_public_id,
            timeout_seconds=exec_timeout,
        )
        validate_modal_exec_smoke_result(exec_result)

        return ModalPreflightResult(
            sandbox_db_id=sandbox_db_id,
            modal_sandbox_id=sandbox.modal_sandbox_id,
            tunnel_url=sandbox.tunnel_url,
            healthcheck_url=healthcheck_url,
            exec_result=exec_result,
        )
    finally:
        await sandbox.terminate()


def main() -> int:
    if not should_run_modal_preflight():
        print("[modal-preflight] skipped because Modal provisioning is disabled")
        return 0

    try:
        result = asyncio.run(run_modal_preflight())
    except Exception as exc:
        print(f"[modal-preflight] failed: {exc}", file=sys.stderr)
        return 1

    print(
        "[modal-preflight] ok "
        f"sandbox_db_id={result.sandbox_db_id} "
        f"modal_sandbox_id={result.modal_sandbox_id} "
        f"healthcheck_url={result.healthcheck_url} "
        f"exec_exit_code={result.exec_result.exit_code} "
        f"exec_duration_ms={result.exec_result.duration_ms}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
