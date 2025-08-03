#!/usr/bin/env python3
"""
Centralized OAuth state management

This module provides a centralized way to manage OAuth state parameters
to prevent CSRF attacks and ensure proper state validation across server restarts.
"""

import secrets
import time
from typing import Dict


class OAuthStateManager:
    """
    Manages OAuth state parameters with timeout and cleanup functionality.
    
    In production, this should be replaced with database storage or Redis
    to persist states across server restarts.
    """
    
    def __init__(self, timeout_minutes: int = 5):
        self._states: Dict[str, float] = {}
        self._state_timeout = timeout_minutes * 60  # Convert to seconds
    
    def generate_state(self) -> str:
        """
        Generate a new OAuth state parameter with timestamp.
        
        Returns:
            A cryptographically secure random state string
        """
        state = secrets.token_urlsafe(32)
        self._states[state] = time.time()
        return state
    
    def validate_state(self, state: str) -> bool:
        """
        Validate and consume a state parameter.
        
        Args:
            state: The state parameter to validate
            
        Returns:
            True if state is valid and not expired, False otherwise
        """
        if state not in self._states:
            return False
        
        # Check if state has expired
        if time.time() - self._states[state] > self._state_timeout:
            self._states.pop(state, None)
            return False
        
        # Remove used state (one-time use)
        self._states.pop(state, None)
        return True
    
    def cleanup_expired_states(self) -> int:
        """
        Clean up expired state parameters.
        
        Returns:
            Number of expired states removed
        """
        current_time = time.time()
        expired_states = [
            state for state, timestamp in self._states.items()
            if current_time - timestamp > self._state_timeout
        ]
        
        for state in expired_states:
            self._states.pop(state, None)
        
        return len(expired_states)
    
    def get_active_states_count(self) -> int:
        """
        Get the number of active (non-expired) states.
        
        Returns:
            Number of active states
        """
        self.cleanup_expired_states()
        return len(self._states)
    
    def clear_all_states(self) -> int:
        """
        Clear all states (useful for testing).
        
        Returns:
            Number of states cleared
        """
        count = len(self._states)
        self._states.clear()
        return count

# Global instance for use across the application
state_manager = OAuthStateManager() 