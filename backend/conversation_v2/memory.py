
"""
SHERLOCK — Conversation V2: Conversation memory manager.

Handles loading recent messages for the LLM context window and generating
rolling summaries for long conversations. This module only deals with
conversation state (messages, summaries) — never investigation state.

Core principle:
    Conversation memory = messages + summaries + language.
    Nothing else. No entity refs, no findings, no investigation state.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from backend.database.models.conversation_v2 import ConversationV2, MessageV2

logger = logging.getLogger(__name__)

# Maximum number of recent messages to include in the LLM context window
MAX_CONTEXT_MESSAGES = 40


def load_conversation_messages(
    db: Session,
    conversation_id: int,
    limit: int = MAX_CONTEXT_MESSAGES,
) -> list[dict]:
    """Load recent messages formatted for LLM consumption.

    Returns a list of dicts with 'role', 'content', and optionally
    'tool_calls' / 'tool_call_id' / 'name' — matching the OpenAI
    message format that all adapters consume.
    """
    msgs = (
        db.query(MessageV2)
        .filter(MessageV2.conversation_id == conversation_id)
        .order_by(MessageV2.created_at.asc())
        .all()
    )

    # If there are more messages than the limit, include the summary
    # (if available) as a system message at the start, then the tail.
    conversation = db.get(ConversationV2, conversation_id)
    formatted: list[dict] = []

    if conversation and conversation.context_summary and len(msgs) > limit:
        formatted.append({
            "role": "system",
            "content": (
                f"[Conversation summary of earlier messages]\n"
                f"{conversation.context_summary}"
            ),
        })
        msgs = msgs[-limit:]

    for m in msgs:
        entry: dict[str, Any] = {"role": m.role, "content": m.content or ""}

        if m.role == "assistant" and m.tool_calls_json:
            try:
                entry["tool_calls"] = json.loads(m.tool_calls_json)
            except (json.JSONDecodeError, TypeError):
                pass

        if m.role == "tool":
            entry["name"] = m.tool_name or ""
            entry["tool_call_id"] = m.tool_call_id or ""
            entry["content"] = m.tool_result_json or m.content or ""

        formatted.append(entry)

    return formatted


def store_message(
    db: Session,
    conversation_id: int,
    role: str,
    content: str | None = None,
    tool_calls_json: str | None = None,
    tool_name: str | None = None,
    tool_result_json: str | None = None,
    tool_call_id: str | None = None,
    metadata_json: str | None = None,
) -> MessageV2:
    """Persist a single message to the database."""
    msg = MessageV2(
        conversation_id=conversation_id,
        role=role,
        content=content,
        tool_calls_json=tool_calls_json,
        tool_name=tool_name,
        tool_result_json=tool_result_json,
        tool_call_id=tool_call_id,
        metadata_json=metadata_json,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_or_create_conversation(
    db: Session,
    conversation_id: int | None,
    investigation_id: int | None = None,
    language: str = "en",
    nickname: str | None = None,
) -> ConversationV2:
    """Return the conversation for the given ID, or create a new one.

    If `conversation_id` is None or doesn't resolve to a real row,
    creates a fresh conversation (optionally linked to an investigation).
    """
    if conversation_id is not None:
        existing = db.get(ConversationV2, conversation_id)
        if existing is not None and not existing.is_deleted:
            return existing
        logger.info(
            "Conversation %s not found — creating new one.", conversation_id
        )

    conv = ConversationV2(
        investigation_id=investigation_id,
        nickname=nickname or "New Conversation",
        language=language,
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    logger.info("Created conversation %d (investigation=%s)", conv.id, investigation_id)
    return conv
