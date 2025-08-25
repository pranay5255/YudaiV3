"""FastAPI router for interacting with the DAifu agent."""

from __future__ import annotations

import time
import uuid
from typing import List, Tuple

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
from models import (
    ChatRequest,
    User,
)
from sqlalchemy.orm import Session

from .llm_service import LLMService


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


# In-memory storage for conversation history (temporary solution)
# In a production environment, this should be replaced with proper database storage
conversation_history: dict[str, List[Tuple[str, str]]] = {}


def get_conversation_history(session_id: str, limit: int = 50) -> List[Tuple[str, str]]:
    """Get conversation history for a session"""
    return conversation_history.get(session_id, [])[-limit:]


def add_to_conversation_history(session_id: str, sender: str, message: str):
    """Add a message to conversation history"""
    if session_id not in conversation_history:
        conversation_history[session_id] = []
    conversation_history[session_id].append((sender, message))


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

        # Add user message to conversation history
        user_message = request.message.content
        add_to_conversation_history(session_id, "User", user_message)
        
        # Get conversation history for context
        history = get_conversation_history(session_id, 50)
        
        # Generate AI response
        reply = await LLMService.generate_response_with_history(
            repo_context=github_context,
            conversation_history=history,
            github_data=github_data
        )
        
        # Add assistant response to conversation history
        add_to_conversation_history(session_id, "DAifu", reply)
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000
        
        # Generate a unique message ID
        message_id = str(uuid.uuid4())
        
        return {
            "reply": reply,
            "conversation": history + [("User", user_message), ("DAifu", reply)],
            "message_id": message_id,
            "processing_time": processing_time,
            "session_id": session_id,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}",
        )
