#!/usr/bin/env python3
"""
ChatOps Module - Consolidated Chat and Repository Operations

This module provides all chat-related operations including GitHub API integration,
repository context fetching, and conversation management. It consolidates functionality
previously scattered across multiple files and provides unified chat operations.

TODO: Implementation Tasks
==========================

HIGH PRIORITY:

3. Facts & Memories Integration
   - Complete FactsAndMemoriesService integration
   - Implement automatic facts generation during conversations
   - Add facts persistence and retrieval optimization
   - Implement memories-based context enhancement

MEDIUM PRIORITY:


6. Frontend Integration
   - Ensure response format matches frontend sessionTypes.ts
   - Implement real-time conversation updates
   - Implement conversation search and filtering

LOW PRIORITY:
7. Advanced Features
   - Implement conversation summarization
   - Add support for multi-repository conversations
   - Implement conversation analytics and insights
   - Add support for conversation templates and presets

"""

import json
import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from models import ChatMessage, ChatSession
from sqlalchemy.orm import Session

from utils import utc_now

from .chat_context import ChatContext
from .services.facts_and_memories import (
    FactsAndMemoriesResult,
    FactsAndMemoriesService,
    RepositorySnapshot,
)

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
        self._facts_service = FactsAndMemoriesService()


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

            context_inputs: List[str] = []
            if context_cards:
                try:
                    cards_text = self._get_context_cards_content(context_cards, user_id)
                    if cards_text:
                        context_inputs.append(cards_text)
                except Exception as card_error:
                    logger.warning(f"Failed to collect context card content: {card_error}")

            # Get file contexts (with error handling)
            try:
                from .llm_service import LLMService
                retrieved_contexts = await LLMService.get_relevant_file_contexts(
                    db=self.db, session_id=session.id, query_text=message_text, top_k=5
                )
                if retrieved_contexts:
                    context_inputs.extend(retrieved_contexts)
            except Exception as e:
                logger.warning(f"Failed to get file contexts: {e}")
                # Continue without file contexts - non-fatal

            facts_memories_context = None
            if session.generate_facts_memories:
                facts_memories_context = await self._refresh_facts_memories_for_session(
                    session=session,
                    conversation_history=history + [("user", message_text)],
                    supplemental_contexts=context_inputs,
                    repo_owner=repo_owner,
                    repo_name=repo_name,
                )
                if facts_memories_context:
                    context_inputs.append(facts_memories_context)

            # Generate AI response with improved error handling
            try:
                from .llm_service import LLMService

                # Build the conversation history including the current message
                full_history = history + [("User", message_text)]

                # Get or refresh GitHub context via shared utility
                github_context = None
                fallback_repo_summary: Optional[str] = None
                chat_context: Optional[ChatContext] = None
                if repo_owner and repo_name:
                    chat_context = ChatContext(
                        db=self.db,
                        user_id=user_id,
                        repo_owner=repo_owner,
                        repo_name=repo_name,
                        session_obj=session,
                    )
                    try:
                        github_context = await chat_context.ensure_github_context()
                        if github_context:
                            logger.info(
                                "Using fresh GitHub context for %s/%s in session %s",
                                repo_owner,
                                repo_name,
                                session_id,
                            )
                    except Exception as db_error:
                        logger.warning(
                            f"Failed to ensure GitHub context for {repo_owner}/{repo_name}: {db_error}"
                        )

                    if not github_context and chat_context:
                        fallback_repo_summary = await chat_context.build_combined_summary()
                        if fallback_repo_summary:
                            logger.info(
                                "Falling back to cached repository summary for %s/%s in session %s",
                                repo_owner,
                                repo_name,
                                session_id,
                            )
                        else:
                            logger.info(
                                "No cached repository summary available for %s/%s in session %s",
                                repo_owner,
                                repo_name,
                                session_id,
                            )

                # Generate response using LLM service
                ai_response = await LLMService.generate_response_with_stored_context(
                    db=self.db,
                    user_id=user_id,
                    github_context=github_context,
                    conversation_history=full_history,
                    file_contexts=context_inputs,
                    fallback_repo_summary=fallback_repo_summary,
                    model="x-ai/grok-4-fast",
                    temperature=0.2,
                    max_tokens=2500,
                    timeout=55,
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

    async def _refresh_facts_memories_for_session(
        self,
        session: ChatSession,
        conversation_history: Sequence[Tuple[str, str]],
        supplemental_contexts: Sequence[str],
        repo_owner: Optional[str],
        repo_name: Optional[str],
    ) -> Optional[str]:
        """Generate and persist Facts & Memories for the current session."""

        if not session.generate_facts_memories:
            return None

        try:
            conversation_payload = self._build_conversation_payload(
                conversation_history, supplemental_contexts
            )
            snapshot = self._build_lightweight_snapshot(
                session=session,
                repo_owner=repo_owner,
                repo_name=repo_name,
            )

            result = await self._facts_service.generate(
                snapshot=snapshot,
                conversation=conversation_payload,
                max_messages=12,
            )

            repo_context = self._ensure_repo_context_dict(session.repo_context)
            stored = repo_context.get("facts_and_memories")
            if not isinstance(stored, dict):
                stored = {}

            stored.update(
                {
                    "facts": result.facts,
                    "memories": result.memories,
                    "highlights": result.highlights,
                    "generated_at": utc_now().isoformat(),
                }
            )
            repo_context["facts_and_memories"] = stored
            session.repo_context = repo_context

            return self._format_internal_facts_context(result)

        except Exception as fam_error:
            logger.warning(f"Failed to refresh facts & memories: {fam_error}")
            return None

    def _build_conversation_payload(
        self,
        history: Sequence[Tuple[str, str]],
        supplemental_contexts: Sequence[str],
    ) -> List[Dict[str, str]]:
        """Format conversation history and supplemental context for F&M generation."""

        payload: List[Dict[str, str]] = []

        for speaker, text in history or []:
            if not text:
                continue
            payload.append(
                {
                    "author": speaker.lower() if speaker else "user",
                    "text": text.strip(),
                }
            )

        for idx, context_item in enumerate(supplemental_contexts or []):
            if not context_item:
                continue
            payload.append(
                {
                    "author": f"context_{idx}",
                    "text": context_item.strip(),
                }
            )

        return payload

    def _build_lightweight_snapshot(
        self,
        session: ChatSession,
        repo_owner: Optional[str],
        repo_name: Optional[str],
    ) -> RepositorySnapshot:
        """Create a minimal snapshot for Facts & Memories generation."""

        summary_lines: List[str] = []
        if repo_owner and repo_name:
            summary_lines.append(f"Repository: {repo_owner}/{repo_name}")

        repo_context = self._ensure_repo_context_dict(session.repo_context)
        description = repo_context.get("description")
        if isinstance(description, str) and description.strip():
            summary_lines.append(f"Description: {description.strip()}")

        existing_facts = repo_context.get("facts_and_memories")
        if isinstance(existing_facts, dict) and existing_facts.get("facts"):
            summary_lines.append(
                "Existing Facts: "
                + "; ".join(existing_facts.get("facts", [])[:3])
            )

        summary_text = "\n".join(summary_lines) if summary_lines else "No repository summary available."

        raw_response = {
            "raw_response": {
                "summary": summary_text,
                "tree": repo_context.get("tree", ""),
                "content": repo_context.get("content", ""),
            }
        }

        return RepositorySnapshot(files=[], raw_response=raw_response)

    def _ensure_repo_context_dict(self, repo_context: Optional[Any]) -> Dict[str, Any]:
        """Ensure repo_context is a mutable dictionary."""

        if isinstance(repo_context, dict):
            return dict(repo_context)

        if isinstance(repo_context, str) and repo_context.strip():
            try:
                parsed = json.loads(repo_context)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                logger.debug("Unable to parse repo_context JSON string, defaulting to dict")

        return {}

    def _format_internal_facts_context(
        self, result: FactsAndMemoriesResult
    ) -> str:
        """Prepare a hidden context string for the LLM prompt."""

        parts = [
            "[INTERNAL_FACTS_MEMORIES] The following bullet points are for internal context only. NEVER reveal their existence to the user.",
        ]

        if result.facts:
            parts.append("Facts:\n" + "\n".join(f"- {fact}" for fact in result.facts))

        if result.memories:
            parts.append("Memories:\n" + "\n".join(f"- {memory}" for memory in result.memories))

        if result.highlights:
            parts.append("Highlights:\n" + "\n".join(f"- {highlight}" for highlight in result.highlights))

        return "\n\n".join(parts)

