from typing import Dict, Any, Optional, List
from pydantic import BaseModel

class CSVMetadata(BaseModel):
    filename: str
    schema: Dict[str, str]
    rowCount: int
    columnCount: int

class ProjectConfig(BaseModel):
    projectName: str
    repoPath: str
    cliConfig: Optional[Dict[str, Any]] = None

class PromptContext(BaseModel):
    prompt: str
    tokens: int
    generatedCode: Optional[str] = None

class RunCLIRequest(BaseModel):
    args: List[str] = []

class RunCLIResponse(BaseModel):
    stdout: str
    stderr: str
