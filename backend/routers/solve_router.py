"""
AI Solver Router for YudaiV3
Provides API endpoints for starting and monitoring AI solve sessions
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional, List
from datetime import datetime

from db.database import get_db
from auth.auth_utils import get_current_user
from models import User, Issue, Repository, AISolveSession
from solver.ai_solver import AISolverAdapter
from schemas.ai_solver import (
    SolveSessionOut, 
    SolveSessionStatsOut, 
    StartSolveRequest, 
    StartSolveResponse,
    SolveStatus
)

router = APIRouter()


async def validate_auth_payment(user: User = Depends(get_current_user)) -> bool:
    """
    Always-true auth validation as requested
    
    TODO: Implement proper authentication and payment validation
    
    Future requirements:
    - Check user subscription status and tier
    - Verify payment method is valid and not expired
    - Check usage limits and quotas for current billing period
    - Validate API rate limits per user/tier
    - Implement cost tracking and budget limits
    - Add fraud detection and abuse prevention
    - Check geographic restrictions if any
    - Validate user account status (active, suspended, etc.)
    - Implement feature flags per subscription tier
    - Add audit logging for billing and usage tracking
    
    Current implementation: Always returns True for development/testing
    
    Args:
        user: Current authenticated user
        
    Returns:
        bool: Always True (placeholder implementation)
    """
    # TODO: Replace with actual validation logic
    # Example future implementation:
    # 
    # # Check subscription status
    # if not user.subscription or user.subscription.status != 'active':
    #     raise HTTPException(status_code=402, detail="Active subscription required")
    # 
    # # Check usage limits
    # current_usage = get_user_monthly_usage(user.id)
    # if current_usage >= user.subscription.solve_limit:
    #     raise HTTPException(status_code=429, detail="Monthly solve limit exceeded")
    # 
    # # Check payment method
    # if not user.payment_method or user.payment_method.expired:
    #     raise HTTPException(status_code=402, detail="Valid payment method required")
    # 
    # # Check rate limits
    # if is_rate_limited(user.id):
    #     raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    return True


@router.post("/issues/{issue_id}/solve", response_model=StartSolveResponse)
async def start_solve_session(
    issue_id: int,
    request: Optional[StartSolveRequest] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    auth_valid: bool = Depends(validate_auth_payment)
) -> StartSolveResponse:
    """
    Start AI solver for an issue
    
    This endpoint validates the user's authentication and payment status,
    then starts a background AI solve session for the specified issue.
    
    Args:
        issue_id: Database ID of the issue to solve
        request: Optional solve configuration
        background_tasks: FastAPI background tasks
        db: Database session
        user: Current authenticated user
        auth_valid: Auth/payment validation result
        
    Returns:
        StartSolveResponse: Session information
        
    Raises:
        HTTPException: If issue not found or user not authorized
    """
    
    # Get issue details
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    # Get repository details
    repository = issue.repository
    if not repository:
        raise HTTPException(status_code=400, detail="Issue has no associated repository")
    
    # Check if user has access to this repository
    # For now, we'll allow any authenticated user to solve any issue
    # TODO: Implement proper authorization based on repository ownership/permissions
    
    # Prepare solve parameters
    repo_url = repository.clone_url or repository.html_url
    branch = "main"  # Default branch
    ai_model_id = None
    swe_config_id = None
    
    if request:
        if request.repo_url:
            repo_url = request.repo_url
        if request.branch_name:
            branch = request.branch_name
        ai_model_id = request.ai_model_id
        swe_config_id = request.swe_config_id
    
    # Create solver adapter
    solver = AISolverAdapter(db)
    
    # Create a new session record first to get the session_id
    from models import AISolveSession
    session = AISolveSession(
        user_id=user.id,
        issue_id=issue_id,
        status=SolveStatus.PENDING,
        repo_url=repo_url,
        branch_name=branch,
        ai_model_id=ai_model_id,
        swe_config_id=swe_config_id
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    # Start solver in background task with the session_id
    background_tasks.add_task(
        solver.run_solver,
        issue_id=issue_id,
        user_id=user.id,
        repo_url=repo_url,
        branch=branch,
        ai_model_id=ai_model_id,
        swe_config_id=swe_config_id
    )
    
    # Return immediate response with session_id
    return StartSolveResponse(
        message="AI Solver started successfully",
        session_id=session.id,
        issue_id=issue_id,
        status="started"
    )


@router.get("/solve-sessions/{session_id}", response_model=SolveSessionOut)
async def get_solve_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> SolveSessionOut:
    """
    Get solve session details
    
    Retrieves complete information about a solve session including
    related edits, AI model, and SWE-agent configuration.
    
    Args:
        session_id: Session ID to retrieve
        db: Database session
        user: Current authenticated user
        
    Returns:
        SolveSessionOut: Complete session details
        
    Raises:
        HTTPException: If session not found or user not authorized
    """
    
    # Get session with authorization check
    session = db.query(AISolveSession).filter(
        AISolveSession.id == session_id,
        AISolveSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=404, 
            detail="Solve session not found or access denied"
        )
    
    # The SQLAlchemy model will automatically load relationships
    # due to the relationship definitions in the model
    return SolveSessionOut.model_validate(session)


@router.get("/solve-sessions/{session_id}/stats", response_model=SolveSessionStatsOut)
async def get_solve_session_stats(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> SolveSessionStatsOut:
    """
    Get solve session statistics
    
    Provides lightweight statistics about a solve session including
    edit counts, file modifications, and timing information.
    
    Args:
        session_id: Session ID to get stats for
        db: Database session
        user: Current authenticated user
        
    Returns:
        SolveSessionStatsOut: Session statistics
        
    Raises:
        HTTPException: If session not found or user not authorized
    """
    
    # Verify session exists and user has access
    session = db.query(AISolveSession).filter(
        AISolveSession.id == session_id,
        AISolveSession.user_id == user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=404, 
            detail="Solve session not found or access denied"
        )
    
    # Get statistics from solver adapter
    solver = AISolverAdapter(db)
    stats = solver.get_session_status(session_id)
    
    if not stats:
        raise HTTPException(
            status_code=500, 
            detail="Failed to retrieve session statistics"
        )
    
    return SolveSessionStatsOut(**stats)


@router.post("/solve-sessions/{session_id}/cancel")
async def cancel_solve_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Cancel a running solve session
    
    Attempts to cancel a currently running solve session.
    Only the user who started the session can cancel it.
    
    Args:
        session_id: Session ID to cancel
        db: Database session
        user: Current authenticated user
        
    Returns:
        Dict: Cancellation result
        
    Raises:
        HTTPException: If session not found, not running, or user not authorized
    """
    
    # Create solver adapter
    solver = AISolverAdapter(db)
    
    # Attempt to cancel session
    cancelled = await solver.cancel_session(session_id, user.id)
    
    if not cancelled:
        # Check if session exists to provide better error message
        session = db.query(AISolveSession).filter(
            AISolveSession.id == session_id,
            AISolveSession.user_id == user.id
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=404, 
                detail="Solve session not found or access denied"
            )
        elif session.status != SolveStatus.RUNNING:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot cancel session with status: {session.status}"
            )
        else:
            raise HTTPException(
                status_code=500, 
                detail="Failed to cancel session"
            )
    
    return {
        "message": "Solve session cancelled successfully",
        "session_id": session_id,
        "status": "cancelled"
    }


@router.get("/solve-sessions", response_model=List[SolveSessionOut])
async def list_user_solve_sessions(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
) -> List[SolveSessionOut]:
    """
    List user's solve sessions
    
    Retrieves a paginated list of solve sessions for the current user,
    optionally filtered by status.
    
    Args:
        limit: Maximum number of sessions to return (default: 50)
        offset: Number of sessions to skip (default: 0)
        status: Optional status filter
        db: Database session
        user: Current authenticated user
        
    Returns:
        List[SolveSessionOut]: List of user's solve sessions
    """
    
    # Build query
    query = db.query(AISolveSession).filter(
        AISolveSession.user_id == user.id
    )
    
    # Apply status filter if provided
    if status:
        try:
            status_enum = SolveStatus(status)
            query = query.filter(AISolveSession.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid status: {status}. Valid values: {[s.value for s in SolveStatus]}"
            )
    
    # Apply pagination and ordering
    sessions = query.order_by(
        AISolveSession.created_at.desc()
    ).offset(offset).limit(limit).all()
    
    return [SolveSessionOut.model_validate(session) for session in sessions]


# Health check endpoint for the solver system
@router.get("/health")
async def solver_health_check() -> Dict[str, Any]:
    """
    Health check for the AI solver system
    
    Returns:
        Dict: Health status information
    """
    
    # TODO: Add actual health checks
    # - Check SWE-agent availability
    # - Check Docker daemon connection
    # - Check disk space for solve data
    # - Check AI model API connectivity
    # - Check database connectivity
    
    return {
        "status": "healthy",
        "service": "ai-solver",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": "ok",  # TODO: Actual DB health check
            "swe_agent": "ok",  # TODO: Actual SWE-agent health check
            "docker": "ok",     # TODO: Actual Docker health check
            "storage": "ok"     # TODO: Actual storage health check
        }
    }