"""
Langfuse utilities for telemetry and observability in Yudai backend services.
"""

import os
import functools
from typing import Dict, Any, Optional, Callable

from langfuse import Langfuse, observe, get_client

# Initialize Langfuse client
def get_langfuse_client() -> Optional[Langfuse]:
    """Get configured Langfuse client or None if not configured"""
    try:
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        host = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
        
        if not secret_key or not public_key:
            print("Langfuse credentials not found, telemetry disabled")
            return None
            
        # Skip dummy keys
        if secret_key == "sk-dummy" or public_key == "pk-dummy":
            print("Langfuse dummy credentials detected, telemetry disabled")
            return None
            
        return Langfuse(
            secret_key=secret_key,
            public_key=public_key,
            host=host
        )
    except Exception as e:
        print(f"Failed to initialize Langfuse: {e}")
        return None

# Global Langfuse client
_langfuse_client = get_langfuse_client()

def is_langfuse_enabled() -> bool:
    """Check if Langfuse is properly configured and enabled"""
    return _langfuse_client is not None

# Decorator aliases for different agents/services
def architect_agent_trace(func: Callable):
    """Decorator for Architect Agent functions"""
    if not is_langfuse_enabled():
        return func
    
    return observe(func)

def daifu_agent_trace(func: Callable):
    """Decorator for Daifu Agent functions"""
    if not is_langfuse_enabled():
        return func
    
    return observe(func)

def issue_service_trace(func: Callable):
    """Decorator for Issue Service functions"""
    if not is_langfuse_enabled():
        return func
    
    return observe(func)

def github_api_trace(func: Callable):
    """Decorator for GitHub API functions"""
    if not is_langfuse_enabled():
        return func
    
    return observe(func)

def chat_service_trace(func: Callable):
    """Decorator for Chat Service functions"""
    if not is_langfuse_enabled():
        return func
    
    return observe(func)

# Utility functions for manual logging when needed
def log_llm_generation(
    name: str,
    model: str,
    input_data: Dict[str, Any],
    output_data: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None,
    tokens_used: Optional[int] = None,
    cost: Optional[float] = None
):
    """
    Log LLM generation manually (use when @observe decorator isn't sufficient)
    
    Args:
        name: Name of the generation
        model: Model used
        input_data: Input prompt/data
        output_data: Output from LLM
        metadata: Additional metadata
        tokens_used: Number of tokens used
        cost: Cost of the generation
    """
    if not is_langfuse_enabled():
        return
    
    try:
        # Use get_client() for manual logging
        client = get_client()
        if client:
            client.generation(
                name=name,
                model=model,
                input=input_data,
                output=output_data,
                metadata={
                    **(metadata or {}),
                    "tokens_used": tokens_used,
                    "cost_usd": cost
                },
                usage={
                    "total_tokens": tokens_used
                } if tokens_used else None
            )
        
    except Exception as e:
        print(f"Failed to log LLM generation to Langfuse: {e}")

def log_github_api_call(
    action: str,
    repository: str,
    input_data: Dict[str, Any],
    output_data: Dict[str, Any],
    success: bool = True,
    error: Optional[str] = None
):
    """
    Log GitHub API calls manually
    
    Args:
        action: Type of GitHub action (create_issue, get_repos, etc.)
        repository: Repository name
        input_data: Input to the API call
        output_data: Output from GitHub API
        success: Whether the call was successful
        error: Error message if any
    """
    if not is_langfuse_enabled():
        return
    
    try:
        # Use get_client() for manual logging
        client = get_client()
        if client:
            client.event(
                name=f"github_api_{action}",
                input=input_data,
                output=output_data if success else {"error": error},
                metadata={
                    "action": action,
                    "repository": repository,
                    "success": success,
                    "service": "github_api"
                }
            )
        
    except Exception as e:
        print(f"Failed to log GitHub API call to Langfuse: {e}")

# Legacy function name for backward compatibility
def langfuse_trace(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Legacy decorator - use specific agent decorators instead
    """
    def decorator(func: Callable):
        if not is_langfuse_enabled():
            return func
        
        return observe(func)
    return decorator 