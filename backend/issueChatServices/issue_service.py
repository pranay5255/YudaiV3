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
    ChatRequest, CreateChatMessageRequest, FileItemResponse
)
from sqlalchemy import and_
from db.database import get_db
from auth.github_oauth import get_current_user
from auth.auth_utils import validate_user_access, require_authentication
from github.github_api import create_issue as create_github_issue, GitHubAPIError
from issueChatServices.chat_service import SessionService

# Add new imports at the top
from pydantic import BaseModel, Field
from daifuUserAgent.architectAgent import CodeInspectorAgent, CodeInspectorService
import json

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

class CreateIssueFromSessionRequest(BaseModel):
    session_id: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(None)
    priority: str = Field(default="medium")
    use_code_inspector: bool = Field(default=True, description="Use CodeInspector agent for analysis")
    create_github_issue: bool = Field(default=False, description="Create actual GitHub issue")

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
    def create_issue_from_session(
        db: Session,
        user_id: int,
        session_id: str,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium"
    ) -> UserIssueResponse:
        """Create an issue from a session with full context"""
        # Get session context
        session_context = SessionService.get_session_context(db, user_id, session_id)
        if not session_context:
            raise ValueError(f"Session {session_id} not found")
        
        # Get session info
        session = session_context.session
        
        # Gather all context cards from session messages
        context_cards = session_context.context_cards
        
        # Create issue text from session messages
        issue_text_raw = f"Session: {session.title or session.session_id}\n\n"
        issue_text_raw += f"Repository: {session.repo_owner}/{session.repo_name} (branch: {session.repo_branch})\n\n"
        
        if description:
            issue_text_raw += f"Description: {description}\n\n"
        
        issue_text_raw += "Chat History:\n"
        for msg in session_context.messages[-10:]:  # Last 10 messages
            role = "User" if msg.sender_type == "user" else "Assistant"
            issue_text_raw += f"{role}: {msg.message_text}\n"
        
        # Create issue request
        issue_request = CreateUserIssueRequest(
            title=title,
            issue_text_raw=issue_text_raw,
            description=description or f"Issue created from session: {session.session_id}",
            conversation_id=session_id,
            context_cards=context_cards,
            repo_owner=session.repo_owner,
            repo_name=session.repo_name,
            priority=priority,
            issue_steps=[
                "Review session context and chat history",
                "Analyze repository structure",
                "Design implementation approach",
                "Implement functionality",
                "Add tests and documentation"
            ]
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

    @staticmethod
    def generate_github_issue_preview(
        request: CreateIssueWithContextRequest,
        use_sample_data: bool = False
    ) -> GitHubIssuePreview:
        """Generate a GitHub issue preview with optional sample data"""
        
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
        
        # Generate real issue from context (this would call LLM in production)
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
                "generation_method": "context_analysis"
            }
        )

    @staticmethod
    async def create_issue_from_session_with_analysis(
        db: Session,
        user_id: int,
        request: CreateIssueFromSessionRequest
    ) -> UserIssueResponse:
        """
        Create an issue from a session with CodeInspector agent analysis.
        
        This method:
        1. Validates the session exists and belongs to the user
        2. Gathers complete session context (messages, repo info, context cards)
        3. Uses CodeInspectorAgent with prompts to analyze the context
        4. Creates a UserIssue with enhanced analysis
        5. Optionally creates a GitHub issue via GitHub API
        """
        
        # Validate session exists BEFORE any processing
        session_context = SessionService.get_session_context(db, user_id, request.session_id)
        if not session_context:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Session '{request.session_id}' not found or invalid"
            )
        
        session = session_context.session
        
        # Build session bundle for analysis
        session_bundle = {
            "session_info": {
                "id": session.session_id,
                "title": session.title,
                "repo_owner": session.repo_owner,
                "repo_name": session.repo_name,
                "repo_branch": session.repo_branch,
                "repo_context": session.repo_context
            },
            "messages": [
                {
                    "id": msg.message_id,
                    "content": msg.message_text,
                    "sender_type": msg.sender_type,
                    "role": msg.role,
                    "is_code": msg.is_code,
                    "tokens": msg.tokens,
                    "timestamp": msg.created_at.isoformat(),
                    "context_cards": msg.context_cards or []
                }
                for msg in session_context.messages
            ],
            "context_cards": session_context.context_cards,
            "repository_info": session_context.repository_info
        }
        
        # Prepare issue text with session analysis
        issue_text_raw = f"## Session Analysis\n"
        issue_text_raw += f"**Session ID**: {session.session_id}\n"
        issue_text_raw += f"**Repository**: {session.repo_owner}/{session.repo_name} (branch: {session.repo_branch})\n"
        issue_text_raw += f"**Total Messages**: {len(session_context.messages)}\n"
        issue_text_raw += f"**Context Cards**: {len(session_context.context_cards)}\n\n"
        
        if request.description:
            issue_text_raw += f"## Description\n{request.description}\n\n"
        
        # Add recent chat context
        issue_text_raw += "## Recent Chat Context\n"
        recent_messages = session_context.messages[-5:]  # Last 5 messages
        for msg in recent_messages:
            role = "User" if msg.sender_type == "user" else "Assistant"
            content_preview = msg.message_text[:200] + "..." if len(msg.message_text) > 200 else msg.message_text
            issue_text_raw += f"**{role}**: {content_preview}\n\n"
        
        # Use CodeInspector agent for enhanced analysis if enabled
        agent_analysis = None
        complexity_score = None
        estimated_hours = None
        github_issue_data = None
        
        if request.use_code_inspector:
            try:
                # Initialize CodeInspector agent
                code_inspector = CodeInspectorAgent()
                
                # Build codebase context for analysis using session data
                codebase_context = f"""
## Session Context Analysis

### Repository Information
- Owner: {session.repo_owner}
- Name: {session.repo_name}
- Branch: {session.repo_branch}
- Full Name: {session.repo_owner}/{session.repo_name}

### Chat Messages ({len(session_context.messages)} total)
"""
                
                # Add significant messages to context
                for msg in session_context.messages:
                    if msg.tokens > 20:  # Only include substantial messages
                        role = "User" if msg.sender_type == "user" else "Assistant"
                        codebase_context += f"**{role}**: {msg.message_text[:500]}...\n\n"
                
                if session_context.context_cards:
                    codebase_context += f"\n### Context Cards\n"
                    for card in session_context.context_cards:
                        codebase_context += f"- {card}\n"
                
                # Use CodeInspector prompt template to generate GitHub issue
                from daifuUserAgent.architectAgent.promptTemplate import build_code_inspector_prompt
                
                repository_info = {
                    'owner': session.repo_owner,
                    'name': session.repo_name,
                    'language': 'Unknown',  # Could be enhanced with actual repo data
                    'description': f'Repository for session: {session.session_id}'
                }
                
                focus_areas = [
                    f"User request: {request.title}",
                    f"Session context with {len(session_context.messages)} messages",
                    "Implementation requirements from chat conversation"
                ]
                
                # Generate comprehensive analysis prompt
                analysis_prompt = build_code_inspector_prompt(
                    codebase_context=codebase_context,
                    analysis_type="comprehensive",
                    focus_areas=focus_areas,
                    repository_info=repository_info
                )
                
                # Add specific instruction to create ONE focused issue
                analysis_prompt += f"""

## Specific Task
Based on the session context and user request "{request.title}", create exactly ONE actionable GitHub issue that addresses the main requirement. Focus on:

1. The primary task from the chat conversation
2. Technical implementation details mentioned
3. Any specific files or components discussed
4. Clear acceptance criteria based on the conversation

Generate exactly one JSON issue object focused on the main user requirement.
"""
                
                # Get analysis from CodeInspector
                agent_analysis = code_inspector._make_llm_call(analysis_prompt, max_tokens=3000)
                
                # Parse the GitHub issue from the analysis
                github_issue_data = code_inspector._parse_issues_from_response(agent_analysis)
                
                if github_issue_data:
                    # Use the first (and ideally only) issue
                    github_issue = github_issue_data[0]
                    
                    # Extract complexity and effort estimates
                    complexity_score = github_issue.get('complexity', 'M')
                    estimated_hours = github_issue.get('estimated_hours', 8)
                    
                    # Override title and description with user input if provided
                    github_issue['title'] = request.title
                    if request.description:
                        github_issue['body'] = f"{request.description}\n\n{github_issue.get('body', '')}"
                    
                    # Add session context to the GitHub issue body
                    enhanced_body = github_issue.get('body', '')
                    enhanced_body += f"\n\n## Session Context\n"
                    enhanced_body += f"**Session ID**: {session.session_id}\n"
                    enhanced_body += f"**Repository**: {session.repo_owner}/{session.repo_name}\n"
                    enhanced_body += f"**Branch**: {session.repo_branch}\n"
                    enhanced_body += f"**Messages**: {len(session_context.messages)}\n"
                    
                    # Add key conversation points
                    if recent_messages:
                        enhanced_body += f"\n### Key Discussion Points\n"
                        for msg in recent_messages[-3:]:  # Last 3 messages
                            role = "User" if msg.sender_type == "user" else "Assistant"
                            content = msg.message_text[:150] + "..." if len(msg.message_text) > 150 else msg.message_text
                            enhanced_body += f"- **{role}**: {content}\n"
                    
                    enhanced_body += f"\n---\n*Generated from session analysis with CodeInspector agent*"
                    github_issue['body'] = enhanced_body
                    
                    # Add agent analysis to issue text
                    issue_text_raw += f"\n## CodeInspector Analysis\n{agent_analysis}\n\n"
                    issue_text_raw += f"\n## Generated GitHub Issue\n```json\n{json.dumps(github_issue, indent=2)}\n```\n"
                else:
                    # Fallback if no issues were parsed
                    complexity_score = "M"
                    estimated_hours = 8
                    agent_analysis = f"Analysis completed but no specific issues generated. Raw response: {agent_analysis[:500]}..."
                
            except Exception as e:
                # Log error but don't fail the issue creation
                print(f"CodeInspector analysis failed: {str(e)}")
                agent_analysis = f"Analysis failed: {str(e)}"
                complexity_score = "M"
                estimated_hours = 8
        else:
            # Default values when not using CodeInspector
            complexity_score = "M"
            estimated_hours = 8
        
        # Add session metadata
        issue_text_raw += f"\n## Session Bundle Metadata\n"
        issue_text_raw += f"```json\n{json.dumps(session_bundle, indent=2, default=str)}\n```\n"
        
        # Create issue request with enhanced data
        issue_request = CreateUserIssueRequest(
            title=request.title,
            issue_text_raw=issue_text_raw,
            description=request.description or f"Issue created from session analysis: {session.session_id}",
            conversation_id=request.session_id,
            context_cards=session_context.context_cards,
            repo_owner=session.repo_owner,
            repo_name=session.repo_name,
            priority=request.priority,
            issue_steps=[
                "Analyze session context and requirements",
                "Review repository structure and codebase", 
                "Design implementation approach",
                "Implement functionality with proper error handling",
                "Add comprehensive tests and documentation",
                "Review and validate implementation"
            ]
        )
        
        # Create the UserIssue
        user_issue = IssueService.create_user_issue(db, user_id, issue_request)
        
        # Update with additional analysis data
        if agent_analysis:
            issue_obj = db.query(UserIssue).filter(
                and_(
                    UserIssue.user_id == user_id,
                    UserIssue.issue_id == user_issue.issue_id
                )
            ).first()
            
            if issue_obj:
                issue_obj.agent_response = agent_analysis
                issue_obj.complexity_score = complexity_score
                issue_obj.estimated_hours = estimated_hours
                issue_obj.status = "ready_for_swe"  # Enhanced issues are ready for SWE processing
                
                # Create GitHub issue if requested
                github_issue_url = None
                github_issue_number = None
                
                if request.create_github_issue and github_issue_data and session.repo_owner and session.repo_name:
                    try:
                        # Get the current user for GitHub API call
                        current_user = db.query(User).filter(User.id == user_id).first()
                        if current_user:
                            github_issue = github_issue_data[0]
                            
                            # Create GitHub issue using the GitHub API
                            created_github_issue = await create_github_issue(
                                owner=session.repo_owner,
                                repo_name=session.repo_name,
                                title=github_issue['title'],
                                body=github_issue['body'],
                                labels=github_issue.get('labels', ['yudai-assistant', 'session-generated']),
                                assignees=github_issue.get('assignees', []),
                                current_user=current_user,
                                db=db
                            )
                            
                            # Update UserIssue with GitHub info
                            issue_obj.github_issue_url = created_github_issue.html_url
                            issue_obj.github_issue_number = created_github_issue.number
                            issue_obj.status = "completed"  # Mark as completed since GitHub issue is created
                            
                            github_issue_url = created_github_issue.html_url
                            github_issue_number = created_github_issue.number
                            
                    except GitHubAPIError as e:
                        print(f"Failed to create GitHub issue: {str(e)}")
                        # Don't fail the whole operation, just log the error
                        issue_obj.agent_response += f"\n\nGitHub Issue Creation Failed: {str(e)}"
                    except Exception as e:
                        print(f"Unexpected error creating GitHub issue: {str(e)}")
                        issue_obj.agent_response += f"\n\nUnexpected error creating GitHub issue: {str(e)}"
                
                db.commit()
                db.refresh(issue_obj)
                
                # Return updated response
                user_issue = UserIssueResponse.model_validate(issue_obj)
        
        return user_issue


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


# Removed redundant /issues/from-chat endpoint
# Enhanced session-based issue creation via /issues/from-session-enhanced provides better functionality


@router.post("/from-session", response_model=UserIssueResponse)
async def create_issue_from_session(
    session_id: str,
    title: str,
    description: Optional[str] = None,
    priority: str = "medium",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create an issue from a session with full context"""
    try:
        return IssueService.create_issue_from_session(db, current_user.id, session_id, title, description, priority)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create issue from session: {str(e)}"
        )


@router.post("/from-session-enhanced", response_model=UserIssueResponse)
async def create_issue_from_session_enhanced(
    request: CreateIssueFromSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create an issue from a session with enhanced CodeInspector analysis.
    
    This endpoint:
    1. Validates session exists and belongs to user
    2. Gathers complete session context (messages, repo info, context cards)
    3. Uses CodeInspectorAgent with prompts from promptTemplate.py for analysis
    4. Creates UserIssue with comprehensive context
    5. Optionally creates a GitHub issue via GitHub API create_issue function
    6. Returns 400 for invalid sessions, 502 for OpenRouter issues
    
    Parameters:
    - session_id: Session to analyze
    - title: Issue title
    - description: Optional description
    - use_code_inspector: Whether to use CodeInspector agent (default: True)
    - create_github_issue: Whether to create actual GitHub issue (default: False)
    """
    try:
        return await IssueService.create_issue_from_session_with_analysis(db, current_user.id, request)
    except HTTPException:
        # Re-raise HTTP exceptions (like 400 for invalid session)
        raise
    except Exception as e:
        # Handle any unexpected errors
        error_msg = str(e)
        
        # Check if it's an OpenRouter/LLM related error
        if "openrouter" in error_msg.lower() or "api" in error_msg.lower() or "timeout" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Upstream service error during issue analysis: {error_msg}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create enhanced issue from session: {error_msg}"
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