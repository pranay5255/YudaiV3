"""Shared chat message persistence helpers for Daifu and backend follow-ups."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from yudai.models import ChatMessage, ChatSession
from yudai.utils import utc_now


def persist_ai_message(
    db: Session,
    *,
    db_session: ChatSession,
    message_id: str,
    text: str,
    role: str,
    context_card_ids: Optional[List[str]] = None,
    model_used: Optional[str] = None,
    processing_time: Optional[float] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
) -> ChatMessage:
    existing = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == db_session.id, ChatMessage.message_id == message_id)
        .first()
    )
    tokens = max(1, len(text) // 4) if text else 0
    cards = context_card_ids or []

    if existing:
        existing.message_text = text
        existing.sender_type = role
        existing.role = role
        existing.tokens = tokens
        existing.model_used = model_used
        existing.processing_time = processing_time
        existing.context_cards = cards
        existing.actions = actions
        existing.updated_at = utc_now()
        return existing

    message = ChatMessage(
        session_id=db_session.id,
        message_id=message_id,
        message_text=text,
        sender_type=role,
        role=role,
        is_code=False,
        tokens=tokens,
        model_used=model_used,
        processing_time=processing_time,
        context_cards=cards,
        actions=actions,
    )
    db.add(message)
    return message


def refresh_session_message_counts(db: Session, db_session: ChatSession) -> None:
    db_session.total_messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == db_session.id)
        .count()
    )
    db_session.total_tokens = sum(
        token_count or 0
        for (token_count,) in db.query(ChatMessage.tokens)
        .filter(ChatMessage.session_id == db_session.id)
        .all()
    )
    db_session.last_activity = utc_now()
