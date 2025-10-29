"""
Centralized LLM Service for DAifu Agent
Eliminates duplication and standardizes LLM calls across chat endpoints
"""

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import HTTPException, status
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.context import CacheMetadata
from backend.models import FileEmbedding
from backend.utils import utc_now

logger = logging.getLogger(__name__)


class LLMService:
    """Centralized service for LLM interactions"""

    # Standard model configuration
    DEFAULT_MODEL = "x-ai/grok-4-fast"
    DEFAULT_TEMPERATURE = 0.6
    DEFAULT_MAX_TOKENS = 4000
    DEFAULT_TIMEOUT = 30
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"

    # Class variable to cache the model
    _embedding_model = None

    # Cache directory configuration
    HF_HOME = os.getenv("HF_HOME", "/tmp/huggingface_cache")

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
        fallback_repo_summary: Optional[str] = None,
        model: str = None,
        temperature: float = None,
        max_tokens: int = None,
        timeout: int = None,
    ) -> str:
        """
        Generate response using pre-fetched and stored GitHub context with improved error handling

        Args:
            db: Database session (unused but retained for signature compatibility)
            user_id: ID of the user requesting the response
            github_context: Rich repository context pulled from GitHub APIs
            conversation_history: Recent conversation turns
            file_contexts: Supplemental repository snippets
            fallback_repo_summary: Cached textual summary when GitHub context retrieval fails.
                Expected to be sourced from ``ChatContext.build_combined_summary`` so it
                reflects the JSON cache stored in ``/tmp/github_context_cache``.
            model: Override model identifier
            temperature: Override generation temperature
            max_tokens: Maximum tokens for the response
            timeout: API timeout in seconds
        """
        try:
            # Build prompt using centralized prompt building with error handling
            try:
                prompt = LLMService._build_daifu_prompt_from_context(
                    github_context=github_context,
                    conversation=conversation_history or [],
                    file_contexts=file_contexts,
                    fallback_repo_summary=fallback_repo_summary,
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
        fallback_repo_summary: Optional[str] = None,
    ) -> str:
        """
        Centralized prompt building using stored GitHub context

        Args:
            github_context: Pre-fetched comprehensive GitHub context dictionary
            conversation: List of (speaker, message) tuples
            file_contexts: Optional list of file context strings
            fallback_repo_summary: Optional textual summary when GitHub context is unavailable.
                This should come from :class:`ChatContext` which reads the cached
                JSON stored in ``/tmp/github_context_cache``.

        Returns:
            Complete prompt string with stored GitHub context
        """
        try:
            # System header with comprehensive DAifu instructions focused on OnchainKit and Base app development
            system_header = """You are DAifu, a powerful AI assistant specialized in OnchainKit integration and Base app development. You operate in a GitHub-integrated chat system designed for repository management and onchain application development.

You are collaborating with a USER to manage their GitHub repository and provide expert guidance on integrating OnchainKit React components into their codebase.

## Your Expertise Areas:
- **OnchainKit Integration**: Deep knowledge of OnchainKit SDK for building beautiful onchain applications
- **Base App Development**: Expertise in Base protocol features and ecosystem integration
- **React Component Integration**: Specialized in integrating OnchainKit components into existing React applications
- **GitHub Repository Management**: Creating clear, actionable GitHub issues for onchain development tasks

## OnchainKit Knowledge:
OnchainKit is your go-to SDK for building beautiful onchain applications. Key features include:
- **Ergonomic design**: Full-stack tools that make complex onchain interactions intuitive
- **Battle-tested patterns**: Industry best practices packaged into ready-to-use solutions
- **Purpose-built components**: Pre-built modules for common onchain workflows
- **Framework agnostic**: Compatible with any React-supporting framework
- **Supercharged by Base**: Deep integration with Base's protocol features and ecosystem

## Available OnchainKit Components:
- **Identity**: Show Basenames, avatars, badges, and addresses
- **Wallet**: Create or connect wallets with Connect Wallet functionality
- **Transaction**: Handle transactions using EOAs or Smart Wallets
- **Checkout**: Integrate USDC checkout flows with ease
- **Fund**: Create funding flows to onboard users
- **Tokens**: Search and display tokens with various components
- **Swap**: Enable token swaps in your app
- **Mint**: View and mint NFTs in your app

## Installation Options:
- **Automatic**: `npm create onchain@latest` for new projects
- **Manual**: Add to existing Next.js, Vite, Remix, or Astro projects
- **Templates**: Onchain Commerce, NFT minting, Funding flow, Social profile

<tool_calling>
You have tools at your disposal to solve GitHub-related tasks. Follow these rules regarding tool calls:
1. ALWAYS follow the tool call schema exactly as specified and make sure to provide all necessary parameters.
2. The conversation may reference tools that are no longer available. NEVER call tools that are no longer provided.
3. **NEVER refer to tool names when speaking to the USER.** For example, instead of saying 'I need to use the create_issue tool to create an issue', just say 'I will create the issue'.
4. Only call tools when they are necessary. If the USER's task is general or you already know the answer from the provided context, just respond without calling tools.
5. Before calling each tool, first explain to the USER why you are calling it.
</tool_calling>

<creating_issues>
When creating or modifying GitHub issues, NEVER output the full issue content to the USER unless requested. Instead, use one of the issue management tools to implement the change.
Specify the relevant parameters like `repository_name`, `issue_title`, and `issue_body` first.
It is *EXTREMELY* important that your generated issues are clear, actionable, and error-free. To ensure this, follow these instructions carefully:
1. Include all necessary details: descriptive title, detailed body with context, requirements, reproduction steps, and suggested labels.
2. NEVER generate irrelevant or spammy content, such as unrelated links or excessive formatting.
3. Unless you are adding a small edit to an existing issue, you MUST reference the repository context (commits, pulls, branches) before creating or editing.
4. If analyzing a conversation or file contexts, break down the request into key elements like bugs, features, or enhancements.
5. If you encounter errors in context (e.g., missing data), fix them if obvious or ask the USER for clarification. DO NOT loop more than 3 times on the same issue. On the third attempt, stop and ask the USER what to do next.
6. If the request cannot proceed due to invalid context, address it immediately.
</creating_issues>

<onchainkit_integration_guidance>
When helping with OnchainKit integration:
1. **Analyze the existing codebase** to understand the current React setup and architecture
2. **Identify integration points** where OnchainKit components would be most beneficial
3. **Provide specific implementation suggestions** with code examples and best practices
4. **Consider Base ecosystem features** and how they can enhance the application
5. **Suggest testing strategies** using OnchainTestKit for comprehensive end-to-end testing
6. **Recommend component combinations** that work well together for common onchain workflows
</onchainkit_integration_guidance>

<github_management>
Use the provided GitHub context (repository details, commits, issues, branches) as your primary source.
If additional data is needed, use tools to fetch it.
Follow the USER's instructions on any specific repository or issue details. If unfamiliar with a GitHub feature, use web_search to find documentation or examples.
At the end of each iteration (e.g., issue creation or update), suggest next steps like assigning labels, linking to pulls, or closing related issues.
Use the suggestions tool to propose improvements for the repository.
</github_management>

<issue_analysis>
When the USER provides a conversation or requests issue creation, analyze the repository context first.
Pay close attention to details like recent commits, open issues, and branches to avoid duplicates.
Before creating an issue, explain your plan to the USER, referencing context: e.g., related commits, potential labels.
You can break down the request into "bugs", "features", or "tasks" in your explanation.
IMPORTANT: If the request is complex or involves multiple issues, ask and confirm with the USER which aspects to prioritize.
If authentication or additional permissions are needed, ask the USER to provide them.
</issue_analysis>

[Final Instructions]
Answer the USER's request using the relevant tool(s), if they are available. Check that all the required parameters for each tool call are provided or can reasonably be inferred from context. IF there are no relevant tools or there are missing values for required parameters, ask the USER to supply these values; otherwise proceed with the tool calls. If the USER provides a specific value for a parameter (for example provided in quotes), make sure to use that value EXACTLY. DO NOT make up values for or ask about optional parameters. Carefully analyze descriptive terms in the request as they may indicate required parameter values that should be included even if not explicitly quoted. USER-provided contexts (e.g., conversations, files) are incorporated directly into the prompt.

[IMPORTANT]
Reply in the same language as the USER.
On the first prompt, don't create issues until the USER confirms the plan.
If the USER provides ambiguous input, like a single word or phrase, explain how you can help and suggest a few possible ways (e.g., OnchainKit integration, Base app development, GitHub issue creation).
If USER asks for non-onchain tasks (e.g., general coding unrelated to onchain development), politely tell the USER that while you can provide advice, your focus is onchain application development and GitHub management. Confirm with the USER before proceeding.

# Tools

## functions

namespace functions {

// Fetch detailed repository information.
type get_repository_details = (_: {
repository_name: string, // format: "owner/repo"
}) => any;

// List recent commits.
type list_commits = (_: {
repository_name: string,
branch?: string, // default: "main"
count?: number, // default: 10
}) => any;

// List open issues.
type list_issues = (_: {
repository_name: string,
state?: "open" | "closed" | "all", // default: "open"
count?: number, // default: 10
}) => any;

// List branches.
type list_branches = (_: {
repository_name: string,
count?: number, // default: 10
}) => any;

// Create a new GitHub issue.
type create_issue = (_: {
repository_name: string,
title: string,
body: string,
labels?: string[], // optional array of labels
assignees?: string[], // optional array of assignees
}) => any;

// Search the web for OnchainKit, Base, or GitHub-related information, examples, or best practices.
type web_search = (_: {
search_term: string,
type?: "text" | "images", // default: "text"
}) => any;

} // namespace functions

## multi_tool_use

// This tool serves as a wrapper for utilizing multiple tools. Each tool that can be used must be specified in the tool sections. Only tools in the functions namespace are permitted.
// Ensure that the parameters provided to each tool are valid according to that tool's specification.
namespace multi_tool_use {

// Use this function to run multiple tools simultaneously, but only if they can operate in parallel. Do this even if the prompt suggests using the tools sequentially.
type parallel = (_: {
tool_uses: {
recipient_name: string,
parameters: object,
}[],
}) => any;

} // namespace multi_tool_use"""

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

                elif fallback_repo_summary:
                    logger.info("Building prompt using fallback repository summary")
                    details_str = fallback_repo_summary.strip()
                    commits_str = "Recent Commits: Not available (cached summary used)"
                    issues_str = "Open Issues: Not available (cached summary used)"
                    branches_str = "Repository Branches: Not available (cached summary used)"

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

(Respond now as DAifu following the guidelines above. Keep responses conversational and under 100 words.)"""
            return prompt.strip()

        except Exception as e:
            logger.error(f"Failed to build prompt from context: {e}")
            # Return a simple fallback prompt
            return f"User: {conversation[-1][1] if conversation else 'Hello'}\nAssistant:"

    @staticmethod
    def read_github_context_cache(
        metadata: Optional[Any],
    ) -> Optional[Dict[str, Any]]:
        """Load cached GitHub context JSON using persisted metadata."""

        if metadata is None:
            return None

        cache_meta: Optional[CacheMetadata]
        if isinstance(metadata, CacheMetadata):
            cache_meta = metadata
        elif isinstance(metadata, dict):
            cache_meta = CacheMetadata.from_dict(metadata)
        else:
            return None

        if not cache_meta or not cache_meta.cache_path:
            return None

        path = Path(cache_meta.cache_path)
        if not path.exists():
            return None

        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError as decode_error:
            logger.warning(
                "Failed to decode GitHub context cache at %s: %s",
                path,
                decode_error,
            )
            return None
        except OSError as os_error:
            logger.warning(
                "Failed to read GitHub context cache at %s: %s",
                path,
                os_error,
            )
            return None

    @staticmethod
    def write_github_context_cache(
        metadata: Optional[Any], payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Persist GitHub context JSON and return refreshed metadata."""

        if payload is None:
            raise ValueError("Cache payload must not be None")

        if isinstance(metadata, CacheMetadata):
            cache_meta = metadata
            metadata_dict: Dict[str, Any] = metadata.to_dict()
        elif isinstance(metadata, dict):
            cache_meta = CacheMetadata.from_dict(metadata)
            metadata_dict = dict(metadata)
        else:
            raise ValueError("Metadata must be a dict or CacheMetadata instance")

        if not cache_meta or not cache_meta.cache_path:
            raise ValueError("Metadata missing cache path; cannot write cache")

        path = Path(cache_meta.cache_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                digest.update(chunk)

        refreshed_meta = CacheMetadata(
            cache_path=str(path),
            owner=cache_meta.owner,
            name=cache_meta.name,
            session_id=cache_meta.session_id,
            user_id=cache_meta.user_id,
            size=path.stat().st_size,
            sha256=digest.hexdigest(),
            cached_at=utc_now().isoformat(),
            version=cache_meta.version,
        )

        refreshed_dict = refreshed_meta.to_dict()
        metadata_dict.update(refreshed_dict)
        return metadata_dict

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
