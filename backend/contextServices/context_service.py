"""
Context service for managing context cards in the database
"""
import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from models import (
    ContextCard, User,
    CreateContextRequest, ContextCardInput,
    ContextCardResponse
)


class ContextService:
    """Service class for managing context card operations"""
    
    @staticmethod
    def create_context_card(
        db: Session,
        user_id: int,
        request: CreateContextRequest
    ) -> ContextCardResponse:
        """Create a new context card"""
        context_input = request.context_card
        
        # Calculate tokens (simple estimation based on content length)
        tokens = len(context_input.content.split())
        
        context_card = ContextCard(
            user_id=user_id,
            title=context_input.title,
            description=context_input.description,
            content=context_input.content,
            source=context_input.source.value,
            tokens=tokens,
            is_active=True
        )
        
        db.add(context_card)
        db.commit()
        db.refresh(context_card)
        
        return ContextCardResponse(
            id=str(context_card.id),
            title=context_card.title,
            description=context_card.description,
            tokens=context_card.tokens,
            source=context_card.source,
            created_at=context_card.created_at
        )
    
    @staticmethod
    def get_user_context_cards(
        db: Session,
        user_id: int,
        limit: int = 100,
        include_inactive: bool = False
    ) -> List[ContextCardResponse]:
        """Get all context cards for a user"""
        query = db.query(ContextCard).filter(ContextCard.user_id == user_id)
        
        if not include_inactive:
            query = query.filter(ContextCard.is_active == True)
        
        context_cards = query.order_by(desc(ContextCard.created_at)).limit(limit).all()
        
        return [
            ContextCardResponse(
                id=str(card.id),
                title=card.title,
                description=card.description,
                tokens=card.tokens,
                source=card.source,
                created_at=card.created_at
            )
            for card in context_cards
        ]
    
    @staticmethod
    def get_context_card(
        db: Session,
        user_id: int,
        card_id: int
    ) -> Optional[ContextCardResponse]:
        """Get a specific context card by ID"""
        context_card = db.query(ContextCard).filter(
            and_(
                ContextCard.id == card_id,
                ContextCard.user_id == user_id,
                ContextCard.is_active == True
            )
        ).first()
        
        if not context_card:
            return None
        
        return ContextCardResponse(
            id=str(context_card.id),
            title=context_card.title,
            description=context_card.description,
            tokens=context_card.tokens,
            source=context_card.source,
            created_at=context_card.created_at
        )
    
    @staticmethod
    def update_context_card(
        db: Session,
        user_id: int,
        card_id: int,
        updates: ContextCardInput
    ) -> Optional[ContextCardResponse]:
        """Update a context card"""
        context_card = db.query(ContextCard).filter(
            and_(
                ContextCard.id == card_id,
                ContextCard.user_id == user_id,
                ContextCard.is_active == True
            )
        ).first()
        
        if not context_card:
            return None
        
        # Update fields
        context_card.title = updates.title
        context_card.description = updates.description
        context_card.content = updates.content
        context_card.source = updates.source.value
        context_card.tokens = len(updates.content.split())  # Recalculate tokens
        context_card.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(context_card)
        
        return ContextCardResponse(
            id=str(context_card.id),
            title=context_card.title,
            description=context_card.description,
            tokens=context_card.tokens,
            source=context_card.source,
            created_at=context_card.created_at
        )
    
    @staticmethod
    def delete_context_card(
        db: Session,
        user_id: int,
        card_id: int
    ) -> bool:
        """Soft delete a context card (mark as inactive)"""
        context_card = db.query(ContextCard).filter(
            and_(
                ContextCard.id == card_id,
                ContextCard.user_id == user_id,
                ContextCard.is_active == True
            )
        ).first()
        
        if not context_card:
            return False
        
        context_card.is_active = False
        context_card.updated_at = datetime.utcnow()
        
        db.commit()
        return True
    
    @staticmethod
    def get_context_card_statistics(
        db: Session,
        user_id: int
    ) -> dict:
        """Get statistics for user's context cards"""
        total_cards = db.query(ContextCard).filter(
            and_(
                ContextCard.user_id == user_id,
                ContextCard.is_active == True
            )
        ).count()
        
        total_tokens = db.query(ContextCard).filter(
            and_(
                ContextCard.user_id == user_id,
                ContextCard.is_active == True
            )
        ).with_entities(ContextCard.tokens).all()
        
        total_token_count = sum(tokens[0] for tokens in total_tokens)
        
        # Count by source
        sources = db.query(ContextCard.source).filter(
            and_(
                ContextCard.user_id == user_id,
                ContextCard.is_active == True
            )
        ).all()
        
        source_counts = {}
        for source in sources:
            source_counts[source[0]] = source_counts.get(source[0], 0) + 1
        
        return {
            "total_cards": total_cards,
            "total_tokens": total_token_count,
            "source_breakdown": source_counts
        } 