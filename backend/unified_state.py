"""
Unified State Management for Python Backend
Mirrors TypeScript interfaces to ensure consistent state across WebSocket communication
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    DAIFU = "daifu"
    ARCHITECT = "architect"
    CODER = "coder"
    TESTER = "tester"


class AgentStatus(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ContextCardSource(str, Enum):
    CHAT = "chat"
    FILE = "file"
    GITHUB = "github"
    MANUAL = "manual"


# Removed WebSocketMessageType enum - no longer needed without WebSockets


# Unified state models that mirror TypeScript interfaces
class UnifiedRepository(BaseModel):
    owner: str
    name: str
    branch: str
    full_name: str
    html_url: str


class UnifiedMessage(BaseModel):
    id: str
    session_id: str
    content: str
    role: MessageRole
    is_code: bool = False
    timestamp: datetime
    tokens: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UnifiedContextCard(BaseModel):
    id: str
    session_id: str
    title: str
    description: str
    content: str
    tokens: int
    source: ContextCardSource
    created_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }





class UnifiedAgentStatus(BaseModel):
    type: AgentType
    status: AgentStatus
    current_task: Optional[str] = None
    progress: Optional[int] = Field(None, ge=0, le=100)  # 0-100
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UnifiedStatistics(BaseModel):
    total_messages: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    session_duration: int = 0  # in seconds
    agent_actions: int = 0
    files_processed: int = 0


class UnifiedSessionState(BaseModel):
    session_id: Optional[str]
    user_id: Optional[int]
    repository: Optional[UnifiedRepository]
    messages: List[UnifiedMessage] = []
    context_cards: List[UnifiedContextCard] = []

    agent_status: UnifiedAgentStatus
    statistics: UnifiedStatistics
    last_activity: datetime
    is_active: bool = True

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Removed UnifiedWebSocketMessage and UnifiedWebSocketManager - no longer needed without WebSockets


# State conversion utilities
class StateConverter:
    """
    Converts between SQLAlchemy models and unified state models
    """
    
    @staticmethod
    def chat_session_to_unified(chat_session, messages=None, context_cards=None) -> UnifiedSessionState:
        """Convert SQLAlchemy ChatSession to UnifiedSessionState"""
        return UnifiedSessionState(
            session_id=chat_session.session_id,
            user_id=chat_session.user_id,
            repository=UnifiedRepository(
                owner=chat_session.repo_owner or "",
                name=chat_session.repo_name or "",
                branch=chat_session.repo_branch or "main",
                full_name=f"{chat_session.repo_owner}/{chat_session.repo_name}" if chat_session.repo_owner and chat_session.repo_name else "",
                html_url=f"https://github.com/{chat_session.repo_owner}/{chat_session.repo_name}" if chat_session.repo_owner and chat_session.repo_name else ""
            ) if chat_session.repo_owner and chat_session.repo_name else None,
            messages=[StateConverter.message_to_unified(msg) for msg in (messages or [])],
            context_cards=[StateConverter.context_card_to_unified(card) for card in (context_cards or [])],

            agent_status=UnifiedAgentStatus(
                type=AgentType.DAIFU,  # Default agent type
                status=AgentStatus.IDLE
            ),
            statistics=UnifiedStatistics(
                total_messages=chat_session.total_messages,
                total_tokens=chat_session.total_tokens
            ),
            last_activity=chat_session.last_activity or chat_session.created_at,
            is_active=chat_session.is_active
        )
    
    @staticmethod
    def message_to_unified(message) -> UnifiedMessage:
        """Convert SQLAlchemy ChatMessage to UnifiedMessage"""
        return UnifiedMessage(
            id=str(message.id),
            session_id=message.session_id,
            content=message.content,
            role=MessageRole(message.role),
            is_code=message.is_code or False,
            timestamp=message.created_at,
            tokens=message.tokens
        )
    
    @staticmethod
    def context_card_to_unified(card) -> UnifiedContextCard:
        """Convert context card to UnifiedContextCard"""
        return UnifiedContextCard(
            id=str(card.id),
            session_id=card.session_id if hasattr(card, 'session_id') else "",
            title=card.title,
            description=card.description or "",
            content=card.content or "",
            tokens=card.tokens or 0,
            source=ContextCardSource.CHAT,  # Default source
            created_at=card.created_at if hasattr(card, 'created_at') else datetime.utcnow()
        )
    



# Removed unified WebSocket manager - no longer needed without WebSockets