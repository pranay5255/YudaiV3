"""Realtime Phase 1 lifecycle service for controller/sandbox coordination."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from datetime import timedelta
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Awaitable, Callable, Dict, Iterable, Optional, Set, Tuple
import uuid

from config.realtime_identity import build_sandbox_identity
from db.database import SessionLocal
from models import (
    ChatSession,
    Sandbox,
    SandboxStatus,
    SessionArtifact,
    SessionAuditEvent,
    SessionAuditEventName,
    SessionRuntime,
    SessionRuntimeStatus,
    Solve,
    SolveRun,
)
from sqlalchemy import or_
from sqlalchemy.orm import Session

from utils import utc_now

from config.realtime_flags import get_realtime_feature_flags

import httpx

from .cache_store import SessionCacheStore
from .errors import RealtimeErrorCode, as_http_exception
from .modal_sandbox import RealtimeModalSandbox, get_modal_registry
from .sandbox_transport import run_sandbox_command


@dataclass
class RuntimeEnvelope:
    sandbox: Sandbox
    runtime: SessionRuntime


class RealtimeLifecycleService:
    """Controller-facing lifecycle operations for sandboxes and session runtimes."""

    def __init__(
        self,
        *,
        sandbox_manager: Optional[SandboxManager] = None,
        cache_store: Optional[SessionCacheStore] = None,
    ) -> None:
        self.sandbox_manager = sandbox_manager or SandboxManager()
        self.cache_store = cache_store or SessionCacheStore()
        self.default_org = os.getenv("REALTIME_DEFAULT_ORG", "yudai")

    # ---------------------------------------------------------------------
    # Sandbox + runtime provisioning
    # ---------------------------------------------------------------------

    async def create_runtime_for_session(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
        org: Optional[str],
        repo_owner: str,
        repo_name: str,
        environment: Optional[str],
        repo_branch: Optional[str],
        repo_url: Optional[str],
        github_token: Optional[str] = None,
        env_inputs: Optional[Dict[str, str]] = None,
    ) -> RuntimeEnvelope:
        identity = build_sandbox_identity(
            org=org or self.default_org,
            repo_owner=repo_owner,
            repo_name=repo_name,
            environment=environment or repo_branch or "main",
        )

        sandbox, reused_existing_sandbox = self._resolve_sandbox_for_identity(
            db,
            identity_key=identity.key,
            user_id=user_id,
            session_id=session.id,
            org_slug=identity.org,
            repo_owner=identity.repo_owner,
            repo_name=identity.repo_name,
            environment=identity.environment,
            repo_branch=repo_branch or "main",
        )
        sandbox.active_session_id = session.id
        sandbox.status = SandboxStatus.RUNNING.value
        workspace_path = os.getenv("REALTIME_WORKSPACE_PATH", "/workspace/repo")
        setup_context: Dict[str, Any] = {
            "repo_url": repo_url,
            "repo_branch": repo_branch or "main",
            "workspace_path": workspace_path,
            "env_inputs": env_inputs or {},
            "session_public_id": session.session_id,
        }

        flags = get_realtime_feature_flags()
        if flags.modal_provisioning_enabled:
            lifecycle_metadata = sandbox.lifecycle_metadata or {}
            existing_modal_sandbox_id = lifecycle_metadata.get("modal_sandbox_id")
            needs_modal_provision = (
                not reused_existing_sandbox
                or not existing_modal_sandbox_id
                or not sandbox.tunnel_url
            )
            if needs_modal_provision:
                controller_base_url = os.getenv("CONTROLLER_BASE_URL", "http://localhost:8000")
                modal_sb = await RealtimeModalSandbox.create(
                    sandbox_db_id=sandbox.id,
                    controller_base_url=controller_base_url,
                    github_token=github_token,
                    session_public_id=session.session_id,
                    repo_url=repo_url,
                    repo_branch=repo_branch or "main",
                    workspace_path=workspace_path,
                    env_inputs=env_inputs or {},
                )
                sandbox.tunnel_url = modal_sb.tunnel_url
                await get_modal_registry().register(sandbox.id, modal_sb)
                lifecycle_metadata["modal_sandbox_id"] = modal_sb.modal_sandbox_id
        else:
            sandbox.tunnel_url = sandbox.tunnel_url or self.sandbox_manager.build_tunnel_url(sandbox.id)

        sandbox.tunnel_token_ttl_seconds = sandbox.tunnel_token_ttl_seconds or 3600
        sandbox.last_heartbeat_at = utc_now()

        lifecycle_metadata = sandbox.lifecycle_metadata or {}
        lifecycle_metadata.update(
            {
                "identity_key": identity.key,
                "controller_managed": True,
                "repo_owner": identity.repo_owner,
                "repo_name": identity.repo_name,
                "environment": identity.environment,
                "setup_context": setup_context,
                "reused_existing_sandbox": reused_existing_sandbox,
            }
        )
        if flags.modal_provisioning_enabled and "modal_sb" in locals():
            lifecycle_metadata["modal_sandbox_id"] = modal_sb.modal_sandbox_id
        sandbox.lifecycle_metadata = lifecycle_metadata

        git_bootstrap = {
            "status": "disabled",
            "reason": "sandbox_workspace_bootstrap_only",
        }

        runtime = self._get_latest_runtime(db, session_id=session.id)
        if runtime and runtime.status != SessionRuntimeStatus.TERMINATED.value:
            runtime.sandbox_id = sandbox.id
            runtime.status = SessionRuntimeStatus.RUNNING.value
            runtime.tunnel_url = sandbox.tunnel_url
            runtime.tunnel_resolved_at = utc_now()
            runtime.tunnel_expires_at = utc_now() + timedelta(
                seconds=sandbox.tunnel_token_ttl_seconds or 3600
            )
            metadata = runtime.runtime_metadata or {}
            metadata["git_bootstrap"] = git_bootstrap
            metadata["setup_context"] = setup_context
            runtime.runtime_metadata = metadata
        else:
            runtime = SessionRuntime(
                runtime_id=self._next_id("rt"),
                session_id=session.id,
                sandbox_id=sandbox.id,
                status=SessionRuntimeStatus.RUNNING.value,
                tunnel_url=sandbox.tunnel_url,
                tunnel_resolved_at=utc_now(),
                tunnel_expires_at=utc_now()
                + timedelta(seconds=sandbox.tunnel_token_ttl_seconds or 3600),
                started_at=utc_now(),
                runtime_metadata={
                    "git_bootstrap": git_bootstrap,
                    "setup_context": setup_context,
                },
            )
            db.add(runtime)
            db.flush()

        self._record_audit_event(
            db,
            event_name=SessionAuditEventName.SANDBOX_START.value,
            user_id=user_id,
            session_id=session.id,
            sandbox_id=sandbox.id,
            runtime_id=runtime.id,
            payload={
                "identity_key": sandbox.identity_key,
                "tunnel_url": sandbox.tunnel_url,
                "token_ttl_seconds": sandbox.tunnel_token_ttl_seconds,
                "setup_context": setup_context,
                "reused_existing_sandbox": reused_existing_sandbox,
            },
        )

        self.cache_store.append_event(
            session_id=session.session_id,
            sandbox_id=sandbox.id,
            runtime_id=runtime.runtime_id,
            identity_key=sandbox.identity_key,
            event_name=SessionAuditEventName.SANDBOX_START.value,
            payload={
                "tunnel_url": sandbox.tunnel_url,
                "token_ttl_seconds": sandbox.tunnel_token_ttl_seconds,
                "setup_context": setup_context,
                "reused_existing_sandbox": reused_existing_sandbox,
            },
        )

        self._start_probe_if_possible(sandbox_id=sandbox.id, tunnel_url=sandbox.tunnel_url)

        return RuntimeEnvelope(sandbox=sandbox, runtime=runtime)

    def _resolve_sandbox_for_identity(
        self,
        db: Session,
        *,
        identity_key: str,
        user_id: int,
        session_id: int,
        org_slug: str,
        repo_owner: str,
        repo_name: str,
        environment: str,
        repo_branch: str,
    ) -> Tuple[Sandbox, bool]:
        """Reuse or reactivate the sandbox row for a repo identity instead of inserting duplicates."""

        sandbox = (
            db.query(Sandbox)
            .filter(Sandbox.identity_key == identity_key)
            .order_by(Sandbox.created_at.desc())
            .first()
        )
        if sandbox is None:
            sandbox = Sandbox(
                id=self._next_id("sbx"),
                identity_key=identity_key,
                org_slug=org_slug,
                repo_owner=repo_owner,
                repo_name=repo_name,
                environment=environment,
                repo_branch=repo_branch,
                status=SandboxStatus.PROVISIONING.value,
                created_by_user_id=user_id,
                active_session_id=session_id,
                lifecycle_metadata={},
            )
            db.add(sandbox)
            db.flush()
            return sandbox, False

        sandbox.org_slug = org_slug
        sandbox.repo_owner = repo_owner
        sandbox.repo_name = repo_name
        sandbox.environment = environment
        sandbox.repo_branch = repo_branch
        sandbox.created_by_user_id = sandbox.created_by_user_id or user_id
        sandbox.active_session_id = session_id
        if sandbox.status == SandboxStatus.TERMINATED.value:
            sandbox.status = SandboxStatus.PROVISIONING.value
            sandbox.terminated_at = None
        return sandbox, True

    # ---------------------------------------------------------------------
    # Controller lifecycle endpoint operations
    # ---------------------------------------------------------------------

    def get_sandbox_or_404(self, db: Session, sandbox_id: str) -> Sandbox:
        sandbox = db.query(Sandbox).filter(Sandbox.id == sandbox_id).first()
        if not sandbox:
            raise as_http_exception(
                RealtimeErrorCode.TUNNEL_RESOLVE_FAILED,
                detail=f"Sandbox {sandbox_id} was not found",
            )
        return sandbox

    def resolve_tunnel(self, db: Session, sandbox_id: str) -> Tuple[Sandbox, SessionRuntime]:
        sandbox = self.get_sandbox_or_404(db, sandbox_id)

        if sandbox.status == SandboxStatus.TERMINATED.value:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_TERMINATED)

        if not sandbox.tunnel_url:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_UNAVAILABLE)

        runtime = self._get_latest_runtime(db, sandbox_id=sandbox.id)
        if not runtime:
            raise as_http_exception(
                RealtimeErrorCode.TUNNEL_RESOLVE_FAILED,
                detail="Runtime metadata missing for sandbox",
            )

        runtime.tunnel_url = sandbox.tunnel_url
        runtime.tunnel_resolved_at = utc_now()
        runtime.tunnel_expires_at = utc_now() + timedelta(
            seconds=sandbox.tunnel_token_ttl_seconds or 3600
        )

        return sandbox, runtime

    def record_heartbeat(self, db: Session, sandbox_id: str) -> Sandbox:
        sandbox = self.get_sandbox_or_404(db, sandbox_id)
        sandbox.last_heartbeat_at = utc_now()
        if sandbox.status in {
            SandboxStatus.PROVISIONING.value,
            SandboxStatus.STOPPED.value,
        }:
            sandbox.status = SandboxStatus.RUNNING.value
        return sandbox

    def cleanup_stale_sandboxes(
        self,
        db: Session,
        *,
        stale_seconds: int = 600,
    ) -> Tuple[int, int]:
        threshold = utc_now() - timedelta(seconds=stale_seconds)
        sandboxes = (
            db.query(Sandbox)
            .filter(
                Sandbox.status.in_(
                    [SandboxStatus.PROVISIONING.value, SandboxStatus.RUNNING.value]
                ),
                or_(Sandbox.last_heartbeat_at.is_(None), Sandbox.last_heartbeat_at < threshold),
            )
            .all()
        )

        terminated = 0
        for sandbox in sandboxes:
            if self._terminate_sandbox_in_db(
                db,
                sandbox=sandbox,
                reason="cleanup_stale",
            ):
                terminated += 1

        return len(sandboxes), terminated

    def terminate_sandbox(
        self,
        db: Session,
        *,
        sandbox_id: str,
        reason: str,
        actor_user_id: Optional[int] = None,
    ) -> bool:
        sandbox = self.get_sandbox_or_404(db, sandbox_id)
        return self._terminate_sandbox_in_db(
            db,
            sandbox=sandbox,
            reason=reason,
            actor_user_id=actor_user_id,
        )

    # ---------------------------------------------------------------------
    # Runtime progress + completion detection
    # ---------------------------------------------------------------------

    def record_solve_start(
        self,
        db: Session,
        *,
        session_public_id: str,
        user_id: int,
        solve_id: str,
        run_ids: Iterable[str],
    ) -> None:
        runtime, session, sandbox = self._load_runtime_bundle(
            db,
            session_public_id=session_public_id,
        )
        if not runtime or not session or not sandbox:
            return

        runtime.status = SessionRuntimeStatus.RUNNING.value
        metadata = runtime.runtime_metadata or {}
        metadata["last_solve"] = {
            "solve_id": solve_id,
            "run_ids": list(run_ids),
            "started_at": utc_now().isoformat(),
        }
        runtime.runtime_metadata = metadata

        self._record_audit_event(
            db,
            event_name=SessionAuditEventName.SOLVE_START.value,
            user_id=user_id,
            session_id=session.id,
            sandbox_id=sandbox.id,
            runtime_id=runtime.id,
            payload={"solve_id": solve_id, "run_ids": list(run_ids)},
        )

        self.cache_store.append_event(
            session_id=session.session_id,
            sandbox_id=sandbox.id,
            runtime_id=runtime.runtime_id,
            identity_key=sandbox.identity_key,
            event_name=SessionAuditEventName.SOLVE_START.value,
            payload={"solve_id": solve_id, "run_ids": list(run_ids)},
        )

    def mark_issue_created(
        self,
        db: Session,
        *,
        session_public_id: str,
        user_id: int,
        issue_url: str,
        issue_number: Optional[int],
    ) -> None:
        runtime, session, sandbox = self._load_runtime_bundle(
            db,
            session_public_id=session_public_id,
        )
        if not runtime or not session or not sandbox:
            return

        runtime.completion_issue_created = True

        metadata = runtime.runtime_metadata or {}
        metadata["github_issue"] = {
            "issue_url": issue_url,
            "issue_number": issue_number,
            "recorded_at": utc_now().isoformat(),
        }
        runtime.runtime_metadata = metadata

        self._record_audit_event(
            db,
            event_name=SessionAuditEventName.GITHUB_ISSUE_CREATE.value,
            user_id=user_id,
            session_id=session.id,
            sandbox_id=sandbox.id,
            runtime_id=runtime.id,
            payload={
                "issue_url": issue_url,
                "issue_number": issue_number,
            },
        )

        self.cache_store.append_event(
            session_id=session.session_id,
            sandbox_id=sandbox.id,
            runtime_id=runtime.runtime_id,
            identity_key=sandbox.identity_key,
            event_name=SessionAuditEventName.GITHUB_ISSUE_CREATE.value,
            payload={
                "issue_url": issue_url,
                "issue_number": issue_number,
            },
        )

        github_refs: Dict[str, Any] = {"issue_url": issue_url}
        if issue_number is not None:
            github_refs["issue_number"] = issue_number

        self.cache_store.merge_github_refs(
            session_id=session.session_id,
            sandbox_id=sandbox.id,
            runtime_id=runtime.runtime_id,
            identity_key=sandbox.identity_key,
            refs=github_refs,
        )

    def mark_pr_created(
        self,
        db: Session,
        *,
        session_db_id: Optional[int],
        session_public_id: Optional[str],
        user_id: Optional[int],
        pr_url: str,
        pr_number: Optional[int],
    ) -> None:
        runtime, session, sandbox = self._load_runtime_bundle(
            db,
            session_db_id=session_db_id,
            session_public_id=session_public_id,
        )
        if not runtime or not session or not sandbox:
            return

        runtime.completion_pr_created = True

        metadata = runtime.runtime_metadata or {}
        metadata["pull_request"] = {
            "pr_url": pr_url,
            "pr_number": pr_number,
            "recorded_at": utc_now().isoformat(),
        }
        runtime.runtime_metadata = metadata

        self._record_audit_event(
            db,
            event_name=SessionAuditEventName.PR_CREATE.value,
            user_id=user_id,
            session_id=session.id,
            sandbox_id=sandbox.id,
            runtime_id=runtime.id,
            payload={
                "pr_url": pr_url,
                "pr_number": pr_number,
            },
        )

        self.cache_store.append_event(
            session_id=session.session_id,
            sandbox_id=sandbox.id,
            runtime_id=runtime.runtime_id,
            identity_key=sandbox.identity_key,
            event_name=SessionAuditEventName.PR_CREATE.value,
            payload={
                "pr_url": pr_url,
                "pr_number": pr_number,
            },
        )

        github_refs: Dict[str, Any] = {"pr_url": pr_url}
        if pr_number is not None:
            github_refs["pr_number"] = pr_number

        self.cache_store.merge_github_refs(
            session_id=session.session_id,
            sandbox_id=sandbox.id,
            runtime_id=runtime.runtime_id,
            identity_key=sandbox.identity_key,
            refs=github_refs,
        )

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    def _load_runtime_bundle(
        self,
        db: Session,
        *,
        session_db_id: Optional[int] = None,
        session_public_id: Optional[str] = None,
    ) -> Tuple[Optional[SessionRuntime], Optional[ChatSession], Optional[Sandbox]]:
        session: Optional[ChatSession] = None
        if session_db_id is not None:
            session = db.query(ChatSession).filter(ChatSession.id == session_db_id).first()
        elif session_public_id:
            session = (
                db.query(ChatSession)
                .filter(ChatSession.session_id == session_public_id)
                .first()
            )

        if not session:
            return None, None, None

        runtime = self._get_latest_runtime(db, session_id=session.id)
        if not runtime or not runtime.sandbox_id:
            return None, session, None

        sandbox = db.query(Sandbox).filter(Sandbox.id == runtime.sandbox_id).first()
        return runtime, session, sandbox

    def _get_latest_runtime(
        self,
        db: Session,
        *,
        session_id: Optional[int] = None,
        sandbox_id: Optional[str] = None,
    ) -> Optional[SessionRuntime]:
        query = db.query(SessionRuntime)
        if session_id is not None:
            query = query.filter(SessionRuntime.session_id == session_id)
        if sandbox_id is not None:
            query = query.filter(SessionRuntime.sandbox_id == sandbox_id)
        return query.order_by(SessionRuntime.id.desc()).first()

    async def finalize_session_execution(
        self,
        db: Session,
        *,
        session: ChatSession,
        reason: str,
        execution_status: str,
        execution_id: Optional[str] = None,
        artifact_source_paths: Optional[Iterable[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        runtime, session_obj, sandbox = self._load_runtime_bundle(
            db,
            session_db_id=session.id,
        )
        if not runtime or not session_obj or not sandbox:
            return None

        runtime.completed_at = runtime.completed_at or utc_now()
        runtime.completion_reason = reason
        runtime.completion_detected = execution_status == "complete"

        trajectory_refs = self._collect_trajectory_refs(db, session_id=session_obj.id)
        if trajectory_refs:
            self.cache_store.merge_trajectory_refs(
                session_id=session_obj.session_id,
                sandbox_id=sandbox.id,
                runtime_id=runtime.runtime_id,
                identity_key=sandbox.identity_key,
                refs=trajectory_refs,
            )

        runtime_summary = {
            "status": execution_status,
            "execution_id": execution_id,
            "issue_created": bool(runtime.completion_issue_created),
            "pr_created": bool(runtime.completion_pr_created),
            "started_at": runtime.started_at.isoformat() if runtime.started_at else None,
            "completed_at": runtime.completed_at.isoformat() if runtime.completed_at else None,
        }

        export_info: Optional[Dict[str, Any]] = None
        source_paths_list = [str(path).strip() for path in (artifact_source_paths or []) if str(path).strip()]
        if (
            sandbox.status != SandboxStatus.TERMINATED.value
            and sandbox.tunnel_url
            and source_paths_list
        ):
            try:
                export_info = await self.cache_store.download_and_export_bundle(
                    tunnel_url=sandbox.tunnel_url,
                    session_public_id=session_obj.session_id,
                    runtime_id=runtime.runtime_id,
                    sandbox_id=sandbox.id,
                    identity_key=sandbox.identity_key,
                    workflow_name=execution_id or "mode-workflow",
                    archive_name="sandbox-workflow.tar.gz",
                    source_paths=source_paths_list,
                    runtime_summary=runtime_summary,
                    cwd=session.runtime_workspace_path,
                    env={"WORKSPACE_PATH": session.runtime_workspace_path or "/workspace/repo"},
                    object_store={
                        "provider": "s3",
                        "key": self._artifact_key(session=session_obj, sandbox=sandbox),
                        "etag": None,
                    },
                )
            except Exception as exc:
                metadata = runtime.runtime_metadata or {}
                metadata["artifact_export_error"] = str(exc)
                runtime.runtime_metadata = metadata

        if export_info:
            artifact = SessionArtifact(
                session_id=session_obj.id,
                runtime_id=runtime.id,
                artifact_key=self._artifact_key(session=session_obj, sandbox=sandbox),
                artifact_type="sandbox_bundle",
                cache_manifest_path=export_info["metadata"]["cache_manifest_path"],
                bundle_path=export_info["bundle_path"],
                checksum_sha256=export_info["bundle_sha256"],
                object_etag=None,
                byte_size=export_info["bundle_size"],
                artifact_metadata=export_info["metadata"],
                exported_at=utc_now(),
            )
            db.add(artifact)

        self._terminate_sandbox_in_db(
            db,
            sandbox=sandbox,
            reason=reason,
        )

        if not export_info:
            return None

        return {
            "bundle_path": export_info["bundle_path"],
            "metadata_path": export_info["metadata_path"],
            "checksum_sha256": export_info["bundle_sha256"],
            "byte_size": export_info["bundle_size"],
        }

    def _finalize_on_completion(
        self,
        db: Session,
        *,
        runtime: SessionRuntime,
        session: ChatSession,
        sandbox: Sandbox,
    ) -> None:
        if runtime.completion_issue_created and runtime.completion_pr_created:
            runtime.completion_detected = True
            runtime.completion_reason = "issue_and_pr_created"
            runtime.completed_at = runtime.completed_at or utc_now()

    def _collect_trajectory_refs(self, db: Session, *, session_id: int) -> list[Dict[str, Any]]:
        refs: list[Dict[str, Any]] = []

        runs = (
            db.query(SolveRun)
            .join(Solve, Solve.id == SolveRun.solve_id)
            .filter(Solve.session_id == session_id)
            .all()
        )

        for run in runs:
            trajectory_data = run.trajectory_data
            if not isinstance(trajectory_data, dict):
                continue

            local_path = trajectory_data.get("local_path")
            if not local_path:
                continue

            ref = self.cache_store.build_trajectory_ref(str(local_path))
            if ref:
                refs.append(ref)

        return refs

    def _terminate_sandbox_in_db(
        self,
        db: Session,
        *,
        sandbox: Sandbox,
        reason: str,
        actor_user_id: Optional[int] = None,
    ) -> bool:
        if sandbox.status == SandboxStatus.TERMINATED.value:
            return False

        sandbox.status = SandboxStatus.TERMINATED.value
        sandbox.terminated_at = utc_now()
        sandbox.active_session_id = None

        flags = get_realtime_feature_flags()
        if flags.modal_provisioning_enabled:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(get_modal_registry().terminate_and_remove(sandbox.id))
            except RuntimeError:
                pass

        runtimes = (
            db.query(SessionRuntime)
            .filter(SessionRuntime.sandbox_id == sandbox.id)
            .all()
        )

        for runtime in runtimes:
            if runtime.status != SessionRuntimeStatus.TERMINATED.value:
                runtime.status = SessionRuntimeStatus.TERMINATED.value
                runtime.completed_at = runtime.completed_at or utc_now()

            session = db.query(ChatSession).filter(ChatSession.id == runtime.session_id).first()
            if session:
                self.cache_store.append_event(
                    session_id=session.session_id,
                    sandbox_id=sandbox.id,
                    runtime_id=runtime.runtime_id,
                    identity_key=sandbox.identity_key,
                    event_name=SessionAuditEventName.SANDBOX_TERMINATE.value,
                    payload={"reason": reason},
                )

            self._record_audit_event(
                db,
                event_name=SessionAuditEventName.SANDBOX_TERMINATE.value,
                user_id=actor_user_id,
                session_id=runtime.session_id,
                sandbox_id=sandbox.id,
                runtime_id=runtime.id,
                payload={"reason": reason},
            )

        self._stop_probe_if_possible(sandbox.id)
        return True

    def _record_audit_event(
        self,
        db: Session,
        *,
        event_name: str,
        user_id: Optional[int],
        session_id: Optional[int],
        sandbox_id: Optional[str],
        runtime_id: Optional[int],
        payload: Optional[Dict[str, Any]],
    ) -> None:
        db.add(
            SessionAuditEvent(
                event_id=self._next_id("evt"),
                event_name=event_name,
                user_id=user_id,
                session_id=session_id,
                sandbox_id=sandbox_id,
                runtime_id=runtime_id,
                event_payload=payload or {},
            )
        )

    def _start_probe_if_possible(self, *, sandbox_id: str, tunnel_url: Optional[str]) -> None:
        if not tunnel_url:
            return

        async def _probe_callback(current_sandbox_id: str, healthy: bool, error_text: Optional[str]) -> None:
            db = SessionLocal()
            try:
                sandbox = (
                    db.query(Sandbox).filter(Sandbox.id == current_sandbox_id).first()
                )
                if not sandbox or sandbox.status == SandboxStatus.TERMINATED.value:
                    return

                sandbox.last_heartbeat_at = utc_now()
                metadata = sandbox.lifecycle_metadata or {}
                metadata["last_probe_at"] = utc_now().isoformat()
                metadata["last_probe_healthy"] = healthy
                if error_text:
                    metadata["last_probe_error"] = error_text
                else:
                    metadata.pop("last_probe_error", None)

                sandbox.lifecycle_metadata = metadata
                if healthy:
                    if sandbox.status in {
                        SandboxStatus.PROVISIONING.value,
                        SandboxStatus.STOPPED.value,
                    }:
                        sandbox.status = SandboxStatus.RUNNING.value
                else:
                    if sandbox.status == SandboxStatus.RUNNING.value:
                        sandbox.status = SandboxStatus.STOPPED.value

                db.commit()
            finally:
                db.close()

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        loop.create_task(
            self.sandbox_manager.start_probe(
                sandbox_id=sandbox_id,
                tunnel_url=tunnel_url,
                callback=_probe_callback,
            )
        )

    def _stop_probe_if_possible(self, sandbox_id: str) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.sandbox_manager.stop_probe(sandbox_id))

    def _artifact_key(self, *, session: ChatSession, sandbox: Sandbox) -> str:
        return (
            "session-artifacts/"
            f"{sandbox.org_slug}/{sandbox.repo_owner}/{sandbox.repo_name}/"
            f"{sandbox.environment}/{session.session_id}.tar.gz"
        )

    @staticmethod
    def _next_id(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:26]}"


_service_singleton: Optional[RealtimeLifecycleService] = None


def get_realtime_lifecycle_service() -> RealtimeLifecycleService:
    global _service_singleton
    if _service_singleton is None:
        _service_singleton = RealtimeLifecycleService()
    return _service_singleton


# ---------------------------------------------------------------------------
# Sandbox tunnel probes and git bootstrap
# (consolidated from sandbox_manager.py)
# ---------------------------------------------------------------------------

ProbeCallback = Callable[[str, bool, Optional[str]], Awaitable[None]]


class SandboxManager:
    """Manages tunnel probes plus git bootstrap for sandbox identities."""

    def __init__(self):
        self.probe_interval_seconds = int(os.getenv("SANDBOX_LIVENESS_INTERVAL_SECONDS", "10"))
        self.probe_timeout_seconds = float(os.getenv("SANDBOX_LIVENESS_TIMEOUT_SECONDS", "3"))
        self.git_fetch_interval_seconds = int(os.getenv("SANDBOX_GIT_FETCH_INTERVAL_SECONDS", "300"))

        self.tunnel_template = os.getenv(
            "SANDBOX_TUNNEL_TEMPLATE",
            "http://localhost:8100/{sandbox_id}",
        )

        self.repo_root = Path(os.getenv("SANDBOX_GIT_ROOT", "/home/yudai/.cache/repos"))
        self.repo_root.mkdir(parents=True, exist_ok=True)

        self._probe_tasks: Dict[str, asyncio.Task] = {}

    def build_tunnel_url(self, sandbox_id: str) -> str:
        template = self.tunnel_template
        if "{sandbox_id}" in template:
            return template.format(sandbox_id=sandbox_id)
        return template.rstrip("/")

    def _identity_repo_dir(self, identity_key: str) -> Path:
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "-", identity_key).strip("-")
        safe = safe or "sandbox"
        return self.repo_root / safe

    def _is_github_https_repo(self, repo_url: Optional[str]) -> bool:
        return bool(repo_url and repo_url.startswith("https://github.com/"))

    def _git_auth_args(
        self,
        *,
        repo_url: Optional[str],
        github_token: Optional[str],
    ) -> list[str]:
        if not github_token or not self._is_github_https_repo(repo_url):
            return []

        encoded = base64.b64encode(f"x-access-token:{github_token}".encode("utf-8")).decode("ascii")
        return [
            "-c",
            f"http.https://github.com/.extraheader=AUTHORIZATION: basic {encoded}",
        ]

    def _describe_git_command(self, cmd: list[str]) -> str:
        if "clone" in cmd:
            return "git clone"
        if "fetch" in cmd:
            return "git fetch"
        return "git command"

    def ensure_git_bootstrap(
        self,
        *,
        identity_key: str,
        repo_url: Optional[str],
        repo_branch: Optional[str],
        github_token: Optional[str] = None,
    ) -> Dict[str, object]:
        """Clone repository once for this sandbox identity and fetch periodically."""
        if not repo_url:
            return {"status": "skipped", "reason": "repo_url_missing"}

        repo_dir = self._identity_repo_dir(identity_key)
        marker_file = repo_dir / ".last_fetch"
        branch = (repo_branch or "main").strip() or "main"

        if not repo_dir.exists():
            repo_dir.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                "git",
                *self._git_auth_args(repo_url=repo_url, github_token=github_token),
                "clone", "--branch", branch, "--single-branch", repo_url, str(repo_dir),
            ]
            self._run_git_command(cmd)
            marker_file.write_text(str(int(time.time())), encoding="utf-8")
            return {"status": "cloned", "path": str(repo_dir), "branch": branch}

        now = int(time.time())
        last_fetch = 0
        if marker_file.exists():
            try:
                last_fetch = int(marker_file.read_text(encoding="utf-8").strip() or "0")
            except ValueError:
                last_fetch = 0

        elapsed = now - last_fetch
        if elapsed >= self.git_fetch_interval_seconds:
            self._run_git_command([
                "git",
                *self._git_auth_args(repo_url=repo_url, github_token=github_token),
                "-C", str(repo_dir), "fetch", "--all", "--prune",
            ])
            marker_file.write_text(str(now), encoding="utf-8")
            return {"status": "fetched", "path": str(repo_dir), "branch": branch, "elapsed_seconds": elapsed}

        return {"status": "reused", "path": str(repo_dir), "branch": branch, "elapsed_seconds": elapsed}

    def _run_git_command(self, cmd: list[str]) -> None:
        result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            stderr_tail = (result.stderr or "")[-2000:]
            raise RuntimeError(f"{self._describe_git_command(cmd)} failed: {stderr_tail}")

    async def start_probe(
        self,
        *,
        sandbox_id: str,
        tunnel_url: str,
        callback: ProbeCallback,
    ) -> None:
        """Start a recurring liveness probe against the sandbox tunnel."""
        existing = self._probe_tasks.get(sandbox_id)
        if existing and not existing.done():
            return

        async def _probe_loop() -> None:
            health_url = f"{tunnel_url.rstrip('/')}/healthz"
            while True:
                healthy = False
                error_text: Optional[str] = None
                try:
                    async with httpx.AsyncClient(timeout=self.probe_timeout_seconds) as client:
                        response = await client.get(health_url)
                    healthy = response.status_code == 200
                    if not healthy:
                        error_text = f"probe_status_{response.status_code}"
                except Exception as exc:  # pragma: no cover - defensive
                    healthy = False
                    error_text = str(exc)

                try:
                    await callback(sandbox_id, healthy, error_text)
                except Exception as callback_error:  # pragma: no cover
                    logger.warning("Probe callback failed for sandbox %s: %s", sandbox_id, callback_error)

                await asyncio.sleep(self.probe_interval_seconds)

        task = asyncio.create_task(_probe_loop(), name=f"sandbox-probe-{sandbox_id}")
        self._probe_tasks[sandbox_id] = task

    async def stop_probe(self, sandbox_id: str) -> None:
        task = self._probe_tasks.pop(sandbox_id, None)
        if not task:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# Controller-side exec broker
# (consolidated from sandbox_exec_broker.py)
# ---------------------------------------------------------------------------

SandboxEventCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class SandboxExecBroker:
    """Sends exec.start/stdin/cancel to sandbox internal WS and streams events back."""

    def __init__(self, lifecycle: Optional[RealtimeLifecycleService] = None) -> None:
        self.lifecycle = lifecycle or get_realtime_lifecycle_service()

    def _resolve_runtime(self, db: Session, session: ChatSession) -> tuple[Sandbox, str]:
        runtime = self.lifecycle._get_latest_runtime(db, session_id=session.id)
        if not runtime or not runtime.sandbox_id:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_UNAVAILABLE)

        sandbox = self.lifecycle.get_sandbox_or_404(db, runtime.sandbox_id)
        if sandbox.status == SandboxStatus.TERMINATED.value:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_TERMINATED)
        if not sandbox.tunnel_url:
            raise as_http_exception(RealtimeErrorCode.TUNNEL_UNAVAILABLE)

        return sandbox, sandbox.tunnel_url

    async def run_command(
        self,
        db: Session,
        *,
        session: ChatSession,
        command: str,
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
        timeout_seconds: int = 1800,
        on_event: Optional[SandboxEventCallback] = None,
    ) -> Dict[str, Any]:
        sandbox, tunnel_url = self._resolve_runtime(db, session)
        result = await run_sandbox_command(
            tunnel_url=tunnel_url,
            session_public_id=session.session_id,
            command=command,
            cwd=cwd,
            env=env,
            timeout_seconds=timeout_seconds,
            on_event=on_event,
        )
        return {
            "sandbox_id": sandbox.id,
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_ms": result.duration_ms,
        }


_exec_broker_singleton: Optional[SandboxExecBroker] = None


def get_sandbox_exec_broker() -> SandboxExecBroker:
    global _exec_broker_singleton
    if _exec_broker_singleton is None:
        _exec_broker_singleton = SandboxExecBroker()
    return _exec_broker_singleton
