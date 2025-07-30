"""
Chat service for managing chat sessions and messages in the database
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from models import (
    ChatMessage,
    ChatMessageResponse,
    ChatSession,
    ChatSessionResponse,
    CreateChatMessageRequest,
    CreateChatSessionRequest,
    CreateFileEmbeddingRequest,
    FileEmbedding,
    FileEmbeddingResponse,
    SessionContextResponse,
    SessionResponse,
)
from sqlalchemy import and_, desc
from sqlalchemy.orm import Session


class ChatService:
    """Service class for managing chat operations"""
    
    @staticmethod
    def create_chat_session(
        db: Session, 
        user_id: int, 
        request: CreateChatSessionRequest
    ) -> ChatSessionResponse:
        """Create a new chat session"""
        session = ChatSession(
            user_id=user_id,
            session_id=request.session_id,
            title=request.title,
            description=request.description,
            is_active=True,
            total_messages=0,
            total_tokens=0,
            last_activity=datetime.utcnow()
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return ChatSessionResponse.model_validate(session)
    
    @staticmethod
    def get_chat_session(
        db: Session, 
        user_id: int, 
        session_id: str
    ) -> Optional[ChatSessionResponse]:
        """Get a chat session by session_id"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
            
        return ChatSessionResponse.model_validate(session)
    
    @staticmethod
    def get_user_chat_sessions(
        db: Session, 
        user_id: int, 
        limit: int = 50
    ) -> List[ChatSessionResponse]:
        """Get all chat sessions for a user"""
        sessions = db.query(ChatSession).filter(
            ChatSession.user_id == user_id
        ).order_by(desc(ChatSession.last_activity)).limit(limit).all()
        
        return [ChatSessionResponse.model_validate(session) for session in sessions]
    
    @staticmethod
    def create_chat_message(
        db: Session,
        user_id: int,
        request: CreateChatMessageRequest
    ) -> ChatMessageResponse:
        """Create a new chat message"""
        # First, get or create the session
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == request.session_id
            )
        ).first()
        
        if not session:
            # Create a new session if it doesn't exist
            session = ChatSession(
                user_id=user_id,
                session_id=request.session_id,
                is_active=True,
                total_messages=0,
                total_tokens=0,
                last_activity=datetime.utcnow()
            )
            db.add(session)
            db.commit()
            db.refresh(session)
        
        # Create the message
        message = ChatMessage(
            session_id=session.id,
            message_id=request.message_id,
            message_text=request.message_text,
            sender_type=request.sender_type,
            role=request.role,
            is_code=request.is_code,
            tokens=request.tokens,
            model_used=request.model_used,
            context_cards=request.context_cards,
            referenced_files=request.referenced_files
        )
        
        db.add(message)
        
        # Update session statistics
        session.total_messages += 1
        session.total_tokens += request.tokens
        session.last_activity = datetime.utcnow()
        
        db.commit()
        db.refresh(message)
        
        return ChatMessageResponse.model_validate(message)
    
    @staticmethod
    def get_chat_messages(
        db: Session,
        user_id: int,
        session_id: str,
        limit: int = 100
    ) -> List[ChatMessageResponse]:
        """Get messages for a specific chat session"""
        # First verify the session belongs to the user
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return []
        
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at).limit(limit).all()
        
        return [ChatMessageResponse.model_validate(message) for message in messages]
    
    @staticmethod
    def update_session_title(
        db: Session,
        user_id: int,
        session_id: str,
        title: str
    ) -> Optional[ChatSessionResponse]:
        """Update the title of a chat session"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
        
        session.title = title
        session.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(session)
        
        return ChatSessionResponse.model_validate(session)
    
    @staticmethod
    def deactivate_session(
        db: Session,
        user_id: int,
        session_id: str
    ) -> bool:
        """Deactivate a chat session"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return False
        
        session.is_active = False
        session.updated_at = datetime.utcnow()
        
        db.commit()
        return True
    
    @staticmethod
    def get_session_statistics(
        db: Session,
        user_id: int,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get statistics for a chat session"""
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
        
        # Get message count by sender type
        user_messages = db.query(ChatMessage).filter(
            and_(
                ChatMessage.session_id == session.id,
                ChatMessage.sender_type == "user"
            )
        ).count()
        
        assistant_messages = db.query(ChatMessage).filter(
            and_(
                ChatMessage.session_id == session.id,
                ChatMessage.sender_type == "assistant"
            )
        ).count()
        
        return {
            "session_id": session.session_id,
            "total_messages": session.total_messages,
            "total_tokens": session.total_tokens,
            "user_messages": user_messages,
            "assistant_messages": assistant_messages,
            "created_at": session.created_at,
            "last_activity": session.last_activity
        }


class SessionService:
    """Service class for managing session-scoped operations"""
    
    @staticmethod
    def get_or_create_session(
        db: Session,
        user_id: int,
        repo_owner: str,
        repo_name: str,
        repo_branch: str = "main",
        title: Optional[str] = None,
        description: Optional[str] = None
    ) -> SessionResponse:
        """Get existing session or create new one for repository"""
        
        # Try to find existing active session for this repo
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.repo_owner == repo_owner,
                ChatSession.repo_name == repo_name,
                ChatSession.repo_branch == repo_branch,
                ChatSession.is_active
            )
        ).first()
        
        if session:
            # Update last activity
            session.last_activity = datetime.utcnow()
            db.commit()
            db.refresh(session)
            return SessionResponse.model_validate(session)
        
        # Create new session
        session_id = f"{repo_owner}_{repo_name}_{repo_branch}_{int(datetime.utcnow().timestamp())}"
        
        # Create repository context
        repo_context = {
            "owner": repo_owner,
            "name": repo_name,
            "branch": repo_branch,
            "created_at": datetime.utcnow().isoformat(),
            "full_name": f"{repo_owner}/{repo_name}"
        }
        
        session = ChatSession(
            user_id=user_id,
            session_id=session_id,
            title=title or f"Session for {repo_owner}/{repo_name}",
            description=description,
            repo_owner=repo_owner,
            repo_name=repo_name,
            repo_branch=repo_branch,
            repo_context=repo_context,
            is_active=True,
            total_messages=0,
            total_tokens=0,
            last_activity=datetime.utcnow()
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        return SessionResponse.model_validate(session)
    
    @staticmethod
    def touch_session(
        db: Session,
        user_id: int,
        session_id: str
    ) -> Optional[SessionResponse]:
        """Update last_activity for a session"""
        
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
        
        session.last_activity = datetime.utcnow()
        db.commit()
        db.refresh(session)
        
        return SessionResponse.model_validate(session)
    
    @staticmethod
    def get_session_context(
        db: Session,
        user_id: int,
        session_id: str
    ) -> Optional[SessionContextResponse]:
        """Get complete session context including messages and context cards"""
        
        session = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.session_id == session_id
            )
        ).first()
        
        if not session:
            return None
        
        # Get messages for this session
        messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session.id
        ).order_by(ChatMessage.created_at).all()
        
        # Get context cards (extract from messages)
        context_cards = set()
        for msg in messages:
            if msg.context_cards:
                context_cards.update(msg.context_cards)
        
        # Get file embeddings count
        file_embeddings_count = db.query(FileEmbedding).filter(
            FileEmbedding.session_id == session.id
        ).count()
        
        return SessionContextResponse(
            session=SessionResponse.model_validate(session),
            messages=[ChatMessageResponse.model_validate(msg) for msg in messages],
            context_cards=list(context_cards),
            repository_info=session.repo_context,
            file_embeddings_count=file_embeddings_count
        )
    
    @staticmethod
    def get_user_sessions_by_repo(
        db: Session,
        user_id: int,
        repo_owner: Optional[str] = None,
        repo_name: Optional[str] = None
    ) -> List[SessionResponse]:
        """Get user sessions filtered by repository"""
        
        query = db.query(ChatSession).filter(
            and_(
                ChatSession.user_id == user_id,
                ChatSession.is_active
            )
        )
        
        if repo_owner:
            query = query.filter(ChatSession.repo_owner == repo_owner)
        if repo_name:
            query = query.filter(ChatSession.repo_name == repo_name)
        
        sessions = query.order_by(desc(ChatSession.last_activity)).all()
        
        return [SessionResponse.model_validate(session) for session in sessions]


class FileEmbeddingService:
    """Service class for managing file embeddings within sessions"""
    
    @staticmethod
    def create_file_embedding(
        db: Session,
        session_id: int,
        request: CreateFileEmbeddingRequest,
        repository_id: Optional[int] = None
    ) -> FileEmbeddingResponse:
        """Create a new file embedding for a session"""
        #TODO: add file embedding to pgvector and also check https://huggingface.co/docs/chat-ui/en/configuration/embeddings for setting up BERT flavour ot whichever is fastest
        
        embedding = FileEmbedding(
            session_id=session_id,
            repository_id=repository_id,
            file_path=request.file_path,
            file_name=request.file_name,
            file_type=request.file_type,
            file_content=request.file_content,
            chunk_text=request.chunk_text,
            chunk_index=request.chunk_index,
            tokens=request.tokens,
            file_metadata=request.file_metadata
        )
        
        db.add(embedding)
        db.commit()
        db.refresh(embedding)
        
        return FileEmbeddingResponse.model_validate(embedding)
    
    @staticmethod
    def get_session_embeddings(
        db: Session,
        session_id: int,
        limit: int = 100
    ) -> List[FileEmbeddingResponse]:
        """Get all file embeddings for a session"""
        #TODO: are supposed to break down all files from filedeps, make chunks of them and create embeddings for the repository
        
        embeddings = db.query(FileEmbedding).filter(
            FileEmbedding.session_id == session_id
        ).order_by(FileEmbedding.created_at).limit(limit).all()
        
        return [FileEmbeddingResponse.model_validate(emb) for emb in embeddings]
    
    @staticmethod
    def search_similar_embeddings(
        db: Session,
        session_id: int,
        query_text: str,
        limit: int = 10
    ) -> List[FileEmbeddingResponse]:
        """Search for similar embeddings based on text content (minimal implementation)"""
        
        # Simple text matching for now - can be enhanced with pgvector later
        #TODO: add pgvector search and how to do it with https://huggingface.co/docs/
        embeddings = db.query(FileEmbedding).filter(
            and_(
                FileEmbedding.session_id == session_id,
                FileEmbedding.chunk_text.contains(query_text)
            )
        ).limit(limit).all()
        
        return [FileEmbeddingResponse.model_validate(emb) for emb in embeddings] 