"""FastAPI router for interacting with the DAifu agent."""

from __future__ import annotations

import time

from auth.github_oauth import get_current_user
from db.database import get_db
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from github.github_api import (
    get_repository_branches,
    get_repository_commits,
    get_repository_details,
    get_repository_issues,
    get_repository_pulls,
)
from issueChatServices.chat_service import ChatService
from issueChatServices.issue_service import IssueService
from models import (
    ChatRequest,
    User,
)
from sqlalchemy.orm import Session

from .llm_service import LLMService
from .message_service import MessageService


async def get_github_context(owner: str, repo: str, current_user: User, db: Session) -> str:
    """Get GitHub repository context by querying various GitHub APIs"""
    try:
        # Get repository details
        repo_details = await get_repository_details(owner, repo, current_user, db)
        
        # Get recent issues
        issues = await get_repository_issues(owner, repo, "open", current_user, db)
        issue_summary = f"Open Issues: {len(issues)}\n"
        
        # Get recent PRs
        pulls = await get_repository_pulls(owner, repo, "open", current_user, db)
        pr_summary = f"Open PRs: {len(pulls)}\n"
        
        # Get recent commits on main branch
        commits = await get_repository_commits(owner, repo, "main", current_user, db)
        commit_summary = f"Recent Commits: {len(commits)}\n"
        
        # Get branches
        branches = await get_repository_branches(owner, repo, current_user, db)
        branch_summary = f"Active Branches: {len(branches)}\n"
        
        return (
            f"Repository: {repo_details.full_name}\n"
            f"Description: {repo_details.description}\n"
            f"Default Branch: {repo_details.default_branch}\n"
            f"{issue_summary}"
            f"{pr_summary}"
            f"{commit_summary}" 
            f"{branch_summary}"
        )
    except Exception as e:
        return f"Error getting GitHub context: {str(e)}"


async def get_github_context_data(owner: str, repo: str, current_user: User, db: Session) -> tuple:
    """Get raw GitHub repository data for prompt building"""
    try:
        # Get repository details
        repo_details = await get_repository_details(owner, repo, current_user, db)
        
        # Get recent issues
        issues = await get_repository_issues(owner, repo, "open", current_user, db)
        
        # Get recent PRs
        pulls = await get_repository_pulls(owner, repo, "open", current_user, db)
        
        # Get recent commits on main branch
        commits = await get_repository_commits(owner, repo, "main", current_user, db)
        
        return repo_details, commits, issues, pulls
    except Exception:
        # Return empty data structures on error
        empty_repo = {"full_name": "Repository", "description": "", "default_branch": "", 
                     "languages": {}, "topics": [], "license": None, "stargazers_count": 0, 
                     "forks_count": 0, "open_issues_count": 0, "html_url": ""}
        return empty_repo, [], [], []

router = APIRouter()
@router.post("/chat")
async def chat_daifu(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Chat Endpoint - HTTP API Only
    
    This endpoint processes chat messages and returns responses synchronously.
    """
    start_time = time.time()
    
    # Validate session_id is provided
    if not request.session_id or not request.session_id.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id is required and cannot be empty"
        )
    
    session_id = request.session_id.strip()
    
    try:
        # Get GitHub context if repository info is provided
        github_context = ""
        repo_owner = None
        repo_name = None
        
        # Check for repository object first (preferred format)
        if request.repository and request.repository.get("owner") and request.repository.get("name"):
            repo_owner = request.repository["owner"]
            repo_name = request.repository["name"]
        
        # Get GitHub context if we have repository information
        github_context = ""
        github_data = None
        if repo_owner and repo_name:
            github_context = await get_github_context(
                repo_owner,
                repo_name,
                current_user,
                db
            )
            github_data = await get_github_context_data(
                repo_owner,
                repo_name,
                current_user,
                db
            )

        # Store user message
        user_message_db = MessageService.store_user_message(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            content=request.message.content,
            is_code=request.message.is_code,
            context_cards=request.context_cards
        )
        
        # Synchronous mode: Process immediately and return response
        # Get conversation history
        history_messages = ChatService.get_chat_messages(
            db, current_user.id, session_id, limit=50
        )
        
        # Convert to format expected by prompt builder
        history = []
        for msg in history_messages:
            sender = "User" if msg.sender_type == "user" else "DAifu"
            history.append((sender, msg.message_text))
        
        # Generate AI response
        reply = await LLMService.generate_response_with_history(
            repo_context=github_context,
            conversation_history=history,
            github_data=github_data
        )
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        # Store assistant response
        MessageService.store_assistant_message(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            content=reply,
            processing_time=processing_time
        )
        
        return {
            "reply": reply,
            "conversation": history + [("User", request.message.content), ("DAifu", reply)],
            "message_id": user_message_db.message_id,
            "processing_time": processing_time,
            "session_id": session_id,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        # Store error message
        MessageService.store_error_message(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            error_message=str(e),
            error_type="system"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}",
        )


@router.post("/create-issue")
async def create_issue_from_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an issue from a chat conversation."""
    try:
        # Create the issue from the chat request
        issue = IssueService.create_issue_from_chat(db, current_user.id, request)

        return {
            "success": True,
            "issue": issue,
            "message": f"Issue created with ID: {issue.issue_id}",
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create issue: {str(e)}",
        )
