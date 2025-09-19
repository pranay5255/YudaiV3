"""
Centralized LLM Service for DAifu Agent
Eliminates duplication and standardizes LLM calls across chat endpoints
"""

import logging
import os
import time
from typing import List, Tuple, Optional, Dict
from datetime import datetime, timezone
from pathlib import Path
import json
import hashlib

import httpx
from fastapi import HTTPException, status
from models import FileEmbedding
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class LLMService:
    """Centralized service for LLM interactions"""

    # Standard model configuration
    DEFAULT_MODEL = "openrouter/sonoma-sky-alpha"
    DEFAULT_TEMPERATURE = 0.6
    DEFAULT_MAX_TOKENS = 4000
    DEFAULT_TIMEOUT = 30
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"

    # Class variable to cache the model
    _embedding_model = None

    # Cache directory configuration
    HF_HOME = os.getenv("HF_HOME", "/tmp/huggingface_cache")
    # Cache for GitHub context (large JSON) – do not store in DB
    GITHUB_CONTEXT_CACHE_DIR = os.getenv(
        "GITHUB_CONTEXT_CACHE_DIR", "/home/yudai/YudaiV3/data/github_context_cache"
    )

    # ----------------------------------------------------------------------------------
    # GitHub Context Cache Helpers
    # ----------------------------------------------------------------------------------
    @staticmethod
    def _safe_component(text: str) -> str:
        """Sanitize path components for filenames."""
        if not text:
            return "unknown"
        # Replace problematic chars with underscores
        return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in str(text))

    @staticmethod
    def get_github_context_cache_dir() -> str:
        """Ensure and return the base cache directory for GitHub context JSON files."""
        base = LLMService.GITHUB_CONTEXT_CACHE_DIR
        Path(base).mkdir(parents=True, exist_ok=True)
        return base

    @staticmethod
    def cache_path_for_repo(user_id: int, session_id: str, owner: str, name: str) -> str:
        """Build a stable cache path for a user's session and repository."""
        base = LLMService.get_github_context_cache_dir()
        user_dir = Path(base) / LLMService._safe_component(user_id)  # cast to str in _safe_component
        session_dir = user_dir / LLMService._safe_component(session_id)
        session_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{LLMService._safe_component(owner)}__{LLMService._safe_component(name)}.json"
        return str(session_dir / filename)

    @staticmethod
    def write_github_context_cache(
        data: Dict,
        user_id: int,
        session_id: str,
        owner: str,
        name: str,
    ) -> Dict[str, object]:
        """
        Write GitHub context JSON to cache and return metadata for DB storage.

        Returns a small metadata dict containing cache path and integrity info.
        """
        path = LLMService.cache_path_for_repo(user_id, session_id, owner, name)
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed writing GitHub context cache to {path}: {e}")
            raise

        # Compute metadata
        try:
            size = os.path.getsize(path)
            h = hashlib.sha256()
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    h.update(chunk)
            sha256 = h.hexdigest()
        except Exception as e:
            logger.warning(f"Failed computing cache metadata for {path}: {e}")
            size = None
            sha256 = None

        meta = {
            "cache_path": path,
            "owner": owner,
            "name": name,
            "session_id": session_id,
            "user_id": user_id,
            "size": size,
            "sha256": sha256,
            "cached_at": datetime.now(tz=timezone.utc).isoformat(),
            "version": 1,
        }
        return meta

    @staticmethod
    def read_github_context_cache(meta: Dict[str, object]) -> Optional[Dict]:
        """
        Read GitHub context JSON from cache using provided metadata. Returns None on failure.
        """
        if not meta or not isinstance(meta, dict):
            return None
        path = meta.get("cache_path")
        if not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed reading GitHub context cache from {path}: {e}")
            return None

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
    def get_api_url() -> str:
        """Resolve the base URL for chat completions (configurable)."""
        return os.getenv(
            "OPENROUTER_API_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        )

    @staticmethod
    def get_embedding_model() -> SentenceTransformer:
        """Get or load the embedding model (cached for performance)"""
        if LLMService._embedding_model is None:
            try:
                # Ensure cache directory exists and has correct permissions
                os.makedirs(LLMService.HF_HOME, exist_ok=True)

                # Set environment variable for huggingface
                os.environ["HF_HOME"] = LLMService.HF_HOME

                logger.info(f"Loading embedding model: {LLMService.EMBEDDING_MODEL}")
                logger.info(f"Using HF cache directory: {LLMService.HF_HOME}")

                LLMService._embedding_model = SentenceTransformer(
                    LLMService.EMBEDDING_MODEL,
                    cache_folder=LLMService.HF_HOME,
                    local_files_only=False
                )
                logger.info("Embedding model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load embedding model: {e}")
                # Try with a fallback model if the primary model fails
                try:
                    logger.info("Attempting to load fallback model: all-MiniLM-L6-v2")
                    LLMService._embedding_model = SentenceTransformer(
                        "all-MiniLM-L6-v2",
                        cache_folder=LLMService.HF_HOME,
                        local_files_only=False
                    )
                    logger.info("Fallback embedding model loaded successfully")
                except Exception as fallback_error:
                    logger.error(f"Fallback model also failed: {fallback_error}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to load embedding model: {str(e)}, fallback also failed: {str(fallback_error)}"
                    )

        return LLMService._embedding_model

    @staticmethod
    async def generate_response(
        prompt: str,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
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
            url = LLMService.get_api_url()

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

            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()

                response_data = resp.json()
                reply = response_data["choices"][0]["message"]["content"].strip()

            processing_time = (time.time() - start_time) * 1000
            logger.info(f"LLM response generated in {processing_time:.2f}ms")
            return reply

        except httpx.TimeoutException as e:
            processing_time = (time.time() - start_time) * 1000
            logger.error(f"LLM request timeout after {processing_time:.2f}ms: {e}")
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="LLM request timed out",
            )
        except httpx.HTTPStatusError as e:
            processing_time = (time.time() - start_time) * 1000
            content = e.response.text if e.response is not None else str(e)
            logger.error(
                f"LLM HTTP error after {processing_time:.2f}ms: {e.response.status_code if e.response else 'unknown'} {content}"
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"LLM HTTP error: {content}",
            )
        except Exception as e:
            processing_time = (time.time() - start_time) * 1000
            logger.exception(
                f"LLM processing failed after {processing_time:.2f}ms: {str(e)}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"LLM call failed: {str(e)}",
            )

    @staticmethod
    async def get_relevant_file_contexts(
        db: Session, session_id: int, query_text: str, top_k: int = 5, model: str = None
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
            .order_by(FileEmbedding.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )

        results = db.execute(stmt).scalars().all()
        return results

    @staticmethod
    async def generate_response_with_stored_context(
        db: Session,
        user_id: int,
        github_context: dict = None,
        conversation_history: List[Tuple[str, str]] = None,
        file_contexts: List[str] = None,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
    ) -> str:
        """
        Generate response using pre-fetched and stored GitHub context with improved error handling
        """
        try:
            # Build prompt using centralized prompt building with error handling
            try:
                prompt = LLMService._build_daifu_prompt_from_context(
                    github_context=github_context,
                    conversation=conversation_history or [],
                    file_contexts=file_contexts,
                )
            except Exception as prompt_error:
                logger.warning(f"Failed to build prompt: {prompt_error}")
                # Fallback to simple prompt
                prompt = f"User: {conversation_history[-1][1] if conversation_history else 'Hello'}\nAssistant:"

            # Generate response with error handling
            try:
                return await LLMService.generate_response(
                    prompt=prompt,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
            except Exception as generation_error:
                logger.error(f"Failed to generate response: {generation_error}")
                # Return fallback response
                return "I'm having trouble processing your request right now. Please try again in a moment."

        except Exception as e:
            logger.error(f"Failed to generate response with stored context: {e}")
            # Return a helpful fallback response instead of raising an exception
            return "I understand you're asking about something, but I'm currently experiencing technical difficulties. Please try again in a moment."

    @staticmethod
    def _build_daifu_prompt_from_context(
        github_context: dict = None,
        conversation: List[Tuple[str, str]] = None,
        file_contexts: List[str] = None,
    ) -> str:
        """
        Centralized prompt building using stored GitHub context

        Args:
            github_context: Pre-fetched comprehensive GitHub context dictionary
            conversation: List of (speaker, message) tuples
            file_contexts: Optional list of file context strings

        Returns:
            Complete prompt string with stored GitHub context
        """
        try:
            # System header
            system_header = """You are **DAifu**, an AI assistant specialized in GitHub repository management and issue creation.
Your primary role is to help users create clear, actionable GitHub issues from their conversations
and repository context.

**Core Responsibilities:**
1. Analyze user requests and repository context to create well-structured GitHub issues
2. Provide direct, professional responses based on available context
3. Suggest next steps and improvements when appropriate
4. Maintain focus on actionable outcomes

**Response Guidelines:**
- Be direct and professional in all communications
- Use repository context to provide informed responses
- Focus on creating clear, actionable GitHub issues when requested
- Ask for clarification only when essential information is missing
- Provide specific recommendations based on repository data

**Output Format:**
When creating issues, structure them with:
- Clear, descriptive titles
- Detailed descriptions including context and requirements
- Appropriate labels and metadata"""

            # Format repository details from stored context with error handling
            details_str = "Repository information not available"
            commits_str = "Recent Commits: None available"
            issues_str = "Open Issues: None available"
            branches_str = "Repository Branches: None available"

            try:
                if github_context and isinstance(github_context, dict) and "repository" in github_context:
                    repo = github_context["repository"]

                    # Repository info with safe access
                    details_str = (
                        f"Repository: {repo.get('full_name', 'Unknown')}\n"
                        f"Description: {repo.get('description', '')}\n"
                        f"Default branch: {repo.get('default_branch', 'main')}\n"
                        f"Language: {repo.get('language', '')}\n"
                        f"Stars: {repo.get('stargazers_count', 0)}, Forks: {repo.get('forks_count', 0)}\n"
                        f"Open issues: {repo.get('open_issues_count', 0)}\n"
                        f"URL: {repo.get('html_url', '')}\n"
                    )

                    # Recent commits with error handling
                    try:
                        if (
                            "recent_commits" in github_context
                            and github_context["recent_commits"]
                            and isinstance(github_context["recent_commits"], list)
                        ):
                            commits = github_context["recent_commits"][:3]  # Limit to 3
                            commits_str = "Recent Commits:\n"
                            for commit in commits:
                                if isinstance(commit, dict):
                                    commits_str += f"- {commit.get('sha', '')[:7]}: {commit.get('message', '')[:50]}\n"
                    except Exception as commits_error:
                        logger.warning(f"Error processing commits: {commits_error}")
                        commits_str = "Recent Commits: Error loading\n"

                    # Open issues with error handling
                    try:
                        if (
                            "recent_issues" in github_context
                            and github_context["recent_issues"]
                            and isinstance(github_context["recent_issues"], list)
                        ):
                            issues = github_context["recent_issues"][:3]  # Limit to 3
                            issues_str = "Open Issues:\n"
                            for issue in issues:
                                if isinstance(issue, dict):
                                    issues_str += f"- #{issue.get('number', '?')}: {issue.get('title', '')[:50]}\n"
                    except Exception as issues_error:
                        logger.warning(f"Error processing issues: {issues_error}")
                        issues_str = "Open Issues: Error loading\n"

                    # Branches with error handling
                    try:
                        if "branches" in github_context and github_context["branches"] and isinstance(github_context["branches"], list):
                            branches = github_context["branches"][:3]  # Limit to 3
                            branches_str = "Repository Branches:\n"
                            for branch in branches:
                                if isinstance(branch, dict):
                                    branches_str += f"- {branch.get('name', 'Unknown')}\n"
                    except Exception as branches_error:
                        logger.warning(f"Error processing branches: {branches_error}")
                        branches_str = "Repository Branches: Error loading\n"

            except Exception as context_error:
                logger.warning(f"Error processing GitHub context: {context_error}")
                # Continue with default values

            # Format file contexts if provided
            file_contexts_str = ""
            if file_contexts:
                file_contexts_str = "Relevant File Contexts:\n" + "\n".join(
                    file_contexts
                )

            # Format conversation
            convo_formatted = ""
            if conversation:
                convo_formatted = "\n".join(
                    f"{speaker}: {utterance}" for speaker, utterance in conversation
                )

            # Combine all into final prompt
            prompt = f"""{system_header}

<GITHUB_CONTEXT_BEGIN>
{details_str}
{commits_str}
{issues_str}
{branches_str}
</GITHUB_CONTEXT_END>

<FILE_CONTEXTS_BEGIN>
{file_contexts_str}
</FILE_CONTEXTS_END>

<CONVERSATION_BEGIN>
{convo_formatted}
</CONVERSATION_END>

(Respond now as **DAifu** following the guidelines above. Focus on providing direct, actionable responses based on the available context.)"""
            return prompt.strip()

        except Exception as e:
            logger.error(f"Failed to build prompt from context: {e}")
            # Return a simple fallback prompt
            return f"User: {conversation[-1][1] if conversation else 'Hello'}\nAssistant:"

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
