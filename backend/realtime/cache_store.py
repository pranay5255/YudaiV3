"""Append-only sandbox cache and artifact export helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tarfile
from typing import Any, Dict, Iterable, Optional


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SessionCacheStore:
    """Stores per-session append-only cache manifests under /home/yudai/.cache."""

    def __init__(self) -> None:
        self.root = Path(os.getenv("SANDBOX_CACHE_ROOT", "/home/yudai/.cache"))
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
