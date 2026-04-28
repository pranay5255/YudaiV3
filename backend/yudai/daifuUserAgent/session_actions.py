"""Shared session actions for REST routes and unified websocket commands."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional
import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from yudai.config import get_sandbox_config
from yudai.config.realtime_flags import get_realtime_feature_flags
from yudai.models import (
    AuthToken,
    ChatMessage,
    ChatSession,
    ConversationRequest,
    ConversationResponse,
    ExecutionStatusResponse,
    SessionMode,
    SessionArtifact,
    SessionModeStatus,
    User,
    UserQuestion,
    UserQuestionStatus,
    WorkflowContextUpdateRequest,
    WorkflowIssueRequest,
    WorkflowResponse,
)
from yudai.realtime.lifecycle import get_realtime_lifecycle_service
from yudai.realtime.mode_orchestrator import (
    ExecutionConflictError,
    ExecutionNotFoundError,
    get_session_execution_orchestrator,
)
from yudai.realtime.schemas import RuntimeEnsureRequest, RuntimeResponse
from yudai.realtime.ws_protocol import WSMessageType, get_ws_hub
from yudai.utils import utc_now

from .mode_tools import get_daifu_mode_tool_service
from .session_service import SessionService


WORKFLOW_METADATA_KEY = "workflow"
RUNTIME_STATUS_NOT_PROVISIONED = "not_provisioned"
ChatChunkCallback = Callable[[str], Awaitable[None]]


def _clean_string_list(raw: Any, *, limit: int = 30) -> List[str]:
    if not isinstance(raw, list):
        return []
    values: List[str] = []
    for item in raw:
        text = str(item or "").strip()
        if text and text not in values:
            values.append(text[:500])
        if len(values) >= limit:
            break
    return values


def normalize_github_issue_labels(labels: Any) -> List[str]:
    if not isinstance(labels, list):
        return []
    normalized: List[str] = []
    for label in labels:
        if isinstance(label, str):
            name = label.strip()
        elif isinstance(label, dict):
            name = str(label.get("name") or label.get("label") or "").strip()
        else:
            name = ""
        if name and name not in normalized:
            normalized.append(name)
    return normalized


def get_workflow_metadata(session: ChatSession) -> Dict[str, Any]:
    metadata = session.mode_metadata if isinstance(session.mode_metadata, dict) else {}
    workflow = metadata.get(WORKFLOW_METADATA_KEY)
    return dict(workflow) if isinstance(workflow, dict) else {}


def set_workflow_metadata(session: ChatSession, workflow: Dict[str, Any]) -> None:
    metadata = dict(session.mode_metadata or {})
    metadata[WORKFLOW_METADATA_KEY] = workflow
    session.mode_metadata = metadata
    flag_modified(session, "mode_metadata")


def _build_pr_readiness(
    *,
    session: ChatSession,
    execution: Any,
    selected_issue: Optional[Dict[str, Any]],
    user_context: Dict[str, Any],
    stage_results: Dict[str, Any],
    pending_questions: List[Any],
) -> Dict[str, Any]:
    checks = {
        "issue_selected": bool(selected_issue or session.architect_issue_url),
        "affected_systems_recorded": bool(user_context.get("affected_systems")),
        "clarifications_answered": not pending_questions,
        "architect_complete": bool(session.architect_completed_at),
        "tester_complete": bool(session.tester_completed_at),
        "coder_complete": bool(session.coder_completed_at),
        "pr_created": bool(session.coder_pr_url),
    }
    status_value = (execution.status or session.mode_status or "").lower()
    if session.coder_pr_url:
        readiness = "ready"
    elif pending_questions or execution.waiting_for_input:
        readiness = "needs_input"
    elif status_value in {"running", "provisioning", "pending"}:
        readiness = "running"
    elif status_value in {"failed", "cancelled", "error"}:
        readiness = status_value
    elif checks["issue_selected"]:
        readiness = "drafting"
    else:
        readiness = "not_started"

    mode_metadata = session.mode_metadata if isinstance(session.mode_metadata, dict) else {}
    return {
        "status": readiness,
        "checks": checks,
        "issue_number": session.architect_issue_number
        or (selected_issue or {}).get("number"),
        "issue_url": session.architect_issue_url
        or (selected_issue or {}).get("html_url"),
        "pr_number": session.coder_pr_number,
        "pr_url": session.coder_pr_url,
        "affected_systems": user_context.get("affected_systems") or [],
        "test_branch": mode_metadata.get("tester_test_branch")
        or (stage_results.get("tester") or {}).get("test_branch"),
    }


def _to_runtime_response(runtime) -> RuntimeResponse:
    metadata = runtime.runtime_metadata if isinstance(runtime.runtime_metadata, dict) else {}
    return RuntimeResponse(
        runtime_id=runtime.runtime_id,
        sandbox_id=runtime.sandbox_id or "",
        identity_key=(metadata.get("identity_key") if isinstance(metadata, dict) else "")
        or "",
        status=runtime.status,
        tunnel_url=None,
        token_ttl_seconds=3600,
        tunnel_expires_at=runtime.tunnel_expires_at,
        completion_issue_created=runtime.completion_issue_created,
        completion_pr_created=runtime.completion_pr_created,
        completion_detected=runtime.completion_detected,
        metadata=metadata,
    )


def _not_provisioned_runtime_response() -> RuntimeResponse:
    return RuntimeResponse(
        status=RUNTIME_STATUS_NOT_PROVISIONED,
        completion_issue_created=False,
        completion_pr_created=False,
        completion_detected=False,
        metadata={},
    )


def _get_user_github_token(db: Session, user_id: int) -> Optional[str]:
    auth_token = (
        db.query(AuthToken)
        .filter(
            AuthToken.user_id == user_id,
            AuthToken.is_active.is_(True),
        )
        .order_by(AuthToken.created_at.desc())
        .first()
    )
    return auth_token.access_token if auth_token else None


def _next_mode_for_session(session: ChatSession) -> str:
    if not session.architect_completed_at:
        return SessionMode.ARCHITECT.value
    if not session.tester_completed_at:
        return SessionMode.TESTER.value
    if not session.coder_completed_at:
        return SessionMode.CODER.value
    return SessionMode.COMPLETE.value


def _build_mode_plan(mode: str, objective: str) -> List[str]:
    if mode == SessionMode.ARCHITECT.value:
        return [
            "Analyze the user objective and synthesize a detailed implementation issue.",
            f"Objective: {objective}",
            "Persist issue metadata and emit mode/state websocket events.",
        ]
    if mode == SessionMode.TESTER.value:
        return [
            "Inspect repository test tooling and generate/run tests in sandbox.",
            "Stream sandbox stdout/stderr/exit to controller unified websocket.",
        ]
    if mode == SessionMode.CODER.value:
        return [
            "Implement changes in sandbox workspace.",
            "Run tests and publish PR metadata to lifecycle completion tracker.",
        ]
    return ["Workflow already complete."]


def _parse_datetime_value(raw: Any) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _artifact_payload_from_row(artifact: SessionArtifact) -> Dict[str, Any]:
    metadata = artifact.artifact_metadata if isinstance(artifact.artifact_metadata, dict) else {}
    sandbox_bundle = metadata.get("sandbox_bundle") if isinstance(metadata.get("sandbox_bundle"), dict) else {}
    return {
        "bundle_path": artifact.bundle_path,
        "metadata_path": sandbox_bundle.get("metadata_path"),
        "checksum_sha256": artifact.checksum_sha256,
        "byte_size": artifact.byte_size,
    }


def _build_lightweight_execution_status(
    db: Session,
    session: ChatSession,
) -> ExecutionStatusResponse:
    metadata = session.mode_metadata if isinstance(session.mode_metadata, dict) else {}
    active_execution = metadata.get("active_execution")
    if not isinstance(active_execution, dict):
        active_execution = {}
    latest_artifact = (
        db.query(SessionArtifact)
        .filter(SessionArtifact.session_id == session.id)
        .order_by(SessionArtifact.id.desc())
        .first()
    )
    artifact_payload = active_execution.get("artifact")
    if artifact_payload is None and latest_artifact:
        artifact_payload = _artifact_payload_from_row(latest_artifact)

    next_mode = _next_mode_for_session(session)
    objective_for_plan = str(active_execution.get("objective_with_context") or "")
    return ExecutionStatusResponse(
        execution_id=active_execution.get("execution_id"),
        session_id=session.session_id,
        mode=str(active_execution.get("mode") or session.current_mode or next_mode),
        status=str(active_execution.get("status") or session.mode_status or SessionModeStatus.IDLE.value),
        plan=list(active_execution.get("plan") or _build_mode_plan(next_mode, objective_for_plan)),
        started_at=_parse_datetime_value(active_execution.get("started_at")),
        completed_at=_parse_datetime_value(active_execution.get("completed_at")),
        cancel_requested=bool(active_execution.get("cancel_requested")),
        waiting_for_input=session.mode_status == SessionModeStatus.WAITING_FOR_INPUT.value,
        current_mode_execution_id=active_execution.get("current_mode_execution_id"),
        artifact=artifact_payload,
        detail=active_execution.get("detail"),
    )


class SessionActionService:
    """Business actions shared by HTTP compatibility routes and WS commands."""

    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def ensure_owned_session(self, session_id: str) -> ChatSession:
        return SessionService.ensure_owned_session(self.db, self.user.id, session_id)

    async def stream_chat_message(
        self,
        *,
        session_id: str,
        message: str,
        on_chunk: ChatChunkCallback,
        repository: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        content = message.strip()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing chat content",
            )

        from .ChatOps import ChatOps

        result = await ChatOps(self.db).process_chat_message_stream(
            session_id=session_id,
            user_id=self.user.id,
            message_text=content,
            on_chunk=on_chunk,
            repository=repository,
        )
        return {
            "session_id": session_id,
            "reply": str(result.get("reply") or ""),
            "message_id": str(result.get("message_id") or ""),
            "processing_time": result.get("processing_time"),
        }

    async def conversation(self, session_id: str, request: ConversationRequest) -> ConversationResponse:
        db_session = self.ensure_owned_session(session_id)

        content = request.message.strip()
        lower_content = content.lower()
        follow_up_question = None

        user_message = ChatMessage(
            session_id=db_session.id,
            message_id=f"msg_{uuid.uuid4().hex[:12]}",
            message_text=content,
            sender_type="user",
            role="user",
            tokens=0,
        )
        self.db.add(user_message)
        db_session.total_messages = (db_session.total_messages or 0) + 1

        ambiguous_terms = ("auth", "authentication", "api", "database", "testing")
        if not request.selected_option_ids and any(
            term in lower_content for term in ambiguous_terms
        ):
            question_options = [
                {"id": "behavior", "label": "Behavioral change first"},
                {"id": "tests", "label": "Test coverage first"},
                {"id": "refactor", "label": "Refactor and structure first"},
            ]
            question = UserQuestion(
                question_id=f"q_{uuid.uuid4().hex[:10]}",
                session_id=db_session.id,
                user_id=self.user.id,
                mode=_next_mode_for_session(db_session),
                question_text="Choose the primary implementation focus for this run.",
                options=question_options,
                multi_select=False,
                status=UserQuestionStatus.PENDING.value,
                question_metadata={"origin": "conversation_ambiguity"},
            )
            self.db.add(question)
            follow_up_question = {
                "question_id": question.question_id,
                "prompt": question.question_text,
                "multi_select": question.multi_select,
                "options": question_options,
            }
            db_session.mode_status = SessionModeStatus.WAITING_FOR_INPUT.value
        else:
            db_session.mode_status = SessionModeStatus.IDLE.value

        reply = (
            "Captured your request. The execution pipeline remains fixed "
            "at Architect -> Tester -> Coder and will continue from the next pending mode."
        )
        assistant_message = ChatMessage(
            session_id=db_session.id,
            message_id=f"msg_{uuid.uuid4().hex[:12]}",
            message_text=reply,
            sender_type="assistant",
            role="assistant",
            tokens=0,
        )
        self.db.add(assistant_message)
        db_session.total_messages = (db_session.total_messages or 0) + 1
        db_session.last_activity = utc_now()
        db_session.mode_updated_at = utc_now()
        self.db.commit()

        ws_hub = get_ws_hub()
        await ws_hub.send_to_session(
            session_id,
            WSMessageType.LLM_STREAM,
            {"stream": "llm", "text": reply, "final": True},
        )
        if follow_up_question:
            await ws_hub.send_to_session(
                session_id,
                WSMessageType.AGENT_QUESTION,
                {
                    "question_id": follow_up_question["question_id"],
                    "question_text": follow_up_question["prompt"],
                    "multi_select": bool(follow_up_question["multi_select"]),
                    "options": follow_up_question["options"],
                },
            )

        return ConversationResponse(
            session_id=session_id,
            reply=reply,
            current_mode=db_session.current_mode,
            mode_status=db_session.mode_status,
            follow_up_question=follow_up_question,
        )

    def build_workflow_response(self, db_session: ChatSession) -> WorkflowResponse:
        context = SessionService.get_context(self.db, db_session)
        execution = _build_lightweight_execution_status(self.db, db_session)
        workflow = get_workflow_metadata(db_session)
        selected_issue = workflow.get("selected_issue")
        if not isinstance(selected_issue, dict):
            selected_issue = None
        user_context = workflow.get("user_context")
        if not isinstance(user_context, dict):
            user_context = {}
        stage_results = workflow.get("stage_results")
        if not isinstance(stage_results, dict):
            stage_results = {}

        pending_questions = context.pending_questions or []
        pr_readiness = _build_pr_readiness(
            session=db_session,
            execution=execution,
            selected_issue=selected_issue,
            user_context=user_context,
            stage_results=stage_results,
            pending_questions=pending_questions,
        )

        return WorkflowResponse(
            session=context.session,
            execution=execution,
            selected_issue=selected_issue,
            user_context=user_context,
            stage_results=stage_results,
            pending_questions=pending_questions,
            pr_readiness=pr_readiness,
            artifact=execution.artifact,
        )

    def get_workflow(self, session_id: str) -> WorkflowResponse:
        return self.build_workflow_response(self.ensure_owned_session(session_id))

    def select_workflow_issue(
        self,
        session_id: str,
        request: WorkflowIssueRequest,
    ) -> WorkflowResponse:
        db_session = self.ensure_owned_session(session_id)
        workflow = get_workflow_metadata(db_session)
        issue_payload = request.model_dump(mode="json", exclude_none=True)
        issue_payload["labels"] = normalize_github_issue_labels(issue_payload.get("labels"))
        workflow["selected_issue"] = issue_payload
        workflow.setdefault("user_context", {})
        workflow.setdefault("stage_results", {})

        db_session.architect_issue_number = request.number
        if request.html_url:
            db_session.architect_issue_url = request.html_url
        db_session.mode_metadata = {
            **(db_session.mode_metadata or {}),
            "pending_resume_objective": (
                f"Resolve GitHub issue #{request.number}: {request.title}"
            ),
        }
        set_workflow_metadata(db_session, workflow)
        db_session.last_activity = utc_now()
        self.db.commit()
        self.db.refresh(db_session)
        return self.build_workflow_response(db_session)

    def update_workflow_context(
        self,
        session_id: str,
        request: WorkflowContextUpdateRequest,
    ) -> WorkflowResponse:
        db_session = self.ensure_owned_session(session_id)
        workflow = get_workflow_metadata(db_session)
        current_context = workflow.get("user_context")
        if not isinstance(current_context, dict):
            current_context = {}

        update = request.model_dump(exclude_none=True)
        if "affected_systems" in update:
            update["affected_systems"] = _clean_string_list(update["affected_systems"])
        current_context.update(update)
        workflow["user_context"] = current_context
        workflow.setdefault("stage_results", {})
        set_workflow_metadata(db_session, workflow)
        db_session.last_activity = utc_now()
        self.db.commit()
        self.db.refresh(db_session)
        return self.build_workflow_response(db_session)

    async def ensure_runtime(
        self,
        session_id: str,
        request: RuntimeEnsureRequest,
    ) -> RuntimeResponse:
        session_obj = self.ensure_owned_session(session_id)
        lifecycle = get_realtime_lifecycle_service()
        github_token = _get_user_github_token(self.db, self.user.id)

        envelope = await lifecycle.create_runtime_for_session(
            self.db,
            session=session_obj,
            user_id=self.user.id,
            org=request.org,
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            environment=request.environment,
            repo_branch=request.repo_branch,
            repo_url=request.repo_url
            or f"https://github.com/{request.repo_owner}/{request.repo_name}.git",
            github_token=github_token,
            env_inputs={
                "SESSION_PUBLIC_ID": session_obj.session_id,
                "WORKSPACE_PATH": session_obj.runtime_workspace_path
                or get_sandbox_config().workspace_path,
            },
        )

        runtime_metadata = envelope.runtime.runtime_metadata or {}
        runtime_metadata["identity_key"] = envelope.sandbox.identity_key
        envelope.runtime.runtime_metadata = runtime_metadata

        self.db.commit()
        self.db.refresh(envelope.runtime)

        response = _to_runtime_response(envelope.runtime)
        response.identity_key = envelope.sandbox.identity_key
        response.token_ttl_seconds = envelope.sandbox.tunnel_token_ttl_seconds or 3600
        return response

    def get_runtime(self, session_id: str) -> RuntimeResponse:
        session_obj = self.ensure_owned_session(session_id)
        lifecycle = get_realtime_lifecycle_service()
        runtime = lifecycle._get_latest_runtime(self.db, session_id=session_obj.id)
        if not runtime:
            return _not_provisioned_runtime_response()

        response = _to_runtime_response(runtime)
        sandbox = (
            lifecycle.get_sandbox_or_404(self.db, runtime.sandbox_id)
            if runtime.sandbox_id
            else None
        )
        if sandbox:
            response.identity_key = sandbox.identity_key
            response.token_ttl_seconds = sandbox.tunnel_token_ttl_seconds or 3600
        return response

    async def start_execution(
        self,
        session_id: str,
        *,
        objective: str,
        force_mode: Optional[str] = None,
    ) -> Any:
        realtime_flags = get_realtime_feature_flags()
        if not realtime_flags.mode_orchestrator_enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mode orchestrator is disabled by feature flags",
            )

        db_session = self.ensure_owned_session(session_id)
        next_mode = _next_mode_for_session(db_session)
        if next_mode == SessionMode.COMPLETE.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Session workflow already complete",
            )
        if force_mode and force_mode != next_mode:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Mode switching is server-controlled. Expected next mode "
                    f"'{next_mode}', got '{force_mode}'."
                ),
            )

        db_session.mode_metadata = {
            **(db_session.mode_metadata or {}),
            "pending_resume_objective": objective,
        }
        self.db.commit()

        try:
            return await get_session_execution_orchestrator().start_execution(
                self.db,
                session=db_session,
                user_id=self.user.id,
                objective=objective,
                force_mode=force_mode,
            )
        except ExecutionConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    async def start_stage_execution(
        self,
        session_id: str,
        *,
        tool_name: str,
        objective: str,
    ) -> Any:
        realtime_flags = get_realtime_feature_flags()
        if not realtime_flags.mode_orchestrator_enabled:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mode orchestrator is disabled by feature flags",
            )

        db_session = self.ensure_owned_session(session_id)
        mode_metadata = dict(db_session.mode_metadata or {})
        mode_metadata["pending_resume_objective"] = objective
        mode_metadata["pending_daifu_tool"] = tool_name
        db_session.mode_metadata = mode_metadata
        flag_modified(db_session, "mode_metadata")
        self.db.commit()

        try:
            return await get_daifu_mode_tool_service().run_stage_tool(
                self.db,
                session=db_session,
                user_id=self.user.id,
                tool_name=tool_name,
                objective=objective,
            )
        except ExecutionConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    def get_execution_status(self, session_id: str) -> Any:
        db_session = self.ensure_owned_session(session_id)
        return get_session_execution_orchestrator().get_execution_status(
            self.db,
            session=db_session,
        )

    async def cancel_execution(self, session_id: str) -> Dict[str, Any]:
        db_session = self.ensure_owned_session(session_id)
        try:
            payload = await get_session_execution_orchestrator().cancel_execution(
                self.db,
                session=db_session,
            )
        except ExecutionNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        return {
            "execution_id": payload.get("execution_id"),
            "session_id": session_id,
            "status": str(payload.get("status") or SessionModeStatus.CANCELLED.value),
            "message": "Execution cancelled",
        }

    async def answer_question(
        self,
        session_id: str,
        question_id: str,
        request: Any,
    ) -> Any:
        # Keep the existing thoroughly tested HTTP implementation as the single
        # behavior source until that larger flow is split out of session_routes.
        from . import session_routes

        return await session_routes.answer_session_question(
            session_id=session_id,
            question_id=question_id,
            request=request,
            db=self.db,
            current_user=self.user,
        )
