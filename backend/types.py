from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal, Union
from datetime import datetime
from enum import Enum

# Enums for type safety
class ContextSource(str, Enum):
    CHAT = "chat"
    FILE_DEPS = "file-deps"
    UPLOAD = "upload"

class ComplexityLevel(str, Enum):
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"

class ToastType(str, Enum):
    SUCCESS = "success"
    ERROR = "error"
    INFO = "info"

class ProgressStep(str, Enum):
    PM = "PM"
    ARCHITECT = "Architect"
    TEST_WRITER = "Test-Writer"
    CODER = "Coder"

class TabType(str, Enum):
    CHAT = "chat"
    FILE_DEPS = "file-deps"
    CONTEXT = "context"
    IDEAS = "ideas"

class FileType(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"

# Core User Input Models
class ChatMessageInput(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)
    is_code: bool = Field(default=False)
    
    @validator('content')
    def validate_content(cls, v):
        if not v.strip():
            raise ValueError('Message content cannot be empty')
        return v

class ContextCardInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)  # Full content for backend processing
    source: ContextSource = Field(default=ContextSource.CHAT)
    
    @validator('title')
    def validate_title(cls, v):
        if len(v.strip()) < 1:
            raise ValueError('Title cannot be empty')
        return v.strip()

class FileItemInput(BaseModel):
    name: str = Field(..., min_length=1)
    file_type: FileType = Field(...)
    tokens: int = Field(..., ge=0)
    is_directory: bool = Field(default=False)
    path: Optional[str] = Field(None)  # File system path
    content: Optional[str] = Field(None)  # File content if available
    
    @validator('name')
    def validate_name(cls, v):
        if not v.strip():
            raise ValueError('File name cannot be empty')
        return v.strip()

class IdeaItemInput(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=1000)
    complexity: ComplexityLevel = Field(...)
    estimated_tests: int = Field(..., ge=0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    
    @validator('title')
    def validate_title(cls, v):
        if len(v.strip()) < 1:
            raise ValueError('Idea title cannot be empty')
        return v.strip()

class CLICommandInput(BaseModel):
    args: List[str] = Field(default_factory=list)
    working_directory: Optional[str] = Field(None)
    environment_vars: Optional[dict] = Field(default_factory=dict)
    
    @validator('args')
    def validate_args(cls, v):
        if not isinstance(v, list):
            raise ValueError('Args must be a list of strings')
        return [str(arg) for arg in v]

# Request/Response Models
class CreateContextRequest(BaseModel):
    context_card: ContextCardInput
    
class CreateIdeaRequest(BaseModel):
    idea: IdeaItemInput
    
class ProcessFileRequest(BaseModel):
    file: FileItemInput
    
class ChatRequest(BaseModel):
    message: ChatMessageInput
    context_cards: Optional[List[str]] = Field(default_factory=list)  # Context card IDs
    
class CLIRequest(BaseModel):
    command: CLICommandInput
    
class CreateIssueRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    context_cards: List[str] = Field(default_factory=list)
    ideas: List[str] = Field(default_factory=list)
    priority: Literal["low", "medium", "high"] = Field(default="medium")
    
class ProcessUploadRequest(BaseModel):
    file_name: str = Field(...)
    file_type: str = Field(...)  # csv, pdf, txt, etc.
    content: str = Field(...)  # Base64 encoded or raw content
    max_tokens: int = Field(default=10000, ge=1, le=100000)

# Response Models
class APIResponse(BaseModel):
    success: bool = Field(...)
    message: str = Field(...)
    data: Optional[dict] = Field(None)
    error: Optional[str] = Field(None)

class ContextCardResponse(BaseModel):
    id: str = Field(...)
    title: str = Field(...)
    description: str = Field(...)
    tokens: int = Field(...)
    source: ContextSource = Field(...)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CLIResponse(BaseModel):
    stdout: str = Field(...)
    stderr: str = Field(...)
    exit_code: int = Field(...)
    execution_time: float = Field(...)

class IssueResponse(BaseModel):
    issue_id: str = Field(...)
    issue_url: str = Field(...)
    title: str = Field(...)
    status: str = Field(...)