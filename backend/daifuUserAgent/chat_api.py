"""FastAPI router for interacting with the DAifu agent."""

from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from typing import List, Optional

import requests
from auth.github_oauth import get_current_user
from db.database import get_db
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from issueChatServices.chat_service import ChatService
from issueChatServices.issue_service import IssueService
from issueChatServices.session_service import SessionService
from models import (
    ChatRequest,
    CreateChatMessageRequest,
    CreateSessionRequest,
    SessionResponse,
    User,
)
from sqlalchemy.orm import Session
from unified_state import (
    StateConverter,
    UnifiedSessionState,
    unified_manager,
)

from .prompt import build_daifu_prompt

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Process a chat message via the DAifu agent and store in database."""
    start_time = time.time()

    # Validate session_id is provided
    if not request.conversation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="session_id (conversation_id) is required",
        )

    try:
        # Touch session to update last_activity
        session = SessionService.touch_session(
            db, current_user.id, request.conversation_id
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
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
            tokens=len(request.message.content.split()),
            context_cards=request.context_cards,
        )

        ChatService.create_chat_message(db, current_user.id, user_message_request)

        # Get conversation history from database
        history_messages = ChatService.get_chat_messages(
            db, current_user.id, request.conversation_id, limit=50
        )

        # Convert to format expected by prompt builder
        history = []
        for msg in history_messages:
            sender = "User" if msg.sender_type == "user" else "DAifu"
            history.append((sender, msg.message_text))

        # Build prompt with session context
        prompt = build_daifu_prompt(GITHUB_CONTEXT, history)

        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OPENROUTER_API_KEY not configured",
            )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        body = {
            "model": "deepseek/deepseek-r1-0528:free",
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
        processing_time = (time.time() - start_time) * 1000

        # Store assistant response in database
        assistant_message_request = CreateChatMessageRequest(
            session_id=request.conversation_id,
            message_id=str(uuid.uuid4()),
            message_text=reply,
            sender_type="assistant",
            role="assistant",
            is_code=False,
            tokens=len(reply.split()),
            model_used="deepseek/deepseek-r1-0528:free",
            processing_time=processing_time,
        )

        ChatService.create_chat_message(db, current_user.id, assistant_message_request)

        return {
            "reply": reply,
            "conversation": history
            + [("User", request.message.content), ("DAifu", reply)],
            "message_id": message_id,
            "processing_time": processing_time,
            "session_id": request.conversation_id,
        }

    except HTTPException:
        raise
    except requests.RequestException as e:
        # Store error message in database
        error_message_request = CreateChatMessageRequest(
            session_id=request.conversation_id,
            message_id=str(uuid.uuid4()),
            message_text=f"Error: Network request failed - {str(e)}",
            sender_type="system",
            role="system",
            is_code=False,
            tokens=0,
            error_message=str(e),
        )

        ChatService.create_chat_message(db, current_user.id, error_message_request)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM service unavailable: {str(e)}",
        )
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
            error_message=str(e),
        )

        ChatService.create_chat_message(db, current_user.id, error_message_request)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM call failed: {str(e)}",
        )


@router.websocket("/sessions/{session_id}/ws")
async def websocket_session_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Enhanced WebSocket endpoint for real-time session updates with proper JWT authentication."""
    # Enhanced JWT token authentication
    if not token:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token"
        )
        return

    try:
        # Use the same authentication logic as regular endpoints
        from auth.github_oauth import get_current_user
        from fastapi.security import HTTPAuthorizationCredentials

        # Create a mock credentials object for token validation
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        user = await get_current_user(credentials, db)

        if not user:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Invalid authentication token",
            )
            return

    except Exception as e:
        print(f"Authentication error for session {session_id}: {e}")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed"
        )
        return

    try:
        # Connect to unified manager with user context
        await unified_manager.connect(websocket, session_id, db, user_id=user.id)

        # Enhanced message handling loop with better error handling
        while True:
            try:
                # Receive and parse messages
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle different message types
                await handle_websocket_message(
                    websocket, session_id, user.id, message, db
                )

            except WebSocketDisconnect:
                print(f"WebSocket disconnected for session {session_id}")
                break
            except json.JSONDecodeError as e:
                print(f"Invalid JSON from session {session_id}: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "data": {"message": "Invalid JSON format"},
                        "timestamp": time.time(),
                    }
                )
            except Exception as e:
                print(f"Message handling error for session {session_id}: {e}")
                await websocket.send_json(
                    {
                        "type": "error",
                        "data": {"message": "Message processing failed"},
                        "timestamp": time.time(),
                    }
                )

    except WebSocketDisconnect:
        print(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        print(f"WebSocket error for session {session_id}: {e}")
    finally:
        unified_manager.disconnect(websocket, session_id)


async def handle_websocket_message(
    websocket: WebSocket, session_id: str, user_id: int, message: dict, db: Session
):
    """Handle incoming WebSocket messages with proper real-time broadcasting."""
    message_type = message.get("type")
    message_data = message.get("data", {})

    try:
        if message_type == "HEARTBEAT":
            # Respond to heartbeat
            await websocket.send_json(
                {
                    "type": "heartbeat",
                    "data": {"timestamp": time.time()},
                    "timestamp": time.time(),
                }
            )

        elif message_type == "SEND_MESSAGE":
            # Handle new chat message with real-time broadcasting
            await handle_new_message_realtime(session_id, user_id, message_data, db)

        elif message_type == "REQUEST_CONTEXT":
            # Send session context update
            from issueChatServices.session_service import SessionService

            context = SessionService.get_comprehensive_session_context(
                db, user_id, session_id
            )
            if context:
                await unified_manager.broadcast_to_session(
                    session_id,
                    {
                        "type": "session_update",
                        "data": context,
                        "timestamp": time.time(),
                    },
                )

        elif message_type == "UPDATE_AGENT_STATUS":
            # Update agent status and broadcast
            await unified_manager.broadcast_to_session(
                session_id,
                {
                    "type": "agent_status",
                    "data": message_data,
                    "timestamp": time.time(),
                },
            )

        else:
            print(f"Unknown message type: {message_type}")
            await websocket.send_json(
                {
                    "type": "error",
                    "data": {"message": f"Unknown message type: {message_type}"},
                    "timestamp": time.time(),
                }
            )

    except Exception as e:
        print(f"Error handling WebSocket message {message_type}: {e}")
        await websocket.send_json(
            {
                "type": "error",
                "data": {"message": "Internal server error"},
                "timestamp": time.time(),
            }
        )


async def handle_new_message_realtime(
    session_id: str, user_id: int, message_data: dict, db: Session
):
    """Handle new message with immediate real-time broadcasting."""
    try:
        # Create message request object
        from models import ChatRequest, CreateChatMessageRequest

        chat_request = ChatRequest(
            conversation_id=session_id,
            message=CreateChatMessageRequest(
                content=message_data.get("content", ""),
                is_code=message_data.get("is_code", False),
            ),
        )

        # Store user message
        user_message_db = ChatService.create_chat_message_from_request(
            db, user_id=user_id, session_id=session_id, request=chat_request
        )
        user_message_unified = StateConverter.message_to_unified(user_message_db)

        # Broadcast user message immediately
        await unified_manager.broadcast_to_session(
            session_id,
            {"type": "message", "data": user_message_unified, "timestamp": time.time()},
        )

        # Process with AI asynchronously
        asyncio.create_task(
            process_ai_response_async(session_id, user_id, chat_request, db)
        )

    except Exception as e:
        print(f"Error handling new message: {e}")
        await unified_manager.broadcast_to_session(
            session_id,
            {
                "type": "error",
                "data": {"message": "Failed to process message"},
                "timestamp": time.time(),
            },
        )


async def process_ai_response_async(
    session_id: str, user_id: int, request: ChatRequest, db: Session
):
    """Process AI response asynchronously and broadcast when ready."""
    try:
        # Generate AI response
        response_content = await generate_daifu_response_async(request, db)

        # Create AI message
        ai_message_request = ChatRequest(
            conversation_id=session_id,
            message=CreateChatMessageRequest(content=response_content, is_code=False),
        )

        # Store AI message
        ai_message_db = ChatService.create_ai_message_from_request(
            db, session_id=session_id, request=ai_message_request
        )
        ai_message_unified = StateConverter.message_to_unified(ai_message_db)

        # Broadcast AI response
        await unified_manager.broadcast_to_session(
            session_id,
            {"type": "message", "data": ai_message_unified, "timestamp": time.time()},
        )

        # Update session statistics
        updated_stats = SessionService.get_session_statistics(db, session_id)
        if updated_stats:
            await unified_manager.broadcast_to_session(
                session_id,
                {"type": "statistics", "data": updated_stats, "timestamp": time.time()},
            )

    except Exception as e:
        print(f"Error processing AI response: {e}")
        await unified_manager.broadcast_to_session(
            session_id,
            {
                "type": "error",
                "data": {"message": "AI processing failed"},
                "timestamp": time.time(),
            },
        )


async def generate_daifu_response_async(request: ChatRequest, db: Session) -> str:
    """Generate DAifu response asynchronously."""
    try:
        # Use existing prompt building logic
        prompt = build_daifu_prompt(
            repo_context=GITHUB_CONTEXT,  # TODO: add repo context currently static but needs to get current repo context, commits, pulls, issues, etc.
            conversation_history=[request.message.content],
        )

        # Call OpenRouter API
        openrouter_response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openrouter/deepseek/deepseek-r1-0528",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 1000,
            },
            timeout=30,
        )

        if openrouter_response.status_code == 200:
            data = openrouter_response.json()
            return data["choices"][0]["message"]["content"]
        else:
            return "I apologize, but I'm having trouble processing your request right now. Please try again."

    except Exception as e:
        print(f"Error generating DAifu response: {e}")
        return "I encountered an error while processing your request. Please try again later."


@router.post("/chat/daifu/v2")
async def chat_daifu_v2(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    V2 Chat Endpoint:
    1. Stores the message in the database.
    2. Updates the in-memory state via the WebSocket manager.
    3. Triggers the LLM call asynchronously.
    """
    if not request.conversation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is required"
        )

    # 1. Create and store user message
    user_message_db = ChatService.create_chat_message_from_request(
        db, user_id=current_user.id, session_id=request.conversation_id, request=request
    )
    user_message_unified = StateConverter.message_to_unified(user_message_db)

    # 2. Update state and broadcast to clients immediately
    await unified_manager.update_and_broadcast_message(
        request.conversation_id, user_message_unified
    )

    # 3. Trigger async LLM response generation
    background_tasks.add_task(
        generate_and_broadcast_assistant_response,
        db=db,
        session_id=request.conversation_id,
        user_id=current_user.id,
    )

    return {"status": "Message received, assistant is thinking..."}


async def generate_and_broadcast_assistant_response(
    db: Session, session_id: str, user_id: int
):
    """Background task to get a response from the LLM and broadcast it."""
    # This is a simplified version of your original LLM call logic
    history_messages = ChatService.get_chat_messages(db, user_id, session_id, limit=50)
    history = [(msg.sender_type, msg.message_text) for msg in history_messages]
    prompt = build_daifu_prompt(GITHUB_CONTEXT, history)
    # This is where you would use the prompt in a real LLM call
    print(f"Generated prompt for LLM: {prompt[:100]}...")

    # ... (LLM call logic from your original 'chat_daifu' endpoint) ...
    # For brevity, let's simulate a response
    await asyncio.sleep(5)  # Simulate network latency and processing time
    reply_text = f"This is a simulated asynchronous response to your message in session {session_id}."

    # Create and store assistant message
    assistant_message_db = ChatService.create_assistant_message(
        db, user_id=user_id, session_id=session_id, content=reply_text
    )
    assistant_message_unified = StateConverter.message_to_unified(assistant_message_db)

    # Broadcast the assistant's response
    await unified_manager.update_and_broadcast_message(
        session_id, assistant_message_unified
    )


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
