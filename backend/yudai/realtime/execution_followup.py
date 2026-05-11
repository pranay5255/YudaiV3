"""Backend-owned assistant follow-up messages for sandbox executions."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from yudai.daifuUserAgent.llm_service import LLMService
from yudai.daifuUserAgent.message_persistence import (
    persist_ai_message,
    refresh_session_message_counts,
)
from yudai.models import AgentExecution, ChatMessage, ChatSession
from yudai.utils import utc_now

from .ws_protocol import WSMessageType, get_ws_hub

logger = logging.getLogger(__name__)


class ExecutionFollowupService:
    """Generates one idempotent assistant message for a terminal execution result."""

    async def create_followup(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        mode: str,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        detail: Optional[str] = None,
        pipeline_execution_id: Optional[str] = None,
    ) -> Optional[str]:
        metadata = dict(execution.execution_metadata or {})
        existing_message_id = metadata.get("followup_message_id")
        if isinstance(existing_message_id, str) and existing_message_id:
            return existing_message_id

        message_id = f"execution_followup_{execution.id}"
        existing_message = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id, ChatMessage.message_id == message_id)
            .first()
        )
        if existing_message:
            metadata["followup_message_id"] = message_id
            execution.execution_metadata = metadata
            flag_modified(execution, "execution_metadata")
            db.commit()
            return message_id

        prompt = self._build_prompt(
            db,
            session=session,
            execution=execution,
            mode=mode,
            status=status,
            result=result or {},
            error=error,
            detail=detail,
        )
        final_text = await self._generate_text(
            prompt,
            mode=mode,
            status=status,
            result=result or {},
            error=error,
            detail=detail,
        )

        persist_ai_message(
            db,
            db_session=session,
            message_id=message_id,
            text=final_text,
            role="assistant",
            context_card_ids=[],
            actions=None,
        )
        metadata["followup_message_id"] = message_id
        metadata["followup_generated_at"] = utc_now().isoformat()
        execution.execution_metadata = metadata
        flag_modified(execution, "execution_metadata")
        refresh_session_message_counts(db, session)
        db.commit()

        await get_ws_hub().send_to_session(
            session.session_id,
            WSMessageType.LLM_STREAM,
            {
                "stream": "llm",
                "message_id": message_id,
                "final_text": final_text,
                "final": True,
                "execution_id": pipeline_execution_id or execution.id,
                "mode": mode,
            },
        )
        return message_id

    def _build_prompt(
        self,
        db: Session,
        *,
        session: ChatSession,
        execution: AgentExecution,
        mode: str,
        status: str,
        result: Dict[str, Any],
        error: Optional[str],
        detail: Optional[str],
    ) -> str:
        objective = ""
        if isinstance(execution.execution_metadata, dict):
            objective = str(
                execution.execution_metadata.get("objective")
                or execution.execution_metadata.get("objective_with_context")
                or ""
            )
        recent_messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(6)
            .all()
        )
        chat_lines = []
        for message in reversed(recent_messages):
            role = (message.role or message.sender_type or "user").strip().lower()
            text = " ".join((message.message_text or "").split())
            if text:
                chat_lines.append(f"- {role}: {text[:280]}")

        compact_result = {
            key: value
            for key, value in result.items()
            if key
            in {
                "status",
                "issue_number",
                "issue_url",
                "test_branch",
                "pr_number",
                "pr_url",
                "changed_files",
                "tests_run",
                "artifact",
                "screenshot_path",
                "visual_report",
                "console_warning_count",
                "failed_request_count",
                "exit_code",
                "duration_ms",
            }
        }

        return "\n".join(
            [
                "You are Daifu, reporting on a completed backend sandbox execution.",
                "Write a concise assistant message for the user. Summarize outcome, useful links, blockers, and next state. Do not include raw logs.",
                f"Mode: {mode}",
                f"Status: {status}",
                f"Detail: {detail or ''}",
                f"Objective: {objective[:1200]}",
                f"Repository: {session.repo_owner or ''}/{session.repo_name or ''}",
                "Recent chat:",
                "\n".join(chat_lines[-6:]) or "- none",
                "Execution result JSON:",
                json.dumps(compact_result, ensure_ascii=True, default=str)[:4000],
                f"Failure details: {error or ''}",
            ]
        )

    async def _generate_text(
        self,
        prompt: str,
        *,
        mode: str,
        status: str,
        result: Dict[str, Any],
        error: Optional[str],
        detail: Optional[str],
    ) -> str:
        try:
            text = await LLMService.generate_response(
                prompt,
                temperature=0.2,
                max_tokens=420,
                timeout=45,
            )
            if text.strip():
                return text.strip()
        except Exception as exc:
            logger.warning("Execution follow-up LLM generation failed: %s", exc)

        return self._fallback_text(mode=mode, status=status, result=result, error=error, detail=detail)

    @staticmethod
    def _fallback_text(
        *,
        mode: str,
        status: str,
        result: Dict[str, Any],
        error: Optional[str],
        detail: Optional[str],
    ) -> str:
        if status == "failed":
            return f"{mode.capitalize()} mode failed: {error or detail or 'no detailed error was reported'}"
        if status == "cancelled":
            return f"{mode.capitalize()} mode was cancelled."
        if status == "waiting_for_input":
            return detail or f"{mode.capitalize()} mode needs input before it can continue."

        parts = [f"{mode.capitalize()} mode completed."]
        issue_url = result.get("issue_url")
        pr_url = result.get("pr_url")
        if issue_url:
            parts.append(f"Issue: {issue_url}")
        if pr_url:
            parts.append(f"Pull request: {pr_url}")
        changed_files = result.get("changed_files")
        if isinstance(changed_files, list) and changed_files:
            parts.append(f"Changed files: {', '.join(str(item) for item in changed_files[:8])}")
        return " ".join(parts)


_followup_service_singleton: Optional[ExecutionFollowupService] = None


def get_execution_followup_service() -> ExecutionFollowupService:
    global _followup_service_singleton
    if _followup_service_singleton is None:
        _followup_service_singleton = ExecutionFollowupService()
    return _followup_service_singleton
