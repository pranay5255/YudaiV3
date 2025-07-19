"""
Context Cards API Routes

This module provides FastAPI routes for context cards functionality,
including CRUD operations for user context cards.
"""

from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from db.database import get_db
from models import (
    CreateContextRequest, ContextCardInput, ContextCardResponse
)
from auth.github_oauth import get_current_user
from .context_service import ContextService

# Create router for context endpoints
router = APIRouter(prefix="/context", tags=["context"])


@router.post("/cards", response_model=ContextCardResponse)
async def create_context_card(
    request: CreateContextRequest,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new context card
    """
    try:
        return ContextService.create_context_card(db, current_user.id, request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create context card: {str(e)}"
        )


@router.get("/cards", response_model=List[ContextCardResponse])
async def get_user_context_cards(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of cards to return"),
    include_inactive: bool = Query(False, description="Include inactive cards"),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all context cards for the authenticated user
    """
    try:
        return ContextService.get_user_context_cards(
            db, current_user.id, limit, include_inactive
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve context cards: {str(e)}"
        )


@router.get("/cards/{card_id}", response_model=ContextCardResponse)
async def get_context_card(
    card_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific context card by ID
    """
    context_card = ContextService.get_context_card(db, current_user.id, card_id)
    
    if not context_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context card not found"
        )
    
    return context_card


@router.put("/cards/{card_id}", response_model=ContextCardResponse)
async def update_context_card(
    card_id: int,
    updates: ContextCardInput,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update a context card
    """
    context_card = ContextService.update_context_card(
        db, current_user.id, card_id, updates
    )
    
    if not context_card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context card not found"
        )
    
    return context_card


@router.delete("/cards/{card_id}")
async def delete_context_card(
    card_id: int,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a context card (soft delete)
    """
    success = ContextService.delete_context_card(db, current_user.id, card_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Context card not found"
        )
    
    return {"message": "Context card deleted successfully"}


@router.get("/statistics")
async def get_context_statistics(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get statistics for user's context cards
    """
    try:
        stats = ContextService.get_context_card_statistics(db, current_user.id)
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve statistics: {str(e)}"
        ) 