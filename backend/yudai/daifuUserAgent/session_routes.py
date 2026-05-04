#!/usr/bin/env python3
"""
Session Management Routes for DAifu Agent

This module provides FastAPI routes for session management,
including session creation, context management, messages, and issue workflows.

TODO: Complete Implementation Tasks
========================================

CRITICAL ISSUES:
1. LLM Service Integration
   - Chat endpoint uses ChatOps.process_chat_message() with LLMService.generate_response_with_stored_context()
   - Issue endpoints use IssueOps.create_issue_with_context() with LLMService.generate_response()
   - Add proper error handling for LLM service failures
   - Implement streaming responses for real-time chat

2. Frontend Integration (@Chat.tsx compatibility)
   - Ensure all API responses match frontend expectations
   - Implement proper error message formatting for UI display
   - Add real-time WebSocket support for chat updates
   - Support context card operations from frontend

3. Session Management Enhancements
   - Add session timeout and cleanup mechanisms
   - Implement session persistence across browser sessions
   - Add session export/import functionality
   - Implement session collaboration features

4. Database Optimization
   - Add proper indexing for all query operations
   - Implement database connection pooling
   - Add query result caching (Redis)
   - Optimize bulk operations for messages and context cards



7. Authentication & Authorization
   - Ensure all endpoints properly validate user access
   - Add role-based access control where needed
   - Implement proper session token validation
   - Add audit logging for sensitive operations

13. Session Context Management
    - Implement proper context window management
    - Add context relevance scoring
    - Support multiple context sources (chat, upload, external)
    - Implement context persistence and retrieval

14. Message Management
    - Add message search and filtering capabilities
    - Implement message threading and conversation management
    - Add message export/import functionality
    - Support message attachments and rich content

17. Deployment & Configuration
    - Add environment-specific configuration
    - Implement proper logging configuration
    - Add health checks and startup validation
    - Support containerized deployment

"""

import json
import logging

# Import chat functionality from chat_api
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from yudai.auth.github_oauth import get_current_user
from yudai.config.realtime_flags import get_realtime_feature_flags
from yudai.db.database import get_db
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from yudai.realtime.lifecycle import get_realtime_lifecycle_service
from yudai.realtime.mode_orchestrator import (
    ExecutionConflictError,
    ExecutionNotFoundError,
    get_session_execution_orchestrator,
)
from yudai.realtime.ws_protocol import get_ws_hub
from yudai.realtime.ws_protocol import WSMessageType

from yudai.models import (
    AgentExecution,
    ChatMessage,
    ChatSession,
    ContextCard,
    SessionMode,
    SessionModeStatus,
    User,
    UserIssue,
    UserQuestion,
    UserQuestionStatus,
)
from yudai.types import (
    AIModelResponse,
    APIError,
    AnswerQuestionRequest,
    AnswerQuestionResponse,
    AskQuestionRequest,
    AskQuestionResponse,
    CancelExecutionResponse,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ContextCardResponse,
    ConversationRequest,
    ConversationResponse,
    CreateContextCardRequest,
    CreateGitHubIssueResponse,
    CreateGitHubIssueToolRequest,
    CreateSessionRequest,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatusResponse,
    FrontendBrowserCheckToolRequest,
    GitHubBranchResponse,
    GitHubIssueResponse,
    GitHubRepositoryResponse,
    IssueCreationResponse,
    SessionContextResponse,
    SessionResponse,
    StageToolRequest,
    TrajectoryFileResponse,
    TrajectorySummaryResponse,
    UpdateSessionRequest,
    UserIssueResponse,
    UserQuestionOption,
    UserQuestionResponse,
)
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from yudai.utils import utc_now

from .mode_tools import get_daifu_issue_tool_service, get_daifu_mode_tool_service
from .session_service import MemoryService, SessionService
from .workflow_state import build_execution_objective, select_workflow_issue

router = APIRouter(tags=["sessions"])

# Configure logging
logger = logging.getLogger(__name__)

DAIFU_STAGE_CONFIRMATION_ORIGIN = "github_issue_created_confirmation"
DAIFU_STAGE_START_OPTION_ID = "start_workflow"
DAIFU_STAGE_DECLINE_OPTION_ID = "not_now"
DAIFU_STAGE_SEQUENCE_TOOL = "run_architect_mode"
USER_ISSUE_CREATION_QUESTION_ORIGINS = {
    "user_issue_creation",
    "issue_creation",
    "issue_creation_clarification",
    "github_issue_creation_validation",
}


def _is_stage_confirmation_question(question: UserQuestion) -> bool:
    metadata = question.question_metadata if isinstance(question.question_metadata, dict) else {}
    return metadata.get("origin") == DAIFU_STAGE_CONFIRMATION_ORIGIN


def _wants_stage_execution(request: AnswerQuestionRequest) -> bool:
    selected = {str(item).strip().lower() for item in request.selected_option_ids or []}
    if DAIFU_STAGE_START_OPTION_ID in selected or "start" in selected:
        return True
    answer_text = (request.answer_text or "").strip().lower()
    return answer_text in {"yes", "y", "start", "start workflow", "run it", "go ahead"}


def _question_references_user_issue(question: UserQuestion, issue_id: str) -> bool:
    metadata = question.question_metadata if isinstance(question.question_metadata, dict) else {}
    referenced_issue_id = str(
        metadata.get("issue_id")
        or metadata.get("user_issue_id")
        or metadata.get("user_issue_public_id")
        or ""
    ).strip()
    if referenced_issue_id:
        return referenced_issue_id == issue_id
    return str(metadata.get("origin") or "").strip() in USER_ISSUE_CREATION_QUESTION_ORIGINS


def _ensure_user_issue_ready_for_github_creation(
    db: Session,
    *,
    db_session: ChatSession,
    current_user: User,
    issue_id: str,
) -> UserIssue:
    user_issue = (
        db.query(UserIssue)
        .filter(
            UserIssue.user_id == current_user.id,
            UserIssue.issue_id == issue_id,
            UserIssue.session_id == db_session.session_id,
        )
        .first()
    )
    if not user_issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found for this session",
        )

    pending_questions = (
        db.query(UserQuestion)
        .filter(
            UserQuestion.session_id == db_session.id,
            UserQuestion.user_id == current_user.id,
            UserQuestion.status == UserQuestionStatus.PENDING.value,
        )
        .all()
    )
    blocking_questions = [
        question
        for question in pending_questions
        if _question_references_user_issue(question, issue_id)
    ]
    if blocking_questions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Answer pending issue clarification questions before creating the GitHub issue",
                "pending_question_ids": [
                    question.question_id for question in blocking_questions
                ],
            },
        )

    return user_issue


def _build_github_issue_execution_objective(
    db_session: ChatSession,
    result: Any,
) -> str:
    return build_execution_objective(_github_issue_ref_from_result(db_session, result))


def _github_issue_ref_from_result(
    db_session: ChatSession,
    result: Any,
) -> Dict[str, Any]:
    return {
        "github_issue_number": result.github_issue_number,
        "github_issue_url": result.github_issue_url,
        "issue_text_raw": result.issue_text_raw or result.description or "",
        "repo_branch": db_session.repo_branch or "main",
        "repo_name": result.repo_name or db_session.repo_name,
        "repo_owner": result.repo_owner or db_session.repo_owner,
        "title": result.title,
    }


def _raise_create_github_issue_http_error(exc: Exception) -> None:
    error_str = str(exc).lower()
    if any(
        keyword in error_str
        for keyword in ["403", "forbidden", "permission", "access denied", "not authorized"]
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if "404" in error_str or "not found" in error_str:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


async def _prepare_github_issue_created_response(
    db: Session,
    *,
    session_id: str,
    db_session: ChatSession,
    current_user: User,
    result: Any,
) -> CreateGitHubIssueResponse:
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found or missing repository information",
        )

    if not result.github_issue_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub issue was created but no URL was returned",
        )

    MemoryService.save_session_snapshot(
        db,
        db_session,
        trigger="github_issue_created",
    )

    select_workflow_issue(db_session, _github_issue_ref_from_result(db_session, result))

    execution_objective = _build_github_issue_execution_objective(db_session, result)
    db_session.mode_metadata = {
        **(db_session.mode_metadata or {}),
        "pending_resume_objective": execution_objective,
        "seed_user_issue_id": result.issue_id,
    }

    lifecycle = get_realtime_lifecycle_service()
    lifecycle.mark_issue_created(
        db,
        session_public_id=session_id,
        user_id=current_user.id,
        issue_url=result.github_issue_url,
        issue_number=result.github_issue_number,
    )

    issue_label = (
        f"#{result.github_issue_number}"
        if result.github_issue_number is not None
        else result.github_issue_url
    )
    confirmation_question = (
        db.query(UserQuestion)
        .filter(
            UserQuestion.session_id == db_session.id,
            UserQuestion.user_id == current_user.id,
            UserQuestion.status == UserQuestionStatus.PENDING.value,
        )
        .all()
    )
    confirmation_question = next(
        (
            question
            for question in confirmation_question
            if _is_stage_confirmation_question(question)
            and isinstance(question.question_metadata, dict)
            and (
                question.question_metadata.get("issue_url") == result.github_issue_url
                or question.question_metadata.get("issue_number")
                == result.github_issue_number
            )
        ),
        None,
    )
    if confirmation_question is None:
        confirmation_question = UserQuestion(
            question_id=f"q_{uuid.uuid4().hex[:10]}",
            session_id=db_session.id,
            user_id=current_user.id,
            mode=SessionMode.ARCHITECT.value,
            question_text=(
                f"Start the Architect -> Tester -> Coder workflow for GitHub issue {issue_label}?"
            ),
            options=[
                {"id": DAIFU_STAGE_START_OPTION_ID, "label": "Start workflow"},
                {"id": DAIFU_STAGE_DECLINE_OPTION_ID, "label": "Not now"},
            ],
            multi_select=False,
            status=UserQuestionStatus.PENDING.value,
            question_metadata={
                "origin": DAIFU_STAGE_CONFIRMATION_ORIGIN,
                "pending_tool": DAIFU_STAGE_SEQUENCE_TOOL,
                "issue_number": result.github_issue_number,
                "issue_url": result.github_issue_url,
            },
        )
        db.add(confirmation_question)
    confirmation_question_id = confirmation_question.question_id

    mode_metadata = dict(db_session.mode_metadata or {})
    pending_question_ids = [
        str(item)
        for item in (mode_metadata.get("pending_question_ids") or [])
        if str(item).strip()
    ]
    if confirmation_question_id not in pending_question_ids:
        pending_question_ids.append(confirmation_question_id)
    mode_metadata.update(
        {
            "pending_question_ids": pending_question_ids,
            "pending_daifu_tool": DAIFU_STAGE_SEQUENCE_TOOL,
            "pending_stage_tool_objective": execution_objective,
            "pending_stage_tool_issue_url": result.github_issue_url,
            "pending_stage_tool_issue_number": result.github_issue_number,
        }
    )
    db_session.mode_metadata = mode_metadata
    db_session.mode_status = SessionModeStatus.WAITING_FOR_INPUT.value
    db_session.mode_updated_at = utc_now()
    db_session.last_activity = utc_now()
    flag_modified(db_session, "mode_metadata")
    db.commit()

    await get_ws_hub().send_to_session(
        session_id,
        WSMessageType.AGENT_QUESTION,
        {
            "question_id": confirmation_question_id,
            "question_text": confirmation_question.question_text,
            "multi_select": False,
            "options": confirmation_question.options,
        },
    )

    message = (
        f"GitHub issue created successfully: {result.github_issue_url}. "
        "Confirm when you want Daifu to start the 3-mode workflow."
    )

    return CreateGitHubIssueResponse(
        success=True,
        github_url=result.github_issue_url,
        github_issue_number=result.github_issue_number,
        message=message,
        execution_started=False,
        execution_status=db_session.mode_status,
        requires_confirmation=True,
        confirmation_question_id=confirmation_question_id,
        pending_tool=DAIFU_STAGE_SEQUENCE_TOOL,
    )


async def _run_create_github_issue_tool(
    db: Session,
    *,
    session_id: str,
    db_session: ChatSession,
    current_user: User,
    issue_id: str,
) -> CreateGitHubIssueResponse:
    _ensure_user_issue_ready_for_github_creation(
        db,
        db_session=db_session,
        current_user=current_user,
        issue_id=issue_id,
    )
    call_id = f"tool_{uuid.uuid4().hex[:10]}"
    await get_ws_hub().send_to_session(
        session_id,
        WSMessageType.TOOL_CALL,
        {
            "tool_name": "create_github_issue",
            "tool_input": {
                "session_id": session_id,
                "issue_id": issue_id,
            },
            "call_id": call_id,
        },
    )
    result = await get_daifu_issue_tool_service().create_github_issue(
        db,
        session=db_session,
        user_id=current_user.id,
        issue_id=issue_id,
    )
    return await _prepare_github_issue_created_response(
        db,
        session_id=session_id,
        db_session=db_session,
        current_user=current_user,
        result=result,
    )


def create_standardized_error(
    status_code: int,
    error_code: str,
    message: str,
    detail: Optional[str] = None,
    path: Optional[str] = None,
) -> HTTPException:
    """
    Create a standardized HTTPException with consistent error format.
    """
    error_response = APIError(
        detail=detail or message,
        message=message,
        status=status_code,
        error_code=error_code,
        timestamp=utc_now(),
        path=path,
        request_id=str(uuid.uuid4()),
    )

    return HTTPException(status_code=status_code, detail=error_response.model_dump())


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


def _truncate_for_context(value: str, limit: int = 400) -> str:
    compact = " ".join((value or "").split())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "..."


def _to_user_question_response(
    question: UserQuestion,
    *,
    session_public_id: str,
) -> UserQuestionResponse:
    options_raw = question.options or []
    options: List[UserQuestionOption] = []
    for opt in options_raw:
        if not isinstance(opt, dict):
            continue
        option_id = str(opt.get("id") or "").strip()
        label = str(opt.get("label") or "").strip()
        if option_id and label:
            options.append(UserQuestionOption(id=option_id, label=label))

    return UserQuestionResponse(
        question_id=question.question_id,
        session_id=session_public_id,
        mode=question.mode,
        prompt=question.question_text,
        options=options,
        multi_select=bool(question.multi_select),
        selected_option_ids=[str(item) for item in (question.selected_option_ids or [])],
        answer_text=question.answer_text,
        status=question.status,
        asked_at=question.asked_at,
        answered_at=question.answered_at,
    )


def _build_objective_with_context(
    db: Session,
    *,
    session: ChatSession,
    objective: str,
) -> str:
    objective_sections = [f"Primary Objective:\n{objective.strip()}"]

    recent_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(12)
        .all()
    )
    if recent_messages:
        lines = []
        for message in reversed(recent_messages):
            role = (message.role or message.sender_type or "user").strip().lower()
            lines.append(f"- [{role}] {_truncate_for_context(message.message_text, 300)}")
        objective_sections.append(
            "Relevant Chat Context (most recent messages):\n" + "\n".join(lines)
        )

    answered_questions = (
        db.query(UserQuestion)
        .filter(
            UserQuestion.session_id == session.id,
            UserQuestion.status == UserQuestionStatus.ANSWERED.value,
        )
        .order_by(UserQuestion.answered_at.desc(), UserQuestion.created_at.desc())
        .limit(10)
        .all()
    )
    if answered_questions:
        qa_lines = []
        for question in reversed(answered_questions):
            options = {
                str(item.get("id")): str(item.get("label"))
                for item in (question.options or [])
                if isinstance(item, dict) and item.get("id") and item.get("label")
            }
            selected = []
            for option_id in question.selected_option_ids or []:
                option_id_str = str(option_id)
                selected.append(options.get(option_id_str, option_id_str))

            answer_parts: List[str] = []
            if selected:
                answer_parts.append("selected: " + ", ".join(selected))
            if question.answer_text:
                answer_parts.append("text: " + _truncate_for_context(question.answer_text, 250))
            if not answer_parts:
                answer_parts.append("answered")

            qa_lines.append(
                f"- Q: {_truncate_for_context(question.question_text, 280)}\n"
                f"  A: {'; '.join(answer_parts)}"
            )
        objective_sections.append("Clarifications from Q&A:\n" + "\n".join(qa_lines))

    return "\n\n".join(section for section in objective_sections if section.strip())


# ============================================================================
# GITHUB ENDPOINTS (ported under DAIFU router)
# ============================================================================


@router.get("/github/repositories", response_model=List[GitHubRepositoryResponse])
async def daifu_github_list_user_repositories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List repositories accessible by the authenticated user using their GitHub token.
    """
    try:
        from yudai.daifuUserAgent.githubOps import GitHubOps

        github_ops = GitHubOps(db)
        repositories = await github_ops.get_user_repositories(user_id=current_user.id)
        return repositories
    except HTTPException:
        raise
    except Exception as e:
        raise create_standardized_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "GITHUB_REPOS_FETCH_FAILED",
            "Failed to fetch repositories",
            detail=str(e),
            path="/daifu/github/repositories",
        )


@router.get(
    "/github/repositories/{owner}/{repo}/branches",
    response_model=List[GitHubBranchResponse],
)
async def daifu_github_list_repository_branches(
    owner: str,
    repo: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List branches for a specific repository the authenticated user can access.
    """
    try:
        from yudai.daifuUserAgent.githubOps import GitHubOps

        github_ops = GitHubOps(db)
        branches = await github_ops.fetch_repository_branches(
            owner, repo, current_user.id
        )
        # Normalize to match frontend's GitHubBranch type shape
        normalized = [
            {
                "name": b.get("name"),
                "protected": bool(b.get("protected", False)),
                "commit": {
                    "sha": b.get("commit_sha"),
                    "url": b.get("commit_url"),
                },
            }
            for b in branches
        ]
        return normalized
    except HTTPException:
        raise
    except Exception as e:
        raise create_standardized_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "GITHUB_BRANCHES_FETCH_FAILED",
            "Failed to fetch branches",
            detail=str(e),
            path=f"/daifu/github/repositories/{owner}/{repo}/branches",
        )


@router.get(
    "/github/repositories/{owner}/{repo}/issues",
    response_model=List[GitHubIssueResponse],
)
async def daifu_github_list_repository_issues(
    owner: str,
    repo: str,
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List issues for a specific repository the authenticated user can access.
    """
    try:
        from yudai.daifuUserAgent.githubOps import GitHubOps

        github_ops = GitHubOps(db)
        issues = await github_ops.fetch_repository_issues(
            owner, repo, current_user.id, limit
        )

        # Store issues in database if not already present
        from yudai.models import Issue, Repository

        # Get or create repository record
        repository = (
            db.query(Repository)
            .filter(
                Repository.owner == owner,
                Repository.name == repo,
                Repository.user_id == current_user.id,
            )
            .first()
        )

        if not repository:
            repository = Repository(
                user_id=current_user.id,
                name=repo,
                owner=owner,
                full_name=f"{owner}/{repo}",
                repo_url=f"https://github.com/{owner}/{repo}",
                html_url=f"https://github.com/{owner}/{repo}",
                clone_url=f"https://github.com/{owner}/{repo}.git",
            )
            db.add(repository)
            db.flush()

        # Store issues in database
        for issue_data in issues:
            issue = (
                db.query(Issue)
                .filter(
                    Issue.repository_id == repository.id,
                    Issue.number == issue_data.get("number"),
                )
                .first()
            )

            if not issue:
                issue = Issue(
                    github_issue_id=issue_data.get("number", 0),
                    repository_id=repository.id,
                    number=issue_data.get("number", 0),
                    title=issue_data.get("title", ""),
                    body=issue_data.get("body", ""),
                    state=issue_data.get("state", "open"),
                    html_url=issue_data.get("html_url", ""),
                    author_username=issue_data.get("user", {}).get("login")
                    if isinstance(issue_data.get("user"), dict)
                    else None,
                    github_created_at=datetime.fromisoformat(
                        issue_data.get("created_at", utc_now().isoformat()).replace(
                            "Z", "+00:00"
                        )
                    ),
                    github_updated_at=datetime.fromisoformat(
                        issue_data.get("updated_at", utc_now().isoformat()).replace(
                            "Z", "+00:00"
                        )
                    )
                    if issue_data.get("updated_at")
                    else None,
                )
                db.add(issue)
                db.flush()  # Ensure ID is available

            # Add issue ID to response
            issue_data["id"] = issue.id

        db.commit()

        return issues
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch issues for {owner}/{repo}: {e}")
        raise create_standardized_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "GITHUB_ISSUES_FETCH_FAILED",
            "Failed to fetch issues",
            detail=str(e),
            path=f"/daifu/github/repositories/{owner}/{repo}/issues",
        )


@router.get("/ai-models", response_model=List[AIModelResponse])
async def get_available_ai_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get list of available AI models for solving issues.
    Fetches models from OpenRouter API and stores them in the database if not already present.
    """
    try:
        from yudai.db.database import fetch_and_add_openrouter_models
        from yudai.models import AIModel

        # Check if we have any models in the database
        model_count = db.query(AIModel).filter(AIModel.is_active.is_(True)).count()

        # If no models exist, fetch from OpenRouter
        if model_count == 0:
            logger.info("No AI models found in database, fetching from OpenRouter...")
            # Run synchronously in a thread pool to avoid blocking the async endpoint
            import asyncio

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, fetch_and_add_openrouter_models)
            # Refresh the query after fetching
            db.expire_all()

        # Get all active models
        models = (
            db.query(AIModel)
            .filter(AIModel.is_active.is_(True))
            .order_by(AIModel.name)
            .all()
        )

        return [
            {
                "id": model.id,
                "name": model.name,
                "provider": model.provider,
                "model_id": model.model_id,
                "description": model.description,
            }
            for model in models
        ]
    except Exception as e:
        logger.error(f"Failed to fetch AI models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch AI models: {str(e)}",
        )


# CRITICAL PRIORITY ENDPOINTS


@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Create a new DAifu session for a repository.
    This is a CRITICAL endpoint required for session initialization.
    """
    try:
        # Debug logging for request data
        logger.info(
            f"[Session] Creating session with request data: repo_owner='{request.repo_owner}', repo_name='{request.repo_name}', repo_branch='{request.repo_branch}'"
        )

        # Generate unique session ID
        session_id = f"session_{uuid.uuid4().hex[:8]}"

        # Create new session in database
        db_session = ChatSession(
            user_id=current_user.id,
            session_id=session_id,
            title=request.title or f"Chat - {request.repo_owner}/{request.repo_name}",
            description=request.description,
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            repo_branch=request.repo_branch or "main",
            repo_url=f"https://github.com/{request.repo_owner}/{request.repo_name}.git",
            repo_context=None,
            runtime_workspace_path="/workspace/repo",
            is_active=True,
            total_messages=0,
            total_tokens=0,
            current_mode=SessionMode.PENDING.value,
            mode_status=SessionModeStatus.IDLE.value,
            mode_updated_at=utc_now(),
            last_activity=utc_now(),
        )

        db.add(db_session)
        db.commit()
        db.refresh(db_session)

        runtime_id: Optional[str] = None
        sandbox_id: Optional[str] = None
        tunnel_url: Optional[str] = None

        return SessionResponse(
            id=db_session.id,
            session_id=db_session.session_id,
            title=db_session.title,
            description=db_session.description,
            repo_owner=db_session.repo_owner,
            repo_name=db_session.repo_name,
            repo_branch=db_session.repo_branch,
            repo_url=db_session.repo_url,
            repo_context=db_session.repo_context,
            runtime_workspace_path=db_session.runtime_workspace_path,
            is_active=db_session.is_active,
            total_messages=db_session.total_messages,
            total_tokens=db_session.total_tokens,
            current_mode=db_session.current_mode,
            mode_status=db_session.mode_status,
            mode_updated_at=db_session.mode_updated_at,
            architect_issue_url=db_session.architect_issue_url,
            architect_issue_number=db_session.architect_issue_number,
            architect_completed_at=db_session.architect_completed_at,
            tester_status=db_session.tester_status,
            tester_completed_at=db_session.tester_completed_at,
            coder_pr_url=db_session.coder_pr_url,
            coder_pr_number=db_session.coder_pr_number,
            coder_completed_at=db_session.coder_completed_at,
            workflow_completed_at=db_session.workflow_completed_at,
            mode_metadata=db_session.mode_metadata,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
            last_activity=db_session.last_activity,
            runtime_id=runtime_id,
            sandbox_id=sandbox_id,
            tunnel_url=tunnel_url,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create session: {str(e)}",
        )


@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update session details (title, description, branch, etc.)
    This is a CRITICAL endpoint for session management.
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Update fields if provided
        if request.title is not None:
            db_session.title = request.title
        if request.description is not None:
            db_session.description = request.description
        if request.repo_branch is not None:
            db_session.repo_branch = request.repo_branch
        if request.is_active is not None:
            if not request.is_active and db_session.is_active:
                try:
                    MemoryService.save_session_snapshot(
                        db,
                        db_session,
                        trigger="session_deactivated",
                    )
                    logger.info("Session snapshot saved for %s", session_id)
                except Exception as snap_err:
                    logger.warning("Failed to save session snapshot: %s", snap_err)
            db_session.is_active = request.is_active

        # Update last activity
        db_session.last_activity = utc_now()
        db_session.updated_at = utc_now()

        db.commit()
        db.refresh(db_session)

        return SessionResponse(
            id=db_session.id,
            session_id=db_session.session_id,
            title=db_session.title,
            description=db_session.description,
            repo_owner=db_session.repo_owner,
            repo_name=db_session.repo_name,
            repo_branch=db_session.repo_branch,
            repo_url=db_session.repo_url,
            repo_context=db_session.repo_context,
            runtime_workspace_path=db_session.runtime_workspace_path,
            is_active=db_session.is_active,
            total_messages=db_session.total_messages,
            total_tokens=db_session.total_tokens,
            current_mode=db_session.current_mode,
            mode_status=db_session.mode_status,
            mode_updated_at=db_session.mode_updated_at,
            architect_issue_url=db_session.architect_issue_url,
            architect_issue_number=db_session.architect_issue_number,
            architect_completed_at=db_session.architect_completed_at,
            tester_status=db_session.tester_status,
            tester_completed_at=db_session.tester_completed_at,
            coder_pr_url=db_session.coder_pr_url,
            coder_pr_number=db_session.coder_pr_number,
            coder_completed_at=db_session.coder_completed_at,
            workflow_completed_at=db_session.workflow_completed_at,
            mode_metadata=db_session.mode_metadata,
            created_at=db_session.created_at,
            updated_at=db_session.updated_at,
            last_activity=db_session.last_activity,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session: {str(e)}",
        )


@router.get("/sessions/{session_id}", response_model=SessionContextResponse)
async def get_session_context(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get session context including messages, context cards, and repository info.
    This is a CRITICAL endpoint required for session loading.
    """
    try:
        from .session_service import SessionService

        # Ensure session exists and belongs to user
        _db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )

        # Get complete session context
        return SessionService.get_context(db, _db_session)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session context: {str(e)}",
        )


# HIGH PRIORITY ENDPOINTS


@router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse)
async def add_chat_message(
    session_id: str,
    message_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add a new chat message to a session.
    This endpoint is used by the chat system to store messages.
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Create new message
        message = ChatMessage(
            session_id=db_session.id,
            message_id=message_data.get("message_id", f"msg_{uuid.uuid4().hex[:8]}"),
            message_text=message_data["message_text"],
            sender_type=message_data["sender_type"],
            role=message_data["role"],
            is_code=message_data.get("is_code", False),
            tokens=message_data.get("tokens", 0),
            model_used=message_data.get("model_used"),
            processing_time=message_data.get("processing_time"),
            context_cards=message_data.get("context_cards"),
            referenced_files=message_data.get("referenced_files"),
            error_message=message_data.get("error_message"),
            actions=message_data.get("actions"),
        )

        db.add(message)

        # Update session statistics
        db_session.total_messages += 1
        db_session.total_tokens += message.tokens
        db_session.last_activity = utc_now()

        db.commit()
        db.refresh(message)

        return ChatMessageResponse(
            id=message.id,
            message_id=message.message_id,
            message_text=message.message_text,
            sender_type=message.sender_type,
            role=message.role,
            is_code=message.is_code,
            tokens=message.tokens,
            model_used=message.model_used,
            processing_time=message.processing_time,
            referenced_files=message.referenced_files,
            error_message=message.error_message,
            actions=message.actions,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add message: {str(e)}",
        )


@router.post(
    "/sessions/{session_id}/messages/bulk", response_model=List[ChatMessageResponse]
)
async def add_bulk_chat_messages(
    session_id: str,
    messages: List[dict],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Add multiple chat messages to a session in bulk.
    This is a HIGH priority endpoint for bulk message operations.
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        created_messages = []
        total_tokens_added = 0

        for message_data in messages:
            # Create new message
            message = ChatMessage(
                session_id=db_session.id,
                message_id=message_data.get(
                    "message_id", f"msg_{uuid.uuid4().hex[:8]}"
                ),
                message_text=message_data["message_text"],
                sender_type=message_data["sender_type"],
                role=message_data["role"],
                is_code=message_data.get("is_code", False),
                tokens=message_data.get("tokens", 0),
                model_used=message_data.get("model_used"),
                processing_time=message_data.get("processing_time"),
                context_cards=message_data.get("context_cards"),
                referenced_files=message_data.get("referenced_files"),
                error_message=message_data.get("error_message"),
                actions=message_data.get("actions"),
            )

            db.add(message)
            created_messages.append(message)
            total_tokens_added += message.tokens

        # Update session statistics
        db_session.total_messages += len(created_messages)
        db_session.total_tokens += total_tokens_added
        db_session.last_activity = utc_now()

        db.commit()

        # Refresh all messages to get IDs
        for message in created_messages:
            db.refresh(message)

        return [
            ChatMessageResponse(
                id=msg.id,
                message_id=msg.message_id,
                message_text=msg.message_text,
                sender_type=msg.sender_type,
                role=msg.role,
                is_code=msg.is_code,
                tokens=msg.tokens,
                model_used=msg.model_used,
                processing_time=msg.processing_time,
                referenced_files=msg.referenced_files,
                error_message=msg.error_message,
                actions=msg.actions,
                created_at=msg.created_at,
                updated_at=msg.updated_at,
            )
            for msg in created_messages
        ]

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add bulk messages: {str(e)}",
        )


@router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
async def get_chat_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get chat messages for a session.
    This is a HIGH priority endpoint for chat history display.
    """
    try:
        from .session_service import SessionService

        # Ensure session exists and belongs to user
        db_session_local = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )

        # Get messages for this session
        return SessionService.get_session_messages(db, db_session_local.id, limit)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat messages: {str(e)}",
        )


@router.post("/sessions/{session_id}/context-cards", response_model=ContextCardResponse)
async def add_context_card(
    session_id: str,
    request: CreateContextCardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a chat/upload context card to a session."""
    try:
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )
        context_card = ContextCard(
            user_id=current_user.id,
            session_id=db_session.id,
            title=request.title,
            description=request.description,
            content=request.content,
            source=request.source,
            tokens=request.tokens,
            is_active=True,
        )

        db.add(context_card)
        db.commit()
        db.refresh(context_card)
        return ContextCardResponse.model_validate(context_card)

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add context card: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/context-cards", response_model=List[ContextCardResponse]
)
async def get_context_cards(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get active context cards for a session."""
    try:
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )
        cards = (
            db.query(ContextCard)
            .filter(ContextCard.session_id == db_session.id, ContextCard.is_active)
            .order_by(ContextCard.created_at.desc())
            .all()
        )
        return [ContextCardResponse.model_validate(card) for card in cards]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context cards: {str(e)}",
        )


@router.delete("/sessions/{session_id}/context-cards/{card_id}")
async def delete_context_card(
    session_id: str,
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete a context card from a session."""
    try:
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )
        context_card = (
            db.query(ContextCard)
            .filter(
                ContextCard.id == card_id,
                ContextCard.session_id == db_session.id,
                ContextCard.user_id == current_user.id,
            )
            .first()
        )
        if not context_card:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Context card not found",
            )

        context_card.is_active = False
        context_card.updated_at = utc_now()
        db.commit()
        return {"success": True, "message": "Context card removed"}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete context card: {str(e)}",
        )

# CHAT ENDPOINTS - Consolidated from chat_api.py
# =================================================================================


@router.post("/sessions/{session_id}/conversation", response_model=ConversationResponse)
async def conversation_in_session(
    session_id: str,
    request: ConversationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Conversation API: immediate natural-language response + optional follow-up question."""
    db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)

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
    db.add(user_message)
    db_session.total_messages = (db_session.total_messages or 0) + 1

    # Lightweight ambiguity detector: ask for preference before execution when request is broad.
    ambiguous_terms = ("auth", "authentication", "api", "database", "testing")
    if not request.selected_option_ids and any(term in lower_content for term in ambiguous_terms):
        question_options = [
            {"id": "behavior", "label": "Behavioral change first"},
            {"id": "tests", "label": "Test coverage first"},
            {"id": "refactor", "label": "Refactor and structure first"},
        ]
        question = UserQuestion(
            question_id=f"q_{uuid.uuid4().hex[:10]}",
            session_id=db_session.id,
            user_id=current_user.id,
            mode=_next_mode_for_session(db_session),
            question_text="Choose the primary implementation focus for this run.",
            options=question_options,
            multi_select=False,
            status=UserQuestionStatus.PENDING.value,
            question_metadata={"origin": "conversation_ambiguity"},
        )
        db.add(question)
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
    db.add(assistant_message)
    db_session.total_messages = (db_session.total_messages or 0) + 1
    db_session.last_activity = utc_now()
    db_session.mode_updated_at = utc_now()
    db.commit()

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


@router.post(
    "/sessions/{session_id}/ask-question",
    response_model=AskQuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ask_question_for_session(
    session_id: str,
    request: AskQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist a follow-up question and move session to waiting-for-input."""
    db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)

    options: List[Dict[str, str]] = []
    seen_ids: set[str] = set()
    for option in request.options:
        option_id = option.id.strip()
        if option_id in seen_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Duplicate option id: {option_id}",
            )
        seen_ids.add(option_id)
        options.append({"id": option_id, "label": option.label.strip()})

    mode = request.mode or _next_mode_for_session(db_session)
    question = UserQuestion(
        question_id=f"q_{uuid.uuid4().hex[:10]}",
        session_id=db_session.id,
        user_id=current_user.id,
        mode=mode,
        question_text=request.prompt.strip(),
        options=options,
        multi_select=bool(request.multi_select),
        status=UserQuestionStatus.PENDING.value,
        question_metadata=request.metadata or {},
    )
    db.add(question)

    mode_metadata = dict(db_session.mode_metadata or {})
    if request.objective:
        mode_metadata["pending_resume_objective"] = request.objective.strip()
    mode_metadata["last_question_id"] = question.question_id
    db_session.mode_metadata = mode_metadata
    db_session.mode_status = SessionModeStatus.WAITING_FOR_INPUT.value
    db_session.mode_updated_at = utc_now()
    db_session.last_activity = utc_now()
    db.commit()
    db.refresh(question)

    await get_ws_hub().send_to_session(
        session_id,
        WSMessageType.AGENT_QUESTION,
        {
            "question_id": question.question_id,
            "question_text": question.question_text,
            "multi_select": bool(question.multi_select),
            "options": options,
        },
    )

    return AskQuestionResponse(
        question=_to_user_question_response(question, session_public_id=session_id),
        mode_status=db_session.mode_status,
    )


@router.post(
    "/sessions/{session_id}/questions/{question_id}/answer",
    response_model=AnswerQuestionResponse,
)
async def answer_session_question(
    session_id: str,
    question_id: str,
    request: AnswerQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Record question answer and resume fixed mode execution when requested."""
    db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)
    question = (
        db.query(UserQuestion)
        .filter(
            UserQuestion.question_id == question_id,
            UserQuestion.session_id == db_session.id,
            UserQuestion.user_id == current_user.id,
        )
        .first()
    )
    if not question:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

    option_ids = [str(item).strip() for item in request.selected_option_ids if str(item).strip()]
    option_set = {item["id"] for item in (question.options or []) if isinstance(item, dict) and item.get("id")}
    invalid_option_ids = [item for item in option_ids if option_set and item not in option_set]
    if invalid_option_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid option id(s): {', '.join(invalid_option_ids)}",
        )

    if not question.multi_select and len(option_ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question only accepts a single selected option",
        )

    answer_text = (request.answer_text or "").strip()
    if not option_ids and not answer_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Answer requires selected_option_ids and/or answer_text",
        )

    was_waiting_for_input = db_session.mode_status == SessionModeStatus.WAITING_FOR_INPUT.value

    question.selected_option_ids = option_ids or None
    question.answer_text = answer_text or None
    question.status = UserQuestionStatus.ANSWERED.value
    question.answered_at = utc_now()
    db_session.last_activity = utc_now()

    original_mode_metadata = dict(db_session.mode_metadata or {})
    original_gathering_state = original_mode_metadata.get("gathering_state")
    mode_metadata = dict(original_mode_metadata)
    mode_metadata["last_answered_question_id"] = question.question_id
    mode_metadata["last_answered_question_at"] = utc_now().isoformat()
    pending_question_ids = [
        str(item)
        for item in (mode_metadata.get("pending_question_ids") or [])
        if str(item).strip() and str(item).strip() != question_id
    ]
    if pending_question_ids:
        mode_metadata["pending_question_ids"] = pending_question_ids
        db_session.mode_status = SessionModeStatus.WAITING_FOR_INPUT.value
    else:
        mode_metadata["pending_question_ids"] = []
        if original_gathering_state and (
            original_gathering_state in {"probes_done", "complete"}
            or not mode_metadata.get("pending_probe_ids")
        ):
            mode_metadata["gathering_state"] = "complete"
        db_session.mode_status = SessionModeStatus.IDLE.value
    db_session.mode_updated_at = utc_now()
    db_session.mode_metadata = mode_metadata
    flag_modified(db_session, "mode_metadata")

    resumed = False
    resumed_mode: Optional[str] = None
    next_mode = _next_mode_for_session(db_session)
    realtime_flags = get_realtime_feature_flags()
    is_stage_confirmation = _is_stage_confirmation_question(question)
    question_metadata = (
        question.question_metadata if isinstance(question.question_metadata, dict) else {}
    )
    is_daifu_gathering_question = (
        question_metadata.get("origin") == "daifu_directive"
        or original_gathering_state in {"active", "probes_done", "complete"}
    )
    if is_stage_confirmation and not pending_question_ids:
        if request.resume_execution and _wants_stage_execution(request):
            if not realtime_flags.mode_orchestrator_enabled:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Mode orchestrator is disabled by feature flags",
                )
            objective_seed = (
                str(mode_metadata.get("pending_stage_tool_objective") or "").strip()
                or str(mode_metadata.get("pending_resume_objective") or "").strip()
                or "Continue the current GitHub issue workflow."
            )
            mode_metadata["pending_resume_objective"] = objective_seed
            mode_metadata["pending_daifu_tool"] = DAIFU_STAGE_SEQUENCE_TOOL
            db_session.mode_metadata = mode_metadata
            flag_modified(db_session, "mode_metadata")
            db.commit()
            try:
                execution_status = await get_daifu_mode_tool_service().run_all_stage_tools(
                    db,
                    session=db_session,
                    user_id=current_user.id,
                    objective=objective_seed,
                )
            except ExecutionConflictError as exc:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            resumed = True
            resumed_mode = str(execution_status.get("mode") or next_mode)
        else:
            mode_metadata.pop("pending_daifu_tool", None)
            mode_metadata.pop("pending_stage_tool_objective", None)
            mode_metadata.pop("pending_stage_tool_issue_url", None)
            mode_metadata.pop("pending_stage_tool_issue_number", None)
            db_session.mode_metadata = mode_metadata
            flag_modified(db_session, "mode_metadata")
            db.commit()
    elif (
        request.resume_execution
        and was_waiting_for_input
        and not pending_question_ids
        and not is_daifu_gathering_question
        and realtime_flags.mode_orchestrator_enabled
        and next_mode != SessionMode.COMPLETE.value
    ):
        orchestrator = get_session_execution_orchestrator()
        objective_seed = (
            answer_text
            or str((db_session.mode_metadata or {}).get("pending_resume_objective") or "").strip()
        )
        if not objective_seed:
            latest_execution = (
                db.query(AgentExecution)
                .filter(AgentExecution.session_id == db_session.id)
                .order_by(AgentExecution.created_at.desc())
                .first()
            )
            if latest_execution and isinstance(latest_execution.execution_metadata, dict):
                objective_seed = str(latest_execution.execution_metadata.get("objective") or "").strip()

        if not objective_seed:
            last_user_message = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.session_id == db_session.id,
                    ChatMessage.role == "user",
                )
                .order_by(ChatMessage.created_at.desc())
                .first()
            )
            if last_user_message:
                objective_seed = last_user_message.message_text

        objective_seed = objective_seed or "Continue the current workflow."
        mode_metadata = dict(db_session.mode_metadata or {})
        mode_metadata["pending_resume_objective"] = objective_seed
        db_session.mode_metadata = mode_metadata
        flag_modified(db_session, "mode_metadata")
        db.commit()
        try:
            execution_status = await orchestrator.resume_execution(
                db,
                session=db_session,
                user_id=current_user.id,
                objective=objective_seed,
            )
        except ExecutionConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except ExecutionNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        resumed = True
        resumed_mode = str(execution_status.get("mode") or next_mode)
    else:
        db.commit()

    if (
        is_daifu_gathering_question
        and not is_stage_confirmation
        and not pending_question_ids
    ):
        latest_metadata = dict(db_session.mode_metadata or {})
        pending_probe_ids = [
            str(item)
            for item in (latest_metadata.get("pending_probe_ids") or [])
            if str(item).strip()
        ]
        if not pending_probe_ids:
            from .ChatOps import ChatOps

            await ChatOps(db)._continue_daifu_after_gathering(
                session_id=session_id,
                user_id=current_user.id,
                trigger="clarification answer",
            )
            db.refresh(db_session)

    return AnswerQuestionResponse(
        question=_to_user_question_response(question, session_public_id=session_id),
        resumed=resumed,
        resumed_mode=resumed_mode,
        mode_status=db_session.mode_status,
    )


@router.post(
    "/sessions/{session_id}/execution",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_session_pipeline(
    session_id: str,
    request: ExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execution API: generate mode plan and run fixed Architect -> Tester -> Coder pipeline."""
    realtime_flags = get_realtime_feature_flags()
    if not realtime_flags.mode_orchestrator_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mode orchestrator is disabled by feature flags",
        )

    db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)
    next_mode = _next_mode_for_session(db_session)

    if next_mode == SessionMode.COMPLETE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Session workflow already complete",
        )

    if request.force_mode and request.force_mode != next_mode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Mode switching is server-controlled. Expected next mode "
                f"'{next_mode}', got '{request.force_mode}'."
            ),
        )

    db_session.mode_metadata = {
        **(db_session.mode_metadata or {}),
        "pending_resume_objective": request.objective,
    }
    db.commit()

    try:
        status_payload = await get_session_execution_orchestrator().start_execution(
            db,
            session=db_session,
            user_id=current_user.id,
            objective=request.objective,
            force_mode=request.force_mode,
        )
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception(
            "Unhandled error in execute_session_pipeline for session %s", session_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {type(exc).__name__}: {exc}",
        ) from exc

    try:
        return ExecutionResponse(**status_payload)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception(
            "Response serialization failed for session %s: payload=%r", session_id, status_payload
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Response serialization failed: {type(exc).__name__}: {exc}",
        ) from exc


@router.post(
    "/sessions/{session_id}/execution/stage-tool",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_session_stage_tool(
    session_id: str,
    request: StageToolRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start exactly one legal Daifu stage tool: Architect, Tester, or Coder."""
    realtime_flags = get_realtime_feature_flags()
    if not realtime_flags.mode_orchestrator_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mode orchestrator is disabled by feature flags",
        )

    db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)
    mode_metadata = dict(db_session.mode_metadata or {})
    mode_metadata["pending_resume_objective"] = request.objective
    mode_metadata["pending_daifu_tool"] = request.tool_name
    db_session.mode_metadata = mode_metadata
    flag_modified(db_session, "mode_metadata")
    db.commit()

    try:
        status_payload = await get_daifu_mode_tool_service().run_stage_tool(
            db,
            session=db_session,
            user_id=current_user.id,
            tool_name=request.tool_name,
            objective=request.objective,
        )
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ExecutionResponse(**status_payload)


@router.post(
    "/sessions/{session_id}/tools/run-frontend-browser-check",
    response_model=ExecutionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def execute_frontend_browser_check_tool(
    session_id: str,
    request: FrontendBrowserCheckToolRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the manual Daifu frontend browser verifier sidecar."""
    realtime_flags = get_realtime_feature_flags()
    if not realtime_flags.mode_orchestrator_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Mode orchestrator is disabled by feature flags",
        )

    db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)

    try:
        status_payload = await get_daifu_mode_tool_service().run_frontend_browser_check(
            db,
            session=db_session,
            user_id=current_user.id,
            objective=request.objective,
        )
    except ExecutionConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ExecutionResponse(**status_payload)


@router.get(
    "/sessions/{session_id}/execution",
    response_model=ExecutionStatusResponse,
)
async def get_session_execution_status(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)
    return ExecutionStatusResponse(
        **get_session_execution_orchestrator().get_execution_status(
            db,
            session=db_session,
        )
    )


@router.post(
    "/sessions/{session_id}/execution/cancel",
    response_model=CancelExecutionResponse,
)
async def cancel_session_execution(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)
    try:
        payload = await get_session_execution_orchestrator().cancel_execution(
            db,
            session=db_session,
        )
    except ExecutionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return CancelExecutionResponse(
        execution_id=payload.get("execution_id"),
        session_id=session_id,
        status=str(payload.get("status") or SessionModeStatus.CANCELLED.value),
        message="Execution cancelled",
    )


@router.post("/sessions/{session_id}/chat", response_model=ChatResponse)
async def chat_in_session(
    session_id: str,
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chat Endpoint within Session Context - Uses ChatOps for unified chat handling

    This endpoint processes chat messages within a specific session context using
    the ChatOps class for consistent processing and response formatting.
    """
    start_time = time.time()

    # Validate session exists and belongs to user
    db_session = (
        db.query(ChatSession)
        .filter(
            ChatSession.session_id == session_id, ChatSession.user_id == current_user.id
        )
        .first()
    )

    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # Validate session_id matches request
    if not request.session_id or request.session_id.strip() != session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session ID mismatch between URL and request body",
        )

    try:
        # Import ChatOps for unified chat processing
        from .ChatOps import ChatOps

        # Initialize ChatOps instance
        chat_ops = ChatOps(db)

        # Prepare repository information for ChatOps
        repository_info = None
        if (
            request.repository
            and request.repository.get("owner")
            and request.repository.get("name")
        ):
            repository_info = {
                "owner": request.repository["owner"],
                "name": request.repository["name"],
                "branch": request.repository.get("branch", "main"),
            }
        elif db_session.repo_owner and db_session.repo_name:
            # Fallback to session repository info
            repository_info = {
                "owner": db_session.repo_owner,
                "name": db_session.repo_name,
                "branch": "main",
            }

        # Process chat message using ChatOps
        chat_response = await chat_ops.process_chat_message(
            session_id=session_id,
            user_id=current_user.id,
            message_text=request.message.message_text,
            repository=repository_info,
        )

        # Get updated conversation history for the response
        raw_history = chat_ops._get_conversation_history(db_session.id, 50)
        # Normalize to ("User"|"DAifu", text) for frontend compatibility
        history = [
            ("User" if s.lower() == "user" else "DAifu", t) for s, t in raw_history
        ]

        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000

        # Map ChatOps response to ChatResponse format
        return ChatResponse(
            reply=chat_response["reply"],
            conversation=history,
            message_id=chat_response["message_id"],
            processing_time=processing_time,
            session_id=session_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat processing failed for session {session_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}",
        )


@router.get("/sessions/{session_id}/memories")
async def get_session_memories(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return stored facts, episodic memories, highlights, and the latest snapshot."""

    db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)
    return MemoryService.get_memories(db_session)


# (Removed duplicate conversation history helpers; using ChatOps._get_conversation_history)


# ISSUES ENDPOINTS - Consolidated under sessions context
# ============================================================================


@router.post(
    "/sessions/{session_id}/issues/create-with-context",
    response_model=IssueCreationResponse,
)
async def create_issue_with_context_for_session(
    session_id: str,
    request: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create an issue with context for a session using consolidated LLM generation and database storage
    """
    try:
        from .IssueOps import IssueService as IssueOpsService
        from .session_service import SessionService

        # Ensure session exists and belongs to user
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )

        # Use consolidated issue creation service
        issue_service = IssueOpsService(db)

        repository_info = request.get("repository_info") or {}
        requested_owner = repository_info.get("owner")
        requested_name = repository_info.get("name")

        repo_owner = db_session.repo_owner
        repo_name = db_session.repo_name

        if requested_owner and requested_name:
            if repo_owner and repo_name:
                if (repo_owner, repo_name) != (requested_owner, requested_name):
                    logger.warning(
                        "Repository mismatch for session %s (user %s): "
                        "session=%s/%s request=%s/%s. Updating session repo fields.",
                        db_session.session_id,
                        current_user.id,
                        repo_owner,
                        repo_name,
                        requested_owner,
                        requested_name,
                    )
            else:
                logger.info(
                    "Repository info provided for session %s (user %s): %s/%s. "
                    "Updating session repo fields.",
                    db_session.session_id,
                    current_user.id,
                    requested_owner,
                    requested_name,
                )

            if (repo_owner, repo_name) != (requested_owner, requested_name):
                db_session.repo_owner = requested_owner
                db_session.repo_name = requested_name
                try:
                    db.commit()
                except Exception as commit_error:
                    logger.error(
                        "Failed to update session repo fields for session %s: %s",
                        db_session.session_id,
                        commit_error,
                    )
                    db.rollback()
                    raise
                repo_owner = requested_owner
                repo_name = requested_name
        elif not repo_owner or not repo_name:
            if repository_info:
                repo_owner = requested_owner or repo_owner
                repo_name = requested_name or repo_name

        result = await issue_service.create_issue_with_context(
            user_id=current_user.id,
            session_id=session_id,
            title=request.get("title", ""),
            description=request.get("description", ""),
            chat_messages=request.get("chat_messages", []),
            repo_owner=repo_owner,
            repo_name=repo_name,
            priority=request.get("priority", "medium"),
            create_github_issue=False,  # We'll create GitHub issue separately in the modal
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create issue with context: {str(e)}",
        )


@router.get("/sessions/{session_id}/issues", response_model=List[UserIssueResponse])
async def get_issues_for_session(
    session_id: str,
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = Query(None, alias="priority"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get issues for a session - Consolidated from issue_service.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Import issue service functionality
        from yudai.models import UserIssue

        # Build query
        query = db.query(UserIssue).filter(
            UserIssue.user_id == current_user.id, UserIssue.session_id == session_id
        )

        # Apply filters
        if status_filter:
            query = query.filter(UserIssue.status == status_filter)
        if priority:
            query = query.filter(UserIssue.priority == priority)

        # Apply pagination and ordering
        issues = query.order_by(UserIssue.created_at.desc()).limit(limit).all()

        return [
            {
                "id": issue.id,
                "issue_id": issue.issue_id,
                "user_id": issue.user_id,
                "title": issue.title,
                "description": issue.description,
                "issue_text_raw": issue.issue_text_raw,
                "issue_steps": issue.issue_steps,
                "session_id": issue.session_id,
                "ideas": issue.ideas,
                "repo_owner": issue.repo_owner,
                "repo_name": issue.repo_name,
                "priority": issue.priority,
                "status": issue.status,
                "agent_response": issue.agent_response,
                "processing_time": issue.processing_time,
                "tokens_used": issue.tokens_used,
                "github_issue_url": issue.github_issue_url,
                "github_issue_number": issue.github_issue_number,
                "created_at": issue.created_at,
                "updated_at": issue.updated_at,
                "processed_at": issue.processed_at,
            }
            for issue in issues
        ]

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get issues: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/issues/{issue_id}", response_model=UserIssueResponse
)
async def get_issue_for_session(
    session_id: str,
    issue_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific issue for a session - Consolidated from issue_service.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Import issue service functionality
        from yudai.models import UserIssue

        # Get the issue
        issue = (
            db.query(UserIssue)
            .filter(
                UserIssue.user_id == current_user.id,
                UserIssue.issue_id == issue_id,
                UserIssue.session_id == session_id,
            )
            .first()
        )

        if not issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
            )

        return {
            "id": issue.id,
            "issue_id": issue.issue_id,
            "user_id": issue.user_id,
            "title": issue.title,
            "description": issue.description,
            "issue_text_raw": issue.issue_text_raw,
            "issue_steps": issue.issue_steps,
            "session_id": issue.session_id,
            "ideas": issue.ideas,
            "repo_owner": issue.repo_owner,
            "repo_name": issue.repo_name,
            "priority": issue.priority,
            "status": issue.status,
            "agent_response": issue.agent_response,
            "processing_time": issue.processing_time,
            "tokens_used": issue.tokens_used,
            "github_issue_url": issue.github_issue_url,
            "github_issue_number": issue.github_issue_number,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "processed_at": issue.processed_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get issue: {str(e)}",
        )


@router.put(
    "/sessions/{session_id}/issues/{issue_id}/status", response_model=UserIssueResponse
)
async def update_issue_status_for_session(
    session_id: str,
    issue_id: str,
    status: str,
    agent_response: Optional[str] = None,
    processing_time: Optional[float] = None,
    tokens_used: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update issue status for a session - Consolidated from issue_service.py
    """
    try:
        # Verify session exists and belongs to user
        db_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
            )
            .first()
        )

        if not db_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )

        # Import issue service functionality
        from yudai.daifuUserAgent.IssueOps import IssueService

        # Update issue status
        issue_service = IssueService(db)
        updated_issue = issue_service.update_issue_status(
            current_user.id,
            issue_id,
            status,
            agent_response,
            processing_time,
            tokens_used,
        )

        if not updated_issue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found"
            )

        return {
            "id": updated_issue.id,
            "issue_id": updated_issue.issue_id,
            "user_id": updated_issue.user_id,
            "title": updated_issue.title,
            "description": updated_issue.description,
            "issue_text_raw": updated_issue.issue_text_raw,
            "issue_steps": updated_issue.issue_steps,
            "session_id": updated_issue.session_id,
            "ideas": updated_issue.ideas,
            "repo_owner": updated_issue.repo_owner,
            "repo_name": updated_issue.repo_name,
            "priority": updated_issue.priority,
            "status": updated_issue.status,
            "agent_response": updated_issue.agent_response,
            "processing_time": updated_issue.processing_time,
            "tokens_used": updated_issue.tokens_used,
            "github_issue_url": updated_issue.github_issue_url,
            "github_issue_number": updated_issue.github_issue_number,
            "created_at": updated_issue.created_at,
            "updated_at": updated_issue.updated_at,
            "processed_at": updated_issue.processed_at,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update issue status: {str(e)}",
        )


@router.post(
    "/sessions/{session_id}/issues/{issue_id}/create-github-issue",
    response_model=CreateGitHubIssueResponse,
)
async def create_github_issue_from_user_issue_for_session(
    session_id: str,
    issue_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create GitHub issue from user issue for a session - Consolidated from issue_service.py
    """
    try:
        db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)
        return await _run_create_github_issue_tool(
            db,
            session_id=session_id,
            db_session=db_session,
            current_user=current_user,
            issue_id=issue_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        _raise_create_github_issue_http_error(e)


@router.post(
    "/sessions/{session_id}/tools/create-github-issue",
    response_model=CreateGitHubIssueResponse,
)
async def execute_create_github_issue_tool(
    session_id: str,
    request: CreateGitHubIssueToolRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run the Daifu create_github_issue tool for an existing drafted issue."""
    try:
        db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)
        return await _run_create_github_issue_tool(
            db,
            session_id=session_id,
            db_session=db_session,
            current_user=current_user,
            issue_id=request.issue_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        _raise_create_github_issue_http_error(exc)


# ============================================================================
# TRAJECTORY VIEWER ENDPOINTS
# ============================================================================


@router.get(
    "/sessions/{session_id}/trajectories",
    response_model=List[TrajectorySummaryResponse],
)
async def get_session_trajectories(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all trajectories for a session from solve runs.
    """
    try:
        from yudai.models import Solve

        from .session_service import SessionService

        # Ensure session exists and belongs to user
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )

        # Get all solves for this session
        solves = (
            db.query(Solve)
            .filter(
                Solve.session_id == db_session.id,
                Solve.user_id == current_user.id,
            )
            .all()
        )

        trajectories = []
        for solve in solves:
            for run in solve.runs:
                if run.trajectory_data:
                    trajectory_data = run.trajectory_data
                    if isinstance(trajectory_data, str):
                        try:
                            trajectory_data = json.loads(trajectory_data)
                        except json.JSONDecodeError:
                            trajectory_data = {}

                    local_path = trajectory_data.get("local_path")
                    metadata = trajectory_data.get("metadata", {})

                    trajectories.append(
                        {
                            "id": run.id,
                            "solve_id": solve.id,
                            "run_id": run.id,
                            "model": run.model,
                            "status": run.status,
                            "local_path": local_path,
                            "remote_path": trajectory_data.get("remote_path"),
                            "exit_status": metadata.get("exit_status"),
                            "instance_cost": metadata.get("instance_cost"),
                            "api_calls": metadata.get("api_calls"),
                            "mini_version": metadata.get("mini_version"),
                            "model_name": metadata.get("model_name"),
                            "total_messages": metadata.get("total_messages"),
                            "created_at": run.created_at.isoformat()
                            if run.created_at
                            else None,
                            "completed_at": run.completed_at.isoformat()
                            if run.completed_at
                            else None,
                        }
                    )

        return trajectories

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trajectories for session {session_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trajectories: {str(e)}",
        )


@router.get(
    "/sessions/{session_id}/trajectories/{run_id}",
    response_model=TrajectoryFileResponse,
)
async def get_trajectory_file(
    session_id: str,
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get trajectory file content for a specific run.
    """
    try:
        from yudai.models import Solve, SolveRun

        from .session_service import SessionService

        # Ensure session exists and belongs to user
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )

        # Get the solve run
        run = (
            db.query(SolveRun)
            .join(Solve)
            .filter(
                SolveRun.id == run_id,
                Solve.session_id == db_session.id,
                Solve.user_id == current_user.id,
            )
            .first()
        )

        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trajectory not found",
            )

        trajectory_data = run.trajectory_data
        if not trajectory_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No trajectory data available for this run",
            )

        if isinstance(trajectory_data, str):
            try:
                trajectory_data = json.loads(trajectory_data)
            except json.JSONDecodeError:
                trajectory_data = {}

        local_path = trajectory_data.get("local_path")
        if not local_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trajectory file path not found",
            )

        # Read trajectory file
        trajectory_file_path = Path(local_path)
        if not trajectory_file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trajectory file not found on disk",
            )

        trajectory_content = json.loads(trajectory_file_path.read_text())

        return {
            "run_id": run.id,
            "solve_id": run.solve_id,
            "model": run.model,
            "status": run.status,
            "local_path": local_path,
            "content": trajectory_content,
            "metadata": trajectory_data.get("metadata", {}),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get trajectory file for run {run_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get trajectory file: {str(e)}",
        )
