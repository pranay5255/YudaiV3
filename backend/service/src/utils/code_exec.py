from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Dict

import structlog

logger = structlog.get_logger(__name__)

LANG_COMMAND: Dict[str, str] = {
    "python": "python",
}

def run_code(code: str, language: str = "python") -> str:
    """Execute code in a sandboxed subprocess and return the output."""
    cmd = LANG_COMMAND.get(language)
    if cmd is None:
        raise ValueError(f"Unsupported language: {language}")

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / f"main.{language}"
        file_path.write_text(code)

        try:
            logger.info("running code", language=language)
            result = subprocess.run(
                [cmd, str(file_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout + result.stderr
            logger.debug("code execution finished", returncode=result.returncode)
            return output
        except subprocess.TimeoutExpired:
            logger.error("code execution timed out")
            return "Execution timed out"
        except Exception as exc:  # noqa: BLE001
            logger.exception("code execution failed", exc=exc)
            return f"Execution failed: {exc}"
