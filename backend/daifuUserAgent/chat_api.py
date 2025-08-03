"""FastAPI router for interacting with the DAifu agent."""

from __future__ import annotations

import time
from typing import List, Optional

from auth.github_oauth import get_current_user
from db.database import get_db
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    status,
)
from issueChatServices.chat_service import ChatService
from issueChatServices.issue_service import IssueService
from issueChatServices.session_service import SessionService
from models import (
    ChatRequest,
    CreateSessionRequest,
    SessionResponse,
    User,
)
from sqlalchemy.orm import Session
from unified_state import (
    UnifiedSessionState,
)

from .llm_service import LLMService
from .message_service import MessageService
from .session_validator import SessionValidator

router = APIRouter()

# Basic repository context fed to the prompt
GITHUB_CONTEXT = (
    "Repository root: YudaiV3\n"
    "Key frontend file: src/components/Chat.tsx\n"
    "Key frontend file: src/App.tsx\n"
    "Backend FastAPI: backend/repo_processor/filedeps.py"
)


@router.post("/sessions", response_model=SessionResponse)
async def create_or_get_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create or get existing session for repository selection using unified SessionService"""
    try:
        session = SessionService.get_or_create_session(
            db=db,
            user_id=current_user.id,
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            repo_branch=request.repo_branch,
            title=request.title,
            description=request.description,
        )
        return session
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/get session: {str(e)}",
        )


@router.get("/sessions/{session_id}", response_model=UnifiedSessionState)
async def get_session_context(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get comprehensive session context as a unified state object"""
    try:
        unified_state = SessionService.get_comprehensive_session_context(
            db, current_user.id, session_id
        )
        if not unified_state:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )
        return unified_state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session context: {str(e)}",
        )


@router.post("/sessions/{session_id}/touch")
async def touch_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update last_activity for a session"""
    try:
        session = SessionService.touch_session(db, current_user.id, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )
        return {"success": True, "session": session}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to touch session: {str(e)}",
        )


@router.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get user sessions filtered by repository using unified SessionService"""
    try:
        sessions = SessionService.get_user_sessions(
            db, current_user.id, repo_owner, repo_name, limit
        )
        return sessions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get sessions: {str(e)}",
        )


@router.post("/chat/daifu")
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
    
    # Validate session_id
    session_id = SessionValidator.validate_session_id(request.session_id)
    
    try:
        # Validate session exists and belongs to user
        SessionValidator.validate_session_active(db, current_user.id, session_id)
        
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
            repo_context=GITHUB_CONTEXT,
            conversation_history=history
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


# Removed WebSocket endpoint and related handlers


@router.get("/chat/sessions/{session_id}/statistics")
async def get_session_statistics(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get comprehensive statistics for a session using unified SessionService"""
    try:
        stats = SessionService.get_session_statistics(db, current_user.id, session_id)
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session statistics: {str(e)}",
        )


@router.put("/chat/sessions/{session_id}/title")
async def update_session_title(
    session_id: str,
    title: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update the title of a session using unified SessionService"""
    try:
        session = SessionService.update_session_title(
            db, current_user.id, session_id, title
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session title: {str(e)}",
        )


@router.delete("/chat/sessions/{session_id}")
async def deactivate_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a session using unified SessionService"""
    try:
        success = SessionService.deactivate_session(db, current_user.id, session_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
            )
        return {"message": "Session deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate session: {str(e)}",
        )


@router.post("/chat/create-issue")
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
