#!/usr/bin/env python3
"""
Session Management Routes for DAifu Agent

This module provides FastAPI routes for session management,
including session creation, context management, messages, and file dependencies.

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

4. File Dependencies Integration
   - Complete the file extraction endpoint integration
   - Add support for large repository processing
   - Implement file dependency caching
   - Add file content preview and search capabilities

5. Database Optimization
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
    - Support multiple context sources (files, chat, external)
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

# Import file dependencies functionality
import asyncio
import json
import logging

# Import chat functionality from chat_api
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from auth.github_oauth import get_current_user
from config.realtime_flags import get_realtime_feature_flags
from context import (
    EmbeddingPipeline,
    FactsAndMemoriesService,
    RepositoryFile,
    RepositorySnapshotService,
)
from daifuUserAgent.githubOps import GitHubOps
from db.database import SessionLocal, get_db
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from realtime.lifecycle import get_realtime_lifecycle_service
from realtime.mode_orchestrator import (
    ExecutionConflictError,
    ExecutionNotFoundError,
    get_session_execution_orchestrator,
)
from realtime.ws_protocol import get_ws_hub
from realtime.ws_protocol import WSMessageType

# Import from filedeps.py
from models import (
    APIError,
    AnswerQuestionRequest,
    AnswerQuestionResponse,
    AgentExecution,
    AskQuestionRequest,
    AskQuestionResponse,
    ChatMessage,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
    ChatSession,
    CancelExecutionResponse,
    ConversationRequest,
    ConversationResponse,
    ContextCard,
    ContextCardResponse,
    CreateContextCardRequest,
    CreateGitHubIssueResponse,
    CreateSessionRequest,
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatusResponse,
    FileEmbedding,
    FileItem,
    FileItemResponse,
    Repository,
    SessionMode,
    SessionModeStatus,
    SessionContextResponse,
    SessionResponse,
    UpdateSessionRequest,
    User,
    UserQuestion,
    UserQuestionOption,
    UserQuestionResponse,
    UserQuestionStatus,
    UserIssueResponse,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from utils import utc_now

from .llm_service import LLMService
from .session_service import MemoryService, SessionService

router = APIRouter(tags=["sessions"])

# Configure logging
logger = logging.getLogger(__name__)


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


@router.get("/github/repositories", response_model=List[Dict[str, Any]])
async def daifu_github_list_user_repositories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List repositories accessible by the authenticated user using their GitHub token.
    """
    try:
        from daifuUserAgent.githubOps import GitHubOps

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
    response_model=List[Dict[str, Any]],
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
        from daifuUserAgent.githubOps import GitHubOps

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
    response_model=List[Dict[str, Any]],
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
        from daifuUserAgent.githubOps import GitHubOps

        github_ops = GitHubOps(db)
        issues = await github_ops.fetch_repository_issues(
            owner, repo, current_user.id, limit
        )

        # Store issues in database if not already present
        from models import Issue, Repository

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


@router.get("/ai-models", response_model=List[Dict[str, Any]])
async def get_available_ai_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get list of available AI models for solving issues.
    Fetches models from OpenRouter API and stores them in the database if not already present.
    """
    try:
        from db.database import fetch_and_add_openrouter_models
        from models import AIModel

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
            generate_embeddings=request.generate_embeddings,
            generate_facts_memories=request.generate_facts_memories,
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

        # Kick off background indexing of the repository if requested
        if getattr(request, "index_codebase", True):
            try:
                repo_owner = request.repo_owner
                repo_name = request.repo_name
                repo_branch = request.repo_branch or "main"
                max_file_size = getattr(request, "index_max_file_size", None)

                logger.info(
                    f"[Session] Triggering background indexing for session {session_id}: {repo_owner}/{repo_name}"
                )

                async def _run_index():
                    logger.info(
                        f"[Session] Starting background indexing task for session {session_id}"
                    )
                    await _index_repository_for_session_background(
                        session_uuid=db_session.session_id,
                        user_id=current_user.id,
                        repo_owner=repo_owner,
                        repo_name=repo_name,
                        repo_branch=repo_branch,
                        max_file_size=max_file_size,
                        generate_embeddings=request.generate_embeddings,
                        generate_facts_memories=request.generate_facts_memories,
                    )
                    logger.info(
                        f"[Session] Background indexing completed for session {session_id}"
                    )

                try:
                    # If inside event loop, schedule directly
                    asyncio.get_running_loop()
                    asyncio.create_task(_run_index())
                except RuntimeError:
                    # Fallback when no loop is active
                    background_tasks.add_task(lambda: asyncio.run(_run_index()))
            except Exception as e_bg:
                logger.error(f"Failed to schedule repository indexing: {e_bg}")

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
            generate_embeddings=db_session.generate_embeddings,
            generate_facts_memories=db_session.generate_facts_memories,
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
        if request.generate_embeddings is not None:
            db_session.generate_embeddings = request.generate_embeddings
        if request.generate_facts_memories is not None:
            db_session.generate_facts_memories = request.generate_facts_memories

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
            generate_embeddings=db_session.generate_embeddings,
            generate_facts_memories=db_session.generate_facts_memories,
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
            context_cards=message.context_cards,
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
                context_cards=msg.context_cards,
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
    """
    Add a context card to a session.
    This is a HIGH priority endpoint for context management.
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

        # Create new context card
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

        return ContextCardResponse(
            id=context_card.id,
            session_id=context_card.session_id,
            title=context_card.title,
            description=context_card.description,
            content=context_card.content,
            source=context_card.source,
            tokens=context_card.tokens,
            is_active=context_card.is_active,
            created_at=context_card.created_at,
            updated_at=context_card.updated_at,
        )

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
    """
    Get context cards for a session.
    This is a HIGH priority endpoint for context display.
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

        # Get active context cards for this session
        context_cards = (
            db.query(ContextCard)
            .filter(ContextCard.session_id == db_session.id, ContextCard.is_active)
            .order_by(ContextCard.created_at.desc())
            .all()
        )

        return [
            ContextCardResponse(
                id=card.id,
                session_id=card.session_id,
                title=card.title,
                description=card.description,
                content=card.content,
                source=card.source,
                tokens=card.tokens,
                is_active=card.is_active,
                created_at=card.created_at,
                updated_at=card.updated_at,
            )
            for card in context_cards
        ]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context cards: {str(e)}",
        )


# MEDIUM PRIORITY ENDPOINTS


@router.get(
    "/sessions/{session_id}/file-deps/session",
    response_model=List[FileItemResponse],
)
async def get_file_dependencies_for_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get file items for a session (matches frontend FileItem interface)"""
    try:
        # Ensure session exists and belongs to user
        db_session = SessionService.ensure_owned_session(
            db, current_user.id, session_id
        )

        # Get file items for this session
        file_items = (
            db.query(FileItem)
            .filter(FileItem.session_id == db_session.id)
            .order_by(FileItem.created_at.desc())
            .all()
        )

        logger.info(
            f"[FileDeps] Found {len(file_items)} file items for session {session_id}"
        )

        # Convert to response format
        response_items = []
        for item in file_items:
            response_item = FileItemResponse(
                id=str(item.id),
                name=item.name,
                path=item.path,
                type=item.type,
                tokens=item.tokens,
                category=item.category,
                isDirectory=item.is_directory,
                content_size=item.content_size,
                created_at=item.created_at.isoformat() if item.created_at else None,
                file_name=item.file_name,
                file_path=item.file_path,
                file_type=item.file_type,
                content_summary=item.content_summary,
            )
            response_items.append(response_item)

        logger.info(
            f"[FileDeps] Returning {len(response_items)} file items for session {session_id}"
        )
        return response_items

    except Exception as e:
        logger.error(
            f"[FileDeps] Failed to get file dependencies for session {session_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file dependencies: {str(e)}",
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

    mode_metadata = db_session.mode_metadata or {}
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
        if (
            mode_metadata.get("gathering_state") in {"probes_done", "complete"}
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
    if (
        request.resume_execution
        and was_waiting_for_input
        and not pending_question_ids
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
            context_cards=request.context_cards or [],
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


# FILE DEPENDENCIES ENDPOINTS - Consolidated from filedeps.py
# =================================================================================


def _estimate_tokens_for_file(file_path: str, content_size: int) -> int:
    """Estimate tokens for a file based on its size and type."""
    # Get file extension
    ext = Path(file_path).suffix.lower()

    # Different ratios for different file types
    token_ratios = {
        ".py": 4,  # Python: ~4 chars per token
        ".js": 4,  # JavaScript: ~4 chars per token
        ".ts": 4,  # TypeScript: ~4 chars per token
        ".jsx": 4,  # React JSX: ~4 chars per token
        ".tsx": 4,  # React TSX: ~4 chars per token
        ".md": 3,  # Markdown: ~3 chars per token
        ".json": 5,  # JSON: ~5 chars per token
        ".yaml": 3,  # YAML: ~3 chars per token
        ".yml": 3,  # YAML: ~3 chars per token
        ".txt": 3,  # Text: ~3 chars per token
        ".html": 4,  # HTML: ~4 chars per token
        ".css": 4,  # CSS: ~4 chars per token
        ".sql": 4,  # SQL: ~4 chars per token
        ".sh": 4,  # Shell: ~4 chars per token
    }

    ratio = token_ratios.get(ext, 4)  # Default to 4 chars per token
    return max(1, content_size // ratio)


def _extract_repo_info_from_url(repo_url: str) -> tuple[str, str]:
    """Extract repository name and owner from GitHub URL."""
    parsed = urlparse(repo_url)
    path_parts = parsed.path.strip("/").split("/")

    if len(path_parts) >= 2:
        owner = path_parts[0]
        repo_name = path_parts[1].replace(".git", "")
        return repo_name, owner
    else:
        return "unknown", "unknown"


def _get_or_create_repository(
    db: Session,
    repo_url: str,
    repo_name: str,
    repo_owner: str,
    user_id: int,
    html_url: Optional[str] = None,
    clone_url: Optional[str] = None,
    description: Optional[str] = None,
    language: Optional[str] = None,
    stargazers_count: Optional[int] = 0,
    forks_count: Optional[int] = 0,
    open_issues_count: Optional[int] = 0,
    default_branch: Optional[str] = None,
    github_created_at: Optional[datetime] = None,
    github_updated_at: Optional[datetime] = None,
    pushed_at: Optional[datetime] = None,
) -> Repository:
    """Retrieve existing repository metadata or create a new record."""
    # First try to find existing repository by URL and user
    repository = (
        db.query(Repository)
        .filter(Repository.repo_url == repo_url, Repository.user_id == user_id)
        .first()
    )

    if repository:
        # Update existing repository with latest data if provided
        if html_url is not None:
            repository.html_url = html_url
        if clone_url is not None:
            repository.clone_url = clone_url
        if description is not None:
            repository.description = description
        if language is not None:
            repository.language = language
        if stargazers_count is not None:
            repository.stargazers_count = stargazers_count
        if forks_count is not None:
            repository.forks_count = forks_count
        if open_issues_count is not None:
            repository.open_issues_count = open_issues_count
        if default_branch is not None:
            repository.default_branch = default_branch
        if github_created_at is not None:
            repository.github_created_at = github_created_at
        if github_updated_at is not None:
            repository.github_updated_at = github_updated_at
        if pushed_at is not None:
            repository.pushed_at = pushed_at
        db.commit()
        return repository

    # Create new repository record
    repository = Repository(
        user_id=user_id,
        name=repo_name,
        owner=repo_owner,
        full_name=f"{repo_owner}/{repo_name}",
        repo_url=repo_url,
        html_url=html_url or repo_url,  # Default to repo_url if html_url is None
        clone_url=clone_url or repo_url,  # Default to repo_url if clone_url is None
        description=description,
        language=language,
        stargazers_count=stargazers_count or 0,
        forks_count=forks_count or 0,
        open_issues_count=open_issues_count or 0,
        default_branch=default_branch,
        github_created_at=github_created_at,
        github_updated_at=github_updated_at,
        pushed_at=pushed_at,
    )
    db.add(repository)
    db.flush()
    return repository


def _build_file_tree(files_data: Any, repo_name: str) -> List[Dict[str, Any]]:
    """Build hierarchical file tree from GitIngest data.

    The helper accepts the normalised snapshot payload returned by
    :class:`RepositorySnapshotService` (``RepositoryFile`` instances) or the
    legacy dict structure containing a ``"files"`` key.  The output is a list
    of dictionaries compatible with the frontend tree component.
    """

    def _normalise_entry(entry: Any) -> Optional[Dict[str, Any]]:
        if isinstance(entry, RepositoryFile):
            return {
                "path": entry.path,
                "type": entry.category or "INTERNAL",
                "Category": entry.category or "INTERNAL",
                "content_size": entry.content_size or entry.size,
                "file_name": entry.file_name,
            }

        if isinstance(entry, dict):
            path = entry.get("path") or ""
            category = (
                entry.get("type")
                or entry.get("Category")
                or entry.get("category")
                or "INTERNAL"
            )
            content_size = entry.get("content_size") or entry.get("size") or 0
            try:
                content_size = int(content_size)
            except (TypeError, ValueError):
                content_size = 0

            return {
                "path": path,
                "type": category,
                "Category": category,
                "content_size": content_size,
                "file_name": entry.get("file_name")
                or (path.split("/")[-1] if path else ""),
            }

        return None

    file_tree: List[Dict[str, Any]] = []

    if not files_data:
        return file_tree

    if isinstance(files_data, dict):
        raw_files = files_data.get("files", [])
    else:
        raw_files = files_data

    # Group files by directory
    dir_structure: Dict[str, Any] = {}

    for raw_entry in raw_files:
        file_info = _normalise_entry(raw_entry)
        if not file_info:
            continue

        path = file_info.get("path") or ""
        if not path:
            continue

        path_parts = [part for part in path.split("/") if part]
        if not path_parts:
            continue

        current_dir = dir_structure

        for part in path_parts[:-1]:  # All parts except the filename
            if part not in current_dir:
                current_dir[part] = {"__files__": []}
            current_dir = current_dir[part]

        # Add file to the appropriate directory
        current_dir.setdefault("__files__", [])

        file_name = path_parts[-1]
        content_size = file_info.get("content_size") or 0
        file_item = {
            "id": path,
            "name": file_name,
            "type": file_info.get("type", "INTERNAL"),
            "Category": file_info.get("Category", "INTERNAL"),
            "tokens": _estimate_tokens_for_file(path, content_size),
            "isDirectory": False,
            "path": path,
        }
        current_dir["__files__"].append(file_item)

    # Convert directory structure to FileItem format
    def convert_to_file_items(
        dir_dict: Dict[str, Any], current_path: str = ""
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        for name, content in dir_dict.items():
            if name == "__files__":
                items.extend(content)
            else:
                full_path = f"{current_path}/{name}" if current_path else name
                children = convert_to_file_items(content, full_path)

                # Calculate total tokens for directory
                total_tokens = sum(
                    child.get("tokens", 0)
                    for child in children
                    if not child.get("isDirectory", False)
                )

                dir_item = {
                    "id": full_path,
                    "name": name,
                    "type": "INTERNAL",
                    "Category": "Directory",
                    "tokens": total_tokens,
                    "isDirectory": True,
                    "children": children,
                    "expanded": False,
                }
                items.append(dir_item)

        return items

    return convert_to_file_items(dir_structure)


def _save_file_analysis_to_db(
    db: Session,
    repository_id: int,
    raw_data: Dict[str, Any],
    processed_data: Dict[str, Any],
    total_files: int,
    total_tokens: int,
    max_file_size: int,
):
    """Log file analysis results instead of storing in database."""
    print(f"Repository analysis completed for repository {repository_id}:")
    print(f"  - Total files processed: {total_files}")
    print(f"  - Total tokens: {total_tokens}")
    print(f"  - Max file size: {max_file_size}")
    print(f"  - Files saved as embeddings: {len(processed_data.get('files', []))}")

    # No database storage - just logging
    return None


def _save_file_items_and_embeddings(
    db: Session,
    repository_id: int,
    file_tree: List[Dict[str, Any]],
    session_id: int,
    content_lookup: Optional[Dict[str, str]] = None,
    generate_embeddings: bool = True,
    embedding_pipeline: Optional[EmbeddingPipeline] = None,
) -> Tuple[List[FileItem], List[FileEmbedding]]:
    """Save file items and their embeddings separately.

    content_lookup maps file paths to full file contents for embedding creation.
    """

    saved_file_items = []
    saved_embeddings = []

    if generate_embeddings and embedding_pipeline is None:
        embedding_pipeline = EmbeddingPipeline()

    def process_recursive(items: List[Dict[str, Any]]):
        for item_data in items:
            # Create FileItem record
            file_item = FileItem(
                session_id=session_id,
                repository_id=repository_id,
                name=item_data.get("name", ""),
                path=item_data.get("path"),
                type=item_data.get("type", "INTERNAL"),
                tokens=item_data.get("tokens", 0),
                category=item_data.get("Category", "unknown"),
                is_directory=item_data.get("isDirectory", False),
                content_size=item_data.get("content_size"),
                file_name=item_data.get("file_name"),
                file_path=item_data.get("file_path"),
                file_type=item_data.get("file_type"),
                content_summary=item_data.get("content_summary"),
            )
            db.add(file_item)
            db.flush()  # Get the ID

            saved_file_items.append(file_item)

            # If it's a file (not a directory), create embeddings using content map
            if (
                generate_embeddings
                and not item_data.get("isDirectory", False)
                and embedding_pipeline
            ):
                fpath = item_data.get("path") or item_data.get("file_path")
                if content_lookup and fpath:
                    content = content_lookup.get(fpath)
                else:
                    content = None

                if content:
                    repo_file = RepositoryFile(
                        path=fpath,
                        content=content,
                        size=len(content),
                        content_size=len(content),
                        category=item_data.get("Category"),
                    )
                    try:
                        chunks = embedding_pipeline.process_file(repo_file)
                        for chunk in chunks:
                            embedding = FileEmbedding(
                                session_id=session_id,
                                repository_id=repository_id,
                                file_item_id=file_item.id,
                                file_path=chunk.file_path,
                                file_name=chunk.file_name,
                                chunk_index=chunk.chunk_index,
                                chunk_text=chunk.chunk_text,
                                embedding=Vector(chunk.embedding),
                                tokens=chunk.tokens,
                                file_metadata=chunk.metadata,
                            )
                            db.add(embedding)
                            saved_embeddings.append(embedding)
                    except Exception as embed_error:
                        logger.warning(
                            f"Failed to create embeddings for {fpath}: {embed_error}"
                        )

            # Process children recursively
            if item_data.get("isDirectory", False) and "children" in item_data:
                process_recursive(item_data["children"])

    process_recursive(file_tree)
    return saved_file_items, saved_embeddings


def _collect_issue_context(db: Session, chat_session: ChatSession) -> Dict[str, Any]:
    """Build repository and conversation context for GitHub issue creation."""

    context: Dict[str, Any] = {}

    if chat_session.repo_owner or chat_session.repo_name:
        context["repository_info"] = {
            "owner": chat_session.repo_owner,
            "name": chat_session.repo_name,
            "branch": chat_session.repo_branch,
            "url": f"https://github.com/{chat_session.repo_owner}/{chat_session.repo_name}"
            if chat_session.repo_owner and chat_session.repo_name
            else None,
        }

    if isinstance(chat_session.repo_context, dict):
        fam = chat_session.repo_context.get("facts_and_memories")
        if fam:
            context["facts_memories"] = fam

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(8)
        .all()
    )
    if messages:
        context["conversation"] = [
            {
                "author": message.sender_type or message.role or "user",
                "text": message.message_text,
            }
            for message in reversed(messages)
        ]

    files = (
        db.query(FileItem)
        .filter(
            FileItem.session_id == chat_session.id, FileItem.is_directory.is_(False)
        )
        .order_by(FileItem.tokens.desc())
        .limit(5)
        .all()
    )
    if files:
        context["files"] = [
            {
                "path": file.path,
                "tokens": file.tokens,
            }
            for file in files
            if file.path
        ]

    return context


async def _index_repository_for_session_background(
    session_uuid: str,
    user_id: int,
    repo_owner: str,
    repo_name: str,
    repo_branch: str = "main",
    max_file_size: Optional[int] = None,
    generate_embeddings: bool = True,
    generate_facts_memories: bool = False,
) -> None:
    """Background task: extract the repository, chunk files, create embeddings and persist.

    This runs after session creation when index_codebase=True.
    """
    db = SessionLocal()
    try:
        logger.info(
            f"[Index] Starting indexing for session={session_uuid} repo={repo_owner}/{repo_name}"
        )

        # Validate repository parameters
        if not repo_owner or not repo_owner.strip():
            logger.error(f"[Index] Invalid repo_owner: '{repo_owner}'")
            return

        if not repo_name or not repo_name.strip():
            logger.error(f"[Index] Invalid repo_name: '{repo_name}'")
            return

        # Sanitize repository parameters (remove any leading/trailing whitespace)
        repo_owner = repo_owner.strip()
        repo_name = repo_name.strip()

        logger.info(
            f"[Index] Sanitized repo_owner='{repo_owner}', repo_name='{repo_name}'"
        )

        # Verify the session exists and is owned by the user
        chat_session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_uuid, ChatSession.user_id == user_id
            )
            .first()
        )
        if not chat_session:
            logger.warning(
                f"[Index] Session not found or not owned by user: {session_uuid}"
            )
            return

        # Construct repository URL with validation
        repo_url = f"https://github.com/{repo_owner}/{repo_name}"
        logger.info(f"[Index] Constructed repo URL: {repo_url}")

        # Validate URL format
        if not repo_url.startswith("https://github.com/"):
            logger.error(f"[Index] Invalid repo URL format: {repo_url}")
            return

        # Extract repository content via GitIngest
        logger.info(f"[Index] Starting GitIngest extraction for: {repo_url}")
        try:
            snapshot = await RepositorySnapshotService.fetch(
                repo_url=repo_url, max_file_size=max_file_size
            )
            # raw_repo not used; snapshot retains raw_response if needed later
            files_data = snapshot.files
            logger.info(
                f"[Index] GitIngest extraction completed, {len(files_data)} files returned"
            )
        except Exception as extract_error:
            logger.error(
                f"[Index] GitIngest extraction failed with exception: {extract_error}"
            )
            return

        # Fetch repo metadata (best effort)
        try:
            gh = GitHubOps(db)
            meta = await gh.fetch_repository_info_detailed(
                repo_owner, repo_name, user_id
            )
        except Exception as e:
            logger.warning(f"[Index] Failed to fetch repo metadata: {e}")
            meta = {}

        repository = _get_or_create_repository(
            db,
            repo_url,
            repo_name,
            repo_owner,
            user_id,
            html_url=meta.get("html_url"),
            clone_url=meta.get("clone_url"),
            description=meta.get("description"),
            language=meta.get("language"),
            stargazers_count=meta.get("stargazers_count", 0),
            forks_count=meta.get("forks_count", 0),
            open_issues_count=meta.get("open_issues_count", 0),
            default_branch=meta.get("default_branch", repo_branch),
            github_created_at=meta.get("created_at"),
            github_updated_at=meta.get("updated_at"),
            pushed_at=meta.get("pushed_at"),
        )

        # Build and persist file tree context for session and repository caches
        file_tree = _build_file_tree(files_data, repo_name)
        file_tree_payload = {
            "tree": file_tree,
            "repo": f"{repo_owner}/{repo_name}",
            "file_count": len(files_data),
            "source": "gitingest",
            "generated_at": utc_now().isoformat(),
        }

        # Update per-session repository context with the tree
        session_repo_context = chat_session.repo_context
        if isinstance(session_repo_context, str):
            try:
                session_repo_context = json.loads(session_repo_context)
            except json.JSONDecodeError:
                session_repo_context = {}
        if not isinstance(session_repo_context, dict):
            session_repo_context = {}
        session_repo_context["file_tree"] = file_tree_payload
        chat_session.repo_context = session_repo_context

        # Merge the tree into repository cache metadata and on-disk cache
        repository_github_context = repository.github_context
        if isinstance(repository_github_context, str):
            try:
                repository_github_context = json.loads(repository_github_context)
            except json.JSONDecodeError:
                repository_github_context = {}
        if not isinstance(repository_github_context, dict):
            repository_github_context = {}
        repository_github_context["file_tree"] = file_tree_payload

        try:
            cache_payload = LLMService.read_github_context_cache(
                repository_github_context
            )
        except Exception as cache_read_error:  # pragma: no cover - defensive logging
            logger.warning(
                "[Index] Failed to read GitHub context cache for %s/%s: %s",
                repo_owner,
                repo_name,
                cache_read_error,
            )
            cache_payload = None

        if cache_payload is not None:
            cache_payload["file_tree"] = file_tree_payload
            try:
                updated_metadata = LLMService.write_github_context_cache(
                    repository_github_context, cache_payload
                )
                if isinstance(updated_metadata, dict):
                    repository_github_context.update(updated_metadata)
            except (
                Exception
            ) as cache_write_error:  # pragma: no cover - defensive logging
                logger.warning(
                    "[Index] Failed to update GitHub context cache for %s/%s: %s",
                    repo_owner,
                    repo_name,
                    cache_write_error,
                )

        repository_github_context["file_tree"] = file_tree_payload
        repository.github_context = repository_github_context
        repository.github_context_updated_at = utc_now()

        # Save file items directly from files_data
        saved_file_items = []
        saved_embeddings = []

        embedding_pipeline = EmbeddingPipeline() if generate_embeddings else None

        logger.info(f"[Index] Processing {len(files_data)} files for database storage")

        for i, repo_file in enumerate(files_data):
            try:
                file_path = repo_file.path
                logger.debug(
                    f"[Index] Processing file {i + 1}/{len(files_data)}: {file_path}"
                )

                # Create FileItem record
                file_item = FileItem(
                    session_id=chat_session.id,
                    repository_id=repository.id,
                    name=repo_file.file_name or "unknown",
                    path=repo_file.path,
                    type=repo_file.category or "INTERNAL",
                    tokens=_estimate_tokens_for_file(
                        repo_file.path,
                        repo_file.content_size,
                    ),
                    category=repo_file.category or "unknown",
                    is_directory=False,
                    content_size=repo_file.content_size,
                    file_name=repo_file.file_name,
                    file_path=repo_file.path,
                    file_type=repo_file.category,
                )
                db.add(file_item)
                db.flush()  # Get the ID
                saved_file_items.append(file_item)
                logger.debug(
                    f"[Index] Successfully saved file item: {file_path} (ID: {file_item.id})"
                )

                # Create embeddings for the file content when requested
                if (
                    generate_embeddings
                    and embedding_pipeline
                    and repo_file.content
                    and repo_file.content.strip()
                ):
                    try:
                        chunks = embedding_pipeline.process_file(repo_file)
                        for chunk in chunks:
                            embedding = FileEmbedding(
                                session_id=chat_session.id,
                                repository_id=repository.id,
                                file_item_id=file_item.id,
                                file_path=chunk.file_path,
                                file_name=chunk.file_name,
                                chunk_index=chunk.chunk_index,
                                chunk_text=chunk.chunk_text,
                                embedding=Vector(chunk.embedding),
                                tokens=chunk.tokens,
                                file_metadata=chunk.metadata,
                            )
                            db.add(embedding)
                            saved_embeddings.append(embedding)
                    except Exception as embed_error:
                        logger.warning(
                            f"[Index] Failed to create embeddings for {repo_file.path}: {embed_error}"
                        )
                        # Continue processing other files

            except Exception as file_error:
                logger.warning(
                    f"[Index] Failed to process file {getattr(repo_file, 'path', 'unknown')}: {file_error}"
                )
                continue

        logger.info(
            f"[Index] Saved {len(saved_file_items)} file items and {len(saved_embeddings)} embeddings"
        )

        try:
            db.commit()
            logger.info(
                f"[Index] Database commit successful for session {session_uuid}"
            )
        except Exception as commit_error:
            logger.error(f"[Index] Database commit failed: {commit_error}")
            db.rollback()
            return

        if generate_facts_memories:
            try:
                logger.info(
                    f"[Index] Generating repository facts for session {session_uuid}"
                )
                facts_service = FactsAndMemoriesService()
                result = await facts_service.generate_facts(
                    snapshot=snapshot,
                )
                MemoryService.store_facts(
                    chat_session,
                    facts=result.facts,
                    highlights=result.highlights,
                )
                db.commit()
                logger.info(
                    f"[Index] Repository facts stored for session {session_uuid}"
                )
            except Exception as fam_error:
                logger.warning(
                    f"[Index] Repository facts generation failed for session {session_uuid}: {fam_error}"
                )
                db.rollback()

        logger.info(
            f"[Index] Completed indexing for session {session_uuid}: {len(saved_file_items)} files processed"
        )
    except Exception as e:
        logger.error(f"[Index] Unexpected indexing error: {e}")
        db.rollback()
    finally:
        db.close()


# ============================================================================
# ISSUES ENDPOINTS - Consolidated under sessions context
# ============================================================================


@router.post("/sessions/{session_id}/issues/create-with-context", response_model=dict)
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
            file_context=request.get("file_context", []),
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
        from models import UserIssue

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
                "context_card_id": issue.context_card_id,
                "context_cards": issue.context_cards,
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
        from models import UserIssue

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
            "context_card_id": issue.context_card_id,
            "context_cards": issue.context_cards,
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
        from daifuUserAgent.IssueOps import IssueService

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
            "context_card_id": updated_issue.context_card_id,
            "context_cards": updated_issue.context_cards,
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
        # Use the consolidated IssueOps service directly to avoid wrapper arg mismatch
        from .IssueOps import IssueService as IssueOpsService
        from .session_service import SessionService

        # Ensure session exists and belongs to user
        db_session = SessionService.ensure_owned_session(db, current_user.id, session_id)

        # Create GitHub issue using consolidated IssueOps (context assembled internally)
        issue_service = IssueOpsService(db)
        result = await issue_service.create_github_issue_from_user_issue(
            current_user.id,
            issue_id,
            context_bundle=None,
        )

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

        db_session.architect_issue_url = result.github_issue_url
        db_session.architect_issue_number = result.github_issue_number

        issue_ref = (
            f"#{result.github_issue_number}"
            if result.github_issue_number is not None
            else result.github_issue_url
        )
        execution_objective = "\n\n".join(
            part
            for part in [
                f"Resolve GitHub issue {issue_ref}: {result.title}",
                f"GitHub issue URL: {result.github_issue_url}",
                f"Repository: {result.repo_owner}/{result.repo_name}@{db_session.repo_branch or 'main'}",
                f"Issue details:\n{result.issue_text_raw or result.description or ''}",
            ]
            if part and part.strip()
        )
        db_session.mode_metadata = {
            **(db_session.mode_metadata or {}),
            "pending_resume_objective": execution_objective,
            "seed_github_issue_url": result.github_issue_url,
            "seed_github_issue_number": result.github_issue_number,
            "seed_user_issue_id": result.issue_id,
        }

        # Phase 1 completion tracking: issue creation event.
        lifecycle = get_realtime_lifecycle_service()
        lifecycle.mark_issue_created(
            db,
            session_public_id=session_id,
            user_id=current_user.id,
            issue_url=result.github_issue_url,
            issue_number=result.github_issue_number,
        )
        db.commit()

        execution_started = False
        execution_id = None
        execution_status = None
        execution_error = None

        realtime_flags = get_realtime_feature_flags()
        if realtime_flags.mode_orchestrator_enabled:
            try:
                status_payload = await get_session_execution_orchestrator().start_execution(
                    db,
                    session=db_session,
                    user_id=current_user.id,
                    objective=execution_objective,
                )
                execution_started = True
                execution_id = str(status_payload.get("execution_id") or "")
                execution_status = str(status_payload.get("status") or "")
            except ExecutionConflictError as exc:
                execution_error = str(exc)
                execution_status = db_session.mode_status
                logger.info(
                    "GitHub issue %s created, but execution was not started for session %s: %s",
                    result.github_issue_url,
                    session_id,
                    exc,
                )
            except Exception as exc:
                execution_error = str(exc)
                execution_status = db_session.mode_status
                logger.exception(
                    "GitHub issue %s created, but execution auto-start failed for session %s",
                    result.github_issue_url,
                    session_id,
                )

        message = f"GitHub issue created successfully: {result.github_issue_url}"
        if execution_started and execution_id:
            message = f"{message}. 3-mode execution started: {execution_id}"
        elif execution_error:
            message = f"{message}. Execution was not started: {execution_error}"

        return CreateGitHubIssueResponse(
            success=True,
            github_url=result.github_issue_url,
            github_issue_number=result.github_issue_number,
            message=message,
            execution_started=execution_started,
            execution_id=execution_id,
            execution_status=execution_status,
            execution_error=execution_error,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Handle specific IssueOps errors with appropriate HTTP status codes
        error_str = str(e).lower()
        if any(
            keyword in error_str
            for keyword in [
                "403",
                "forbidden",
                "permission",
                "access denied",
                "not authorized",
            ]
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e),
            )
        elif "404" in error_str or "not found" in error_str:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )


# ============================================================================
# TRAJECTORY VIEWER ENDPOINTS
# ============================================================================


@router.get("/sessions/{session_id}/trajectories", response_model=List[Dict[str, Any]])
async def get_session_trajectories(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all trajectories for a session from solve runs.
    """
    try:
        from models import Solve

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
    "/sessions/{session_id}/trajectories/{run_id}", response_model=Dict[str, Any]
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
        from models import Solve, SolveRun

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
