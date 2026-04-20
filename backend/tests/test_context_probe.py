import json
import os
from pathlib import Path
import subprocess
import sys


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/context-probe-tests.db")

from daifuUserAgent.context_probe import (  # noqa: E402
    ContextProbeService,
    ProbeRequest,
    ProbeResult,
)


def test_format_as_context_includes_successful_probe_outputs_only():
    context = ContextProbeService.format_as_context(
        [
            ProbeResult(
                probe_id="probe_done",
                query="how auth connects to the DB",
                status="completed",
                output_text="Auth routes call `get_db()` in backend/auth/auth_routes.py:42.",
                summary="Auth uses FastAPI dependencies.",
                files=["backend/auth/auth_routes.py"],
                duration_ms=123,
            ),
            ProbeResult(
                probe_id="probe_failed",
                query="failing query",
                status="error",
                output_text="",
                summary=None,
                files=[],
                duration_ms=1,
            ),
        ]
    )

    assert context is not None
    assert '[CODE_EXPLORATION_CONTEXT]' in context
    assert '## Query: "how auth connects to the DB"' in context
    assert "backend/auth/auth_routes.py" in context
    assert "failing query" not in context


def test_build_probe_command_uses_probe_config_and_query(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    mini = bin_dir / "mini"
    mini.write_text("#!/usr/bin/env bash\nprintf 'fake mini\\n'\n", encoding="utf-8")
    mini.chmod(0o755)

    workspace = tmp_path / "repo"
    service = ContextProbeService(broker=object())
    command = service._build_probe_command(
        ProbeRequest(probe_id="probe_test", query="How does auth connect to DB?"),
        str(workspace),
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}{os.pathsep}{env.get('PATH', '')}",
            "WORKSPACE_PATH": str(workspace),
            "YUDAI_PROBE_ID": "probe_test",
            "YUDAI_PROBE_OUTPUT": str(workspace / ".yudai" / "probes" / "probe_test.md"),
            "MSWEA_PROBE_QUERY": "How does auth connect to DB?",
            "MSWEA_MODEL_NAME": "openrouter/x-ai/grok-4-fast",
            "YUDAI_MSWEA_COMMAND_PROBE": "1",
        }
    )

    completed = subprocess.run(
        ["bash", "-lc", command],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.strip().splitlines()[-1])
    argv = payload["argv"]

    assert argv[0] == "mini"
    assert argv[1:3] == ["-c", "/app/mswea_mode_configs/probe/config.yaml"]
    assert "-y" in argv
    assert argv[argv.index("-m") + 1] == "openrouter/x-ai/grok-4-fast"
    assert argv[argv.index("-t") + 1] == "How does auth connect to DB?"
    assert payload["output_file"] == str(workspace / ".yudai" / "probes" / "probe_test.md")
    assert (workspace / ".yudai" / "probes" / "probe_test.query.txt").is_file()
