"""FastAPI router for interacting with the DAifu agent."""

from __future__ import annotations

import asyncio
import json
import time
from typing import List, Optional

from auth.github_oauth import get_current_user
from db.database import get_db
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
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
    StateConverter,
    UnifiedSessionState,
    unified_manager,
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
    async_mode: bool = Query(False, description="Use async mode for real-time updates"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Unified Chat Endpoint with WebSocket Support
    
    This endpoint consolidates the previous /chat/daifu and /chat/daifu/v2 endpoints.
    Use async_mode=true for real-time WebSocket updates, false for synchronous responses.
    """
    start_time = time.time()
    
    # Validate conversation_id (session_id)
    conversation_id = SessionValidator.validate_conversation_id(request.conversation_id)
    
    try:
        # Validate session exists and belongs to user
        session = SessionValidator.validate_session_active(db, current_user.id, conversation_id)
        
        # Store user message
        user_message_db = MessageService.store_user_message(
            db=db,
            user_id=current_user.id,
            session_id=conversation_id,
            content=request.message.content,
            is_code=request.message.is_code,
            context_cards=request.context_cards
        )
        
        if async_mode:
            # Async mode: Return immediately and process in background
            user_message_unified = StateConverter.message_to_unified(user_message_db)
            
            # Broadcast user message via WebSocket
            await unified_manager.update_and_broadcast_message(
                conversation_id, user_message_unified
            )
            
            # Process AI response in background
            background_tasks.add_task(
                process_ai_response_background,
                db=db,
                session_id=conversation_id,
                user_id=current_user.id,
                start_time=start_time
            )
            
            return {"status": "Message received, assistant is thinking..."}
        
        else:
            # Synchronous mode: Process immediately and return response
            # Get conversation history
            history_messages = ChatService.get_chat_messages(
                db, current_user.id, conversation_id, limit=50
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
            assistant_message_db = MessageService.store_assistant_message(
                db=db,
                user_id=current_user.id,
                session_id=conversation_id,
                content=reply,
                processing_time=processing_time
            )
            
            return {
                "reply": reply,
                "conversation": history + [("User", request.message.content), ("DAifu", reply)],
                "message_id": user_message_db.message_id,
                "processing_time": processing_time,
                "session_id": conversation_id,
            }
    
    except HTTPException:
        raise
    except Exception as e:
        # Store error message
        MessageService.store_error_message(
            db=db,
            user_id=current_user.id,
            session_id=conversation_id,
            error_message=str(e),
            error_type="system"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat processing failed: {str(e)}",
        )


async def process_ai_response_background(
    db: Session,
    session_id: str,
    user_id: int,
    start_time: float
):
    """Background task to process AI response and broadcast via WebSocket"""
    try:
        # Get conversation history
        history_messages = ChatService.get_chat_messages(
            db, user_id, session_id, limit=50
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
        assistant_message_db = MessageService.store_assistant_message(
            db=db,
            user_id=user_id,
            session_id=session_id,
            content=reply,
            processing_time=processing_time
        )
        
        # Convert to unified format and broadcast
        assistant_message_unified = StateConverter.message_to_unified(assistant_message_db)
        await unified_manager.update_and_broadcast_message(
            session_id, assistant_message_unified
        )
        
        # Update session statistics
        updated_stats = SessionService.get_session_statistics(db, user_id, session_id)
        if updated_stats:
            await unified_manager.broadcast_to_session(
                session_id,
                {"type": "statistics", "data": updated_stats, "timestamp": time.time()},
            )
    
    except Exception as e:
        print(f"Error processing AI response: {e}")
        # Store error message
        MessageService.store_error_message(
            db=db,
            user_id=user_id,
            session_id=session_id,
            error_message=str(e),
            error_type="system"
        )
        
        # Broadcast error via WebSocket
        await unified_manager.broadcast_to_session(
            session_id,
            {
                "type": "error",
                "data": {"message": "AI processing failed"},
                "timestamp": time.time(),
            },
        )


@router.websocket("/sessions/{session_id}/ws")
async def websocket_session_endpoint(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Enhanced WebSocket endpoint for real-time session updates with proper GitHub App authentication."""
    # Enhanced GitHub App token authentication
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

        # Log successful authentication for debugging
        print(f"WebSocket authenticated for user {user.github_username} on session {session_id}")

    except Exception as e:
        print(f"GitHub App authentication error for session {session_id}: {e}")
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="GitHub App authentication failed"
        )
        return

    try:
        # Validate session exists and belongs to user
        SessionValidator.validate_session_active(db, user.id, session_id, touch_session=False)
        
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
        # Store user message
        user_message_db = MessageService.store_user_message(
            db=db,
            user_id=user_id,
            session_id=session_id,
            content=message_data.get("content", ""),
            is_code=message_data.get("is_code", False),
        )
        user_message_unified = StateConverter.message_to_unified(user_message_db)

        # Broadcast user message immediately
        await unified_manager.broadcast_to_session(
            session_id,
            {"type": "message", "data": user_message_unified, "timestamp": time.time()},
        )

        # Process with AI asynchronously
        asyncio.create_task(
            process_ai_response_background(db, session_id, user_id, time.time())
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
