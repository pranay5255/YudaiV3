"""Compatibility wrappers around the :mod:`backend.context.chat_context` helpers."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from .chat_context import ChatContext


async def ensure_github_context(
    db: Session,
    user_id: int,
    session_obj,
    repo_owner: str,
    repo_name: str,
) -> Optional[dict]:
    """Proxy to :class:`ChatContext` for refreshing GitHub repository context."""

    context = ChatContext(
        db=db,
        user_id=user_id,
        repo_owner=repo_owner,
        repo_name=repo_name,
        session_obj=session_obj,
    )
    return await context.ensure_github_context()


async def get_best_repo_context_string(
    db: Session,
    user_id: int,
    session_id: str,
    repo_owner: str,
    repo_name: str,
) -> str:
    """Return the best available repository context summary for IssueOps."""

    context = ChatContext(
        db=db,
        user_id=user_id,
        repo_owner=repo_owner,
        repo_name=repo_name,
        session_id=session_id,
    )
    return await context.get_best_context_string()
