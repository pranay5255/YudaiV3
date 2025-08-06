"""
Unified Issue Service and API for User-Generated Issues

This module provides both the service logic and FastAPI routes for handling 
user-generated issues that are created from chat conversations and can be 
processed by agents to create GitHub issues.
"""

import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from auth.github_oauth import get_current_user
from daifuUserAgent.architectAgent.promptTemplate import build_architect_prompt
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, status
from github.github_api import GitHubAPIError
from github.github_api import create_issue as create_github_issue
from models import (
    ChatRequest,
    ChatSession,
    CreateUserIssueRequest,
    User,
    UserIssue,
    UserIssueResponse,
)

# Add new imports at the top
from pydantic import BaseModel, Field
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session


# Use local unified data models for frontend-backend consistency
class FileContextItem(BaseModel):
    id: str
    name: str
    type: str
    tokens: int
    category: str
    path: Optional[str] = None

class ChatContextMessage(BaseModel):
    id: str
    content: str
    isCode: bool
    timestamp: str

class CreateIssueWithContextRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    chat_messages: List[ChatContextMessage] = Field(default_factory=list)
    file_context: List[FileContextItem] = Field(default_factory=list)
    repository_info: Optional[Dict[str, str]] = Field(None)  # owner, name, branch
    priority: str = Field(default="medium")

class GitHubIssuePreview(BaseModel):
    title: str
    body: str
    labels: List[str] = Field(default_factory=list)
    assignees: List[str] = Field(default_factory=list)
    repository_info: Optional[Dict[str, str]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

# Create FastAPI router
router = APIRouter(tags=["issues"])


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
        
        # Get chat session if session_id is provided
        chat_session_id = None
        if request.session_id:
            chat_session = db.query(ChatSession).filter(
                and_(
                    ChatSession.user_id == user_id,
                    ChatSession.session_id == request.session_id
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
            session_id=request.session_id,
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
        """
        Create an issue from a chat request with context
        Links to the session for unified state management
        """
        # Extract repository info from request
        repo_owner = chat_request.repo_owner
        repo_name = chat_request.repo_name
        
        # Create comprehensive issue request
        title = f"Issue from chat: {chat_request.message.content[:50]}..."
        description = f"Generated from chat session: {chat_request.session_id}"
        
        issue_request = CreateUserIssueRequest(
            title=title,
            issue_text_raw=chat_request.message.content,
            description=description,
            session_id=chat_request.session_id,
            context_cards=chat_request.context_cards,
            repo_owner=repo_owner,
            repo_name=repo_name
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
            
            if issue.session_id:
                github_body += f"**Generated from session:** {issue.session_id}\n"
            
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
        """Get comprehensive statistics for user issues with session context"""
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
        
        # Get issues linked to sessions
        issues_with_sessions = db.query(UserIssue).filter(
            and_(
                UserIssue.user_id == user_id,
                UserIssue.session_id.isnot(None)
            )
        ).count()
        
        # Get average processing time
        avg_processing_time = db.query(func.avg(UserIssue.processing_time)).filter(
            and_(
                UserIssue.user_id == user_id,
                UserIssue.processing_time.isnot(None)
            )
        ).scalar() or 0
        
        return {
            "total_issues": total_issues,
            "pending_issues": pending_issues,
            "completed_issues": completed_issues,
            "failed_issues": failed_issues,
            "issues_with_sessions": issues_with_sessions,
            "avg_processing_time": float(avg_processing_time),
            "success_rate": completed_issues / total_issues if total_issues > 0 else 0,
            "session_integration_rate": issues_with_sessions / total_issues if total_issues > 0 else 0
        }

    @staticmethod
    def generate_github_issue_preview(
        request: CreateIssueWithContextRequest,
        use_sample_data: bool = False,
        db: Optional[Session] = None,
        user_id: Optional[int] = None
    ) -> GitHubIssuePreview:
        """Generate a GitHub issue preview using the architect agent with session context"""
        
        if use_sample_data:
            # Generate sample data when LLM is not available
            return GitHubIssuePreview(
                title=f"[Feature Request] {request.title}",
                body=f"""## Description
{request.description or 'Implement new functionality based on user requirements.'}

## Context from Chat Conversation
{len(request.chat_messages)} messages were analyzed to understand the requirements.

## File Dependencies Analyzed
- **Total files reviewed**: {len(request.file_context)}
- **Total tokens**: {sum(f.tokens for f in request.file_context)}
- **Key files**: {', '.join([f.name for f in request.file_context[:5]])}

## Implementation Steps
1. **Analysis Phase**: Review existing codebase structure
2. **Design Phase**: Create implementation plan based on context
3. **Development Phase**: Implement the requested functionality
4. **Testing Phase**: Write comprehensive tests
5. **Documentation Phase**: Update relevant documentation

## Technical Requirements
- Maintain compatibility with existing codebase
- Follow project coding standards
- Include proper error handling
- Add appropriate unit tests

## Acceptance Criteria
- [ ] Feature works as described in chat conversation
- [ ] Code follows project patterns and standards
- [ ] Tests are added and passing
- [ ] Documentation is updated

## Priority
{request.priority.capitalize()}

---
*This issue was auto-generated from chat conversation and file dependency analysis.*
""",
                labels=["enhancement", "yudai-assistant", f"priority-{request.priority}"],
                assignees=[],
                repository_info=request.repository_info,
                metadata={
                    "chat_messages_count": len(request.chat_messages),
                    "file_context_count": len(request.file_context),
                    "total_tokens": sum(f.tokens for f in request.file_context),
                    "generated_at": datetime.utcnow().isoformat(),
                    "generation_method": "sample_data"
                }
            )
        
        # Enhanced context gathering with session information
        conversation_context = ""
        file_dependencies_context = ""
        code_aware_context = ""
        
        # Prepare conversation context
        if request.chat_messages:
            conversation_context = "\n".join(
                f"{'Code' if m.isCode else 'User'}: {m.content}" for m in request.chat_messages
            )
        
        # Prepare file dependencies context
        if request.file_context:
            file_dependencies_context = "\n".join(
                f"{f.name} ({f.type}, {f.tokens} tokens): {f.category}" for f in request.file_context
            )
        
        # Enhanced context gathering from session if available
        # Session management is not implemented, so we skip session context enhancement
        
        # Build architect prompt
        prompt = build_architect_prompt(
            conversation_context=conversation_context,
            file_dependencies_context=file_dependencies_context,
            code_aware_context=code_aware_context,
        )
        
        # Make LLM call to architect agent
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not configured")
            
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        body = {
            "model": "deepseek/deepseek-r1-0528:free",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=60,
            )
            resp.raise_for_status()
            llm_reply = resp.json()["choices"][0]["message"]["content"].strip()
            
            # Parse LLM output for GitHub issue fields
            title = request.title
            labels = ["yudai-assistant", "architect-agent"]
            assignees = []
            body_text = llm_reply
            
            # Try to extract a markdown H1 or 'Title:'
            title_match = re.search(r"^# (.+)$", llm_reply, re.MULTILINE)
            if title_match:
                title = title_match.group(1).strip()
                body_text = llm_reply[title_match.end():].strip()
            else:
                title_match = re.search(r"^Title:\s*(.+)$", llm_reply, re.MULTILINE)
                if title_match:
                    title = title_match.group(1).strip()
                    body_text = llm_reply[title_match.end():].strip()
            
            # Extract labels if present
            labels_match = re.search(r"Labels?:\s*\[(.*?)\]", llm_reply, re.IGNORECASE)
            if labels_match:
                extracted_labels = [label.strip().strip('"') for label in labels_match.group(1).split(",") if label.strip()]
                labels.extend(extracted_labels)
            
            # Extract assignees if present
            assignees_match = re.search(r"Assignees?:\s*\[(.*?)\]", llm_reply, re.IGNORECASE)
            if assignees_match:
                assignees = [a.strip().strip('"') for a in assignees_match.group(1).split(",") if a.strip()]
            
            # Add priority-based label
            labels.append(f"priority-{request.priority}")
            
            return GitHubIssuePreview(
                title=title,
                body=body_text,
                labels=list(set(labels)),  # Remove duplicates
                assignees=assignees,
                repository_info=request.repository_info,
                metadata={
                    "chat_messages_count": len(request.chat_messages),
                    "file_context_count": len(request.file_context),
                    "total_tokens": sum(f.tokens for f in request.file_context),
                    "generated_at": datetime.utcnow().isoformat(),
                    "generation_method": "architect_agent_llm",
                    "enhanced_with_session": bool(db and user_id)
                }
            )
            
        except Exception as e:
            print(f"LLM call failed, using fallback: {e}")
            # Fallback to context analysis
            context_summary = ""
            if request.chat_messages:
                context_summary += "## Chat Context\n"
                for msg in request.chat_messages[-5:]:  # Last 5 messages
                    role = "User" if not msg.isCode else "Code"
                    context_summary += f"**{role}**: {msg.content[:100]}...\n\n"
            
            if request.file_context:
                context_summary += "## File Context\n"
                for file in request.file_context[:10]:  # Top 10 files
                    context_summary += f"- **{file.name}** ({file.type}, {file.tokens} tokens): {file.category}\n"
            
            return GitHubIssuePreview(
                title=request.title,
                body=f"""{request.description or ''}

{context_summary}

## Implementation Notes
Based on the analyzed context, this issue requires attention to the following files and components.

## Next Steps
1. Review the chat conversation for detailed requirements
2. Analyze the file dependencies for implementation approach
3. Create detailed implementation plan
4. Begin development with proper testing

*Generated from chat and file dependency analysis (LLM fallback)*
""",
                labels=["enhancement", "yudai-assistant", f"priority-{request.priority}"],
                assignees=[],
                repository_info=request.repository_info,
                metadata={
                    "chat_messages_count": len(request.chat_messages),
                    "file_context_count": len(request.file_context),
                    "total_tokens": sum(f.tokens for f in request.file_context),
                    "generated_at": datetime.utcnow().isoformat(),
                    "generation_method": "context_analysis_fallback",
                    "error": str(e)
                }
            )


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


@router.post("/create-with-context", response_model=Dict[str, Any])
async def create_issue_with_context(
    request: CreateIssueWithContextRequest,
    preview_only: bool = Query(default=False, description="Only generate preview without saving"),
    use_sample_data: bool = Query(default=True, description="Use sample data when LLM is unavailable"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a user issue with comprehensive context from chat and file dependencies.
    Optionally generate a GitHub issue preview.
    """
    try:
        # Generate GitHub issue preview
        github_preview = IssueService.generate_github_issue_preview(request, use_sample_data, db, current_user.id)
        
        if preview_only:
            return {
                "success": True,
                "preview_only": True,
                "github_preview": github_preview.dict(),
                "message": "GitHub issue preview generated successfully"
            }
        
        # Create the user issue in database
        issue_request = CreateUserIssueRequest(
            title=request.title,
            issue_text_raw=github_preview.body,
            description=request.description,
            context_cards=[f.id for f in request.file_context],  # Use file IDs as context cards
            repo_owner=request.repository_info.get("owner") if request.repository_info else None,
            repo_name=request.repository_info.get("name") if request.repository_info else None,
            priority=request.priority,
            issue_steps=[
                "Analyze chat conversation context",
                "Review file dependencies",
                "Design implementation approach",
                "Implement functionality",
                "Add tests and documentation"
            ]
        )
        
        user_issue = IssueService.create_user_issue(db, current_user.id, issue_request)
        
        # Session management is not implemented, so we skip session linking
        
        return {
            "success": True,
            "preview_only": False,
            "user_issue": user_issue.dict(),
            "github_preview": github_preview.dict(),
            "message": f"Issue created successfully with ID: {user_issue.issue_id}"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create issue with context: {str(e)}"
        )


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


@router.post("/{issue_id}/create-github-issue")
async def create_github_issue_from_user_issue(
    issue_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Convert a user issue to an actual GitHub issue"""
    try:
        result = await IssueService.create_github_issue_from_user_issue(
            db, current_user.id, issue_id, current_user
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Issue not found or missing repository information"
            )
        
        return {
            "success": True,
            "issue": result.dict(),
            "github_url": result.github_issue_url,
            "message": f"GitHub issue created successfully: {result.github_issue_url}"
        }
        
    except GitHubAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create GitHub issue: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create GitHub issue: {str(e)}"
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