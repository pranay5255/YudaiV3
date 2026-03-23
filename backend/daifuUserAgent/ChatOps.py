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

import logging
from typing import Any, Dict, List, Optional, Sequence, Tuple

from context.chat_context import ChatContext
from context.facts_and_memories import FactsAndMemoriesService
from models import ChatMessage, ChatSession
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

            repo_owner, repo_name = self._resolve_session_repository(
                session,
                repository,
            )

            # Get conversation history
            history = self._get_conversation_history(session.id, 10)

            context_inputs: List[str] = []
            if context_cards:
                try:
                    cards_text = self._get_context_cards_content(context_cards, user_id)
                    if cards_text:
                        context_inputs.append(cards_text)
                except Exception as card_error:
                    logger.warning(
                        f"Failed to collect context card content: {card_error}"
                    )

            bootstrap_ctx = self._bootstrap_memory_context(session)
            if bootstrap_ctx:
                context_inputs.append(bootstrap_ctx)

            # Get file contexts (with error handling)
            try:
                from .llm_service import LLMService

                retrieved_contexts = await LLMService.get_relevant_file_contexts(
                    db=self.db,
                    session_id=session.id,
                    query_text=message_text,
                    top_k=5,
                    expected_repo_owner=repo_owner,
                    expected_repo_name=repo_name,
                )
                if retrieved_contexts:
                    context_inputs.extend(retrieved_contexts)
            except Exception as e:
                logger.warning(f"Failed to get file contexts: {e}")
                # Continue without file contexts - non-fatal

            memory_context = None
            if session.generate_facts_memories:
                memory_context = await self._refresh_session_memories(
                    session=session,
                    conversation_history=history + [("user", message_text)],
                )
                if memory_context:
                    context_inputs.append(memory_context)

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
                        fallback_repo_summary = (
                            await chat_context.build_combined_summary()
                        )
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
                llm_result = await LLMService.generate_response_with_stored_context(
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
                ai_response = llm_result.get("text", "")
                ai_actions = llm_result.get("actions", [])

            except Exception as llm_error:
                logger.error(f"LLM service error: {llm_error}")
                # Fallback response
                ai_response = f"I understand you said: '{message_text}'. I'm currently having trouble processing your request. Could you please try again?"
                ai_actions = []

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
                actions=ai_actions,
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

    def _resolve_session_repository(
        self,
        session: ChatSession,
        repository: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Treat the session repo as the source of truth for retrieval and chat context."""

        session_repo = (
            (session.repo_owner, session.repo_name)
            if session.repo_owner and session.repo_name
            else (None, None)
        )
        requested_repo = (
            (repository.get("owner"), repository.get("name"))
            if repository
            else (None, None)
        )

        if all(session_repo):
            if all(requested_repo) and requested_repo != session_repo:
                logger.warning(
                    "Ignoring mismatched chat repository for session %s: session=%s/%s request=%s/%s",
                    session.session_id,
                    session_repo[0],
                    session_repo[1],
                    requested_repo[0],
                    requested_repo[1],
                )
            return session_repo

        return requested_repo

    async def _refresh_session_memories(
        self,
        session: ChatSession,
        conversation_history: Sequence[Tuple[str, str]],
    ) -> Optional[str]:
        """Append new episodic memories for the active session chat."""

        if not session.generate_facts_memories:
            return None

        try:
            from .session_service import MemoryService

            conversation_payload = self._build_conversation_payload(conversation_history)
            stored = MemoryService.get_memories(session)

            result = await self._facts_service.generate_memories(
                conversation=conversation_payload,
                existing_memories=stored.get("memories", []),
                repo_facts=stored.get("facts", []),
                repo_highlights=stored.get("highlights", []),
                max_messages=12,
            )

            appended = MemoryService.append_memories(
                session,
                new_memories=result.memories,
            )
            if not appended:
                return None

            return MemoryService.render_internal_context(memories=appended)

        except Exception as memory_error:
            logger.warning(f"Failed to refresh session memories: {memory_error}")
            return None

    def _build_conversation_payload(
        self,
        history: Sequence[Tuple[str, str]],
    ) -> List[Dict[str, str]]:
        """Format conversation history for episodic memory extraction."""

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

        return payload

    def _bootstrap_memory_context(self, session: ChatSession) -> Optional[str]:
        """Inject stored facts, memories, and the latest snapshot into each turn."""

        from .session_service import MemoryService

        return MemoryService.build_bootstrap_context(session)
