"""
Centralized Message Service for DAifu Agent
Eliminates duplication in message creation and storage logic
"""

import uuid
from typing import List, Optional

from issueChatServices.chat_service import ChatService
from models import ChatRequest, CreateChatMessageRequest
from sqlalchemy.orm import Session


class MessageService:
    """Centralized service for message operations"""
    
    @staticmethod
    def create_user_message_request(
        session_id: str,
        content: str,
        is_code: bool = False,
        context_cards: Optional[List[str]] = None,
        message_id: Optional[str] = None
    ) -> CreateChatMessageRequest:
        """
        Create a standardized user message request
        
        Args:
            session_id: Session ID for the message
            content: Message content
            is_code: Whether the message contains code
            context_cards: Optional context cards
            message_id: Optional custom message ID (generates UUID if not provided)
            
        Returns:
            CreateChatMessageRequest object
        """
        return CreateChatMessageRequest(
            session_id=session_id,
            message_id=message_id or str(uuid.uuid4()),
            message_text=content,
            sender_type="user",
            role="user",
            is_code=is_code,
            tokens=len(content.split()),
            context_cards=context_cards or [],
        )
    
    @staticmethod
    def create_assistant_message_request(
        session_id: str,
        content: str,
        model_used: str = "deepseek/deepseek-r1-0528:free",
        processing_time: Optional[float] = None,
        message_id: Optional[str] = None
    ) -> CreateChatMessageRequest:
        """
        Create a standardized assistant message request
        
        Args:
            session_id: Session ID for the message
            content: Message content
            model_used: Model used for generation
            processing_time: Processing time in milliseconds
            message_id: Optional custom message ID (generates UUID if not provided)
            
        Returns:
            CreateChatMessageRequest object
        """
        return CreateChatMessageRequest(
            session_id=session_id,
            message_id=message_id or str(uuid.uuid4()),
            message_text=content,
            sender_type="assistant",
            role="assistant",
            is_code=False,
            tokens=len(content.split()),
            model_used=model_used,
            processing_time=processing_time,
        )
    
    @staticmethod
    def create_error_message_request(
        session_id: str,
        error_message: str,
        error_type: str = "system",
        message_id: Optional[str] = None
    ) -> CreateChatMessageRequest:
        """
        Create a standardized error message request
        
        Args:
            session_id: Session ID for the message
            error_message: Error message content
            error_type: Type of error (system, network, etc.)
            message_id: Optional custom message ID (generates UUID if not provided)
            
        Returns:
            CreateChatMessageRequest object
        """
        return CreateChatMessageRequest(
            session_id=session_id,
            message_id=message_id or str(uuid.uuid4()),
            message_text=f"Error: {error_message}",
            sender_type=error_type,
            role="system",
            is_code=False,
            tokens=0,
            error_message=error_message,
        )
    
    @staticmethod
    def store_user_message(
        db: Session,
        user_id: int,
        session_id: str,
        content: str,
        is_code: bool = False,
        context_cards: Optional[List[str]] = None
    ):
        """
        Store a user message in the database
        
        Args:
            db: Database session
            user_id: User ID
            session_id: Session ID
            content: Message content
            is_code: Whether the message contains code
            context_cards: Optional context cards
        """
        user_message_request = MessageService.create_user_message_request(
            session_id=session_id,
            content=content,
            is_code=is_code,
            context_cards=context_cards
        )
        return ChatService.create_chat_message(db, user_id, user_message_request)
    
    @staticmethod
    def store_assistant_message(
        db: Session,
        user_id: int,
        session_id: str,
        content: str,
        model_used: str = "deepseek/deepseek-r1-0528:free",
        processing_time: Optional[float] = None
    ):
        """
        Store an assistant message in the database
        
        Args:
            db: Database session
            user_id: User ID
            session_id: Session ID
            content: Message content
            model_used: Model used for generation
            processing_time: Processing time in milliseconds
        """
        assistant_message_request = MessageService.create_assistant_message_request(
            session_id=session_id,
            content=content,
            model_used=model_used,
            processing_time=processing_time
        )
        return ChatService.create_chat_message(db, user_id, assistant_message_request)
    
    @staticmethod
    def store_error_message(
        db: Session,
        user_id: int,
        session_id: str,
        error_message: str,
        error_type: str = "system"
    ):
        """
        Store an error message in the database
        
        Args:
            db: Database session
            user_id: User ID
            session_id: Session ID
            error_message: Error message
            error_type: Type of error
        """
        error_message_request = MessageService.create_error_message_request(
            session_id=session_id,
            error_message=error_message,
            error_type=error_type
        )
        return ChatService.create_chat_message(db, user_id, error_message_request)
    
    @staticmethod
    def convert_chat_request_to_message_request(
        chat_request: ChatRequest,
        message_id: Optional[str] = None
    ) -> CreateChatMessageRequest:
        """
        Convert a ChatRequest to CreateChatMessageRequest for user messages
        
        Args:
            chat_request: ChatRequest object
            message_id: Optional custom message ID
            
        Returns:
            CreateChatMessageRequest object
        """
        return MessageService.create_user_message_request(
            session_id=chat_request.session_id,
            content=chat_request.message.content,
            is_code=chat_request.message.is_code,
            context_cards=chat_request.context_cards,
            message_id=message_id
        ) 