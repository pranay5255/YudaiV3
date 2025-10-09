from typing import List, Optional

from pydantic import BaseModel, Field


class ExperimentMatrix(BaseModel):
    models: List[str] = Field(default_factory=list, description="List of models to use")
    temps: List[float] = Field(default_factory=list, description="List of temperatures")
    max_edits: List[int] = Field(default_factory=list, description="List of max edits")
    evolution: List[str] = Field(default_factory=list, description="List of evolution strategies")

class Limits(BaseModel):
    max_parallel: int = Field(default=6, description="Maximum parallel experiments")
    time_budget_s: int = Field(default=1800, description="Time budget in seconds")

class SolveRequest(BaseModel):
    repo_url: str = Field(..., description="URL of the repository")
    issue_number: int = Field(..., description="GitHub issue number")
    base_branch: str = Field(default="main", description="Base branch")
    matrix: ExperimentMatrix = Field(..., description="Experiment matrix")
    limits: Optional[Limits] = Field(None, description="Execution limits")
    requested_by: Optional[str] = Field(
        None, description="Human readable identifier for the requester"
    )

class SolveResponse(BaseModel):
    solve_id: str = Field(..., description="ID of the solve job")
    status: str = Field(..., description="Initial status")
