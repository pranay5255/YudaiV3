"""Lightweight sandbox code exploration for Daifu chat turns."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from yudai.config import get_agent_config, get_model_config, get_sandbox_config
from yudai.models import ChatSession, Sandbox, SandboxStatus
from yudai.realtime.lifecycle import SandboxExecBroker
from yudai.realtime.modal_sandbox import (
    SANDBOX_MSWEA_CONFIG_ROOT,
    SANDBOX_WORKSPACE_PATH,
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class ProbeRequest:
    probe_id: str
    query: str


@dataclass
class ProbeResult:
    probe_id: str
    status: str
    output_text: str
    summary: Optional[str]
    files: List[str]
    duration_ms: int
    query: Optional[str] = None
    error: Optional[str] = None


class ContextProbeService:
    """Spawns lightweight Architect agents in the sandbox for context gathering."""

    PROBE_CONFIG_PATH = f"{SANDBOX_MSWEA_CONFIG_ROOT}/probe/config.yaml"
    PROBE_TIMEOUT_SECONDS = 60
    OUTPUT_BEGIN = "__YUDAI_PROBE_OUTPUT_BEGIN__"
    OUTPUT_END = "__YUDAI_PROBE_OUTPUT_END__"
    MAX_CONTEXT_CHARS_PER_PROBE = 6000

    def __init__(self, broker: SandboxExecBroker):
        self.broker = broker

    async def run_probe(
        self,
        db: Session,
        *,
        session: ChatSession,
        probe: ProbeRequest,
    ) -> ProbeResult:
        """Run a single mini Architect probe with a natural-language query."""

        started = asyncio.get_running_loop().time()
        if not self.has_active_sandbox(db, session):
            return ProbeResult(
                probe_id=probe.probe_id,
                query=probe.query,
                status="no_sandbox",
                output_text="",
                summary=None,
                files=[],
                duration_ms=0,
                error="No active sandbox runtime is available for this session.",
            )

        workspace = session.runtime_workspace_path or SANDBOX_WORKSPACE_PATH
        output_path = f"{workspace}/.yudai/probes/{probe.probe_id}.md"
        env: Dict[str, str] = {
            "WORKSPACE_PATH": workspace,
            "YUDAI_PROBE_ID": probe.probe_id,
            "YUDAI_PROBE_OUTPUT": output_path,
            "MSWEA_PROBE_QUERY": probe.query,
            "MSWEA_CONFIG_ROOT": SANDBOX_MSWEA_CONFIG_ROOT,
            "REPO_BRANCH": session.repo_branch or "main",
        }

        repo_url = session.repo_url
        if not repo_url and session.repo_owner and session.repo_name:
            repo_url = f"https://github.com/{session.repo_owner}/{session.repo_name}.git"
        if repo_url:
            env["REPO_URL"] = repo_url

        env.update(dict(get_sandbox_config().env_passthrough_values))

        try:
            result = await self.broker.run_command(
                db,
                session=session,
                command=self._build_probe_command(probe, workspace),
                cwd=workspace,
                env=env,
                timeout_seconds=get_agent_config().probe_timeout_seconds,
            )
        except HTTPException as exc:
            status = "no_sandbox" if exc.status_code in {404, 409, 410, 503} else "error"
            return self._error_result(probe, started, status=status, error=str(exc.detail))
        except Exception as exc:
            message = str(exc)
            status = "timeout" if "timed out" in message.lower() else "error"
            return self._error_result(probe, started, status=status, error=message)

        stdout = str(result.get("stdout") or "")
        stderr = str(result.get("stderr") or "")
        combined = f"{stdout}\n{stderr}".strip()
        output_text = self._extract_marked_output(stdout).strip()
        if not output_text:
            output_text = combined

        parsed = self._parse_json_summary(combined)
        summary = parsed.get("summary") if isinstance(parsed.get("summary"), str) else None
        files = self._coerce_files(parsed.get("files"))

        status = "completed" if int(result.get("exit_code") or 0) == 0 else "error"
        if not files:
            files = self._extract_file_paths(output_text)

        return ProbeResult(
            probe_id=probe.probe_id,
            query=probe.query,
            status=status,
            output_text=output_text,
            summary=summary,
            files=files,
            duration_ms=int(result.get("duration_ms") or 0),
            error=None if status == "completed" else stderr or stdout,
        )

    async def run_probes_parallel(
        self,
        db: Session,
        *,
        session: ChatSession,
        probes: List[ProbeRequest],
    ) -> List[ProbeResult]:
        """Run up to three probes concurrently and normalize failures."""

        tasks = [self.run_probe(db, session=session, probe=p) for p in probes[:3]]
        raw_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: List[ProbeResult] = []
        for probe, result in zip(probes[:3], raw_results):
            if isinstance(result, ProbeResult):
                results.append(result)
            else:
                results.append(
                    ProbeResult(
                        probe_id=probe.probe_id,
                        query=probe.query,
                        status="error",
                        output_text="",
                        summary=None,
                        files=[],
                        duration_ms=0,
                        error=str(result),
                    )
                )
        return results

    @staticmethod
    def format_as_context(results: List[ProbeResult]) -> Optional[str]:
        """Format probe results for Daifu's next prompt."""

        sections: List[str] = []
        for result in results:
            if result.status not in {"completed", "timeout"}:
                continue
            body = (result.output_text or result.summary or "").strip()
            if not body:
                continue
            if len(body) > ContextProbeService.MAX_CONTEXT_CHARS_PER_PROBE:
                body = body[: ContextProbeService.MAX_CONTEXT_CHARS_PER_PROBE].rstrip()
                body += "\n\n[truncated]"

            query = result.query or result.probe_id
            section_lines = [
                f'## Query: "{query}"',
                f"Status: {result.status}",
                "",
                body,
            ]
            if result.files:
                section_lines.extend(["", "Files found: " + ", ".join(result.files[:20])])
            sections.append("\n".join(section_lines).strip())

        if not sections:
            return None

        return "[CODE_EXPLORATION_CONTEXT]\n" + "\n\n".join(sections)

    @staticmethod
    def has_active_sandbox(db: Session, session: ChatSession) -> bool:
        """Return whether this session has a non-terminated sandbox with a tunnel."""

        try:
            runtime_records = getattr(session, "runtime_records", None)
            runtime = None
            if runtime_records:
                runtime = sorted(runtime_records, key=lambda item: item.id)[-1]
            if runtime is None:
                from yudai.models import SessionRuntime

                runtime = (
                    db.query(SessionRuntime)
                    .filter(SessionRuntime.session_id == session.id)
                    .order_by(SessionRuntime.id.desc())
                    .first()
                )
            if not runtime or not runtime.sandbox_id:
                return False
            sandbox = db.query(Sandbox).filter(Sandbox.id == runtime.sandbox_id).first()
            if not sandbox:
                return False
            if sandbox.status == SandboxStatus.TERMINATED.value:
                return False
            return bool(sandbox.tunnel_url)
        except Exception:
            logger.debug("Failed to check active sandbox for session %s", session.id, exc_info=True)
            return False

    def _build_probe_command(self, probe: ProbeRequest, workspace: str) -> str:
        """Build the bash script that invokes mini with the probe config."""

        command_lines = [
            "set -euo pipefail",
            f'workspace="${{WORKSPACE_PATH:-{workspace or SANDBOX_WORKSPACE_PATH}}}"',
            'HOME="${HOME:-/root}"',
            'probe_id="${YUDAI_PROBE_ID:-probe_manual}"',
            'probe_output="${YUDAI_PROBE_OUTPUT:-$workspace/.yudai/probes/$probe_id.md}"',
            'case "$probe_output" in /*) ;; *) probe_output="$workspace/$probe_output" ;; esac',
            'mkdir -p "$workspace" "$(dirname "$probe_output")"',
            'cd "$workspace"',
            'config_path="${MSWEA_PROBE_CONFIG_PATH:-' + self.PROBE_CONFIG_PATH + '}"',
            'if ! command -v mini >/dev/null 2>&1; then',
            '  echo "mini-swe-agent CLI not found: expected executable named mini" >&2',
            '  exit 127',
            'fi',
            'python_bin="${PYTHON:-}"',
            'if [ -z "$python_bin" ]; then',
            '  if command -v python3 >/dev/null 2>&1; then',
            '    python_bin="python3"',
            '  elif command -v python >/dev/null 2>&1; then',
            '    python_bin="python"',
            '  else',
            '    echo "python interpreter not found: expected python3 or python" >&2',
            '    exit 127',
            '  fi',
            'fi',
            f'model_name="${{MSWEA_MODEL_NAME:-{get_model_config().agent_model_name}}}"',
            'task_text="${MSWEA_PROBE_QUERY:-}"',
            'printf "%s\\n" "$task_text" > "$workspace/.yudai/probes/$probe_id.query.txt"',
            'cmd=(mini -c "$config_path" -y -m "$model_name" -t "$task_text")',
            'if [ "${YUDAI_MSWEA_COMMAND_PROBE:-0}" = "1" ]; then',
            '  export probe_id config_path model_name probe_output task_text',
            '  "$python_bin" - "${probe_output}.command_probe.json" "${cmd[@]}" <<\'PY\'',
            'import json',
            'import os',
            'import sys',
            'payload = {',
            '    "probe_id": os.environ.get("probe_id", ""),',
            '    "workspace": os.environ.get("WORKSPACE_PATH", ""),',
            '    "config_path": os.environ.get("config_path", ""),',
            '    "model_name": os.environ.get("model_name", ""),',
            '    "query": os.environ.get("task_text", ""),',
            '    "output_file": os.environ.get("probe_output", ""),',
            '    "argv": sys.argv[2:],',
            '}',
            'path = sys.argv[1]',
            'with open(path, "w", encoding="utf-8") as fh:',
            '    json.dump(payload, fh, ensure_ascii=True, indent=2)',
            '    fh.write("\\n")',
            'print(json.dumps(payload, ensure_ascii=True))',
            'PY',
            '  exit 0',
            'fi',
            'printf "[probe:%s] running:" "$probe_id"',
            'printf " %q" "${cmd[@]}"',
            'printf "\\n"',
            'set +e',
            '"${cmd[@]}"',
            'exit_code=$?',
            'set -e',
            f'printf "\\n{self.OUTPUT_BEGIN}\\n"',
            'if [ -f "$probe_output" ]; then',
            '  cat "$probe_output"',
            'fi',
            f'printf "\\n{self.OUTPUT_END}\\n"',
            'exit "$exit_code"',
        ]
        return "\n".join(command_lines)

    def _error_result(
        self,
        probe: ProbeRequest,
        started: float,
        *,
        status: str,
        error: str,
    ) -> ProbeResult:
        return ProbeResult(
            probe_id=probe.probe_id,
            query=probe.query,
            status=status,
            output_text="",
            summary=None,
            files=[],
            duration_ms=int((asyncio.get_running_loop().time() - started) * 1000),
            error=error,
        )

    @classmethod
    def _extract_marked_output(cls, stdout: str) -> str:
        pattern = re.compile(
            rf"{re.escape(cls.OUTPUT_BEGIN)}\n?(?P<body>.*?){re.escape(cls.OUTPUT_END)}",
            re.DOTALL,
        )
        match = pattern.search(stdout or "")
        return match.group("body") if match else ""

    @staticmethod
    def _parse_json_summary(output_text: str) -> Dict[str, Any]:
        for line in reversed((output_text or "").splitlines()):
            raw = line.strip()
            if not raw.startswith("{") or not raw.endswith("}"):
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return {}

    @staticmethod
    def _coerce_files(value: Any) -> List[str]:
        if not isinstance(value, list):
            return []
        files: List[str] = []
        for item in value:
            text = str(item or "").strip()
            if text and text not in files:
                files.append(text)
        return files

    @staticmethod
    def _extract_file_paths(output_text: str) -> List[str]:
        candidates = re.findall(
            r"(?<![\w/.-])(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9_]+(?::\d+)?",
            output_text or "",
        )
        files: List[str] = []
        for candidate in candidates:
            path = candidate.split(":", 1)[0]
            if path not in files:
                files.append(path)
        return files
