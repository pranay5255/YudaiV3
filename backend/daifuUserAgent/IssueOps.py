#!/usr/bin/env python3
"""
IssueOps Module - Consolidated Issue Management Operations

This module provides all issue-related operations including GitHub issue creation,
management, and integration with the chat system. It consolidates functionality
previously scattered across multiple files and provides unified issue operations.

TODO: Complete Implementation Tasks
========================================

CRITICAL ISSUES:
1. LLM Integration for Issue Processing
   - Implement IssueService.update_issue_status() with actual LLM calls
   - Add agent response generation using OpenRouter/OpenAI
   - Implement issue steps processing and validation

2. GitHub Issue Creation & Management
   - Implement robust GitHub API error handling
   - Add support for issue labels, assignees, and milestones
   - Handle GitHub API rate limiting with exponential backoff
   - Add GitHub webhook integration for issue updates

3. Issue Content Processing
   - Implement proper chat message to issue conversion
   - Add file context integration in issue descriptions
   - Support multiple issue templates and formats
   - Add issue priority calculation based on content analysis

4. Frontend Integration (@Chat.tsx compatibility)
   - Ensure createIssueWithContext response matches expected format
   - Add proper error message formatting for UI display
   - Support issue preview in chat interface

5. Database & Session Integration
   - Implement proper foreign key relationships
   - Add session-based issue filtering and management
   - Implement issue archiving and cleanup strategies
   - Add database constraints and validation

6. Authentication & Authorization
   - Implement proper GitHub repository access validation
   - Add user permission checking for issue operations
   - Support organization-level access controls
   - Implement issue ownership and collaboration features

14. Issue Workflow Management
    - Implement issue status transition workflows
    - Add support for issue templates and checklists
    - Implement automated issue categorization
    - Add support for issue dependencies and relationships

15. Integration with External Systems
    - Add webhook support for external integrations
    - Implement API for third-party issue management tools
    - Add support for issue import/export functionality
    - Create integration points for CI/CD systems
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from models import CreateUserIssueRequest, User, UserIssue
from sqlalchemy.orm import Session

from utils import utc_now

# Configure logging
logger = logging.getLogger(__name__)


class IssueOpsError(Exception):
    """Custom exception for IssueOps operations"""

    pass


class IssueService:
    """
    Consolidated Issue Service Class

    Provides all issue-related functionality including:
    - GitHub issue creation and management
    - User issue tracking
    - Issue status updates
    - Integration with chat sessions
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

    def generate_github_issue_preview(
        self,
        request: Dict[str, Any],
        use_sample_data: bool = True,
        db: Session = None,
        user_id: int = None,
    ) -> Dict[str, Any]:
        """
        Generate a preview of what the GitHub issue would look like

        Args:
            request: Issue creation request data
            use_sample_data: Whether to use sample data for preview
            db: Database session
            user_id: User ID for context

        Returns:
            GitHub issue preview data
        """
        try:
            logger.info("Generating GitHub issue preview")

            title = request.get("title", "New Issue")
            description = request.get("description", "")
            chat_messages = request.get("chat_messages", [])
            file_context = request.get("file_context", [])
            repository_info = request.get("repository_info")

            # Build issue body from chat context
            body_parts = []

            if description:
                body_parts.append(f"## Description\n{description}\n")

            if chat_messages:
                body_parts.append("## Chat Context\n")
                # Include last few messages for context
                recent_messages = chat_messages[-5:]  # Last 5 messages
                for msg in recent_messages:
                    sender = "User" if msg.get("isUser", True) else "Assistant"
                    content = msg.get("content", "")[:200]  # Truncate long messages
                    body_parts.append(f"**{sender}**: {content}")
                body_parts.append("")

            if file_context:
                body_parts.append("## Relevant Files\n")
                for file in file_context[:5]:  # Limit to 5 files
                    file_name = file.get("name", file.get("file_name", "Unknown"))
                    body_parts.append(
                        f"- `{file_name}` ({file.get('tokens', 0)} tokens)"
                    )
                body_parts.append("")

            # Add standard footer
            body_parts.append(
                "---\n*This issue was generated from a chat conversation.*"
            )

            body = "\n".join(body_parts)

            # Determine labels based on content
            labels = ["chat-generated"]
            if "bug" in title.lower() or "fix" in title.lower():
                labels.append("bug")
            if "feature" in title.lower() or "add" in title.lower():
                labels.append("enhancement")

            preview_data = {
                "title": title,
                "body": body,
                "labels": labels,
                "assignees": [],
                "repository_info": repository_info or {},
                "metadata": {
                    "generated_from": "chat",
                    "chat_messages_count": len(chat_messages),
                    "files_context_count": len(file_context),
                    "preview_generated_at": utc_now().isoformat(),
                },
            }

            logger.info("Successfully generated GitHub issue preview")
            return preview_data

        except Exception as e:
            logger.error(f"Failed to generate GitHub issue preview: {e}")
            return {
                "title": "Error Generating Preview",
                "body": f"Failed to generate preview: {str(e)}",
                "labels": ["error"],
                "assignees": [],
                "repository_info": {},
                "metadata": {"error": str(e)},
            }

    async def create_issue_with_context(
        self,
        user_id: int,
        session_id: str,
        title: str,
        description: str,
        chat_messages: List[Dict[str, Any]],
        file_context: List[Dict[str, Any]],
        repo_owner: str,
        repo_name: str,
        priority: str = "medium",
        create_github_issue: bool = False,
    ) -> Dict[str, Any]:
        """
        Unified function to create issue with context - combines LLM generation and database storage

        Args:
            user_id: User ID
            session_id: Session ID
            title: Issue title
            description: Issue description
            chat_messages: List of chat messages
            file_context: List of relevant files
            repo_owner: Repository owner
            repo_name: Repository name
            priority: Issue priority
            create_github_issue: Whether to also create GitHub issue

        Returns:
            Dictionary containing created issue data and GitHub issue info if requested
        """
        try:
            logger.info(f"Creating issue with context for user {user_id}")

            # Generate issue content using LLM
            llm_generated_issue = await self.generate_issue_from_context(
                user_id=user_id,
                session_id=session_id,
                title=title,
                description=description,
                chat_messages=chat_messages,
                file_context=file_context,
                repo_owner=repo_owner,
                repo_name=repo_name,
                priority=priority,
            )

            # Create user issue in database
            from models import CreateUserIssueRequest

            issue_request = CreateUserIssueRequest(
                title=llm_generated_issue["title"],
                issue_text_raw=llm_generated_issue["body"],
                description=description,
                session_id=session_id,
                context_cards=[],  # Will be populated from session
                repo_owner=repo_owner,
                repo_name=repo_name,
                priority=priority,
                issue_steps=[
                    "Analyze chat conversation context",
                    "Review file dependencies and implementation details",
                    "Design implementation approach based on static analysis",
                    "Implement functionality according to specifications",
                    "Add comprehensive tests and documentation",
                    "Validate implementation against acceptance criteria",
                ],
            )

            user_issue = self._create_user_issue_record(user_id, issue_request)

            result = {
                "success": True,
                "user_issue": {
                    "id": user_issue.id,
                    "issue_id": user_issue.issue_id,
                    "title": user_issue.title,
                    "description": user_issue.description,
                    "issue_text_raw": user_issue.issue_text_raw,
                },
                "github_preview": {
                    "title": llm_generated_issue["title"],
                    "body": llm_generated_issue["body"],
                    "labels": llm_generated_issue["labels"],
                    "assignees": llm_generated_issue["assignees"],
                    "repository_info": {
                        "owner": repo_owner,
                        "name": repo_name,
                        "branch": "main",  # Default branch
                    },
                    "metadata": {
                        "generated_by_llm": True,
                        "processing_time": llm_generated_issue["processing_time"],
                        "tokens_used": llm_generated_issue["tokens_used"],
                        "llm_model": "openrouter/sonoma-sky-alpha",
                        "generated_at": utc_now().isoformat(),
                    },
                },
                "llm_response": llm_generated_issue["llm_response"],
                "message": f"Issue created successfully with ID: {user_issue.issue_id}",
            }

            # Optionally create GitHub issue
            if create_github_issue:
                github_issue = await self.create_github_issue_from_user_issue(
                    user_id, user_issue.issue_id
                )
                if github_issue:
                    result["github_issue"] = github_issue

            return result

        except Exception as e:
            logger.error(f"Failed to create issue with context: {e}")
            raise IssueOpsError(f"Failed to create issue: {str(e)}")

    def _create_user_issue_record(
        self, user_id: int, issue_request: CreateUserIssueRequest
    ) -> UserIssue:
        """
        Helper method to create user issue record in database
        """
        # Generate unique issue ID
        issue_id = f"issue_{uuid.uuid4().hex[:12]}"

        # Create the user issue
        user_issue = UserIssue(
            issue_id=issue_id,
            user_id=user_id,
            title=issue_request.title,
            issue_text_raw=issue_request.issue_text_raw,
            description=issue_request.description,
            session_id=issue_request.session_id,
            context_card_id=issue_request.context_card_id,
            # Note: context_cards and ideas fields are commented out in the SQLAlchemy model
            # context_cards=json.dumps(issue_request.context_cards) if issue_request.context_cards else None,
            # ideas=json.dumps(issue_request.ideas) if issue_request.ideas else None,
            repo_owner=issue_request.repo_owner,
            repo_name=issue_request.repo_name,
            priority=issue_request.priority,
            issue_steps=issue_request.issue_steps,
            status="pending",
            agent_response=None,
            processing_time=None,
            tokens_used=0,
        )

        self.db.add(user_issue)
        self.db.flush()  # Get the ID without committing

        logger.info(f"Successfully created user issue {issue_id} for user {user_id}")
        return user_issue

    def update_issue_status(
        self,
        user_id: int,
        issue_id: str,
        status: str,
        agent_response: Optional[str] = None,
        processing_time: Optional[float] = None,
        tokens_used: int = 0,
    ) -> Optional[UserIssue]:
        """
        Update the status of a user issue

        Args:
            user_id: User ID
            issue_id: Issue ID
            status: New status
            agent_response: Optional agent response
            processing_time: Processing time in seconds
            tokens_used: Tokens used

        Returns:
            Updated UserIssue object or None if not found
        """
        try:
            logger.info(f"Updating issue status for issue {issue_id} by user {user_id}")

            # Find the issue
            issue = (
                self.db.query(UserIssue)
                .filter(UserIssue.user_id == user_id, UserIssue.issue_id == issue_id)
                .first()
            )

            if not issue:
                logger.warning(f"Issue {issue_id} not found for user {user_id}")
                return None

            # Update the issue
            issue.status = status
            if agent_response is not None:
                issue.agent_response = agent_response
            if processing_time is not None:
                issue.processing_time = processing_time
            issue.tokens_used = tokens_used
            issue.updated_at = utc_now()
            issue.processed_at = utc_now()

            self.db.commit()

            logger.info(f"Successfully updated issue {issue_id} status to {status}")
            return issue

        except Exception as e:
            logger.error(f"Failed to update issue status: {e}")
            self.db.rollback()
            raise IssueOpsError(f"Failed to update issue status: {str(e)}")

    async def generate_issue_from_context(
        self,
        user_id: int,
        session_id: str,
        title: str,
        description: str,
        chat_messages: List[Dict[str, Any]],
        file_context: List[Dict[str, Any]],
        repo_owner: str,
        repo_name: str,
        priority: str = "medium",
    ) -> Dict[str, Any]:
        """
        Generate a GitHub issue from chat context using LLM

        Args:
            user_id: User ID
            session_id: Session ID
            title: Issue title
            description: Issue description
            chat_messages: List of chat messages
            file_context: List of relevant files
            repo_owner: Repository owner
            repo_name: Repository name
            priority: Issue priority

        Returns:
            Dictionary containing generated issue data
        """
        try:
            logger.info(f"Generating issue from context for user {user_id}")

            # Get stored GitHub context from repository
            repo_context = ""
            try:
                from models import Repository

                repository = (
                    self.db.query(Repository)
                    .filter(
                        Repository.owner == repo_owner,
                        Repository.name == repo_name,
                        Repository.user_id == user_id,
                    )
                    .first()
                )
                if repository and repository.github_context:
                    # Extract basic context string from stored GitHub context
                    repo_data = repository.github_context.get("repository", {})
                    repo_context = f"Repository: {repo_data.get('full_name', f'{repo_owner}/{repo_name}')}\n"
                    repo_context += f"Description: {repo_data.get('description', 'No description')}\n"
                    repo_context += (
                        f"Language: {repo_data.get('language', 'Unknown')}\n"
                    )
                    repo_context += (
                        f"Open Issues: {repo_data.get('open_issues_count', 0)}\n"
                    )

                    # Add recent issues if available
                    recent_issues = repository.github_context.get("recent_issues", [])
                    if recent_issues:
                        repo_context += "\nRecent Open Issues:\n"
                        for issue in recent_issues[:3]:
                            repo_context += f"- #{issue['number']}: {issue['title']}\n"
                else:
                    repo_context = f"Repository: {repo_owner}/{repo_name}"
            except Exception as e:
                logger.warning(f"Failed to get stored GitHub context: {e}")
                repo_context = f"Repository: {repo_owner}/{repo_name}"

            # Get context cards for additional context
            context_cards = self._get_session_context_cards(session_id, user_id)

            # Retrieve relevant file contexts via embeddings using last few messages + description
            embedding_contexts: List[str] = []
            try:
                from models import ChatSession as _ChatSession

                from .llm_service import LLMService as _LLM

                # Fetch numeric session id
                sess = (
                    self.db.query(_ChatSession)
                    .filter(
                        _ChatSession.session_id == session_id,
                        _ChatSession.user_id == user_id,
                    )
                    .first()
                )
                if sess:
                    # Build comprehensive query text including context cards
                    last_msgs = " ".join(
                        m.get("content", "") for m in (chat_messages or [])[-5:]
                    )
                    context_card_content = self._get_session_context_cards_content(
                        session_id, user_id
                    )
                    query_text = " ".join(
                        filter(
                            None,
                            [
                                title or "",
                                description or "",
                                last_msgs,
                                context_card_content,
                            ],
                        )
                    )
                    embedding_contexts = await _LLM.get_relevant_file_contexts(
                        db=self.db, session_id=sess.id, query_text=query_text, top_k=5
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to retrieve embedding contexts for issue generation: {e}"
                )

            # Build the LLM prompt for issue generation
            prompt = self._build_issue_generation_prompt(
                title=title,
                description=description,
                chat_messages=chat_messages,
                file_context=file_context,
                repo_context=repo_context,
                context_cards=context_cards,
                embedding_contexts=embedding_contexts,
                priority=priority,
            )

            # Import LLM service and generate response
            from .llm_service import LLMService

            start_time = time.time()
            llm_response = await LLMService.generate_response(
                prompt=prompt,
                model="openrouter/sonoma-sky-alpha",  # Use the same model as chat
                temperature=0.3,  # Lower temperature for more focused issue generation
                max_tokens=2000,
                timeout=60,
            )
            processing_time = time.time() - start_time

            # Parse the LLM response to extract structured issue data
            issue_data = self._parse_llm_issue_response(llm_response)

            # Estimate tokens used
            tokens_used = len(prompt.split()) + len(llm_response.split())

            return {
                "title": issue_data.get("title", title),
                "body": issue_data.get("body", ""),
                "labels": issue_data.get("labels", ["chat-generated"]),
                "assignees": issue_data.get("assignees", []),
                "processing_time": processing_time,
                "tokens_used": tokens_used,
                "llm_response": llm_response,
                "raw_response": issue_data,
            }

        except Exception as e:
            logger.error(f"Failed to generate issue from context: {e}")
            raise IssueOpsError(f"Failed to generate issue: {str(e)}")

    def _get_session_context_cards(
        self, session_id: str, user_id: int
    ) -> List[Dict[str, Any]]:
        """Get context cards for a session"""
        try:
            from models import ContextCard

            cards = (
                self.db.query(ContextCard)
                .filter(
                    ContextCard.session_id == session_id,
                    ContextCard.user_id == user_id,
                    ContextCard.is_active,
                )
                .order_by(ContextCard.created_at.desc())
                .all()
            )

            return [
                {
                    "id": card.id,
                    "title": card.title,
                    "content": card.content,
                    "source": card.source,
                    "tokens": card.tokens,
                }
                for card in cards
            ]

        except Exception as e:
            logger.error(f"Failed to get context cards: {e}")
            return []

    def _get_session_context_cards_content(
        self, session_id: str, user_id: int
    ) -> str:
        """Get concatenated content from all context cards for a session"""
        try:
            cards = self._get_session_context_cards(session_id, user_id)
            if not cards:
                return ""

            # Concatenate card titles and content for embedding query
            card_contents = []
            for card in cards[:5]:  # Limit to 5 cards to avoid overly long queries
                card_contents.append(
                    f"{card['title']}: {card['content'][:200]}"
                )  # Truncate content

            return " ".join(card_contents)

        except Exception as e:
            logger.error(f"Failed to get context cards content: {e}")
            return ""

    def _build_issue_generation_prompt(
        self,
        title: str,
        description: str,
        priority: str,
        chat_messages: List[Dict[str, Any]],
        file_context: List[Dict[str, Any]],
        repo_context: str,
        context_cards: List[Dict[str, Any]],
        embedding_contexts: Optional[List[str]] = None,
    ) -> str:
        """Build the prompt for LLM issue generation"""
        prompt_parts = [
            "You are an expert at creating clear, actionable GitHub issues from chat conversations.",
            "",
            "Your task is to analyze the provided chat conversation, file context, and repository information",
            "to create a well-structured GitHub issue that captures the user's intent and provides enough",
            "context for developers to understand and implement the requested changes.",
            "",
            "INSTRUCTIONS:",
            "1. Create a clear, descriptive title that summarizes the issue",
            "2. Write a detailed body that includes:",
            "   - Problem description",
            "   - Context from the conversation",
            "   - Relevant files and code sections",
            "   - Implementation suggestions if mentioned",
            "   - Acceptance criteria",
            "3. Suggest appropriate labels based on the content",
            "4. Use proper GitHub issue formatting with sections and code blocks",
            "",
            f"ORIGINAL TITLE: {title}",
            f"DESCRIPTION: {description}",
            f"PRIORITY: {priority}",
            "",
            "REPOSITORY CONTEXT:",
            f"{repo_context}",
            "",
        ]

        if context_cards:
            prompt_parts.extend(
                [
                    "CONTEXT CARDS:",
                    *[
                        f"- {card['title']}: {card['content'][:200]}..."
                        for card in context_cards
                    ],
                    "",
                ]
            )

        if file_context:
            prompt_parts.extend(
                [
                    "RELEVANT FILES:",
                    *[
                        f"- {file.get('name', file.get('file_name', 'Unknown'))} ({file.get('tokens', 0)} tokens)"
                        for file in file_context
                    ],
                    "",
                ]
            )

        # Include semantic code snippets from embeddings when available
        if embedding_contexts:
            prompt_parts.extend(
                [
                    "RELEVANT CODE CONTEXT (semantic):",
                    *[ctx[:400] for ctx in embedding_contexts[:5]],
                    "",
                ]
            )

        if chat_messages:
            prompt_parts.extend(
                [
                    "CHAT CONVERSATION:",
                ]
            )
            for msg in chat_messages[-10:]:  # Last 10 messages for context
                sender = "User" if msg.get("isUser", True) else "Assistant"
                content = msg.get("content", "")[:300]  # Truncate long messages
                prompt_parts.append(f"{sender}: {content}")
            prompt_parts.append("")

        prompt_parts.extend(
            [
                "OUTPUT FORMAT:",
                "Return a JSON object with the following structure:",
                "{",
                '  "title": "Clear, descriptive issue title",',
                '  "body": "Detailed issue description with sections and formatting",',
                '  "labels": ["label1", "label2"],',
                '  "assignees": []',
                "}",
                "",
                "Make the body comprehensive but focused. Use GitHub's markdown formatting.",
            ]
        )

        return "\n".join(prompt_parts)

    def _parse_llm_issue_response(self, llm_response: str) -> Dict[str, Any]:
        """Parse the LLM response to extract structured issue data"""
        try:
            # Try to extract JSON from the response
            import json
            import re

            # Look for JSON in the response
            json_match = re.search(r"\{.*\}", llm_response, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                return json.loads(json_str)

            # Fallback: try to parse the entire response as JSON
            return json.loads(llm_response.strip())

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            # Fallback: create a basic issue structure from the raw response
            return {
                "title": "Generated Issue",
                "body": llm_response.strip(),
                "labels": ["chat-generated"],
                "assignees": [],
            }

    async def create_github_issue_from_user_issue(
        self, user_id: int, issue_id: str
    ) -> Optional[UserIssue]:
        """
        Create a GitHub issue from a user issue

        Args:
            user_id: User ID
            issue_id: User issue ID

        Returns:
            Updated UserIssue object with GitHub issue URL or None if failed
        """
        try:
            logger.info(
                f"Creating GitHub issue from user issue {issue_id} for user {user_id}"
            )

            # Find the user issue
            user_issue = (
                self.db.query(UserIssue)
                .filter(UserIssue.user_id == user_id, UserIssue.issue_id == issue_id)
                .first()
            )

            if not user_issue:
                logger.warning(f"User issue {issue_id} not found for user {user_id}")
                return None

            # Check if issue already has GitHub URL
            if user_issue.github_issue_url:
                logger.info(f"GitHub issue already exists for user issue {issue_id}")
                return user_issue

            # Validate repository information
            if not user_issue.repo_owner or not user_issue.repo_name:
                logger.error(
                    f"Missing repository information for user issue {issue_id}"
                )
                raise IssueOpsError(
                    "Repository information is required to create GitHub issue"
                )

            # Get user's GitHub token
            github_token = self.get_user_github_token(user_id, self.db)
            if not github_token:
                raise IssueOpsError("No valid GitHub token available")

            # Create the GitHub issue
            github_issue_data = await self._create_github_issue(
                user_issue.repo_owner,
                user_issue.repo_name,
                user_issue.title,
                user_issue.issue_text_raw,
                user_id,
            )

            if github_issue_data:
                # Update the user issue with GitHub information
                user_issue.github_issue_url = github_issue_data["html_url"]
                user_issue.github_issue_number = github_issue_data["number"]
                user_issue.status = "completed"
                user_issue.updated_at = utc_now()
                user_issue.processed_at = utc_now()

                self.db.commit()

                logger.info(
                    f"Successfully created GitHub issue for user issue {issue_id}"
                )
                return user_issue
            else:
                logger.error(f"Failed to create GitHub issue for user issue {issue_id}")
                return None

        except Exception as e:
            logger.error(f"Failed to create GitHub issue from user issue: {e}")
            self.db.rollback()
            raise IssueOpsError(f"Failed to create GitHub issue: {str(e)}")

    async def _create_github_issue(
        self, repo_owner: str, repo_name: str, title: str, body: str, user_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Create a GitHub issue via API

        Args:
            repo_owner: Repository owner
            repo_name: Repository name
            title: Issue title
            body: Issue body
            user_id: User ID for authentication

        Returns:
            GitHub issue data or None if failed
        """
        try:
            from .githubOps import GitHubOps

            github_ops = GitHubOps(self.db)

            # Create the GitHub issue using centralized GitHubOps
            issue_data = await github_ops.create_github_issue(
                repo_owner, repo_name, title, body, user_id, labels=["chat-generated"]
            )

            if issue_data:
                logger.info(
                    f"Successfully created GitHub issue #{issue_data.get('number')}"
                )
                return {
                    "id": issue_data.get("id"),
                    "number": issue_data.get("number"),
                    "html_url": issue_data.get("html_url"),
                    "url": issue_data.get("url"),
                }
            else:
                logger.error("Failed to create GitHub issue")
                return None

        except Exception as e:
            logger.error(f"Error creating GitHub issue: {e}")
            return None

    def get_user_issues(
        self,
        user_id: int,
        session_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[UserIssue]:
        """
        Get user issues with optional filtering

        Args:
            user_id: User ID
            session_id: Optional session ID filter
            status_filter: Optional status filter
            limit: Maximum number of issues to return

        Returns:
            List of UserIssue objects
        """
        try:
            logger.info(f"Getting user issues for user {user_id}")

            query = self.db.query(UserIssue).filter(UserIssue.user_id == user_id)

            if session_id:
                query = query.filter(UserIssue.session_id == session_id)

            if status_filter:
                query = query.filter(UserIssue.status == status_filter)

            issues = query.order_by(UserIssue.created_at.desc()).limit(limit).all()

            logger.info(f"Retrieved {len(issues)} issues for user {user_id}")
            return issues

        except Exception as e:
            logger.error(f"Failed to get user issues: {e}")
            return []

    def get_user_issue(
        self, user_id: int, issue_id: str
    ) -> Optional[UserIssue]:
        """
        Get a specific user issue

        Args:
            user_id: User ID
            issue_id: Issue ID

        Returns:
            UserIssue object or None if not found
        """
        try:
            logger.info(f"Getting user issue {issue_id} for user {user_id}")

            issue = (
                self.db.query(UserIssue)
                .filter(UserIssue.user_id == user_id, UserIssue.issue_id == issue_id)
                .first()
            )

            if issue:
                logger.info(f"Found user issue {issue_id}")
            else:
                logger.warning(f"User issue {issue_id} not found for user {user_id}")

            return issue

        except Exception as e:
            logger.error(f"Failed to get user issue: {e}")
            return None
