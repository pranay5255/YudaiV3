"""
Centralized LLM Service for DAifu Agent
Eliminates duplication and standardizes LLM calls across chat endpoints
"""

import os
import time
from typing import List, Tuple

import requests
from fastapi import HTTPException, status
from models import FileEmbedding
from pgvector.sqlalchemy import Vector
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.orm import Session


class LLMService:
    """Centralized service for LLM interactions"""

    # Standard model configuration
    DEFAULT_MODEL = "deepseek/deepseek-r1-0528"
    DEFAULT_TEMPERATURE = 0.4
    DEFAULT_MAX_TOKENS = 4000
    DEFAULT_TIMEOUT = 30
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    # Class variable to cache the model
    _embedding_model = None
    
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
    def get_embedding_model() -> SentenceTransformer:
        """Get or load the embedding model (cached for performance)"""
        if LLMService._embedding_model is None:
            LLMService._embedding_model = SentenceTransformer(LLMService.EMBEDDING_MODEL)
        return LLMService._embedding_model
    
    @staticmethod
    def build_prompt_from_history(
        repo_context: str,
        conversation_history: List[Tuple[str, str]],
        github_data: tuple = None,
        file_contexts: List[str] = None
    ) -> str:
        """Build prompt from conversation history"""
        from .prompt import build_daifu_prompt

        if github_data:
            repo_details, commits, issues, pulls = github_data
            return build_daifu_prompt(repo_details, commits, issues, pulls, conversation_history, file_contexts)
        else:
            # Fallback to empty data structures
            repo_details = {"full_name": "Repository", "description": "", "default_branch": "",
                           "languages": {}, "topics": [], "license": None, "stargazers_count": 0,
                           "forks_count": 0, "open_issues_count": 0, "html_url": ""}
            commits = []
            issues = []
            pulls = []
            return build_daifu_prompt(repo_details, commits, issues, pulls, conversation_history, file_contexts)
    
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
    async def get_relevant_file_contexts(
        db: Session,
        session_id: int,
        query_text: str,
        top_k: int = 5,
        model: str = None
    ) -> List[str]:
        """
        Retrieve relevant file chunk texts using embedding similarity search.

        Args:
            db: Database session
            session_id: Session ID to scope the search
            query_text: Text to embed and search against
            top_k: Number of top results to return
            model: Ignored (uses local sentence-transformers model)

        Returns:
            List of relevant chunk texts
        """
        # Generate embedding for query
        query_embedding = LLMService.embed_text(query_text)
        
        # Query for top similar embeddings
        stmt = (
            select(FileEmbedding.chunk_text)
            .where(FileEmbedding.session_id == session_id)
            .order_by(FileEmbedding.embedding.cosine_distance(Vector(query_embedding)))
            .limit(top_k)
        )
        
        results = db.execute(stmt).scalars().all()
        return results

    @staticmethod
    async def generate_response_with_history(
        repo_context: str,
        conversation_history: List[Tuple[str, str]],
        github_data: tuple = None,
        file_contexts: List[str] = None,
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
            github_data: Tuple of (repo_details, commits, issues, pulls)
            file_contexts: List of relevant file context strings
            model: Model to use
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            timeout: Request timeout in seconds

        Returns:
            Generated response text
        """
        prompt = LLMService.build_prompt_from_history(repo_context, conversation_history, github_data, file_contexts)
        return await LLMService.generate_response(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout
        ) 
    
    @staticmethod
    def embed_text(text: str) -> List[float]:
        """
        Generate embedding for text using local sentence-transformers model.

        This is a minimal, synchronous implementation optimized for local inference.

        Args:
            text: Text to embed

        Returns:
            Embedding vector as list of floats (384 dimensions for all-MiniLM-L6-v2)

        Raises:
            HTTPException: For model loading or inference errors
        """
        try:
            model_instance = LLMService.get_embedding_model()
            embedding = model_instance.encode(text, convert_to_numpy=False)
            return embedding.tolist()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Embedding generation failed: {str(e)}",
            )