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

import asyncio
from dataclasses import asdict
import logging
import uuid
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
)

from yudai.context.chat_context import ChatContext
from yudai.context.facts_and_memories import FactsAndMemoriesService
from yudai.models import (
    ChatMessage,
    ChatSession,
    SessionMode,
    SessionModeStatus,
    UserQuestion,
    UserQuestionStatus,
)
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import Session

from yudai.utils import utc_now

if TYPE_CHECKING:
    from .context_probe import ProbeRequest

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

            probe_context = self._consume_probe_context(session)

            answered_question_context = self._answered_question_context(session)
            if answered_question_context:
                context_inputs.append(answered_question_context)

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
                    probe_context=probe_context,
                    fallback_repo_summary=fallback_repo_summary,
                    model="x-ai/grok-4-fast",
                    temperature=0.2,
                    max_tokens=2500,
                    timeout=55,
                )
                ai_response = llm_result.get("text", "")
                ai_actions = llm_result.get("actions", [])
                ai_questions = llm_result.get("questions", [])
                ai_probes = llm_result.get("probes", [])
                if not ai_response and (ai_questions or ai_probes):
                    ai_response = "I need a bit more context before I continue."

            except Exception as llm_error:
                logger.error(f"LLM service error: {llm_error}")
                # Fallback response
                ai_response = f"I understand you said: '{message_text}'. I'm currently having trouble processing your request. Could you please try again?"
                ai_actions = []
                ai_questions = []
                ai_probes = []

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

            if ai_questions or ai_probes:
                await self._start_gathering_phase(
                    session=session,
                    user_id=user_id,
                    questions=ai_questions,
                    probes=ai_probes,
                )

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

    async def process_chat_message_stream(
        self,
        session_id: str,
        user_id: int,
        message_text: str,
        *,
        on_chunk: Callable[[str], Awaitable[None]],
        context_cards: Optional[List[str]] = None,
        repository: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Process a chat message and stream provider deltas before persisting the final reply.
        """
        try:
            logger.info(f"Streaming chat message for session {session_id}")

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

            repo_owner, repo_name = self._resolve_session_repository(session, repository)
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

            probe_context = self._consume_probe_context(session)

            answered_question_context = self._answered_question_context(session)
            if answered_question_context:
                context_inputs.append(answered_question_context)

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

            if session.generate_facts_memories:
                memory_context = await self._refresh_session_memories(
                    session=session,
                    conversation_history=history + [("user", message_text)],
                )
                if memory_context:
                    context_inputs.append(memory_context)

            ai_actions: List[Dict[str, Any]] = []
            ai_questions: List[Dict[str, Any]] = []
            ai_probes: List[Dict[str, Any]] = []
            try:
                from .llm_service import LLMService

                full_history = history + [("User", message_text)]
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
                    except Exception as db_error:
                        logger.warning(
                            f"Failed to ensure GitHub context for {repo_owner}/{repo_name}: {db_error}"
                        )

                    if not github_context and chat_context:
                        fallback_repo_summary = (
                            await chat_context.build_combined_summary()
                        )

                try:
                    prompt = LLMService._build_daifu_prompt_from_context(
                        github_context=github_context,
                        conversation=full_history,
                        file_contexts=context_inputs,
                        probe_context=probe_context,
                        fallback_repo_summary=fallback_repo_summary,
                    )
                except Exception as prompt_error:
                    logger.warning(f"Failed to build streaming prompt: {prompt_error}")
                    prompt = f"User: {message_text}\nAssistant:"

                raw_parts: List[str] = []
                async for chunk in LLMService.stream_response(
                    prompt=prompt,
                    model="x-ai/grok-4-fast",
                    temperature=0.2,
                    max_tokens=2500,
                    timeout=55,
                ):
                    raw_parts.append(chunk)
                    await on_chunk(chunk)

                raw_response = "".join(raw_parts).strip()
                if not raw_response:
                    raise ChatOpsError("LLM stream completed without content")
                parsed = LLMService.format_chat_response_v2(raw_response)
                ai_response = parsed.text
                ai_actions = parsed.actions
                ai_questions = parsed.questions
                ai_probes = parsed.probes
                if not ai_response:
                    ai_response = "I need a bit more context before I continue."

            except Exception as llm_error:
                logger.error(f"LLM stream service error: {llm_error}")
                ai_response = (
                    f"I understand you said: '{message_text}'. I'm currently having "
                    "trouble processing your request. Could you please try again?"
                )
                await on_chunk(ai_response)
                ai_actions = []
                ai_questions = []
                ai_probes = []

            user_msg = ChatMessage(
                session_id=session.id,
                message_id=f"msg_{utc_now().timestamp()}_{user_id}",
                message_text=message_text,
                sender_type="user",
                role="user",
                tokens=len(message_text.split()),
            )
            self.db.add(user_msg)

            ai_msg = ChatMessage(
                session_id=session.id,
                message_id=f"msg_{utc_now().timestamp()}_ai",
                message_text=ai_response,
                sender_type="assistant",
                role="assistant",
                tokens=len(ai_response.split()),
                actions=ai_actions,
            )
            self.db.add(ai_msg)

            session.total_messages += 2
            session.total_tokens += user_msg.tokens + ai_msg.tokens
            session.last_activity = utc_now()
            self.db.commit()

            if ai_questions or ai_probes:
                await self._start_gathering_phase(
                    session=session,
                    user_id=user_id,
                    questions=ai_questions,
                    probes=ai_probes,
                )

            logger.info(f"Successfully streamed chat message for session {session_id}")
            return {
                "reply": ai_response,
                "message_id": ai_msg.message_id,
                "processing_time": 0.5,
                "session_id": session_id,
            }

        except Exception as e:
            logger.error(f"Failed to stream chat message: {e}")
            self.db.rollback()
            raise ChatOpsError(f"Chat streaming failed: {str(e)}")

    def _consume_probe_context(self, session: ChatSession) -> Optional[str]:
        """Read and clear cached probe results from session metadata."""

        meta = dict(session.mode_metadata or {})
        probe_results = meta.get("probe_results")
        if not isinstance(probe_results, list) or not probe_results:
            return None

        meta.pop("probe_results", None)
        meta.pop("gathering_state", None)
        meta.pop("pending_probe_ids", None)
        session.mode_metadata = meta
        flag_modified(session, "mode_metadata")

        try:
            from .context_probe import ContextProbeService, ProbeResult

            results: List[ProbeResult] = []
            for raw in probe_results:
                if not isinstance(raw, dict):
                    continue
                try:
                    results.append(ProbeResult(**raw))
                except TypeError:
                    logger.warning("Skipping malformed probe result metadata: %s", raw)
            return ContextProbeService.format_as_context(results)
        except Exception as exc:
            logger.warning("Failed to consume probe context: %s", exc)
            return None

    def _answered_question_context(self, session: ChatSession) -> Optional[str]:
        """Render recent user answers to Daifu clarification questions."""

        try:
            answered_questions = (
                self.db.query(UserQuestion)
                .filter(
                    UserQuestion.session_id == session.id,
                    UserQuestion.status == UserQuestionStatus.ANSWERED.value,
                )
                .order_by(UserQuestion.answered_at.desc(), UserQuestion.created_at.desc())
                .limit(10)
                .all()
            )
        except Exception as exc:
            logger.warning("Failed to load answered questions: %s", exc)
            return None

        if not answered_questions:
            return None

        lines: List[str] = ["[USER_CLARIFICATIONS]"]
        for question in reversed(answered_questions):
            option_labels = {
                str(option.get("id")): str(option.get("label"))
                for option in (question.options or [])
                if isinstance(option, dict) and option.get("id") and option.get("label")
            }
            selected = [
                option_labels.get(str(option_id), str(option_id))
                for option_id in (question.selected_option_ids or [])
            ]
            answer_parts: List[str] = []
            if selected:
                answer_parts.append("selected: " + ", ".join(selected))
            if question.answer_text:
                answer_parts.append("text: " + self._truncate_context(question.answer_text, 300))
            if not answer_parts:
                answer_parts.append("answered")
            lines.append(
                f"- Q: {self._truncate_context(question.question_text, 300)}\n"
                f"  A: {'; '.join(answer_parts)}"
            )

        return "\n".join(lines)

    async def _start_gathering_phase(
        self,
        *,
        session: ChatSession,
        user_id: int,
        questions: List[Dict[str, Any]],
        probes: List[Dict[str, Any]],
    ) -> None:
        """Persist user questions and start background code probes."""

        from .context_probe import ContextProbeService, ProbeRequest
        from yudai.realtime.ws_protocol import WSMessageType, get_ws_hub

        ws_hub = get_ws_hub()
        question_ids: List[str] = []
        question_deliveries: List[Tuple[str, str, List[Dict[str, str]]]] = []
        normalized_questions = questions[:2]
        probe_requests = [
            ProbeRequest(
                probe_id=f"probe_{uuid.uuid4().hex[:10]}",
                query=str(probe.get("query") or "").strip(),
            )
            for probe in probes[:3]
            if str(probe.get("query") or "").strip()
        ]

        question_mode = self._question_mode(session)
        for question_payload in normalized_questions:
            question_text = str(question_payload.get("text") or "").strip()
            if not question_text:
                continue
            options = self._normalize_question_options(question_payload.get("options"))
            question = UserQuestion(
                question_id=f"q_{uuid.uuid4().hex[:10]}",
                session_id=session.id,
                user_id=user_id,
                mode=question_mode,
                question_text=question_text,
                options=options,
                multi_select=False,
                status=UserQuestionStatus.PENDING.value,
                question_metadata={"origin": "daifu_directive"},
            )
            self.db.add(question)
            question_ids.append(question.question_id)
            question_deliveries.append((question.question_id, question_text, options))

        runnable_probe_requests = probe_requests
        if probe_requests and not ContextProbeService.has_active_sandbox(self.db, session):
            runnable_probe_requests = []
            logger.info("Skipping %d probe(s): no active sandbox", len(probe_requests))

        meta = dict(session.mode_metadata or {})
        if question_ids:
            meta["pending_question_ids"] = question_ids
        else:
            meta.pop("pending_question_ids", None)

        if runnable_probe_requests:
            meta["pending_probe_ids"] = [probe.probe_id for probe in runnable_probe_requests]
        else:
            meta.pop("pending_probe_ids", None)

        if question_ids or runnable_probe_requests:
            meta["gathering_state"] = "active"
        else:
            meta["gathering_state"] = "complete"

        session.mode_metadata = meta
        flag_modified(session, "mode_metadata")
        if question_ids:
            session.mode_status = SessionModeStatus.WAITING_FOR_INPUT.value
            session.mode_updated_at = utc_now()
        session.last_activity = utc_now()
        self.db.commit()

        for question_id, question_text, options in question_deliveries:
            await ws_hub.send_to_session(
                session.session_id,
                WSMessageType.AGENT_QUESTION,
                {
                    "question_id": question_id,
                    "question_text": question_text,
                    "multi_select": False,
                    "options": options,
                },
            )

        if probe_requests and not runnable_probe_requests:
            await ws_hub.send_to_session(
                session.session_id,
                WSMessageType.STATUS,
                {
                    "status": "exploration_skipped",
                    "detail": "No active sandbox is available for code exploration.",
                },
            )

        if runnable_probe_requests:
            task = asyncio.create_task(
                self._run_probes_background(
                    session.session_id,
                    session.id,
                    runnable_probe_requests,
                ),
                name=f"context-probes-{session.session_id}",
            )
            task.add_done_callback(self._log_background_task_result)
            await ws_hub.send_to_session(
                session.session_id,
                WSMessageType.STATUS,
                {
                    "status": "exploring_codebase",
                    "detail": f"Running {len(runnable_probe_requests)} code exploration(s)...",
                },
            )

    async def _run_probes_background(
        self,
        session_public_id: str,
        session_db_id: int,
        probes: List["ProbeRequest"],
    ) -> None:
        """Run probes in parallel and cache results in session metadata."""

        from yudai.db.database import SessionLocal
        from yudai.realtime.lifecycle import get_sandbox_exec_broker
        from yudai.realtime.ws_protocol import WSMessageType, get_ws_hub

        from .context_probe import ContextProbeService

        service = ContextProbeService(get_sandbox_exec_broker())
        db = SessionLocal()
        try:
            session = db.query(ChatSession).filter(ChatSession.id == session_db_id).first()
            if not session:
                return

            results = await service.run_probes_parallel(db, session=session, probes=probes)

            meta = dict(session.mode_metadata or {})
            meta["probe_results"] = [asdict(result) for result in results]
            meta.pop("pending_probe_ids", None)

            pending_questions = [
                str(item)
                for item in (meta.get("pending_question_ids") or [])
                if str(item).strip()
            ]
            meta["gathering_state"] = "probes_done" if pending_questions else "complete"
            session.mode_metadata = meta
            flag_modified(session, "mode_metadata")
            session.last_activity = utc_now()
            db.commit()

            completed = len([result for result in results if result.status == "completed"])
            await get_ws_hub().send_to_session(
                session_public_id,
                WSMessageType.STATUS,
                {
                    "status": "exploration_complete",
                    "detail": f"{completed}/{len(results)} exploration(s) finished",
                },
            )
        except Exception:
            logger.exception("Background context probes failed for session %s", session_public_id)
            await get_ws_hub().send_to_session(
                session_public_id,
                WSMessageType.STATUS,
                {
                    "status": "exploration_failed",
                    "detail": "Code exploration failed.",
                },
            )
        finally:
            db.close()

    @staticmethod
    def _log_background_task_result(task: asyncio.Task[None]) -> None:
        try:
            task.result()
        except asyncio.CancelledError:
            logger.info("Context probe background task was cancelled")
        except Exception:
            logger.exception("Context probe background task failed")

    @staticmethod
    def _question_mode(session: ChatSession) -> Optional[str]:
        if session.current_mode in {
            SessionMode.ARCHITECT.value,
            SessionMode.TESTER.value,
            SessionMode.CODER.value,
        }:
            return session.current_mode
        return None

    @staticmethod
    def _normalize_question_options(raw_options: Any) -> List[Dict[str, str]]:
        if not isinstance(raw_options, list):
            return []
        options: List[Dict[str, str]] = []
        for index, raw in enumerate(raw_options):
            if isinstance(raw, dict):
                label = str(raw.get("label") or "").strip()
                option_id = str(raw.get("id") or "").strip()
            else:
                label = str(raw or "").strip()
                option_id = ""
            if not label:
                continue
            if not option_id:
                option_id = f"option-{index + 1}"
            options.append({"id": option_id, "label": label})
        return options

    @staticmethod
    def _truncate_context(value: str, limit: int) -> str:
        compact = " ".join((value or "").split())
        if len(compact) <= limit:
            return compact
        return compact[:limit].rstrip() + "..."

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
            from yudai.models import ContextCard

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
