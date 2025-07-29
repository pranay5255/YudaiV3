"""FastAPI router for interacting with the DAifu agent."""
from __future__ import annotations

import os
import uuid
import time
from typing import Dict, List, Tuple, Optional

from fastapi import APIRouter, HTTPException, Depends, status
import requests
from sqlalchemy.orm import Session

from models import ChatRequest, CreateChatMessageRequest, CreateSessionRequest, SessionResponse, SessionContextResponse, User
from db.database import get_db
from issueChatServices.chat_service import ChatService, SessionService
from issueChatServices.issue_service import IssueService
from auth.github_oauth import get_current_user, get_current_user_optional
from auth.auth_utils import handle_auth_error, validate_user_access
from .prompt import build_daifu_prompt

router = APIRouter()

# Basic repository context fed to the prompt
GITHUB_CONTEXT = (
    "Repository root: YudaiV3\n"
    "Key frontend file: src/components/Chat.tsx\n"
    "Key frontend file: src/App.tsx\n"
    "Backend FastAPI: backend/repo_processor/filedeps.py"
)

# OpenRouter configuration from environment
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-r1-0528:free")
OPENROUTER_TIMEOUT = int(os.getenv("OPENROUTER_TIMEOUT", "30"))


class OpenRouterError(Exception):
    """Custom exception for OpenRouter API errors"""
    def __init__(self, message: str, status_code: int = None, upstream_error: str = None):
        self.message = message
        self.status_code = status_code
        self.upstream_error = upstream_error
        super().__init__(self.message)


def call_openrouter_api(prompt: str) -> str:
    """
    Make a hardened call to OpenRouter API with proper error handling
    
    Returns:
        str: The response content from the API
        
    Raises:
        OpenRouterError: For any API-related errors
    """
    if not OPENROUTER_API_KEY:
        raise OpenRouterError(
            "OPENROUTER_API_KEY not configured",
            status_code=500,
            upstream_error="Missing API configuration"
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    body = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=body,
            timeout=OPENROUTER_TIMEOUT,
        )
        
        # Check for HTTP errors
        if resp.status_code >= 500:
            # Upstream server error
            raise OpenRouterError(
                f"OpenRouter service unavailable (HTTP {resp.status_code})",
                status_code=502,
                upstream_error=f"Upstream returned {resp.status_code}: {resp.text[:200]}"
            )
        elif resp.status_code >= 400:
            # Client error (API key, rate limit, etc.)
            error_detail = "Invalid request to OpenRouter API"
            try:
                error_json = resp.json()
                if "error" in error_json:
                    error_detail = f"OpenRouter API error: {error_json['error'].get('message', 'Unknown error')}"
            except:
                pass
            
            raise OpenRouterError(
                error_detail,
                status_code=502,
                upstream_error=f"Upstream returned {resp.status_code}: {resp.text[:200]}"
            )
        
        # Parse successful response
        try:
            response_data = resp.json()
            if "choices" not in response_data or not response_data["choices"]:
                raise OpenRouterError(
                    "Invalid response format from OpenRouter API",
                    status_code=502,
                    upstream_error="Missing choices in API response"
                )
            
            return response_data["choices"][0]["message"]["content"].strip()
            
        except (KeyError, IndexError, ValueError) as e:
            raise OpenRouterError(
                "Failed to parse OpenRouter API response",
                status_code=502,
                upstream_error=f"JSON parsing error: {str(e)}"
            )
            
    except requests.Timeout:
        raise OpenRouterError(
            "OpenRouter API request timed out",
            status_code=502,
            upstream_error=f"Request timeout after {OPENROUTER_TIMEOUT} seconds"
        )
    except requests.ConnectionError as e:
        raise OpenRouterError(
            "Failed to connect to OpenRouter API",
            status_code=502,
            upstream_error=f"Connection error: {str(e)}"
        )
    except requests.RequestException as e:
        raise OpenRouterError(
            "OpenRouter API request failed",
            status_code=502,
            upstream_error=f"Request error: {str(e)}"
        )


@router.post("/sessions", response_model=SessionResponse)
async def create_or_get_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Create or get existing session for repository selection"""
    try:
        validate_user_access(user)
        
        session = SessionService.get_or_create_session(
            db=db,
            user_id=user.id,
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            repo_branch=request.repo_branch,
            title=request.title,
            description=request.description
        )
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to create/get session: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SessionContextResponse)
async def get_session_context(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get complete session context including messages and context cards"""
    try:
        validate_user_access(user, session_id)
        
        context = SessionService.get_session_context(db, user.id, session_id)
        if not context:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Session not found"
            )
        return context
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to get session context: {str(e)}"
        )


@router.post("/sessions/{session_id}/touch")
async def touch_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Update last_activity for a session"""
    try:
        validate_user_access(user, session_id)
        
        session = SessionService.touch_session(db, user.id, session_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Session not found"
            )
        return {"success": True, "session": session}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to touch session: {str(e)}"
        )


@router.get("/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get user sessions filtered by repository"""
    try:
        validate_user_access(user)
        
        sessions = SessionService.get_user_sessions_by_repo(
            db, user.id, repo_owner, repo_name
        )
        return sessions
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Failed to get sessions: {str(e)}"
        )


@router.post("/chat/daifu")
async def chat_daifu(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Process a chat message via the DAifu agent and store in database."""
    start_time = time.time()
    
    # Validate session_id is provided
    if not request.conversation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="session_id (conversation_id) is required"
        )
    
    try:
        validate_user_access(user, request.conversation_id)
        
        # Validate session exists BEFORE calling OpenRouter
        session = SessionService.touch_session(db, user.id, request.conversation_id)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Session '{request.conversation_id}' not found or invalid"
            )
        
        # Generate unique message ID
        message_id = str(uuid.uuid4())
        
        # Store user message in database
        user_message_request = CreateChatMessageRequest(
            session_id=request.conversation_id,
            message_id=message_id,
            message_text=request.message.content,
            sender_type="user",
            role="user",
            is_code=request.message.is_code,
            tokens=len(request.message.content.split()),  # Simple token estimation
            context_cards=request.context_cards
        )
        
        user_message = ChatService.create_chat_message(db, user.id, user_message_request)
        
        # Get conversation history from database
        history_messages = ChatService.get_chat_messages(
            db, user.id, request.conversation_id, limit=50
        )
        
        # Convert to format expected by prompt builder
        history = []
        for msg in history_messages:
            sender = "User" if msg.sender_type == "user" else "DAifu"
            history.append((sender, msg.message_text))
        
        # Build prompt
        prompt = build_daifu_prompt(GITHUB_CONTEXT, history)

        # Call OpenRouter API with proper error handling
        try:
            reply = call_openrouter_api(prompt)
        except OpenRouterError as e:
            # Store error message in database
            error_message_request = CreateChatMessageRequest(
                session_id=request.conversation_id,
                message_id=str(uuid.uuid4()),
                message_text=f"Error: {e.message}",
                sender_type="system",
                role="system",
                is_code=False,
                tokens=0,
                error_message=e.upstream_error
            )
            
            ChatService.create_chat_message(db, user.id, error_message_request)
            
            # Return appropriate HTTP status code
            http_status = status.HTTP_502_BAD_GATEWAY if e.status_code == 502 else status.HTTP_500_INTERNAL_SERVER_ERROR
            raise HTTPException(
                status_code=http_status,
                detail=e.message
            )
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Store assistant response in database
        assistant_message_request = CreateChatMessageRequest(
            session_id=request.conversation_id,
            message_id=str(uuid.uuid4()),
            message_text=reply,
            sender_type="assistant",
            role="assistant",
            is_code=False,
            tokens=len(reply.split()),  # Simple token estimation
            model_used=OPENROUTER_MODEL,
            processing_time=processing_time
        )
        
        assistant_message = ChatService.create_chat_message(db, user.id, assistant_message_request)
        
        return {
            "reply": reply, 
            "conversation": history + [("User", request.message.content), ("DAifu", reply)],
            "message_id": message_id,
            "processing_time": processing_time,
            "session_id": request.conversation_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        # Store error message in database
        error_message_request = CreateChatMessageRequest(
            session_id=request.conversation_id,
            message_id=str(uuid.uuid4()),
            message_text=f"Error: {str(e)}",
            sender_type="system",
            role="system",
            is_code=False,
            tokens=0,
            error_message=str(e)
        )
        
        ChatService.create_chat_message(db, user.id, error_message_request)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/chat/sessions")
async def get_chat_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 50
):
    """Get all chat sessions for a user."""
    try:
        validate_user_access(user)
        
        sessions = ChatService.get_user_chat_sessions(db, user.id, limit)
        return {"sessions": sessions}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat sessions: {str(e)}"
        )


@router.get("/chat/sessions/{session_id}/messages")
async def get_chat_messages(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 100
):
    """Get messages for a specific chat session."""
    try:
        validate_user_access(user, session_id)
        
        messages = ChatService.get_chat_messages(db, user.id, session_id, limit)
        return {"messages": messages}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get chat messages: {str(e)}"
        )


@router.get("/chat/sessions/{session_id}/statistics")
async def get_session_statistics(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get statistics for a chat session."""
    try:
        validate_user_access(user, session_id)
        
        stats = ChatService.get_session_statistics(db, user.id, session_id)
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Session not found"
            )
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get session statistics: {str(e)}"
        )


@router.put("/chat/sessions/{session_id}/title")
async def update_session_title(
    session_id: str,
    title: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Update the title of a chat session."""
    try:
        validate_user_access(user, session_id)
        
        session = ChatService.update_session_title(db, user.id, session_id, title)
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Session not found"
            )
        return session
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update session title: {str(e)}"
        )


@router.delete("/chat/sessions/{session_id}")
async def deactivate_session(
    session_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Deactivate a chat session."""
    try:
        validate_user_access(user, session_id)
        
        success = ChatService.deactivate_session(db, user.id, session_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Session not found"
            )
        return {"message": "Session deactivated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate session: {str(e)}"
        )


# Removed redundant /chat/create-issue endpoint
# Issue creation is now handled by /issues/from-session-enhanced in issue_service.py
