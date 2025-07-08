from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def run_tests(code: str, tests: str | None = None) -> str:
    """Run pytest on the given code and optional tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        code_path = Path(tmpdir) / "main.py"
        code_path.write_text(code)

        if tests:
            tests_path = Path(tmpdir) / "tests.py"
            tests_path.write_text(tests)
        else:
            tests_path = None

        cmd = ["pytest", "-q"]
        if tests_path:
            cmd.append(str(tests_path))
        else:
            cmd.append(str(code_path))

        try:
            logger.info("running tests")
            result = subprocess.run(
                cmd,
                cwd=tmpdir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = result.stdout + result.stderr
            logger.debug("tests finished", returncode=result.returncode)
            return output
        except subprocess.TimeoutExpired:
            logger.error("tests timed out")
            return "Tests timed out"
        except Exception as exc:  # noqa: BLE001
            logger.exception("test run failed", exc=exc)
            return f"Tests failed: {exc}"
