"""Download sandbox-generated artifacts to persistent controller storage."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
import shlex
from typing import Any, Dict, Iterable, Optional

from .sandbox_transport import run_sandbox_command

ARTIFACT_STREAM_START = "__YUDAI_ARTIFACT_STREAM_START__"
ARTIFACT_STREAM_END = "__YUDAI_ARTIFACT_STREAM_END__"


@dataclass(frozen=True)
class DownloadedArtifactBundle:
    bundle_path: str
    metadata_path: str
    checksum_sha256: str
    byte_size: int
    source_paths: list[str]


class SandboxArtifactStore:
    """Writes downloaded sandbox bundles to local persistent storage."""

    def __init__(self, root: Optional[str] = None) -> None:
        self.root = Path(root or os.getenv("SANDBOX_ARTIFACT_ROOT", "/data/sandbox_artifacts"))
        self.root.mkdir(parents=True, exist_ok=True)

    def bundle_dir(self, session_public_id: str, workflow_name: str) -> Path:
        safe_session = _safe_path_component(session_public_id)
        safe_workflow = _safe_path_component(workflow_name)
        path = self.root / safe_session / safe_workflow
        path.mkdir(parents=True, exist_ok=True)
        return path


def _safe_path_component(raw: str) -> str:
    sanitized = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in raw)
    return sanitized.strip("-") or "artifact"


def build_artifact_archive_command(
    *,
    source_paths: Iterable[str],
    archive_prefix: str,
) -> str:
    encoded_paths = json.dumps(list(source_paths))
    encoded_prefix = json.dumps(archive_prefix)
    return "\n".join(
        [
            "set -euo pipefail",
            "python -u - <<'PY'",
            "import base64",
            "import io",
            "import json",
            "import os",
            "import pathlib",
            "import tarfile",
            f"source_paths = json.loads({encoded_paths!r})",
            f"archive_prefix = json.loads({encoded_prefix!r})",
            "workspace_path = pathlib.Path(os.environ.get('WORKSPACE_PATH', '/workspace/repo'))",
            "buffer = io.BytesIO()",
            "with tarfile.open(fileobj=buffer, mode='w:gz') as archive:",
            "    for raw in source_paths:",
            "        path = pathlib.Path(raw)",
            "        if not path.is_absolute():",
            "            path = workspace_path / path",
            "        path = path.resolve()",
            "        if not path.exists():",
            "            continue",
            "        try:",
            "            arcname = str(path.relative_to(workspace_path.resolve()))",
            "            arcname = arcname if arcname and arcname != '.' else path.name",
            "        except Exception:",
            "            arcname = path.name",
            "        archive.add(str(path), arcname=f'{archive_prefix}/{arcname}')",
            f"print({ARTIFACT_STREAM_START!r})",
            "buffer.seek(0)",
            "while True:",
            "    chunk = buffer.read(24 * 1024)",
            "    if not chunk:",
            "        break",
            "    print(base64.b64encode(chunk).decode('ascii'))",
            f"print({ARTIFACT_STREAM_END!r})",
            "PY",
        ]
    )


async def download_sandbox_artifact_bundle(
    *,
    tunnel_url: str,
    session_public_id: str,
    store: SandboxArtifactStore,
    workflow_name: str,
    archive_name: str,
    source_paths: Iterable[str],
    timeout_seconds: int = 1800,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> DownloadedArtifactBundle:
    bundle_dir = store.bundle_dir(session_public_id, workflow_name)
    bundle_path = bundle_dir / archive_name
    metadata_path = bundle_dir / f"{bundle_path.stem}.metadata.json"
    source_paths_list = [str(item) for item in source_paths]

    stream_started = False
    stream_finished = False
    line_buffer = ""

    with bundle_path.open("wb") as artifact_handle:
        async def _on_event(event: Dict[str, Any]) -> None:
            nonlocal stream_started, stream_finished, line_buffer
            if event.get("type") != "sandbox_stream":
                return
            payload = event.get("payload", {}) or {}
            if payload.get("event") != "stdout":
                return
            chunk = payload.get("data")
            if not isinstance(chunk, str):
                return
            line_buffer += chunk
            while "\n" in line_buffer:
                line, line_buffer = line_buffer.split("\n", 1)
                stripped = line.rstrip("\r")
                if not stream_started:
                    if stripped == ARTIFACT_STREAM_START:
                        stream_started = True
                    continue
                if stripped == ARTIFACT_STREAM_END:
                    stream_finished = True
                    continue
                if stream_finished or not stripped:
                    continue
                artifact_handle.write(base64.b64decode(stripped.encode("ascii")))

        result = await run_sandbox_command(
            tunnel_url=tunnel_url,
            session_public_id=session_public_id,
            command=build_artifact_archive_command(
                source_paths=source_paths_list,
                archive_prefix=workflow_name,
            ),
            cwd=cwd,
            env=env,
            timeout_seconds=timeout_seconds,
            on_event=_on_event,
            capture_stdout=False,
            capture_stderr=True,
        )

    if line_buffer.strip():
        if line_buffer.strip() == ARTIFACT_STREAM_END:
            stream_finished = True

    if result.exit_code != 0:
        stderr_tail = result.stderr.strip()[-2000:]
        raise RuntimeError(
            "Sandbox artifact download failed "
            f"with exit_code={result.exit_code}: {stderr_tail or 'no stderr output'}"
        )
    if not stream_started or not stream_finished:
        raise RuntimeError("Sandbox artifact stream markers were not observed during download")
    if not bundle_path.exists() or bundle_path.stat().st_size == 0:
        raise RuntimeError("Downloaded sandbox artifact bundle is empty")

    checksum = await asyncio.to_thread(_sha256_file, bundle_path)
    metadata = {
        "session_public_id": session_public_id,
        "workflow_name": workflow_name,
        "bundle_path": str(bundle_path),
        "checksum_sha256": checksum,
        "byte_size": bundle_path.stat().st_size,
        "source_paths": source_paths_list,
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")

    return DownloadedArtifactBundle(
        bundle_path=str(bundle_path),
        metadata_path=str(metadata_path),
        checksum_sha256=checksum,
        byte_size=bundle_path.stat().st_size,
        source_paths=source_paths_list,
    )


def _sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
