"""
Unified State Management for Python Backend
Mirrors TypeScript interfaces to ensure consistent state across WebSocket communication
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from enum import Enum


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


class WebSocketMessageType(str, Enum):
    SESSION_UPDATE = "session_update"
    MESSAGE = "message"
    CONTEXT_CARD = "context_card"
    FILE_EMBEDDING = "file_embedding"
    AGENT_STATUS = "agent_status"
    STATISTICS = "statistics"
    HEARTBEAT = "heartbeat"
    ERROR = "error"


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


class UnifiedFileEmbedding(BaseModel):
    id: int
    session_id: str
    file_name: str
    file_path: str
    file_type: str
    content_summary: Optional[str] = None
    tokens: int
    embedding_vector: Optional[List[float]] = None
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
    file_embeddings: List[UnifiedFileEmbedding] = []
    agent_status: UnifiedAgentStatus
    statistics: UnifiedStatistics
    last_activity: datetime
    is_active: bool = True

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UnifiedWebSocketMessage(BaseModel):
    type: WebSocketMessageType
    session_id: str
    data: Dict[str, Any]  # Union of all possible data types
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# WebSocket connection manager for unified state
class UnifiedWebSocketManager:
    """
    WebSocket connection manager that maintains unified state
    and broadcasts updates to connected clients
    """
    
    def __init__(self):
        # {session_id: [WebSocket, WebSocket, ...]}
        self.connections: Dict[str, List[Any]] = {}
        # {session_id: UnifiedSessionState}
        self.session_states: Dict[str, UnifiedSessionState] = {}

    async def connect(self, websocket: Any, session_id: str, db_session):
        """
        Connect a WebSocket to a session. If it's the first connection
        for this session, load the state from the database.
        """
        await websocket.accept()
        if session_id not in self.connections:
            self.connections[session_id] = []
        self.connections[session_id].append(websocket)

        # If state is not already in memory, load it from the database
        if session_id not in self.session_states:
            from issueChatServices.session_service import SessionService  # Avoid circular import
            # Assuming user_id is retrievable from a token or similar, for now, this is a simplification
            # In a real scenario, you would authenticate the websocket connection
            try:
                # We need a user_id to fetch the comprehensive context.
                # This is a simplification. A real implementation would get the user from the websocket scope/token.
                # For now, let's find the user associated with the session.
                from models import ChatSession
                session_db = db_session.query(ChatSession).filter(ChatSession.session_id == session_id).first()
                if not session_db:
                    print(f"Session {session_id} not found in DB for new connection.")
                    return # Or send an error
                
                state = SessionService.get_comprehensive_session_context(db_session, session_db.user_id, session_id)
                if state:
                    self.session_states[session_id] = state
                else:
                    print(f"Could not load state for session {session_id}")

            except Exception as e:
                print(f"Error loading session state for {session_id}: {e}")


        # Send the latest state to the newly connected client
        if session_id in self.session_states:
            await self.send_session_state(session_id, self.session_states[session_id], specific_ws=websocket)

    def disconnect(self, websocket: Any, session_id: str):
        """Disconnect a WebSocket. If it's the last connection, clear the state from memory."""
        if session_id in self.connections and websocket in self.connections[session_id]:
            self.connections[session_id].remove(websocket)
            if not self.connections[session_id]:
                # Last client disconnected, clean up
                del self.connections[session_id]
                if session_id in self.session_states:
                    del self.session_states[session_id]
                    print(f"Session state for {session_id} cleared from memory.")
    
    async def broadcast_to_session(self, session_id: str, message: UnifiedWebSocketMessage):
        """Broadcast a message to all connections for a session"""
        if session_id in self.connections:
            message_json = message.json()
            disconnected = []
            
            for connection in self.connections[session_id]:
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    print(f"Error sending WebSocket message: {e}")
                    disconnected.append(connection)
            
            # Remove disconnected connections
            for connection in disconnected:
                self.disconnect(connection, session_id)
    
    async def send_session_state(self, session_id: str, state: UnifiedSessionState, specific_ws: Optional[Any] = None):
        """Send the complete session state to all connections for a session, or just one."""
        message = UnifiedWebSocketMessage(
            type=WebSocketMessageType.SESSION_UPDATE,
            session_id=session_id,
            data=state.dict()
        )
        if specific_ws:
             await specific_ws.send_text(message.json())
        else:
            await self.broadcast_to_session(session_id, message)
    
    async def update_and_broadcast_message(self, session_id: str, message: UnifiedMessage):
        """Adds a message to the state and broadcasts the update."""
        if session_id in self.session_states:
            self.session_states[session_id].messages.append(message)
            self.session_states[session_id].statistics.total_messages += 1
            ws_message = UnifiedWebSocketMessage(
                type=WebSocketMessageType.MESSAGE,
                session_id=session_id,
                data=message.dict()
            )
            await self.broadcast_to_session(session_id, ws_message)
    
    async def send_context_card_update(self, session_id: str, card: UnifiedContextCard, action: str = "add"):
        """Send a context card update to all connections"""
        ws_message = UnifiedWebSocketMessage(
            type=WebSocketMessageType.CONTEXT_CARD,
            session_id=session_id,
            data={"action": action, "card": card.dict()}
        )
        await self.broadcast_to_session(session_id, ws_message)
    
    async def send_agent_status_update(self, session_id: str, status: UnifiedAgentStatus):
        """Send an agent status update to all connections"""
        ws_message = UnifiedWebSocketMessage(
            type=WebSocketMessageType.AGENT_STATUS,
            session_id=session_id,
            data=status.dict()
        )
        await self.broadcast_to_session(session_id, ws_message)
    
    async def send_statistics_update(self, session_id: str, stats: UnifiedStatistics):
        """Send statistics update to all connections"""
        ws_message = UnifiedWebSocketMessage(
            type=WebSocketMessageType.STATISTICS,
            session_id=session_id,
            data=stats.dict()
        )
        await self.broadcast_to_session(session_id, ws_message)
    
    async def send_heartbeat(self, session_id: str):
        """Send heartbeat to all connections"""
        ws_message = UnifiedWebSocketMessage(
            type=WebSocketMessageType.HEARTBEAT,
            session_id=session_id,
            data={"timestamp": datetime.utcnow().timestamp()}
        )
        await self.broadcast_to_session(session_id, ws_message)


# State conversion utilities
class StateConverter:
    """
    Converts between SQLAlchemy models and unified state models
    """
    
    @staticmethod
    def chat_session_to_unified(chat_session, messages=None, context_cards=None, file_embeddings=None) -> UnifiedSessionState:
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
            file_embeddings=[StateConverter.file_embedding_to_unified(emb) for emb in (file_embeddings or [])],
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
    
    @staticmethod
    def file_embedding_to_unified(embedding) -> UnifiedFileEmbedding:
        """Convert SQLAlchemy FileEmbedding to UnifiedFileEmbedding"""
        return UnifiedFileEmbedding(
            id=embedding.id,
            session_id=embedding.session_id,
            file_name=embedding.file_name,
            file_path=embedding.file_path,
            file_type=embedding.file_type,
            content_summary=embedding.content_summary,
            tokens=embedding.tokens,
            embedding_vector=embedding.embedding_vector,
            created_at=embedding.created_at
        )


# Global unified WebSocket manager instance
unified_manager = UnifiedWebSocketManager()