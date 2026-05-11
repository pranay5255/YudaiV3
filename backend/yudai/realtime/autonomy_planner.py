"""Backend-owned next-action planner for autonomous sandbox workflows."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from yudai.daifuUserAgent.llm_service import LLMService
from yudai.models import ChatMessage, ChatSession, SessionMode

logger = logging.getLogger(__name__)

WORKFLOW_ACTIONS = {
    "run_architect_mode": SessionMode.ARCHITECT.value,
    "run_tester_mode": SessionMode.TESTER.value,
    "run_coder_mode": SessionMode.CODER.value,
}
CONTROL_ACTIONS = {"ask_user", "stop"}
ALLOWED_ACTIONS = set(WORKFLOW_ACTIONS) | CONTROL_ACTIONS | {"run_frontend_browser_check"}


@dataclass
class AutonomyDecision:
    action: str
    objective: str
    reason: str
    user_visible_summary: str
    questions: List[str]
    todo_items: List[str]
    confidence: float
    raw_output: Dict[str, Any]
    source: str = "llm"

    @property
    def workflow_mode(self) -> Optional[str]:
        return WORKFLOW_ACTIONS.get(self.action)


class DaifuAutonomyPlanner:
    """Asks a backend LLM what the worker should do after a sandbox result."""

    async def decide_next_action(
        self,
        db: Session,
        *,
        session: ChatSession,
        pipeline_execution_id: str,
        objective: str,
        completed_mode: Optional[str],
        result: Dict[str, Any],
        remaining_modes: List[str],
        step_index: int,
    ) -> AutonomyDecision:
        fallback = self.fallback_decision(
            objective=objective,
            remaining_modes=remaining_modes,
            completed_mode=completed_mode,
            result=result,
        )
        prompt = self._build_prompt(
            db,
            session=session,
            pipeline_execution_id=pipeline_execution_id,
            objective=objective,
            completed_mode=completed_mode,
            result=result,
            remaining_modes=remaining_modes,
            step_index=step_index,
        )
        try:
            text = await LLMService.generate_response(
                prompt,
                temperature=0.0,
                max_tokens=700,
                timeout=45,
            )
            payload = self._extract_json_object(text)
            return self._normalize_decision(payload, fallback=fallback)
        except Exception as exc:
            logger.warning("Autonomy planner fell back after error: %s", exc)
            return fallback

    def fallback_decision(
        self,
        *,
        objective: str,
        remaining_modes: List[str],
        completed_mode: Optional[str],
        result: Dict[str, Any],
    ) -> AutonomyDecision:
        if result.get("waiting_for_input"):
            questions = [
                str(question)
                for question in (result.get("questions") or [])
                if str(question).strip()
            ]
            return AutonomyDecision(
                action="ask_user",
                objective=objective,
                reason="The last mode requested clarification before continuing.",
                user_visible_summary="I need clarification before continuing the workflow.",
                questions=questions,
                todo_items=[],
                confidence=1.0,
                raw_output={"fallback": True},
                source="fallback",
            )
        if remaining_modes:
            next_mode = remaining_modes[0]
            action = {
                SessionMode.ARCHITECT.value: "run_architect_mode",
                SessionMode.TESTER.value: "run_tester_mode",
                SessionMode.CODER.value: "run_coder_mode",
            }.get(next_mode, "stop")
            return AutonomyDecision(
                action=action,
                objective=objective,
                reason=f"{next_mode.capitalize()} is the next incomplete workflow mode.",
                user_visible_summary=f"{completed_mode.capitalize() if completed_mode else 'The previous stage'} completed; continuing to {next_mode}.",
                questions=[],
                todo_items=[],
                confidence=0.8,
                raw_output={"fallback": True, "remaining_modes": remaining_modes},
                source="fallback",
            )
        return AutonomyDecision(
            action="stop",
            objective=objective,
            reason="All required workflow modes are complete.",
            user_visible_summary="The autonomous workflow is complete.",
            questions=[],
            todo_items=[],
            confidence=1.0,
            raw_output={"fallback": True},
            source="fallback",
        )

    def _build_prompt(
        self,
        db: Session,
        *,
        session: ChatSession,
        pipeline_execution_id: str,
        objective: str,
        completed_mode: Optional[str],
        result: Dict[str, Any],
        remaining_modes: List[str],
        step_index: int,
    ) -> str:
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
                chat_lines.append(f"- {role}: {text[:300]}")

        compact_result = {
            key: value
            for key, value in result.items()
            if key
            in {
                "status",
                "mode",
                "issue_number",
                "issue_url",
                "questions",
                "ready_for_tester",
                "test_branch",
                "pr_number",
                "pr_url",
                "changed_files",
                "tests_run",
                "exit_code",
                "duration_ms",
                "artifact",
            }
        }
        schema = {
            "action": "run_architect_mode | run_tester_mode | run_coder_mode | run_frontend_browser_check | ask_user | stop",
            "objective": "string",
            "reason": "string",
            "user_visible_summary": "string",
            "questions": ["string"],
            "todo_items": ["string"],
            "confidence": 0.0,
        }
        return "\n".join(
            [
                "You are Daifu's backend autonomy planner.",
                "Choose exactly one next action for the worker. Return only a JSON object matching the schema.",
                "Only select workflow actions that are safe and necessary. Do not invent tools.",
                "Use ask_user if the result needs clarification. Use stop when enough work is done or no safe action remains.",
                f"Allowed schema: {json.dumps(schema, ensure_ascii=True)}",
                f"Pipeline execution id: {pipeline_execution_id}",
                f"Step index: {step_index}",
                f"Repository: {session.repo_owner or ''}/{session.repo_name or ''}@{session.repo_branch or 'main'}",
                f"Original objective: {objective[:1200]}",
                f"Completed mode: {completed_mode or ''}",
                f"Remaining modes: {', '.join(remaining_modes) or 'none'}",
                "Recent chat:",
                "\n".join(chat_lines) or "- none",
                "Last sandbox result:",
                json.dumps(compact_result, ensure_ascii=True, default=str)[:4000],
            ]
        )

    @staticmethod
    def _extract_json_object(text: str) -> Dict[str, Any]:
        raw = text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        if not raw.startswith("{"):
            match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
            if not match:
                raise ValueError("planner response did not contain JSON")
            raw = match.group(0)
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("planner JSON must be an object")
        return parsed

    @staticmethod
    def _normalize_decision(payload: Dict[str, Any], *, fallback: AutonomyDecision) -> AutonomyDecision:
        action = str(payload.get("action") or "").strip()
        if action not in ALLOWED_ACTIONS:
            return fallback
        objective = str(payload.get("objective") or fallback.objective or "").strip()
        reason = str(payload.get("reason") or "").strip() or fallback.reason
        summary = str(payload.get("user_visible_summary") or "").strip() or fallback.user_visible_summary
        questions = [
            str(item).strip()
            for item in (payload.get("questions") or [])
            if str(item).strip()
        ][:5]
        todo_items = [
            str(item).strip()
            for item in (payload.get("todo_items") or [])
            if str(item).strip()
        ][:8]
        try:
            confidence = float(payload.get("confidence"))
        except (TypeError, ValueError):
            confidence = fallback.confidence
        confidence = min(1.0, max(0.0, confidence))
        return AutonomyDecision(
            action=action,
            objective=objective or fallback.objective,
            reason=reason,
            user_visible_summary=summary,
            questions=questions,
            todo_items=todo_items,
            confidence=confidence,
            raw_output=payload,
        )


_planner_singleton: Optional[DaifuAutonomyPlanner] = None


def get_daifu_autonomy_planner() -> DaifuAutonomyPlanner:
    global _planner_singleton
    if _planner_singleton is None:
        _planner_singleton = DaifuAutonomyPlanner()
    return _planner_singleton
