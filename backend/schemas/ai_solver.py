"""
AI Solver Pydantic schemas for API serialization
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, ConfigDict
from enum import Enum

# Enums (matching the ones in models.py)
class SolveStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class EditType(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"

# Output schemas for API responses
class AIModelOut(BaseModel):
    """AI Model output schema"""
    id: int
    name: str
    provider: str
    model_id: str
    config: Optional[Dict[str, Any]] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class SWEAgentConfigOut(BaseModel):
    """SWE-agent Configuration output schema"""
    id: int
    name: str
    config_path: str
    parameters: Optional[Dict[str, Any]] = None
    is_default: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)

class SolveEditOut(BaseModel):
    """AI Solve Edit output schema"""
    id: int
    session_id: int
    file_path: str
    edit_type: EditType
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class SolveSessionOut(BaseModel):
    """AI Solve Session output schema"""
    id: int
    user_id: int
    issue_id: int
    ai_model_id: Optional[int] = None
    swe_config_id: Optional[int] = None
    status: SolveStatus
    repo_url: Optional[str] = None
    branch_name: str
    trajectory_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Related data (populated via relationships)
    edits: List[SolveEditOut] = []
    ai_model: Optional[AIModelOut] = None
    swe_config: Optional[SWEAgentConfigOut] = None
    
    model_config = ConfigDict(from_attributes=True)

class SolveSessionStatsOut(BaseModel):
    """AI Solve Session statistics output schema"""
    session_id: int
    status: SolveStatus
    total_edits: int
    files_modified: int
    lines_added: int
    lines_removed: int
    duration_seconds: Optional[int] = None
    last_activity: Optional[datetime] = None
    trajectory_steps: int
    
    model_config = ConfigDict(from_attributes=True)

# Input schemas for API requests
class StartSolveRequest(BaseModel):
    """Request to start AI solver"""
    repo_url: Optional[str] = None
    branch_name: str = "main"
    ai_model_id: Optional[int] = None
    swe_config_id: Optional[int] = None

class StartSolveResponse(BaseModel):
    """Response when starting AI solver"""
    message: str
    session_id: int
    issue_id: int
    status: str

# Solver progress tracking schemas
class SolverProgressUpdate(BaseModel):
    """Real-time solver progress update"""
    session_id: int
    status: SolveStatus
    current_step: Optional[str] = None
    progress_percentage: Optional[float] = None
    files_processed: int = 0
    edits_made: int = 0
    estimated_completion: Optional[datetime] = None
    last_action: Optional[str] = None

class SolverTrajectoryStep(BaseModel):
    """Individual step in solver trajectory"""
    step_index: int
    timestamp: datetime
    action: str
    command: Optional[str] = None
    result: Optional[str] = None
    file_path: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None

class SolverTrajectoryOut(BaseModel):
    """Complete solver trajectory output"""
    session_id: int
    total_steps: int
    steps: List[SolverTrajectoryStep]
    final_status: SolveStatus
    summary: Optional[Dict[str, Any]] = None
    
    model_config = ConfigDict(from_attributes=True)