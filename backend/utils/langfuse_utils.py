"""
Langfuse utilities for telemetry and observability in Yudai backend services.
"""

import os
import functools
import time
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import json

from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

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

def langfuse_trace(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Decorator for tracing function calls with Langfuse
    
    Args:
        name: Name of the trace
        metadata: Additional metadata to include
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not _langfuse_client:
                return await func(*args, **kwargs)
            
            trace = _langfuse_client.trace(
                name=name,
                metadata=metadata or {}
            )
            
            start_time = time.time()
            try:
                # Add input data to trace
                input_data = {
                    "args": str(args)[:500],  # Limit size
                    "kwargs": {k: str(v)[:200] for k, v in kwargs.items()}
                }
                trace.update(input=input_data)
                
                result = await func(*args, **kwargs)
                
                # Add successful output
                execution_time = time.time() - start_time
                trace.update(
                    output={"result": str(result)[:1000]},
                    metadata={
                        **(metadata or {}),
                        "execution_time_seconds": execution_time,
                        "status": "success"
                    }
                )
                
                return result
                
            except Exception as e:
                # Add error information
                execution_time = time.time() - start_time
                trace.update(
                    output={"error": str(e)},
                    metadata={
                        **(metadata or {}),
                        "execution_time_seconds": execution_time,
                        "status": "error",
                        "error_type": type(e).__name__
                    }
                )
                raise
            finally:
                _langfuse_client.flush()
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if not _langfuse_client:
                return func(*args, **kwargs)
            
            trace = _langfuse_client.trace(
                name=name,
                metadata=metadata or {}
            )
            
            start_time = time.time()
            try:
                # Add input data to trace
                input_data = {
                    "args": str(args)[:500],  # Limit size
                    "kwargs": {k: str(v)[:200] for k, v in kwargs.items()}
                }
                trace.update(input=input_data)
                
                result = func(*args, **kwargs)
                
                # Add successful output
                execution_time = time.time() - start_time
                trace.update(
                    output={"result": str(result)[:1000]},
                    metadata={
                        **(metadata or {}),
                        "execution_time_seconds": execution_time,
                        "status": "success"
                    }
                )
                
                return result
                
            except Exception as e:
                # Add error information
                execution_time = time.time() - start_time
                trace.update(
                    output={"error": str(e)},
                    metadata={
                        **(metadata or {}),
                        "execution_time_seconds": execution_time,
                        "status": "error",
                        "error_type": type(e).__name__
                    }
                )
                raise
            finally:
                _langfuse_client.flush()
        
        return async_wrapper if functools.iscoroutinefunction(func) else sync_wrapper
    return decorator

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
    Log LLM generation to Langfuse
    
    Args:
        name: Name of the generation
        model: Model used
        input_data: Input prompt/data
        output_data: Output from LLM
        metadata: Additional metadata
        tokens_used: Number of tokens used
        cost: Cost of the generation
    """
    if not _langfuse_client:
        return
    
    try:
        generation_data = {
            "name": name,
            "model": model,
            "input": input_data,
            "output": output_data,
            "metadata": metadata or {}
        }
        
        if tokens_used:
            generation_data["usage"] = {"total_tokens": tokens_used}
            
        if cost:
            generation_data["metadata"]["cost_usd"] = cost
        
        _langfuse_client.generation(**generation_data)
        _langfuse_client.flush()
        
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
    Log GitHub API calls to Langfuse
    
    Args:
        action: Type of GitHub action (create_issue, get_repos, etc.)
        repository: Repository name
        input_data: Input to the API call
        output_data: Output from GitHub API
        success: Whether the call was successful
        error: Error message if any
    """
    if not _langfuse_client:
        return
    
    try:
        event_data = {
            "name": f"github_api_{action}",
            "input": input_data,
            "output": output_data if success else {"error": error},
            "metadata": {
                "action": action,
                "repository": repository,
                "success": success,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        
        if error:
            event_data["metadata"]["error"] = error
        
        _langfuse_client.event(**event_data)
        _langfuse_client.flush()
        
    except Exception as e:
        print(f"Failed to log GitHub API call to Langfuse: {e}")

def architect_agent_trace(func: Callable):
    """
    Specific decorator for Architect Agent functions
    """
    return langfuse_trace(
        name=f"architect_agent_{func.__name__}",
        metadata={
            "agent": "yudai_architect",
            "function": func.__name__
        }
    )(func)

def daifu_agent_trace(func: Callable):
    """
    Specific decorator for Daifu Agent functions
    """
    return langfuse_trace(
        name=f"daifu_agent_{func.__name__}",
        metadata={
            "agent": "daifu_user_agent",
            "function": func.__name__
        }
    )(func)

def issue_service_trace(func: Callable):
    """
    Specific decorator for Issue Service functions
    """
    return langfuse_trace(
        name=f"issue_service_{func.__name__}",
        metadata={
            "service": "issue_service",
            "function": func.__name__
        }
    )(func) 