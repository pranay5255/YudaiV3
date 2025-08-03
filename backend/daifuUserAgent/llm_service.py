"""
Centralized LLM Service for DAifu Agent
Eliminates duplication and standardizes LLM calls across chat endpoints
"""

import os
import time
from typing import List, Tuple

import requests
from fastapi import HTTPException, status


class LLMService:
    """Centralized service for LLM interactions"""
    
    # Standard model configuration
    DEFAULT_MODEL = "deepseek/deepseek-r1-0528:free"
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 1000
    DEFAULT_TIMEOUT = 30
    
    @staticmethod
    def get_api_key() -> str:
        """Get OpenRouter API key from environment"""
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OPENROUTER_API_KEY not configured",
            )
        return api_key
    
    @staticmethod
    def build_prompt_from_history(
        repo_context: str, 
        conversation_history: List[Tuple[str, str]]
    ) -> str:
        """Build prompt from conversation history"""
        from .prompt import build_daifu_prompt
        return build_daifu_prompt(repo_context, conversation_history)
    
    @staticmethod
    async def generate_response(
        prompt: str,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None
    ) -> str:
        """
        Generate response from LLM with standardized configuration
        
        Args:
            prompt: The prompt to send to the LLM
            model: Model to use (defaults to DEFAULT_MODEL)
            temperature: Temperature for generation (defaults to DEFAULT_TEMPERATURE)
            max_tokens: Maximum tokens to generate (defaults to DEFAULT_MAX_TOKENS)
            timeout: Request timeout in seconds (defaults to DEFAULT_TIMEOUT)
            
        Returns:
            Generated response text
            
        Raises:
            HTTPException: For API errors or configuration issues
        """
        start_time = time.time()
        
        # Use defaults if not provided
        model = model or LLMService.DEFAULT_MODEL
        temperature = temperature or LLMService.DEFAULT_TEMPERATURE
        max_tokens = max_tokens or LLMService.DEFAULT_MAX_TOKENS
        timeout = timeout or LLMService.DEFAULT_TIMEOUT
        
        try:
            api_key = LLMService.get_api_key()
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            
            body = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=body,
                timeout=timeout,
            )
            resp.raise_for_status()
            
            response_data = resp.json()
            reply = response_data["choices"][0]["message"]["content"].strip()
            
            processing_time = (time.time() - start_time) * 1000
            print(f"LLM response generated in {processing_time:.2f}ms")
            
            return reply
            
        except requests.RequestException as e:
            processing_time = (time.time() - start_time) * 1000
            print(f"LLM request failed after {processing_time:.2f}ms: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"LLM service unavailable: {str(e)}",
            )
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            print(f"LLM processing failed after {processing_time:.2f}ms: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM call failed: {str(e)}",
            )
    
    @staticmethod
    async def generate_response_with_history(
        repo_context: str,
        conversation_history: List[Tuple[str, str]],
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None
    ) -> str:
        """
        Generate response using conversation history
        
        Args:
            repo_context: Repository context for the prompt
            conversation_history: List of (sender, message) tuples
            model: Model to use
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds
            
        Returns:
            Generated response text
        """
        prompt = LLMService.build_prompt_from_history(repo_context, conversation_history)
        return await LLMService.generate_response(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        ) 