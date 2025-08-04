#!/usr/bin/env python3
"""
Centralized OAuth state management with database persistence

This module provides persistent OAuth state management using the database
to prevent CSRF attacks and ensure state validation survives server restarts.
"""

import secrets
from datetime import datetime, timedelta

from models import OAuthState  # Import the OAuthState model
from sqlalchemy.orm import Session


class OAuthStateManager:
    """
    Manages OAuth state parameters with persistent database storage.
    """
    
    def __init__(self, timeout_minutes: int = 5):
        self._timeout_minutes = timeout_minutes
    
    def generate_state(self, db: Session) -> str:
        """
        Generate a new OAuth state parameter and store it in the database.
        
        Returns:
            A cryptographically secure random state string
        """
        state = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=self._timeout_minutes)
        
        # Create new state record
        state_record = OAuthState(
            state=state,
            expires_at=expires_at,
            is_used=False
        )
        db.add(state_record)
        db.commit()
        return state
    
    def validate_state(self, db: Session, state: str) -> bool:
        """
        Validate and consume a state parameter from the database.
        
        Args:
            state: The state parameter to validate
            
        Returns:
            True if state is valid and not expired, False otherwise
        """
        # Query the database for the state
        state_record = db.query(OAuthState).filter(OAuthState.state == state).first()
        
        if not state_record:
            return False
        
        # Check if state has been used
        if state_record.is_used:
            return False
        
        # Check if state has expired
        if datetime.utcnow() > state_record.expires_at:
            db.delete(state_record)
            db.commit()
            return False
        
        # Mark state as used
        state_record.is_used = True
        db.commit()
        return True
    
    def cleanup_expired_states(self, db: Session) -> int:
        """
        Clean up expired state parameters from the database.
        
        Returns:
            Number of expired states removed
        """
        now = datetime.utcnow()
        expired_states = db.query(OAuthState).filter(OAuthState.expires_at < now).all()
        
        count = len(expired_states)
        for state in expired_states:
            db.delete(state)
        
        db.commit()
        return count

# Global instance for use across the application
state_manager = OAuthStateManager()