"""
Session Management Routes for DAifu Agent
Handles session creation and component CRUD operations
"""
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_
from sqlalchemy.orm import Session

from auth.github_oauth import get_current_user
from db.database import get_db
from models import (
    ChatSession,
    CreateSessionRequest,
    SessionResponse,
    SessionContextResponse,
    User,
    ChatMessageResponse,
    UserIssueResponse,
    FileEmbeddingResponse,
    ChatMessage,
    UserIssue,
    FileEmbedding,
    ContextCard,
)
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
                ChatSession.is_active == True
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
                ContextCard.is_active == True
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