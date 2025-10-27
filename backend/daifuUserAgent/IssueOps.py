#!/usr/bin/env python3
"""
IssueOps Module - Consolidated Issue Management Operations

This module provides all issue-related operations including GitHub issue creation,
management, and integration with the chat system. It consolidates functionality
previously scattered across multiple files and provides unified issue operations.

TODO: Implementation Tasks
==========================

HIGH PRIORITY:







6. Issue Content Processing
   - Implement proper chat message to issue conversion
   - Add file context integration in issue descriptions
   - Support multiple issue templates and formats
   - Add issue priority calculation based on content analysis

LOW PRIORITY:
7. Issue Workflow Management
   - Implement issue status transition workflows
   - Add support for issue templates and checklists
   - Implement automated issue categorization
   - Add support for issue dependencies and relationships

8. External System Integration
   - Add webhook support for external integrations

   - Create integration points for CI/CD systems
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from models import (
    ChatMessage,
    ChatSession,
    CreateUserIssueRequest,
    FileItem,
    UserIssue,
)
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

    # Removed unused token/session helpers; use GitHubOps directly when needed

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
            #TODO: Add more labels based on content
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

            # Persist a user issue record that the UI can reference for final GH creation
            user_issue = self._create_user_issue_record(user_id, issue_request)

            result = {
                "success": True,
                "preview_only": False,
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
                        "llm_model": "x-ai/grok-4-fast",
                        "generated_at": utc_now().isoformat(),
                        "generation_method": "create-with-context",
                    },
                },
                "llm_response": llm_generated_issue["llm_response"],
                "message": f"Issue created successfully with ID: {user_issue.issue_id}",
            }

            # Ensure DB persistence before responding so the follow-up
            # "Create GitHub Issue" action can find the record reliably.
            try:
                self.db.commit()
            except Exception as commit_err:
                logger.error(f"Commit failed after creating user issue: {commit_err}")
                self.db.rollback()
                raise

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

        try:
            # Create the user issue
            user_issue = UserIssue(
                issue_id=issue_id,
                user_id=user_id,
                title=issue_request.title,
                issue_text_raw=issue_request.issue_text_raw,
                description=issue_request.description,
                session_id=issue_request.session_id,
                context_card_id=issue_request.context_card_id,
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

            logger.info(
                f"Successfully created user issue {issue_id} for user {user_id}"
            )
            return user_issue
        except Exception as e:
            logger.error(
                f"Failed while creating user issue {issue_id} for user {user_id}: {e}"
            )
            # If any prior DB SELECT failed, the transaction may be aborted.
            # Roll back to reset the session state.
            self.db.rollback()
            raise

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

            # Get comprehensive repository context string using shared utility
            from .services.context_utils import get_best_repo_context_string

            repo_context = await get_best_repo_context_string(
                db=self.db,
                user_id=user_id,
                session_id=session_id,
                repo_owner=repo_owner,
                repo_name=repo_name,
            )

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
                # Reset DB session if a read failed to avoid aborted transaction state
                try:
                    self.db.rollback()
                except Exception:
                    pass

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
                model="x-ai/grok-4-fast",  # Use the same model as chat
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
            from models import ChatSession as _ChatSession
            from models import ContextCard

            # Resolve the numeric chat session primary key from the public session_id
            sess = (
                self.db.query(_ChatSession)
                .filter(
                    _ChatSession.session_id == session_id,
                    _ChatSession.user_id == user_id,
                )
                .first()
            )
            if not sess:
                return []

            cards = (
                self.db.query(ContextCard)
                .filter(
                    ContextCard.session_id == sess.id,
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
            try:
                self.db.rollback()
            except Exception:
                pass
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

    # Consolidated repo context helpers moved to services.context_utils

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
            "Goal: Produce a machine-actionable GitHub issue that a code agent (mini-swe-agent) can execute to completion.",
            "The issue must include a deterministic Runbook with exact non-interactive commands, concrete file targets,",
            "and verification steps. Prefer repo-native tooling and include dependency discovery fallbacks.",
            "",
            "INSTRUCTIONS (CRITICAL):",
            "1) Craft a precise title summarizing the task.",
            "2) Write a detailed body using the following sections in order:",
            "   - Summary (one paragraph of the problem/goal)",
            "   - Repository context (short, derived from provided context)",
            "   - Files in scope (bullet list of specific file paths to modify/create)",
            "   - Steps to reproduce (one bash block, minimal commands)",
            "   - Environment setup (one bash block; detect package manager/tooling from context; prefer non-interactive flags)",
            "   - Implementation plan (ordered list; concrete edits with file paths; include fallback discovery e.g. `pnpm search onchainkit` if package unclear)",
            "   - Verification (one bash block to build/run/tests; include expected outputs)",
            "   - Acceptance criteria (checkbox list; binary verifiable)",
            "   - Risks / Rollback (brief)",
            "   - Labels (suggested labels)",
            "3) When suggesting installs or commands, use repo-native tooling (e.g., pnpm if pnpm lock is present) and include non-interactive flags.",
            "4) Provide concise code snippets only where essential.",
            "5) Keep the Runbook safe for CI: no interactive prompts, no background daemons, avoid long-running servers unless necessary.",
            "6) If a dependency/package name is ambiguous or missing, first add a discovery step (search command) before install.",
            "",
            f"ORIGINAL TITLE: {title}",
            f"DESCRIPTION: {description}",
            f"PRIORITY: {priority}",
            "",
            "REPOSITORY CONTEXT (summary/snippet):",
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
                    "RELEVANT FILES (top candidates):",
                    *[
                        f"- {file.get('path', file.get('name', file.get('file_name', 'Unknown')))} (tokens: {file.get('tokens', 0)})"
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
                "AGENT CONSTRAINTS:",
                "- Commands must be non-interactive (add flags like --yes, --legacy-peer-deps, or equivalent where safe).",
                "- Prefer repo-native tooling (e.g., pnpm over npm if pnpm lock exists).",
                "- Include an explicit discovery step before installing ambiguous packages.",
                "- Keep bash blocks minimal and directly executable.",
                "",
                "OUTPUT FORMAT:",
                "Return a JSON object with the following structure (extra keys allowed):",
                "{",
                '  "title": "Clear, descriptive issue title",',
                '  "body": "Detailed issue description with sections (Summary, Repository context, Files in scope, Steps to reproduce, Environment setup, Implementation plan, Verification, Acceptance criteria, Risks / Rollback, Labels)",',
                '  "labels": ["label1", "label2"],',
                '  "assignees": []',
                "}",
                "",
                "Notes:",
                "- You may include additional keys like \"mswea\": {\"runbook\": {...}} if useful. The system will ignore unknown keys.",
                "- Ensure the body contains exactly one bash block for each of: Steps to reproduce, Environment setup, Verification.",
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
        self,
        user_id: int,
        issue_id: str,
        context_bundle: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserIssue]:
        """
        Create a GitHub issue from a user issue

        Args:
            user_id: User ID
            issue_id: User issue ID
            context_bundle: Optional structured context to augment the issue body

        Returns:
            Updated UserIssue object with GitHub issue URL or None if failed
        """
        user_issue: Optional[UserIssue] = None
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
                raise IssueOpsError("User issue not found for this session or it may have been removed.")

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
                    "Repository information is required to create GitHub issue. "
                    "Please ensure the repository owner and name are properly set."
                )

            # Get user's GitHub token
            from .githubOps import GitHubOps as _GitHubOps
            github_token = _GitHubOps.get_user_github_token(user_id, self.db)
            if not github_token:
                raise IssueOpsError(
                    "No valid GitHub token available. "
                    "Please ensure you have authenticated with GitHub and have the necessary permissions. "
                    "Required OAuth scopes: repo, public_repo, user:email, read:org"
                )

            context = self._build_issue_context(user_issue, context_bundle)
            issue_body = self._compose_issue_body(user_issue.issue_text_raw, context)

            # Create the GitHub issue
            github_issue_data = await self._create_github_issue(
                user_issue.repo_owner,
                user_issue.repo_name,
                user_issue.title,
                issue_body,
                user_id,
            )

            if not github_issue_data:
                raise IssueOpsError(
                    f"GitHub issue creation returned no data for repository "
                    f"{user_issue.repo_owner}/{user_issue.repo_name}. "
                    "Please verify repository permissions and retry."
                )

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

        except IssueOpsError as e:
            logger.error(f"Failed to create GitHub issue from user issue: {e}")
            self.db.rollback()
            raise
        except Exception as e:
            logger.error(f"Failed to create GitHub issue from user issue: {e}")
            self.db.rollback()

            repo_ref = None
            if user_issue:
                repo_owner = getattr(user_issue, 'repo_owner', None)
                repo_name = getattr(user_issue, 'repo_name', None)
                if repo_owner and repo_name:
                    repo_ref = f"{repo_owner}/{repo_name}"
            if not repo_ref:
                repo_ref = "the selected repository"

            error_str = str(e).lower()
            if any(
                keyword in error_str for keyword in [
                    '403', 'forbidden', 'permission', 'access denied', 'not authorized'
                ]
            ):
                raise IssueOpsError(
                    f"Permission denied creating GitHub issue for {repo_ref}. "
                    f"Please ensure your GitHub App has 'Issues' repository permission enabled and that you have write access. "
                    f"Original error: {str(e)}"
                )
            if any(keyword in error_str for keyword in ['404', 'not found']):
                raise IssueOpsError(
                    f"Repository {repo_ref} not found or not accessible. "
                    f"Please verify the repository exists and you have access to it. "
                    f"Original error: {str(e)}"
                )

            raise IssueOpsError(f"Failed to create GitHub issue: {str(e)}")


    def _build_issue_context(
        self,
        user_issue: UserIssue,
        context_bundle: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Assemble repository and conversation context for issue body rendering."""

        context: Dict[str, Any] = dict(context_bundle or {})
        chat_session: Optional[ChatSession] = None

        if user_issue.session_id:
            chat_session = (
                self.db.query(ChatSession)
                .filter(ChatSession.session_id == user_issue.session_id)
                .first()
            )

        if chat_session:
            context.setdefault(
                "repository_info",
                {
                    "owner": chat_session.repo_owner,
                    "name": chat_session.repo_name,
                    "branch": chat_session.repo_branch,
                    "url": f"https://github.com/{chat_session.repo_owner}/{chat_session.repo_name}"
                    if chat_session.repo_owner and chat_session.repo_name
                    else None,
                },
            )

            if (
                isinstance(chat_session.repo_context, dict)
                and "facts_memories" not in context
            ):
                fam = chat_session.repo_context.get("facts_and_memories")
                if isinstance(fam, dict):
                    context["facts_memories"] = fam

            if "conversation" not in context:
                messages = (
                    self.db.query(ChatMessage)
                    .filter(ChatMessage.session_id == chat_session.id)
                    .order_by(ChatMessage.created_at.desc())
                    .limit(8)
                    .all()
                )
                context["conversation"] = [
                    {
                        "author": message.sender_type or message.role or "user",
                        "text": message.message_text,
                    }
                    for message in reversed(messages)
                ]

            if "files" not in context:
                files = (
                    self.db.query(FileItem)
                    .filter(
                        FileItem.session_id == chat_session.id,
                        FileItem.is_directory.is_(False),
                    )
                    .order_by(FileItem.tokens.desc())
                    .limit(5)
                    .all()
                )
                context["files"] = [
                    {
                        "path": file.path,
                        "tokens": file.tokens,
                    }
                    for file in files
                    if file.path
                ]

        return context

    def _compose_issue_body(
        self, base_body: str, context: Optional[Dict[str, Any]]
    ) -> str:
        """Combine base issue description with contextual sections."""

        sections: List[str] = []
        base = (base_body or "").strip()
        if base:
            sections.append(base)

        repo_info = (context or {}).get("repository_info") or {}
        if repo_info:
            repo_lines = ["## Repository"]
            owner = repo_info.get("owner")
            name = repo_info.get("name")
            url = repo_info.get("url")
            branch = repo_info.get("branch")
            if owner and name:
                repo_lines.append(f"- **Name**: {owner}/{name}")
            elif name:
                repo_lines.append(f"- **Name**: {name}")
            if branch:
                repo_lines.append(f"- **Branch**: {branch}")
            if url:
                repo_lines.append(f"- **URL**: {url}")
            sections.append("\n".join(repo_lines))

        facts_memories = (context or {}).get("facts_memories") or {}
        facts = facts_memories.get("facts") or []
        memories = facts_memories.get("memories") or []
        highlights = facts_memories.get("highlights") or []
        if facts:
            sections.append(
                "## Repository Facts\n" + "\n".join(f"- {fact}" for fact in facts)
            )
        if memories:
            sections.append(
                "## Session Memories\n" + "\n".join(f"- {memory}" for memory in memories)
            )
        if highlights:
            sections.append(
                "## Highlights\n" + "\n".join(f"- {highlight}" for highlight in highlights)
            )

        conversation = (context or {}).get("conversation") or []
        if conversation:
            convo_lines = ["## Recent Conversation"]
            for entry in conversation:
                author = entry.get("author", "user")
                text = (entry.get("text") or "").strip()
                if len(text) > 250:
                    text = f"{text[:247]}..."
                convo_lines.append(f"- **{author}**: {text}")
            sections.append("\n".join(convo_lines))

        files = (context or {}).get("files") or []
        if files:
            file_lines = ["## Relevant Files"]
            for entry in files:
                path = entry.get("path")
                tokens = entry.get("tokens")
                if not path:
                    continue
                if tokens:
                    file_lines.append(f"- `{path}` ({tokens} tokens)")
                else:
                    file_lines.append(f"- `{path}`")
            sections.append("\n".join(file_lines))

        sections.append("---\n*Issue generated with DAifu session context.*")
        return "\n\n".join(section for section in sections if section)


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
            from .githubOps import GitHubOps, GitHubOpsError
        except ImportError as import_error:
            logger.error(f"GitHub operations module unavailable: {import_error}")
            raise IssueOpsError("GitHub integration is not available. Please verify the backend deployment.") from import_error

        try:
            github_ops = GitHubOps(self.db)

            issue_data = await github_ops.create_github_issue(
                repo_owner, repo_name, title, body, user_id, labels=["chat-generated"]
            )

            if not issue_data:
                raise IssueOpsError(
                    f"GitHub issue creation returned no data for {repo_owner}/{repo_name}. "
                    "Please verify repository permissions and retry."
                )

            logger.info(
                f"Successfully created GitHub issue #{issue_data.get('number')}"
            )
            return {
                "id": issue_data.get("id"),
                "number": issue_data.get("number"),
                "html_url": issue_data.get("html_url"),
                "url": issue_data.get("url"),
            }

        except GitHubOpsError as e:
            logger.error(f"GitHubOps error while creating issue: {e}")
            raise IssueOpsError(str(e)) from e
        except Exception as e:
            logger.error(f"Unexpected error creating GitHub issue: {e}")
            raise IssueOpsError(f"Failed to create GitHub issue: {str(e)}")

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
