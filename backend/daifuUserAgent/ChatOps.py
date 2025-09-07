#!/usr/bin/env python3
"""
ChatOps Module - Consolidated Chat and Repository Operations

This module provides all chat-related operations including GitHub API integration,
repository context fetching, and conversation management. It consolidates functionality
previously scattered across multiple files and provides unified chat operations.

TODO: Complete Implementation Tasks
========================================

CRITICAL ISSUES:
1. LLM Integration - The _generate_ai_response() method is a placeholder
   - Replace with actual OpenRouter/OpenAI API integration
   - Implement proper conversation history formatting
   - Add token counting and cost tracking
   - Handle rate limiting and retries

2. GitHub API Error Handling
   - Implement exponential backoff for rate limits
   - Add proper error recovery for network failures
   - Handle GitHub API token refresh scenarios

3. Session Management Integration
   - Implement proper message deduplication
   - Add conversation context window management
   - Handle session cleanup and archiving

4. Frontend Integration (@Chat.tsx compatibility)
   - Ensure response format matches ChatResponse model
   - Implement real-time streaming responses
   - Add proper error message formatting for UI display
   - Support context card integration in responses

6. Security Enhancements
   - Add input sanitization for user messages
   - Implement content filtering for sensitive data
   - Add audit logging for all GitHub API calls
   - Validate repository access permissions

8. Database Optimization
   - Add proper indexing for message queries



"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from models import ChatMessage, ChatSession, User
from sqlalchemy.orm import Session

from utils import utc_now

# Configure logging
logger = logging.getLogger(__name__)


class ChatOpsError(Exception):
    """Custom exception for ChatOps operations"""

    pass


class ChatOps:
    """
    Consolidated Chat Operations Class

    Provides all chat-related functionality including:
    - GitHub repository context fetching
    - Repository data extraction
    - Chat message processing
    - Session management
    """

    def __init__(self, db: Session):
        self.db = db
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def get_user_from_session_token(session_token: str, db: Session) -> Optional[User]:
        """Get user from session token"""
        try:
            from auth.github_oauth import validate_session_token

            return validate_session_token(db, session_token)
        except Exception as e:
            logger.error(f"Failed to validate session token: {e}")
            return None

    @staticmethod
    def get_user_github_token(user_id: int, db: Session) -> Optional[str]:
        """Get user's active GitHub access token"""
        from .githubOps import GitHubOps

        return GitHubOps.get_user_github_token(user_id, db)

    async def get_github_context(
        self, repo_owner: str, repo_name: str, user: User, db: Session
    ) -> str:
        """
        Fetch GitHub repository context for chat conversations

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            user: User object
            db: Database session

        Returns:
            Repository context string for AI processing
        """
        try:
            logger.info(
                f"Fetching GitHub context for {repo_owner}/{repo_name} by user {user.id}"
            )

            from .githubOps import GitHubOps

            github_ops = GitHubOps(db)

            # Fetch repository information
            repo_data = await github_ops.fetch_repository_info(
                repo_owner, repo_name, user.id
            )

            # Fetch recent issues
            issues_data = await github_ops.fetch_repository_issues(
                repo_owner, repo_name, user.id, limit=5
            )

            # Fetch recent commits
            commits_data = await github_ops.fetch_repository_commits(
                repo_owner, repo_name, user.id, limit=5
            )

            # Combine all context
            full_context = self._build_context_string(
                repo_data, issues_data, commits_data
            )

            logger.info(
                f"Successfully fetched GitHub context for {repo_owner}/{repo_name}"
            )
            return full_context

        except Exception as e:
            logger.error(
                f"Failed to fetch GitHub context for {repo_owner}/{repo_name}: {e}"
            )
            # Return basic context as fallback
            return f"Repository: {repo_owner}/{repo_name}. Limited context available due to API error."

    async def get_github_context_data(
        self, repo_owner: str, repo_name: str, user: User, db: Session
    ) -> Dict[str, Any]:
        """
        Fetch structured GitHub repository data

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            user: User object
            db: Database session

        Returns:
            Structured repository data dictionary
        """
        try:
            logger.info(
                f"Fetching structured GitHub data for {repo_owner}/{repo_name} by user {user.id}"
            )

            from .githubOps import GitHubOps

            github_ops = GitHubOps(db)

            # Fetch repository information
            repo_data = await github_ops.fetch_repository_info_detailed(
                repo_owner, repo_name, user.id
            )

            # Fetch branches
            branches = await github_ops.fetch_repository_branches(
                repo_owner, repo_name, user.id
            )

            # Fetch contributors
            contributors = await github_ops.fetch_repository_contributors(
                repo_owner, repo_name, user.id, limit=10
            )

            # Structure the response
            structured_data = {
                "repository": repo_data,
                "branches": branches,
                "contributors": contributors,
                "fetched_at": utc_now().isoformat(),
                "owner": repo_owner,
                "name": repo_name,
            }

            logger.info(
                f"Successfully fetched structured data for {repo_owner}/{repo_name}"
            )
            return structured_data

        except Exception as e:
            logger.error(
                f"Failed to fetch structured GitHub data for {repo_owner}/{repo_name}: {e}"
            )
            return {
                "error": str(e),
                "repository": {"name": repo_name, "owner": repo_owner},
                "branches": [],
                "contributors": [],
                "fetched_at": utc_now().isoformat(),
            }

    def _build_context_string(
        self,
        repo_info: Dict[str, Any],
        issues: List[Dict[str, Any]],
        commits: List[Dict[str, Any]],
    ) -> str:
        """Build context string from repository data"""
        context_parts = []

        # Repository info
        if repo_info.get("name"):
            context_parts.append(f"Repository: {repo_info['name']}")
            if repo_info.get("description"):
                context_parts.append(f"Description: {repo_info['description']}")
            if repo_info.get("language"):
                context_parts.append(f"Primary Language: {repo_info['language']}")
            if repo_info.get("topics"):
                context_parts.append(f"Topics: {', '.join(repo_info['topics'][:5])}")

        # Recent issues
        if issues:
            context_parts.append(f"\nRecent Issues ({len(issues)}):")
            for issue in issues[:3]:
                context_parts.append(f"- #{issue['number']}: {issue['title']}")

        # Recent commits
        if commits:
            context_parts.append(f"\nRecent Commits ({len(commits)}):")
            for commit in commits[:3]:
                context_parts.append(f"- {commit['sha']}: {commit['message']}")

        return (
            "\n".join(context_parts)
            if context_parts
            else "Repository context not available"
        )

    async def process_chat_message(
        self,
        session_id: str,
        user_id: int,
        message_text: str,
        context_cards: Optional[List[str]] = None,
        repository: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a chat message and return AI response

        Args:
            session_id: Chat session ID
            user_id: User ID
            message_text: User's message
            context_cards: Optional context card IDs
            repository: Optional repository info

        Returns:
            AI response data
        """
        try:
            logger.info(
                f"Processing chat message for session {session_id}, user {user_id}"
            )

            # Get session and validate access
            session = (
                self.db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id, ChatSession.user_id == user_id
                )
                .first()
            )

            if not session:
                raise ChatOpsError(f"Session {session_id} not found or access denied")

            # Get conversation history
            history = self._get_conversation_history(session.id)

            # Get repository context if available
            repo_context = ""
            if repository and repository.get("owner") and repository.get("name"):
                # Get user for GitHub API access
                user = self.db.query(User).filter(User.id == user_id).first()
                if user:
                    repo_context = await self.get_github_context(
                        repository["owner"], repository["name"], user, self.db
                    )

            # Get context cards content
            context_content = ""
            if context_cards:
                context_content = self._get_context_cards_content(
                    context_cards, user_id
                )

            # Generate AI response using LLM service
            ai_response = await self._generate_ai_response(
                message_text, history, repo_context, context_content, None
            )

            # Save user message to database
            user_msg = ChatMessage(
                session_id=session.id,
                message_id=f"msg_{utc_now().timestamp()}_{user_id}",
                message_text=message_text,
                sender_type="user",
                role="user",
                tokens=len(message_text.split()),  # Rough estimate
            )
            self.db.add(user_msg)

            # Save AI response to database
            ai_msg = ChatMessage(
                session_id=session.id,
                message_id=f"msg_{utc_now().timestamp()}_ai",
                message_text=ai_response,
                sender_type="assistant",
                role="assistant",
                tokens=len(ai_response.split()),  # Rough estimate
            )
            self.db.add(ai_msg)

            # Update session statistics
            session.total_messages += 2
            session.total_tokens += user_msg.tokens + ai_msg.tokens
            session.last_activity = utc_now()

            self.db.commit()

            logger.info(f"Successfully processed chat message for session {session_id}")
            return {
                "reply": ai_response,
                "message_id": ai_msg.message_id,
                "processing_time": 0.5,  # Placeholder
                "session_id": session_id,
            }

        except Exception as e:
            logger.error(f"Failed to process chat message: {e}")
            self.db.rollback()
            raise ChatOpsError(f"Chat processing failed: {str(e)}")

    def _get_conversation_history(
        self, session_id: int, limit: int = 10
    ) -> List[Tuple[str, str]]:
        """Get recent conversation history for a session"""
        try:
            messages = (
                self.db.query(ChatMessage)
                .filter(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc())
                .limit(limit)
                .all()
            )

            # Reverse to get chronological order
            messages.reverse()

            return [(msg.sender_type, msg.message_text) for msg in messages]

        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []

    def _get_context_cards_content(self, card_ids: List[str], user_id: int) -> str:
        """Get content from context cards"""
        try:
            from models import ContextCard

            cards = (
                self.db.query(ContextCard)
                .filter(
                    ContextCard.id.in_(card_ids),
                    ContextCard.user_id == user_id,
                    ContextCard.is_active,
                )
                .all()
            )

            return "\n\n".join(
                [f"Context: {card.title}\n{card.content}" for card in cards]
            )

        except Exception as e:
            logger.error(f"Failed to get context cards content: {e}")
            return ""

    def _generate_ai_response(
        self,
        message: str,
        history: List[Tuple[str, str]],
        repo_context: str,
        context_content: str,
        github_data: tuple = None,
    ) -> str:
        """
        Generate AI response using LLM service with proper context

        Args:
            message: User's current message
            history: Conversation history as (sender, message) tuples
            repo_context: GitHub repository context
            context_content: Additional context from context cards
            github_data: Tuple of (repo_details, commits, issues, pulls)

        Returns:
            AI response string
        """
        try:
            from .llm_service import LLMService
            from .prompt import build_daifu_prompt

            # Build the conversation history including the current message
            full_history = history + [("User", message)]

            # Build the prompt using the same template as prompt.py
            if github_data and len(github_data) >= 4:
                repo_details, commits, issues, pulls = github_data
                prompt = build_daifu_prompt(
                    repo_details, commits, issues, pulls, full_history
                )
            else:
                # Fallback with minimal data structure
                repo_details = {
                    "full_name": repo_context.split("\n")[0].replace("Repository: ", "")
                    if repo_context
                    else "Unknown Repository",
                    "description": "",
                    "default_branch": "main",
                    "languages": {},
                    "topics": [],
                    "license": None,
                    "stargazers_count": 0,
                    "forks_count": 0,
                    "open_issues_count": 0,
                    "html_url": "",
                }
                commits = []
                issues = []
                pulls = []

                # Add context content to the prompt if available
                if context_content:
                    # Insert context content into the prompt
                    context_str = f"\nAdditional Context:\n{context_content}\n"
                    prompt = build_daifu_prompt(
                        repo_details, commits, issues, pulls, full_history
                    )
                    prompt = prompt.replace(
                        "<FILE_CONTEXTS_BEGIN>\n</FILE_CONTEXTS_END>",
                        f"<FILE_CONTEXTS_BEGIN>\n{context_str}</FILE_CONTEXTS_END>",
                    )
                else:
                    prompt = build_daifu_prompt(
                        repo_details, commits, issues, pulls, full_history
                    )

            # Generate response using LLM service (already in async context)
            ai_response = await LLMService.generate_response(
                prompt=prompt,
                model="deepseek/deepseek-r1-0528",
                temperature=0.4,
                max_tokens=1500,
                timeout=45,
            )

            return ai_response

        except Exception as e:
            logger.error(f"Failed to generate AI response: {e}")
            # Fallback response
            return f"I understand you said: '{message}'. I'm currently having trouble processing your request. Could you please try again?"
