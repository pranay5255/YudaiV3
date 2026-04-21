"""Daifu-facing tools for issue creation and Modal-backed MSWEA execution."""

from __future__ import annotations

from typing import Any, Dict, Optional

from yudai.models import ChatSession, SessionMode, UserIssue
from yudai.realtime.mode_orchestrator import (
    SessionExecutionOrchestrator,
    get_session_execution_orchestrator,
)
from sqlalchemy.orm import Session


STAGE_TOOL_TO_MODE = {
    "run_architect_mode": SessionMode.ARCHITECT.value,
    "run_tester_mode": SessionMode.TESTER.value,
    "run_coder_mode": SessionMode.CODER.value,
}


class DaifuModeToolService:
    """Runs one legal Architect/Tester/Coder stage through the existing orchestrator."""

    def __init__(self, orchestrator: Optional[SessionExecutionOrchestrator] = None) -> None:
        self.orchestrator = orchestrator or get_session_execution_orchestrator()

    async def run_stage_tool(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
        tool_name: str,
        objective: str,
    ) -> Dict[str, Any]:
        mode = STAGE_TOOL_TO_MODE.get(tool_name)
        if mode is None:
            raise ValueError(f"Unknown Daifu stage tool: {tool_name}")

        return await self.orchestrator.start_stage_execution(
            db,
            session=session,
            user_id=user_id,
            objective=objective,
            mode=mode,
            trigger=f"daifu_tool:{tool_name}",
        )

    async def run_all_stage_tools(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
        objective: str,
    ) -> Dict[str, Any]:
        """Start the remaining stage sequence; each stage emits its own tool_call event."""

        return await self.orchestrator.start_execution(
            db,
            session=session,
            user_id=user_id,
            objective=objective,
            trigger="daifu_tool_sequence",
        )

    async def run_frontend_browser_check(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
        objective: str,
    ) -> Dict[str, Any]:
        """Run the manual browser verifier sidecar in the existing sandbox."""

        return await self.orchestrator.start_browser_check(
            db,
            session=session,
            user_id=user_id,
            objective=objective,
            trigger="daifu_tool:run_frontend_browser_check",
        )


class DaifuIssueToolService:
    """Thin Daifu tool wrapper around the backend GitHub issue creation flow."""

    async def create_github_issue(
        self,
        db: Session,
        *,
        session: ChatSession,
        user_id: int,
        issue_id: str,
    ) -> Any:
        """Create a GitHub issue from an existing UserIssue via IssueOps."""

        from .IssueOps import IssueService as IssueOpsService

        user_issue = (
            db.query(UserIssue)
            .filter(
                UserIssue.user_id == user_id,
                UserIssue.issue_id == issue_id,
                UserIssue.session_id == session.session_id,
            )
            .first()
        )
        if not user_issue:
            raise ValueError("Issue not found for this session")

        issue_service = IssueOpsService(db)
        result = await issue_service.create_github_issue_from_user_issue(
            user_id,
            issue_id,
            context_bundle=None,
        )

        if result and result.session_id and result.session_id != session.session_id:
            raise ValueError("Issue does not belong to this session")

        return result


_mode_tool_service_singleton: Optional[DaifuModeToolService] = None
_issue_tool_service_singleton: Optional[DaifuIssueToolService] = None


def get_daifu_mode_tool_service() -> DaifuModeToolService:
    global _mode_tool_service_singleton
    if _mode_tool_service_singleton is None:
        _mode_tool_service_singleton = DaifuModeToolService()
    return _mode_tool_service_singleton


def get_daifu_issue_tool_service() -> DaifuIssueToolService:
    global _issue_tool_service_singleton
    if _issue_tool_service_singleton is None:
        _issue_tool_service_singleton = DaifuIssueToolService()
    return _issue_tool_service_singleton
