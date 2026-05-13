"""Shared helpers for Daifu-controlled execution stage gates."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from yudai.models import ChatSession, SessionMode, SessionModeStatus, UserQuestion, UserQuestionStatus
from yudai.utils import utc_now


STAGE_GATE_ORIGIN = "stage_gate"
LEGACY_ISSUE_CONFIRMATION_ORIGIN = "github_issue_created_confirmation"

STAGE_GATE_START_OPTION_ID = "start_next_stage"
STAGE_GATE_ADD_NOTES_OPTION_ID = "add_notes"
STAGE_GATE_STOP_OPTION_ID = "stop_here"
LEGACY_STAGE_START_OPTION_ID = "start_workflow"
LEGACY_STAGE_DECLINE_OPTION_ID = "not_now"

STAGE_TOOL_TO_MODE = {
    "run_architect_mode": SessionMode.ARCHITECT.value,
    "run_tester_mode": SessionMode.TESTER.value,
    "run_coder_mode": SessionMode.CODER.value,
}
MODE_TO_STAGE_TOOL = {mode: tool for tool, mode in STAGE_TOOL_TO_MODE.items()}
STAGE_LABELS = {
    SessionMode.ARCHITECT.value: "Architect",
    SessionMode.TESTER.value: "Tester",
    SessionMode.CODER.value: "Coder",
}


def next_mode_for_session(session: ChatSession) -> str:
    if not session.architect_completed_at:
        return SessionMode.ARCHITECT.value
    if not session.tester_completed_at:
        return SessionMode.TESTER.value
    if not session.coder_completed_at:
        return SessionMode.CODER.value
    return SessionMode.COMPLETE.value


def stage_tool_for_mode(mode: Optional[str]) -> Optional[str]:
    if not mode:
        return None
    return MODE_TO_STAGE_TOOL.get(str(mode))


def mode_for_stage_tool(tool_name: Optional[str]) -> Optional[str]:
    if not tool_name:
        return None
    return STAGE_TOOL_TO_MODE.get(str(tool_name))


def is_stage_gate_question(question: UserQuestion) -> bool:
    metadata = question.question_metadata if isinstance(question.question_metadata, dict) else {}
    return metadata.get("origin") in {
        STAGE_GATE_ORIGIN,
        LEGACY_ISSUE_CONFIRMATION_ORIGIN,
    }


def wants_stage_execution(request: Any) -> bool:
    selected = {
        str(item).strip().lower()
        for item in getattr(request, "selected_option_ids", []) or []
        if str(item).strip()
    }
    if selected.intersection(
        {
            STAGE_GATE_START_OPTION_ID,
            LEGACY_STAGE_START_OPTION_ID,
            "start",
            "yes",
        }
    ):
        return True
    if any(item.startswith("start_") for item in selected):
        return True

    answer_text = str(getattr(request, "answer_text", None) or "").strip().lower()
    return answer_text in {"yes", "y", "start", "start workflow", "run it", "go ahead"}


def wants_stage_notes(request: Any) -> bool:
    selected = {
        str(item).strip().lower()
        for item in getattr(request, "selected_option_ids", []) or []
        if str(item).strip()
    }
    return STAGE_GATE_ADD_NOTES_OPTION_ID in selected


def wants_stage_stop(request: Any) -> bool:
    selected = {
        str(item).strip().lower()
        for item in getattr(request, "selected_option_ids", []) or []
        if str(item).strip()
    }
    if selected.intersection({STAGE_GATE_STOP_OPTION_ID, LEGACY_STAGE_DECLINE_OPTION_ID, "stop"}):
        return True
    answer_text = str(getattr(request, "answer_text", None) or "").strip().lower()
    return answer_text in {"no", "n", "stop", "stop here", "not now"}


def append_stage_notes(objective: str, *, next_mode: str, notes: str) -> str:
    cleaned_notes = " ".join((notes or "").split())
    if not cleaned_notes:
        return objective
    label = STAGE_LABELS.get(next_mode, next_mode.capitalize())
    return (
        f"{objective.strip()}\n\n"
        f"Additional user constraints before {label}:\n{cleaned_notes}"
    ).strip()


def summarize_stage_result(mode: Optional[str], result: Dict[str, Any], detail: Optional[str] = None) -> str:
    label = STAGE_LABELS.get(str(mode), str(mode or "Stage").capitalize())
    parts = [detail or f"{label} completed."]
    for key, display in (
        ("issue_url", "Issue"),
        ("test_branch", "Test branch"),
        ("pr_url", "Pull request"),
    ):
        value = result.get(key)
        if value:
            parts.append(f"{display}: {value}")
    changed_files = result.get("changed_files")
    if isinstance(changed_files, list) and changed_files:
        parts.append(
            "Changed files: "
            + ", ".join(str(item) for item in changed_files[:8])
        )
    return " ".join(part for part in parts if part)


def build_stage_recommendation(from_mode: Optional[str], next_mode: str) -> str:
    next_label = STAGE_LABELS.get(next_mode, next_mode.capitalize())
    if from_mode:
        from_label = STAGE_LABELS.get(from_mode, from_mode.capitalize())
        return f"{from_label} is complete. Daifu recommends starting {next_label} next."
    return f"Daifu recommends starting {next_label} first."


def build_stage_gate_prompt(from_mode: Optional[str], next_mode: str) -> str:
    next_label = STAGE_LABELS.get(next_mode, next_mode.capitalize())
    if from_mode:
        from_label = STAGE_LABELS.get(from_mode, from_mode.capitalize())
        return f"{from_label} completed. Start {next_label}?"
    return f"Start {next_label}?"


def stage_gate_payload(question: UserQuestion) -> Dict[str, Any]:
    return {
        "question_id": question.question_id,
        "question_text": question.question_text,
        "multi_select": bool(question.multi_select),
        "options": question.options or [],
        "question_metadata": (
            question.question_metadata if isinstance(question.question_metadata, dict) else {}
        ),
    }


def ensure_stage_gate_question(
    db: Session,
    *,
    session: ChatSession,
    user_id: int,
    from_mode: Optional[str],
    next_mode: str,
    objective: str,
    execution_id: Optional[str],
    summary: Optional[str] = None,
    mode_execution_id: Optional[str] = None,
    recommendation: Optional[str] = None,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> UserQuestion:
    pending_tool = stage_tool_for_mode(next_mode)
    if not pending_tool:
        raise ValueError(f"No Daifu stage tool exists for mode {next_mode!r}")

    pending_questions = (
        db.query(UserQuestion)
        .filter(
            UserQuestion.session_id == session.id,
            UserQuestion.user_id == user_id,
            UserQuestion.status == UserQuestionStatus.PENDING.value,
        )
        .all()
    )
    for question in pending_questions:
        metadata = question.question_metadata if isinstance(question.question_metadata, dict) else {}
        if (
            metadata.get("origin") == STAGE_GATE_ORIGIN
            and metadata.get("next_mode") == next_mode
            and metadata.get("pending_tool") == pending_tool
        ):
            _record_stage_gate_metadata(
                session,
                question=question,
                objective=objective,
                pending_tool=pending_tool,
            )
            return question

    metadata = {
        "origin": STAGE_GATE_ORIGIN,
        "from_mode": from_mode,
        "next_mode": next_mode,
        "pending_tool": pending_tool,
        "objective": objective,
        "execution_id": execution_id,
        "mode_execution_id": mode_execution_id,
        "summary": summary,
        "recommendation": recommendation or build_stage_recommendation(from_mode, next_mode),
    }
    metadata.update(extra_metadata or {})
    question = UserQuestion(
        question_id=f"q_{uuid.uuid4().hex[:10]}",
        session_id=session.id,
        user_id=user_id,
        mode=next_mode,
        question_text=build_stage_gate_prompt(from_mode, next_mode),
        options=[
            {
                "id": STAGE_GATE_START_OPTION_ID,
                "label": f"Start {STAGE_LABELS.get(next_mode, next_mode.capitalize())}",
            },
            {
                "id": STAGE_GATE_ADD_NOTES_OPTION_ID,
                "label": "Add notes or constraints",
            },
            {"id": STAGE_GATE_STOP_OPTION_ID, "label": "Stop here"},
        ],
        multi_select=False,
        status=UserQuestionStatus.PENDING.value,
        question_metadata=metadata,
        asked_at=utc_now(),
    )
    db.add(question)
    db.flush()
    _record_stage_gate_metadata(
        session,
        question=question,
        objective=objective,
        pending_tool=pending_tool,
    )
    return question


def clear_stage_gate_metadata(session: ChatSession) -> None:
    metadata = dict(session.mode_metadata or {})
    for key in (
        "pending_daifu_tool",
        "pending_stage_tool_objective",
        "pending_stage_tool_issue_url",
        "pending_stage_tool_issue_number",
        "pending_stage_gate_question_id",
        "pending_stage_gate",
        "approved_stage_tool",
    ):
        metadata.pop(key, None)
    session.mode_metadata = metadata
    flag_modified(session, "mode_metadata")


def approve_stage_tool(
    session: ChatSession,
    *,
    question: UserQuestion,
    tool_name: str,
    objective: str,
) -> None:
    metadata = dict(session.mode_metadata or {})
    metadata["approved_stage_tool"] = {
        "question_id": question.question_id,
        "tool_name": tool_name,
        "objective": objective,
        "approved_at": utc_now().isoformat(),
    }
    metadata["pending_resume_objective"] = objective
    metadata["pending_daifu_tool"] = tool_name
    metadata["pending_stage_tool_objective"] = objective
    session.mode_metadata = metadata
    flag_modified(session, "mode_metadata")


def _record_stage_gate_metadata(
    session: ChatSession,
    *,
    question: UserQuestion,
    objective: str,
    pending_tool: str,
) -> None:
    metadata = dict(session.mode_metadata or {})
    pending_question_ids = [
        str(item)
        for item in (metadata.get("pending_question_ids") or [])
        if str(item).strip()
    ]
    if question.question_id not in pending_question_ids:
        pending_question_ids.append(question.question_id)
    metadata.update(
        {
            "pending_question_ids": pending_question_ids,
            "pending_daifu_tool": pending_tool,
            "pending_stage_tool_objective": objective,
            "pending_stage_gate_question_id": question.question_id,
            "pending_stage_gate": (
                question.question_metadata if isinstance(question.question_metadata, dict) else {}
            ),
        }
    )
    session.mode_metadata = metadata
    session.mode_status = SessionModeStatus.WAITING_FOR_INPUT.value
    session.current_mode = mode_for_stage_tool(pending_tool) or session.current_mode
    session.mode_updated_at = utc_now()
    session.last_activity = utc_now()
    flag_modified(session, "mode_metadata")
