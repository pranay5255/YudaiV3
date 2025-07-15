"""
Unified Issue Service and API for User-Generated Issues

This module provides both the service logic and FastAPI routes for handling 
user-generated issues that are created from chat conversations and can be 
processed by agents to create GitHub issues.
"""

import uuid
import time
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, or_
from fastapi import APIRouter, HTTPException, Depends, status, Query

from ..models import (
    UserIssue, User, ChatSession, ContextCard,
    CreateUserIssueRequest, UserIssueResponse,
    ChatRequest, CreateChatMessageRequest
)
from ..db.database import get_db
from ..auth.github_oauth import get_current_user
from ..github.github_api import create_issue as create_github_issue, GitHubAPIError

# Create FastAPI router
router = APIRouter(prefix="/issues", tags=["issues"])


class IssueService:
    """Service class for managing user issues"""
    
    @staticmethod
    def create_user_issue(
        db: Session,
        user_id: int,
        request: CreateUserIssueRequest
    ) -> UserIssueResponse:
        """Create a new user issue from chat context"""
        # Generate unique issue ID
        issue_id = str(uuid.uuid4())
        
        # Get chat session if conversation_id is provided
        chat_session_id = None
        if request.conversation_id:
            chat_session = db.query(ChatSession).filter(
                and_(
                    ChatSession.user_id == user_id,
                    ChatSession.session_id == request.conversation_id
                )
            ).first()
            if chat_session:
                chat_session_id = chat_session.id
        
        # Create the issue
        issue = UserIssue(
            user_id=user_id,
            issue_id=issue_id,
            context_card_id=request.context_card_id,
            issue_text_raw=request.issue_text_raw,
            issue_steps=request.issue_steps,
            title=request.title,
            description=request.description,
            conversation_id=request.conversation_id,
            chat_session_id=chat_session_id,
            context_cards=request.context_cards,
            ideas=request.ideas,
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            priority=request.priority,
            status="pending"
        )
        
        db.add(issue)
        db.commit()
        db.refresh(issue)
        
        return UserIssueResponse.model_validate(issue)
    
    @staticmethod
    def get_user_issue(
        db: Session,
        user_id: int,
        issue_id: str
    ) -> Optional[UserIssueResponse]:
        """Get a specific user issue by issue_id"""
        issue = db.query(UserIssue).filter(
            and_(
                UserIssue.user_id == user_id,
                UserIssue.issue_id == issue_id
            )
        ).first()
        
        if not issue:
            return None
        
        return UserIssueResponse.model_validate(issue)
    
    @staticmethod
    def get_user_issues(
        db: Session,
        user_id: int,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None,
        limit: int = 50
    ) -> List[UserIssueResponse]:
        """Get user issues with optional filtering"""
        query = db.query(UserIssue).filter(UserIssue.user_id == user_id)
        
        if status:
            query = query.filter(UserIssue.status == status)
        if priority:
            query = query.filter(UserIssue.priority == priority)
        if repo_owner:
            query = query.filter(UserIssue.repo_owner == repo_owner)
        if repo_name:
            query = query.filter(UserIssue.repo_name == repo_name)
        
        issues = query.order_by(desc(UserIssue.created_at)).limit(limit).all()
        return [UserIssueResponse.model_validate(issue) for issue in issues]
    
    @staticmethod
    def update_issue_status(
        db: Session,
        user_id: int,
        issue_id: str,
        status: str,
        agent_response: Optional[str] = None,
        processing_time: Optional[float] = None,
        tokens_used: int = 0
    ) -> Optional[UserIssueResponse]:
        """Update issue status and processing metadata"""
        issue = db.query(UserIssue).filter(
            and_(
                UserIssue.user_id == user_id,
                UserIssue.issue_id == issue_id
            )
        ).first()
        
        if not issue:
            return None
        
        issue.status = status
        if agent_response:
            issue.agent_response = agent_response
        if processing_time:
            issue.processing_time = processing_time
        if tokens_used > 0:
            issue.tokens_used = tokens_used
        
        if status in ["completed", "failed"]:
            issue.processed_at = datetime.utcnow()
        
        issue.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(issue)
        
        return UserIssueResponse.model_validate(issue)
    
    @staticmethod
    def create_issue_from_chat(
        db: Session,
        user_id: int,
        chat_request: ChatRequest
    ) -> UserIssueResponse:
        """Create an issue from a chat request with context"""
        # Extract issue information from chat request
        title = f"Issue from chat: {chat_request.message.content[:50]}..."
        
        # Create issue request
        issue_request = CreateUserIssueRequest(
            title=title,
            issue_text_raw=chat_request.message.content,
            description=f"Generated from chat conversation: {chat_request.conversation_id}",
            conversation_id=chat_request.conversation_id,
            context_cards=chat_request.context_cards,
            repo_owner=chat_request.repo_owner,
            repo_name=chat_request.repo_name
        )
        
        return IssueService.create_user_issue(db, user_id, issue_request)
    
    @staticmethod
    async def create_github_issue_from_user_issue(
        db: Session,
        user_id: int,
        issue_id: str,
        current_user: User
    ) -> Optional[UserIssueResponse]:
        """Convert a user issue to a GitHub issue"""
        # Get the user issue
        issue = db.query(UserIssue).filter(
            and_(
                UserIssue.user_id == user_id,
                UserIssue.issue_id == issue_id
            )
        ).first()
        
        if not issue or not issue.repo_owner or not issue.repo_name:
            return None
        
        try:
            # Prepare GitHub issue content
            github_body = f"{issue.description or ''}\n\n"
            github_body += f"**Raw Issue Text:**\n{issue.issue_text_raw}\n\n"
            
            if issue.issue_steps:
                github_body += "**Steps:**\n"
                for i, step in enumerate(issue.issue_steps, 1):
                    github_body += f"{i}. {step}\n"
                github_body += "\n"
            
            if issue.context_cards:
                github_body += f"**Context Cards:** {', '.join(issue.context_cards)}\n"
            
            if issue.conversation_id:
                github_body += f"**Generated from conversation:** {issue.conversation_id}\n"
            
            # Create GitHub issue
            github_issue = await create_github_issue(
                owner=issue.repo_owner,
                repo_name=issue.repo_name,
                title=issue.title,
                body=github_body,
                current_user=current_user,
                db=db
            )
            
            # Update user issue with GitHub info
            issue.github_issue_url = github_issue.html_url
            issue.github_issue_number = github_issue.number
            issue.status = "completed"
            issue.processed_at = datetime.utcnow()
            issue.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(issue)
            
            return UserIssueResponse.model_validate(issue)
            
        except GitHubAPIError as e:
            # Update issue status to failed
            issue.status = "failed"
            issue.agent_response = f"Failed to create GitHub issue: {str(e)}"
            issue.processed_at = datetime.utcnow()
            issue.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(issue)
            
            return UserIssueResponse.model_validate(issue)
    
    @staticmethod
    def get_issue_statistics(
        db: Session,
        user_id: int
    ) -> Dict[str, Any]:
        """Get statistics for user issues"""
        total_issues = db.query(UserIssue).filter(UserIssue.user_id == user_id).count()
        
        pending_issues = db.query(UserIssue).filter(
            and_(
                UserIssue.user_id == user_id,
                UserIssue.status == "pending"
            )
        ).count()
        
        completed_issues = db.query(UserIssue).filter(
            and_(
                UserIssue.user_id == user_id,
                UserIssue.status == "completed"
            )
        ).count()
        
        failed_issues = db.query(UserIssue).filter(
            and_(
                UserIssue.user_id == user_id,
                UserIssue.status == "failed"
            )
        ).count()
        
        return {
            "total_issues": total_issues,
            "pending_issues": pending_issues,
            "completed_issues": completed_issues,
            "failed_issues": failed_issues,
            "success_rate": completed_issues / total_issues if total_issues > 0 else 0
        }


# API Routes
@router.post("/", response_model=UserIssueResponse)
async def create_issue(
    request: CreateUserIssueRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new user issue"""
    try:
        return IssueService.create_user_issue(db, current_user.id, request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create issue: {str(e)}"
        )


@router.get("/", response_model=List[UserIssueResponse])
async def get_issues(
    status: Optional[str] = Query(None, description="Filter by status"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    repo_owner: Optional[str] = Query(None, description="Filter by repository owner"),
    repo_name: Optional[str] = Query(None, description="Filter by repository name"),
    limit: int = Query(50, ge=1, le=100, description="Number of issues to return"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get user issues with optional filtering"""
    try:
        return IssueService.get_user_issues(
            db, current_user.id, status, priority, repo_owner, repo_name, limit
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve issues: {str(e)}"
        )


@router.get("/{issue_id}", response_model=UserIssueResponse)
async def get_issue(
    issue_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific user issue by ID"""
    issue = IssueService.get_user_issue(db, current_user.id, issue_id)
    
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    return issue


@router.put("/{issue_id}/status")
async def update_issue_status(
    issue_id: str,
    status: str,
    agent_response: Optional[str] = None,
    processing_time: Optional[float] = None,
    tokens_used: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update issue status and processing metadata"""
    issue = IssueService.update_issue_status(
        db, current_user.id, issue_id, status, agent_response, processing_time, tokens_used
    )
    
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Issue not found"
        )
    
    return issue


@router.post("/{issue_id}/convert-to-github", response_model=UserIssueResponse)
async def convert_to_github_issue(
    issue_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Convert a user issue to a GitHub issue"""
    try:
        result = await IssueService.create_github_issue_from_user_issue(
            db, current_user.id, issue_id, current_user
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Issue not found or missing repository information"
            )
        
        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to convert to GitHub issue: {str(e)}"
        )


@router.post("/from-chat", response_model=UserIssueResponse)
async def create_issue_from_chat(
    chat_request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create an issue from a chat request"""
    try:
        return IssueService.create_issue_from_chat(db, current_user.id, chat_request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create issue from chat: {str(e)}"
        )


@router.get("/statistics", response_model=Dict[str, Any])
async def get_issue_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get statistics for user issues"""
    try:
        return IssueService.get_issue_statistics(db, current_user.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        ) 