import os
from pathlib import Path
import sys

import pytest

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/modal-preflight-tests.db")

from yudai.config.realtime_flags import RealtimeFeatureFlags  # noqa: E402
from yudai.realtime import modal_preflight, modal_sandbox  # noqa: E402


def test_solver_distribution_uses_published_package_name():
    assert "mini-swe-agent" in modal_sandbox.SANDBOX_SOLVER_PIP_PACKAGES
    assert "playwright" in modal_sandbox.SANDBOX_SOLVER_PIP_PACKAGES
    assert "minisweagent" not in modal_sandbox.SANDBOX_SOLVER_PIP_PACKAGES


def test_build_modal_exec_smoke_command_checks_import_and_bash():
    command = modal_preflight.build_modal_exec_smoke_command()

    assert "import minisweagent" in command
    assert "command -v mini >/dev/null" in command
    assert modal_preflight.MODAL_PREFLIGHT_IMPORT_MARKER in command
    assert modal_preflight.MODAL_PREFLIGHT_BASH_MARKER in command
    assert "command -v bash >/dev/null" in command


def test_validate_modal_exec_smoke_result_accepts_expected_markers():
    result = modal_preflight.ModalExecSmokeResult(
        exit_code=0,
        stdout=(
            f"{modal_preflight.MODAL_PREFLIGHT_IMPORT_MARKER}\n"
            f"{modal_preflight.MODAL_PREFLIGHT_BASH_MARKER}\n"
        ),
        stderr="",
        duration_ms=12,
    )

    modal_preflight.validate_modal_exec_smoke_result(result)


def test_validate_modal_exec_smoke_result_rejects_nonzero_exit_code():
    result = modal_preflight.ModalExecSmokeResult(
        exit_code=7,
        stdout="",
        stderr="module import failed",
        duration_ms=12,
    )

    with pytest.raises(RuntimeError, match="exit code 7"):
        modal_preflight.validate_modal_exec_smoke_result(result)


def test_validate_modal_exec_smoke_result_rejects_missing_import_marker():
    result = modal_preflight.ModalExecSmokeResult(
        exit_code=0,
        stdout=f"{modal_preflight.MODAL_PREFLIGHT_BASH_MARKER}\n",
        stderr="",
        duration_ms=12,
    )

    with pytest.raises(RuntimeError, match="did not import minisweagent"):
        modal_preflight.validate_modal_exec_smoke_result(result)


def test_validate_modal_exec_smoke_result_rejects_missing_bash_marker():
    result = modal_preflight.ModalExecSmokeResult(
        exit_code=0,
        stdout=f"{modal_preflight.MODAL_PREFLIGHT_IMPORT_MARKER}\n",
        stderr="",
        duration_ms=12,
    )

    with pytest.raises(RuntimeError, match="did not complete bash execution"):
        modal_preflight.validate_modal_exec_smoke_result(result)


def test_should_run_modal_preflight_requires_modal_provisioning():
    flags = RealtimeFeatureFlags(
        controller_split_enabled=False,
        controller_broker_enabled=True,
        sandbox_internal_exec_enabled=True,
        mode_orchestrator_enabled=True,
        ws_chat_enabled=False,
        modal_provisioning_enabled=False,
        ws_unified_enabled=False,
        contract_version="test",
    )

    assert modal_preflight.should_run_modal_preflight(flags) is False


def test_should_run_modal_preflight_respects_explicit_disable(monkeypatch):
    flags = RealtimeFeatureFlags(
        controller_split_enabled=False,
        controller_broker_enabled=True,
        sandbox_internal_exec_enabled=True,
        mode_orchestrator_enabled=True,
        ws_chat_enabled=False,
        modal_provisioning_enabled=True,
        ws_unified_enabled=False,
        contract_version="test",
    )
    monkeypatch.setenv("MODAL_SANDBOX_PREFLIGHT_ENABLED", "false")

    assert modal_preflight.should_run_modal_preflight(flags) is False
