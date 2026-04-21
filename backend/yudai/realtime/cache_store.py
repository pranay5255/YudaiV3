"""Append-only sandbox cache, artifact export, and artifact download helpers."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tarfile
from typing import Any, Dict, Iterable, Optional

from yudai.config import get_sandbox_config


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SessionCacheStore:
    """Stores per-session append-only cache manifests under /home/yudai/.cache."""

    def __init__(self) -> None:
        self.root = Path(get_sandbox_config().cache_root)
        self.session_dir = self.root / "session"
        self.artifact_dir = self.root / "artifacts"
        self.metadata_dir = self.root / "artifact-metadata"

        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def manifest_path(self, session_id: str) -> Path:
        return self.session_dir / f"{session_id}.json"

    def bundle_path(self, session_id: str) -> Path:
        return self.artifact_dir / f"{session_id}.tar.gz"

    def metadata_path(self, session_id: str) -> Path:
        return self.metadata_dir / f"{session_id}.metadata.json"

    def ensure_manifest(
        self,
        *,
        session_id: str,
        sandbox_id: str,
        runtime_id: str,
        identity_key: str,
    ) -> Dict[str, Any]:
        path = self.manifest_path(session_id)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

        now = _utc_iso()
        payload: Dict[str, Any] = {
            "schema_version": "phase0.v1",
            "session_id": session_id,
            "sandbox_id": sandbox_id,
            "runtime_id": runtime_id,
            "identity_key": identity_key,
            "created_at": now,
            "updated_at": now,
            "events": [],
            "trajectory_refs": [],
            "github_refs": {},
        }
        self._write_json(path, payload)
        return payload

    def append_event(
        self,
        *,
        session_id: str,
        sandbox_id: str,
        runtime_id: str,
        identity_key: str,
        event_name: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        manifest = self.ensure_manifest(
            session_id=session_id,
            sandbox_id=sandbox_id,
            runtime_id=runtime_id,
            identity_key=identity_key,
        )

        manifest.setdefault("events", [])
        manifest["events"].append(
            {
                "event_name": event_name,
                "timestamp": _utc_iso(),
                "payload": payload or {},
            }
        )
        manifest["updated_at"] = _utc_iso()

        self._write_json(self.manifest_path(session_id), manifest)
        return manifest

    def merge_github_refs(
        self,
        *,
        session_id: str,
        sandbox_id: str,
        runtime_id: str,
        identity_key: str,
        refs: Dict[str, Any],
    ) -> Dict[str, Any]:
        manifest = self.ensure_manifest(
            session_id=session_id,
            sandbox_id=sandbox_id,
            runtime_id=runtime_id,
            identity_key=identity_key,
        )

        existing = manifest.get("github_refs")
        if not isinstance(existing, dict):
            existing = {}
        existing.update(refs)
        manifest["github_refs"] = existing
        manifest["updated_at"] = _utc_iso()

        self._write_json(self.manifest_path(session_id), manifest)
        return manifest

    def merge_trajectory_refs(
        self,
        *,
        session_id: str,
        sandbox_id: str,
        runtime_id: str,
        identity_key: str,
        refs: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        manifest = self.ensure_manifest(
            session_id=session_id,
            sandbox_id=sandbox_id,
            runtime_id=runtime_id,
            identity_key=identity_key,
        )

        existing_refs = manifest.get("trajectory_refs")
        if not isinstance(existing_refs, list):
            existing_refs = []

        seen = {(str(item.get("path")), str(item.get("sha256"))) for item in existing_refs}
        for ref in refs:
            key = (str(ref.get("path")), str(ref.get("sha256")))
            if key in seen:
                continue
            existing_refs.append(ref)
            seen.add(key)

        manifest["trajectory_refs"] = existing_refs
        manifest["updated_at"] = _utc_iso()

        self._write_json(self.manifest_path(session_id), manifest)
        return manifest

    def export_bundle(
        self,
        *,
        session_id: str,
        runtime_id: str,
        sandbox_id: str,
        identity_key: str,
        runtime_summary: Dict[str, Any],
        object_store: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        manifest = self.ensure_manifest(
            session_id=session_id,
            sandbox_id=sandbox_id,
            runtime_id=runtime_id,
            identity_key=identity_key,
        )

        manifest_path = self.manifest_path(session_id)
        bundle_path = self.bundle_path(session_id)

        with tarfile.open(bundle_path, mode="w:gz") as archive:
            archive.add(manifest_path, arcname=f"{session_id}/manifest.json")

            for ref in manifest.get("trajectory_refs", []):
                trajectory_path = Path(str(ref.get("path", "")))
                if not trajectory_path.exists() or not trajectory_path.is_file():
                    continue
                archive.add(
                    trajectory_path,
                    arcname=f"{session_id}/trajectory/{trajectory_path.name}",
                )

        manifest_sha = self.sha256_file(manifest_path)
        bundle_sha = self.sha256_file(bundle_path)
        exported_at = _utc_iso()

        metadata: Dict[str, Any] = {
            "schema_version": "phase0.v1",
            "session_id": session_id,
            "runtime_id": runtime_id,
            "sandbox_id": sandbox_id,
            "identity_key": identity_key,
            "exported_at": exported_at,
            "cache_manifest_path": str(manifest_path),
            "bundle_path": str(bundle_path),
            "checksums": {
                "bundle_sha256": bundle_sha,
                "manifest_sha256": manifest_sha,
            },
            "runtime_summary": runtime_summary,
        }

        if object_store:
            metadata["object_store"] = object_store

        metadata_path = self.metadata_path(session_id)
        self._write_json(metadata_path, metadata)

        return {
            "metadata": metadata,
            "metadata_path": str(metadata_path),
            "bundle_path": str(bundle_path),
            "bundle_sha256": bundle_sha,
            "manifest_sha256": manifest_sha,
            "bundle_size": bundle_path.stat().st_size if bundle_path.exists() else 0,
        }

    def artifact_store(self) -> "SandboxArtifactStore":
        return SandboxArtifactStore(root=str(self.artifact_dir))

    async def download_and_export_bundle(
        self,
        *,
        tunnel_url: str,
        session_public_id: str,
        runtime_id: str,
        sandbox_id: str,
        identity_key: str,
        workflow_name: str,
        archive_name: str,
        source_paths: Iterable[str],
        runtime_summary: Dict[str, Any],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 1800,
        object_store: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        manifest = self.ensure_manifest(
            session_id=session_public_id,
            sandbox_id=sandbox_id,
            runtime_id=runtime_id,
            identity_key=identity_key,
        )
        manifest["updated_at"] = _utc_iso()
        self._write_json(self.manifest_path(session_public_id), manifest)

        downloaded = await download_sandbox_artifact_bundle(
            tunnel_url=tunnel_url,
            session_public_id=session_public_id,
            store=self.artifact_store(),
            workflow_name=workflow_name,
            archive_name=archive_name,
            source_paths=source_paths,
            timeout_seconds=timeout_seconds,
            cwd=cwd,
            env=env,
        )

        metadata: Dict[str, Any] = {
            "schema_version": "phase1.execution.v1",
            "session_id": session_public_id,
            "runtime_id": runtime_id,
            "sandbox_id": sandbox_id,
            "identity_key": identity_key,
            "exported_at": _utc_iso(),
            "cache_manifest_path": str(self.manifest_path(session_public_id)),
            "bundle_path": downloaded.bundle_path,
            "checksums": {
                "bundle_sha256": downloaded.checksum_sha256,
                "manifest_sha256": self.sha256_file(self.manifest_path(session_public_id)),
            },
            "runtime_summary": runtime_summary,
            "sandbox_bundle": {
                "bundle_path": downloaded.bundle_path,
                "metadata_path": downloaded.metadata_path,
                "checksum_sha256": downloaded.checksum_sha256,
                "byte_size": downloaded.byte_size,
                "source_paths": downloaded.source_paths,
                "workflow_name": workflow_name,
            },
        }
        if object_store:
            metadata["object_store"] = object_store

        metadata_path = self.metadata_path(session_public_id)
        self._write_json(metadata_path, metadata)

        return {
            "metadata": metadata,
            "metadata_path": str(metadata_path),
            "bundle_path": downloaded.bundle_path,
            "bundle_sha256": downloaded.checksum_sha256,
            "manifest_sha256": metadata["checksums"]["manifest_sha256"],
            "bundle_size": downloaded.byte_size,
        }

    def sha256_file(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temp_path.replace(path)

    def build_trajectory_ref(self, file_path: str) -> Optional[Dict[str, Any]]:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return None

        return {
            "path": str(path),
            "sha256": self.sha256_file(path),
            "bytes": path.stat().st_size,
        }


# ---------------------------------------------------------------------------
# Sandbox artifact download helpers
# (consolidated from sandbox_artifacts.py)
# ---------------------------------------------------------------------------

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
        self.root = Path(root or get_sandbox_config().artifact_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def bundle_dir(self, session_public_id: str, workflow_name: str) -> Path:
        safe_session = _safe_artifact_path_component(session_public_id)
        safe_workflow = _safe_artifact_path_component(workflow_name)
        path = self.root / safe_session / safe_workflow
        path.mkdir(parents=True, exist_ok=True)
        return path


def _safe_artifact_path_component(raw: str) -> str:
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
    from .sandbox_transport import run_sandbox_command  # local import to avoid circular dependency

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

    checksum = await asyncio.to_thread(_sha256_artifact_file, bundle_path)
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


def _sha256_artifact_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
