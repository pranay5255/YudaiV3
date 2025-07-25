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

from models import (
    UserIssue, User, ChatSession, ContextCard,
    CreateUserIssueRequest, UserIssueResponse,
    ChatRequest, CreateChatMessageRequest, FileItemResponse,
    FileContextItem, ChatContextMessage, CreateIssueWithContextRequest, GitHubIssuePreview
)
from db.database import get_db
from auth.github_oauth import get_current_user
from github.github_api import create_issue as create_github_issue, GitHubAPIError

# Add new imports at the top
import os
import requests
import json
from daifuUserAgent.architectAgent.promptTemplate import build_architect_prompt
import re

# Import Langfuse utilities for telemetry
from utils.langfuse_utils import (
    architect_agent_trace, 
    issue_service_trace, 
    log_llm_generation,
    log_github_api_call
)



# Create FastAPI router
router = APIRouter(tags=["issues"])


class IssueService:
    """Service class for managing user issues"""
    
    @staticmethod
    @issue_service_trace
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
    @issue_service_trace
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
            
            # Prepare GitHub API input for logging
            github_input = {
                "owner": issue.repo_owner,
                "repo_name": issue.repo_name,
                "title": issue.title,
                "body_length": len(github_body),
                "user_issue_id": issue.issue_id
            }
            
            # Create GitHub issue
            github_issue = await create_github_issue(
                owner=issue.repo_owner,
                repo_name=issue.repo_name,
                title=issue.title,
                body=github_body,
                current_user=current_user,
                db=db
            )
            
            # Log successful GitHub API call
            log_github_api_call(
                action="create_issue",
                repository=f"{issue.repo_owner}/{issue.repo_name}",
                input_data=github_input,
                output_data={
                    "issue_number": github_issue.number,
                    "issue_url": github_issue.html_url,
                    "status": "success"
                },
                success=True
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
            # Log failed GitHub API call
            log_github_api_call(
                action="create_issue",
                repository=f"{issue.repo_owner}/{issue.repo_name}",
                input_data=github_input,
                output_data={},
                success=False,
                error=str(e)
            )
            
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

    @staticmethod
    @architect_agent_trace
    def generate_github_issue_preview(
        request: CreateIssueWithContextRequest,
        use_sample_data: bool = False
    ) -> GitHubIssuePreview:
        """Generate a GitHub issue preview with optional sample data or via LLM (architect agent)"""
        
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
        # --- LLM/Architect Agent Integration ---
        # Prepare conversation context
        conversation_context = "\n".join(
            f"{'Code' if m.isCode else 'User'}: {m.content}" for m in request.chat_messages
        )
        # Prepare file dependencies context
        file_dependencies_context = "\n".join(
            f"{f.name} ({f.type}, {f.tokens} tokens): {f.category}" for f in request.file_context
        )
        # Code-aware context - could include file contents or summaries
        code_aware_context = ""
        if request.file_context:
            code_aware_context = f"Total files analyzed: {len(request.file_context)}\n"
            code_aware_context += f"Total tokens: {sum(f.tokens for f in request.file_context)}\n"
            code_aware_context += "Key files: " + ", ".join([f.name for f in request.file_context[:10]])

        # Build prompt using the Yudai Architect agent
        prompt = build_architect_prompt(
            conversation_context=conversation_context,
            file_dependencies_context=file_dependencies_context,
            code_aware_context=code_aware_context,
        )
        
        # Add specific instruction for JSON output
        prompt += "\n\nIMPORTANT: Respond with ONLY a valid JSON object as specified in the output_format section. Do not include any text before or after the JSON."
        
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
            
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        
        model = "deepseek/deepseek-r1-0528:free"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,  # Lower temperature for more consistent JSON output
            "max_tokens": 2000
        }
        
        # Log the LLM input for telemetry
        input_data = {
            "prompt_length": len(prompt),
            "chat_messages_count": len(request.chat_messages),
            "file_context_count": len(request.file_context),
            "model": model,
            "request_title": request.title
        }
        
        try:
            start_time = time.time()
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=120,  # Increased timeout for better reliability
            )
            resp.raise_for_status()
            
            response_data = resp.json()
            llm_reply = response_data["choices"][0]["message"]["content"].strip()
            execution_time = time.time() - start_time
            
            # Extract usage information if available
            usage = response_data.get("usage", {})
            tokens_used = usage.get("total_tokens", 0)
            
            # Log the LLM generation for telemetry
            output_data = {
                "response_length": len(llm_reply),
                "tokens_used": tokens_used,
                "execution_time": execution_time
            }
            
            log_llm_generation(
                name="architect_agent_github_issue_generation",
                model=model,
                input_data=input_data,
                output_data=output_data,
                metadata={
                    "service": "issue_service",
                    "agent": "yudai_architect",
                    "use_case": "github_issue_preview"
                },
                tokens_used=tokens_used
            )
            
            # --- Parse JSON output from Architect Agent ---
            try:
                # Try to parse as direct JSON first
                issue_data = json.loads(llm_reply)
                
                # Validate required fields
                if not all(key in issue_data for key in ["title", "body", "labels"]):
                    raise ValueError("Missing required fields in JSON response")
                
                # Extract data with defaults
                title = issue_data.get("title", request.title)[:255]  # Limit title length
                body = issue_data.get("body", "")
                labels = issue_data.get("labels", ["yudai-assistant"])
                assignees = issue_data.get("assignees", [])
                metadata = issue_data.get("metadata", {})
                
                # Ensure yudai-assistant label is always present
                if "yudai-assistant" not in labels:
                    labels.append("yudai-assistant")
                
                return GitHubIssuePreview(
                    title=title,
                    body=body,
                    labels=labels,
                    assignees=assignees,
                    repository_info=request.repository_info,
                    metadata={
                        **metadata,
                        "chat_messages_count": len(request.chat_messages),
                        "file_context_count": len(request.file_context),
                        "total_tokens": sum(f.tokens for f in request.file_context),
                        "generated_at": datetime.utcnow().isoformat(),
                        "generation_method": "architect_agent_json",
                        "llm_tokens_used": tokens_used,
                        "llm_execution_time": execution_time
                    }
                )
                
            except json.JSONDecodeError:
                # Fallback: try to extract JSON from within the response
                json_match = re.search(r'\{.*\}', llm_reply, re.DOTALL)
                if json_match:
                    try:
                        issue_data = json.loads(json_match.group())
                        title = issue_data.get("title", request.title)[:255]
                        body = issue_data.get("body", llm_reply)
                        labels = issue_data.get("labels", ["yudai-assistant"])
                        assignees = issue_data.get("assignees", [])
                        
                        if "yudai-assistant" not in labels:
                            labels.append("yudai-assistant")
                        
                        return GitHubIssuePreview(
                            title=title,
                            body=body,
                            labels=labels,
                            assignees=assignees,
                            repository_info=request.repository_info,
                            metadata={
                                "chat_messages_count": len(request.chat_messages),
                                "file_context_count": len(request.file_context),
                                "total_tokens": sum(f.tokens for f in request.file_context),
                                "generated_at": datetime.utcnow().isoformat(),
                                "generation_method": "architect_agent_json_extracted",
                                "llm_tokens_used": tokens_used,
                                "llm_execution_time": execution_time
                            }
                        )
                    except json.JSONDecodeError:
                        pass
                
                # Last fallback: treat as markdown response
                return GitHubIssuePreview(
                    title=request.title,
                    body=llm_reply,
                    labels=["yudai-assistant", "needs-review"],
                    assignees=[],
                    repository_info=request.repository_info,
                    metadata={
                        "chat_messages_count": len(request.chat_messages),
                        "file_context_count": len(request.file_context),
                        "total_tokens": sum(f.tokens for f in request.file_context),
                        "generated_at": datetime.utcnow().isoformat(),
                        "generation_method": "architect_agent_markdown_fallback",
                        "llm_tokens_used": tokens_used,
                        "llm_execution_time": execution_time,
                        "parsing_error": "Could not parse JSON output"
                    }
                )
        except Exception as e:
            # Fallback to static template if LLM fails
            context_summary = ""
            if request.chat_messages:
                context_summary += f"## Chat Context\n"
                for msg in request.chat_messages[-5:]:  # Last 5 messages
                    role = "User" if not msg.isCode else "Code"
                    context_summary += f"**{role}**: {msg.content[:100]}...\n\n"
            if request.file_context:
                context_summary += f"## File Context\n"
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

*Generated from chat and file dependency analysis*
""",
                labels=["enhancement", "yudai-assistant"],
                assignees=[],
                repository_info=request.repository_info,
                metadata={
                    "chat_messages_count": len(request.chat_messages),
                    "file_context_count": len(request.file_context),
                    "total_tokens": sum(f.tokens for f in request.file_context),
                    "generated_at": datetime.utcnow().isoformat(),
                    "generation_method": "context_analysis|llm_fallback",
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
        github_preview = IssueService.generate_github_issue_preview(request, use_sample_data)
        
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