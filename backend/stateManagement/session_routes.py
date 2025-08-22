"""
Session Management Routes for DAifu Agent
Handles session creation and component CRUD operations
"""
import logging
import uuid
from typing import List

from auth.github_oauth import get_current_user
from db.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from models import (
    APIResponse,
    ChatMessage,
    ChatMessageResponse,
    ChatSession,
    ContextCard,
    CreateSessionRequest,
    FileEmbedding,
    FileEmbeddingResponse,
    SessionContextResponse,
    SessionResponse,
    UpdateSessionRequest,
    User,
    UserIssue,
    UserIssueResponse,
)
from sqlalchemy import and_
from sqlalchemy.orm import Session

from utils import utc_now

logger = logging.getLogger(__name__)
router = APIRouter()

def generate_session_id() -> str:
    """Generate a unique session ID"""
    return f"session_{uuid.uuid4().hex[:12]}"

@router.post("/sessions", response_model=SessionResponse)
async def create_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new chat session for a user with repository context
    """
    try:
        logger.info(f"Creating session for user {current_user.github_username} with repo {request.repo_owner}/{request.repo_name}")
        
        # Generate unique session ID
        session_id = generate_session_id()
        
        # Create new chat session
        chat_session = ChatSession(
            user_id=current_user.id,
            session_id=session_id,
            title=request.title or f"Chat - {request.repo_owner}/{request.repo_name}",
            description=request.description,
            repo_owner=request.repo_owner,
            repo_name=request.repo_name,
            repo_branch=request.repo_branch,
            is_active=True,
            total_messages=0,
            total_tokens=0,
            last_activity=utc_now()
        )
        
        db.add(chat_session)
        db.commit()
        db.refresh(chat_session)
        
        logger.info(f"Successfully created session {session_id} for user {current_user.github_username}")
        
        return SessionResponse.model_validate(chat_session)
        
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create session"
        )

@router.get("/sessions/{session_id}", response_model=SessionContextResponse)
async def get_session_context(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get complete session context including messages, context cards, and metadata
    """
    try:
        # Get session and verify ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Get session messages
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at).all()
        
        # Get user issues for this session
        user_issues = db.query(UserIssue).filter(
            UserIssue.session_id == session_id
        ).all()
        
        # Get file embeddings for this session
        file_embeddings = db.query(FileEmbedding).filter(
            FileEmbedding.session_id == session.id
        ).all()
        
        # Get context cards for this session
        context_cards = db.query(ContextCard).filter(
            and_(
                ContextCard.session_id == session.id,
                ContextCard.is_active
            )
        ).all()
        
        # Build repository info
        repository_info = None
        if session.repo_owner and session.repo_name:
            repository_info = {
                "owner": session.repo_owner,
                "name": session.repo_name,
                "branch": session.repo_branch or "main",
                "full_name": f"{session.repo_owner}/{session.repo_name}",
                "html_url": f"https://github.com/{session.repo_owner}/{session.repo_name}"
            }
        
        # Calculate statistics
        statistics = {
            "total_messages": session.total_messages,
            "total_tokens": session.total_tokens,
            "total_cost": 0,  # TODO: Implement cost calculation
            "session_duration": (utc_now() - session.created_at).total_seconds(),
            "user_issues_count": len(user_issues),
            "file_embeddings_count": len(file_embeddings)
        }
        
        return SessionContextResponse(
            session=SessionResponse.model_validate(session),
            messages=[ChatMessageResponse.model_validate(msg) for msg in messages],
            context_cards=[str(card.id) for card in context_cards],  # Return card IDs as strings
            repository_info=repository_info,
            file_embeddings_count=len(file_embeddings),
            statistics=statistics,
            user_issues=[UserIssueResponse.model_validate(issue) for issue in user_issues],
            file_embeddings=[FileEmbeddingResponse.model_validate(emb) for emb in file_embeddings]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session context: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve session context"
        )

# ============================================================================
# MISSING SESSION MANAGEMENT APIs
# ============================================================================

@router.get("/sessions", response_model=List[SessionResponse])
async def list_user_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all sessions for the current user"""
    try:
        sessions = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).order_by(ChatSession.last_activity.desc()).all()
        
        return [SessionResponse.model_validate(session) for session in sessions]
        
    except Exception as e:
        logger.error(f"Error listing user sessions: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user sessions"
        )

@router.put("/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    updates: UpdateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a session"""
    try:
        # Get session and verify ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Apply updates only for non-None fields
        update_data = updates.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(session, field, value)
        
        session.updated_at = utc_now()
        
        db.commit()
        db.refresh(session)
        
        return SessionResponse.model_validate(session)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update session"
        )

@router.delete("/sessions/{session_id}", response_model=APIResponse)
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a session (soft delete by setting is_active=False)"""
    try:
        # Get session and verify ownership
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.session_id == session_id,
                ChatSession.user_id == current_user.id,
                ChatSession.is_active
            )
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Session not found"
            )
        
        # Soft delete the session
        session.is_active = False
        session.updated_at = utc_now()
        
        db.commit()
        
        return APIResponse(
            success=True,
            message=f"Session {session_id} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session"
        )