"""FastAPI router for interacting with the DAifu agent."""
from __future__ import annotations

import os
import uuid
import time
from typing import Dict, List, Tuple

from fastapi import APIRouter, HTTPException, Depends
import requests
from sqlalchemy.orm import Session

from ..models import ChatRequest, CreateChatMessageRequest
from ..db.database import get_db
from ..issueChatServices.chat_service import ChatService
from ..issueChatServices.issue_service import IssueService
from .prompt import build_daifu_prompt

router = APIRouter()

# Basic repository context fed to the prompt
GITHUB_CONTEXT = (
    "Repository root: YudaiV3\n"
    "Key frontend file: src/components/Chat.tsx\n"
    "Key frontend file: src/App.tsx\n"
    "Backend FastAPI: backend/repo_processor/filedeps.py"
)


@router.post("/chat/daifu")
async def chat_daifu(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from authentication
):
    """Process a chat message via the DAifu agent and store in database."""
    start_time = time.time()
    
    # Generate unique message ID
    message_id = str(uuid.uuid4())
    
    # Store user message in database
    user_message_request = CreateChatMessageRequest(
        session_id=request.conversation_id or "default",
        message_id=message_id,
        message_text=request.message.content,
        sender_type="user",
        role="user",
        is_code=request.message.is_code,
        tokens=len(request.message.content.split()),  # Simple token estimation
        context_cards=request.context_cards
    )
    
    user_message = ChatService.create_chat_message(db, user_id, user_message_request)
    
    # Get conversation history from database
    history_messages = ChatService.get_chat_messages(
        db, user_id, request.conversation_id or "default", limit=50
    )
    
    # Convert to format expected by prompt builder
    history = []
    for msg in history_messages:
        sender = "User" if msg.sender_type == "user" else "DAifu"
        history.append((sender, msg.message_text))
    
    # Build prompt
    prompt = build_daifu_prompt(GITHUB_CONTEXT, history)

    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not configured")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": "openai/gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
        }

        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"].strip()
        
        # Calculate processing time
        processing_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Store assistant response in database
        assistant_message_request = CreateChatMessageRequest(
            session_id=request.conversation_id or "default",
            message_id=str(uuid.uuid4()),
            message_text=reply,
            sender_type="assistant",
            role="assistant",
            is_code=False,
            tokens=len(reply.split()),  # Simple token estimation
            model_used="openai/gpt-3.5-turbo",
            processing_time=processing_time
        )
        
        assistant_message = ChatService.create_chat_message(db, user_id, assistant_message_request)
        
    except Exception as e:  # pragma: no cover - network failures
        # Store error message in database
        error_message_request = CreateChatMessageRequest(
            session_id=request.conversation_id or "default",
            message_id=str(uuid.uuid4()),
            message_text=f"Error: {str(e)}",
            sender_type="system",
            role="system",
            is_code=False,
            tokens=0,
            error_message=str(e)
        )
        
        ChatService.create_chat_message(db, user_id, error_message_request)
        raise HTTPException(status_code=500, detail=f"LLM call failed: {e}")

    return {
        "reply": reply, 
        "conversation": history + [("User", request.message.content), ("DAifu", reply)],
        "message_id": message_id,
        "processing_time": processing_time
    }


@router.get("/chat/sessions")
async def get_chat_sessions(
    db: Session = Depends(get_db),
    user_id: int = 1,  # TODO: Get from authentication
    limit: int = 50
):
    """Get all chat sessions for a user."""
    sessions = ChatService.get_user_chat_sessions(db, user_id, limit)
    return {"sessions": sessions}


@router.get("/chat/sessions/{session_id}/messages")
async def get_chat_messages(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: int = 1,  # TODO: Get from authentication
    limit: int = 100
):
    """Get messages for a specific chat session."""
    messages = ChatService.get_chat_messages(db, user_id, session_id, limit)
    return {"messages": messages}


@router.get("/chat/sessions/{session_id}/statistics")
async def get_session_statistics(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from authentication
):
    """Get statistics for a chat session."""
    stats = ChatService.get_session_statistics(db, user_id, session_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Session not found")
    return stats


@router.put("/chat/sessions/{session_id}/title")
async def update_session_title(
    session_id: str,
    title: str,
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from authentication
):
    """Update the title of a chat session."""
    session = ChatService.update_session_title(db, user_id, session_id, title)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/chat/sessions/{session_id}")
async def deactivate_session(
    session_id: str,
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from authentication
):
    """Deactivate a chat session."""
    success = ChatService.deactivate_session(db, user_id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deactivated successfully"}


@router.post("/chat/create-issue")
async def create_issue_from_chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user_id: int = 1  # TODO: Get from authentication
):
    """Create an issue from a chat conversation."""
    try:
        # Create the issue from the chat request
        issue = IssueService.create_issue_from_chat(db, user_id, request)
        
        return {
            "success": True,
            "issue": issue,
            "message": f"Issue created with ID: {issue.issue_id}"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create issue: {e}")
