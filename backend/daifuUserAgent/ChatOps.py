#!/usr/bin/env python3
"""
ChatOps Module - Consolidated Chat and Repository Operations

This module provides all chat-related operations including GitHub API integration,
repository context fetching, and conversation management. It consolidates functionality
previously scattered across multiple files and provides unified chat operations.

TODO: Complete Implementation Tasks
========================================

LLM INTEGRATION: Implemented
- Uses centralized LLMService with OpenRouter for responses
- Conversation history and stored GitHub context are incorporated
- Add token counting/cost tracking (future)
- Add rate limiting/retries (future)




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
    ) -> Dict[str, Any]:
        """
        Fetch comprehensive GitHub repository context for downstream AI tasks

        This function combines both context string generation and structured data fetching
        to provide complete repository context for AI processing and programmatic access.

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            user: User object
            db: Database session

        Returns:
            Dictionary containing both structured data and formatted context string
        """
        try:
            logger.info(
                f"Fetching comprehensive GitHub context for {repo_owner}/{repo_name} by user {user.id}"
            )

            from .githubOps import GitHubOps

            github_ops = GitHubOps(db)

            # Fetch detailed repository information
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

            # Fetch recent issues
            issues_data = await github_ops.fetch_repository_issues(
                repo_owner, repo_name, user.id, limit=5
            )

            # Fetch recent commits
            commits_data = await github_ops.fetch_repository_commits(
                repo_owner, repo_name, user.id, limit=5
            )

            # Build context string from basic repo info (for backward compatibility)
            basic_repo_info = await github_ops.fetch_repository_info(
                repo_owner, repo_name, user.id
            )
            context_string = self._build_context_string(
                basic_repo_info, issues_data, commits_data
            )

            # Structure the comprehensive response
            comprehensive_data = {
                "repository": repo_data,
                "branches": branches,
                "contributors": contributors,
                "recent_issues": issues_data,
                "recent_commits": commits_data,
                "context_string": context_string,
                "fetched_at": utc_now().isoformat(),
                "owner": repo_owner,
                "name": repo_name,
            }

            logger.info(
                f"Successfully fetched comprehensive GitHub context for {repo_owner}/{repo_name}"
            )
            return comprehensive_data

        except Exception as e:
            logger.error(
                f"Failed to fetch comprehensive GitHub context for {repo_owner}/{repo_name}: {e}"
            )
            # Return fallback data
            fallback_context = f"Repository: {repo_owner}/{repo_name}. Limited context available due to API error."
            return {
                "error": str(e),
                "repository": {"name": repo_name, "owner": repo_owner},
                "branches": [],
                "contributors": [],
                "recent_issues": [],
                "recent_commits": [],
                "context_string": fallback_context,
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
        Process a chat message and generate AI response with comprehensive error handling
        """
        try:
            logger.info(f"Processing chat message for session {session_id}")

            # Get session from database
            session = (
                self.db.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_id,
                    ChatSession.user_id == user_id,
                )
                .first()
            )

            if not session:
                raise ChatOpsError(f"Session {session_id} not found")

            # Extract repository info
            repo_owner = None
            repo_name = None
            if repository:
                repo_owner = repository.get("owner")
                repo_name = repository.get("name")
            elif session.repo_owner and session.repo_name:
                repo_owner = session.repo_owner
                repo_name = session.repo_name

            # Get conversation history
            history = self._get_conversation_history(session.id, 10)

            # Get file contexts (with error handling)
            file_contexts = []
            try:
                from .llm_service import LLMService
                file_contexts = await LLMService.get_relevant_file_contexts(
                    db=self.db, session_id=session.id, query_text=message_text, top_k=5
                )
            except Exception as e:
                logger.warning(f"Failed to get file contexts: {e}")
                # Continue without file contexts - non-fatal

            # Generate AI response with improved error handling
            try:
                from .llm_service import LLMService

                # Build the conversation history including the current message
                full_history = history + [("User", message_text)]

                # Get stored GitHub context using filesystem cache; store only metadata in DB
                github_context = None
                if repo_owner and repo_name:
                    try:
                        from models import Repository, User

                        from utils import utc_now

                        repository = (
                            self.db.query(Repository)
                            .filter(
                                Repository.owner == repo_owner,
                                Repository.name == repo_name,
                                Repository.user_id == user_id,
                            )
                            .first()
                        )

                        # Try reading from cache if we have recent metadata
                        if (
                            repository
                            and hasattr(repository, "github_context")
                            and repository.github_context
                            and hasattr(repository, "github_context_updated_at")
                            and repository.github_context_updated_at
                        ):
                            # Check if context is less than 24 hours old
                            if (
                                (utc_now() - repository.github_context_updated_at).total_seconds()
                                < 86400
                            ):
                                github_context = LLMService.read_github_context_cache(
                                    repository.github_context
                                )
                            else:
                                logger.info(
                                    f"GitHub context for {repo_owner}/{repo_name} is stale, will refresh"
                                )

                        # If no cached data or cache missing/stale, fetch and write to cache
                        if not github_context:
                            try:
                                user = self.db.query(User).filter(User.id == user_id).first()
                                if user:
                                    logger.info(
                                        f"Fetching fresh GitHub context for {repo_owner}/{repo_name}"
                                    )
                                    fetched_context = await self.get_github_context(
                                        repo_owner, repo_name, user, self.db
                                    )

                                    if fetched_context:
                                        # Write to cache, get metadata
                                        cache_meta = LLMService.write_github_context_cache(
                                            data=fetched_context,
                                            user_id=user_id,
                                            session_id=session.session_id,
                                            owner=repo_owner,
                                            name=repo_name,
                                        )

                                        # Load what we just cached
                                        github_context = LLMService.read_github_context_cache(
                                            cache_meta
                                        )

                                        # Create or update repository metadata only
                                        if not repository:
                                            repository = Repository(
                                                user_id=user_id,
                                                name=repo_name,
                                                owner=repo_owner,
                                                full_name=f"{repo_owner}/{repo_name}",
                                                repo_url=f"https://github.com/{repo_owner}/{repo_name}",
                                                html_url=f"https://github.com/{repo_owner}/{repo_name}",
                                                clone_url=f"https://github.com/{repo_owner}/{repo_name}.git",
                                                github_context=cache_meta,
                                                github_context_updated_at=utc_now(),
                                            )
                                            self.db.add(repository)
                                        else:
                                            repository.github_context = cache_meta
                                            repository.github_context_updated_at = utc_now()

                                        self.db.commit()
                                        logger.info(
                                            f"Cached GitHub context metadata for {repo_owner}/{repo_name} at {cache_meta.get('cache_path')}"
                                        )
                                    else:
                                        logger.warning(
                                            f"Failed to fetch GitHub context for {repo_owner}/{repo_name}"
                                        )
                                else:
                                    logger.warning(
                                        f"User {user_id} not found for GitHub context fetch"
                                    )
                            except Exception as fetch_error:
                                logger.warning(
                                    f"Failed to fetch/cache GitHub context: {fetch_error}"
                                )
                                # Continue without GitHub context - non-fatal

                    except Exception as db_error:
                        logger.warning(
                            f"Database error while fetching GitHub context: {db_error}"
                        )
                        # Continue without GitHub context - non-fatal

                # Generate response using LLM service
                ai_response = await LLMService.generate_response_with_stored_context(
                    db=self.db,
                    user_id=user_id,
                    github_context=github_context,
                    conversation_history=full_history,
                    file_contexts=file_contexts,
                    model="x-ai/grok-4-fast:free",
                    temperature=0.4,
                    max_tokens=2500,
                    timeout=25,
                )

            except Exception as llm_error:
                logger.error(f"LLM service error: {llm_error}")
                # Fallback response
                ai_response = f"I understand you said: '{message_text}'. I'm currently having trouble processing your request. Could you please try again?"

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

    async def _generate_ai_response(
        self,
        message: str,
        history: List[Tuple[str, str]],
        repo_context: str,
        file_contexts: Optional[List[str]] = None,
        github_data: tuple = None,
        repo_owner: str = None,
        repo_name: str = None,
        repo_branch: str = None,
        user_id: int = None,
    ) -> str:
        """
        Generate AI response using stored GitHub context

        Args:
            message: User's current message
            history: Conversation history as (sender, message) tuples
            repo_context: GitHub repository context (deprecated)
            file_contexts: Additional file context strings
            github_data: Tuple of (repo_details, commits, issues, pulls) - legacy fallback
            repo_owner: Repository owner
            repo_name: Repository name
            repo_branch: Repository branch
            user_id: User ID for authentication

        Returns:
            AI response string
        """
        try:
            from .llm_service import LLMService

            # Build the conversation history including the current message
            full_history = history + [("User", message)]

            # Get stored GitHub context from filesystem cache (metadata in DB)
            github_context = None
            if repo_owner and repo_name:
                from models import Repository

                from utils import utc_now

                repository = (
                    self.db.query(Repository)
                    .filter(
                        Repository.owner == repo_owner,
                        Repository.name == repo_name,
                        Repository.user_id == user_id,
                    )
                    .first()
                )

                if (
                    repository
                    and repository.github_context
                    and repository.github_context_updated_at
                    and (utc_now() - repository.github_context_updated_at).total_seconds() < 86400
                ):
                    from .llm_service import LLMService as _LLM

                    github_context = _LLM.read_github_context_cache(
                        repository.github_context
                    )
                else:
                    logger.warning(
                        f"No recent cached GitHub context found for {repo_owner}/{repo_name}"
                    )

            # Generate response using LLM service with stored GitHub context
            ai_response = await LLMService.generate_response_with_stored_context(
                db=self.db,
                user_id=user_id,
                github_context=github_context,
                conversation_history=full_history,
                file_contexts=file_contexts,
                model="x-ai/grok-4-fast:free",
                temperature=0.4,
                max_tokens=2500,
                timeout=25,
            )

            return ai_response

        except Exception as e:
            logger.error(f"Failed to generate AI response: {e}")
            # Fallback response
            return f"I understand you said: '{message}'. I'm currently having trouble processing your request. Could you please try again?"
