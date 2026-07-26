"""
SHERLOCK — Conversation V2: ConversationV2 + MessageV2.

A Conversation is a chat thread — a sequence of messages between the user
and the LLM assistant. It optionally belongs to an Investigation, but its
identity is its message history, not any investigation state.

Core principle:
    Conversation ≠ Investigation.
    A conversation stores messages, tool calls, context memory, nickname,
    timestamps, and language. Nothing else.

Messages are stored as individual rows (one per user utterance, one per
assistant reply, one per tool call/result). This replaces the overloaded
`ConversationTurn` which tried to store user input, assistant response,
findings, entity references, and clarification state all in one row.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from backend.database.config import Base


class ConversationV2(Base):
    """A single chat thread. Optionally scoped to an investigation."""

    __tablename__ = "conversations_v2"

    id = Column(Integer, primary_key=True)

    # Nullable: standalone conversations exist without an investigation
    investigation_id = Column(
        Integer,
        ForeignKey("investigations_v2.id"),
        nullable=True,
        index=True,
    )

    nickname = Column(String, nullable=False, default="New Conversation")
    language = Column(String, nullable=False, default="en")  # en | kn | hi

    # User-facing state
    pinned = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)  # soft-delete
    archived_at = Column(DateTime, nullable=True)                # user-facing archive

    # Rolling conversation summary for long conversations
    # (used to compress history before feeding to LLM context window)
    context_summary = Column(Text, nullable=True)
    context_summary_through_msg = Column(Integer, nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    investigation = relationship("InvestigationV2", back_populates="conversations")
    messages = relationship(
        "MessageV2",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="MessageV2.created_at",
    )

    def __repr__(self):
        return (
            f"<ConversationV2 {self.id}: '{self.nickname}'"
            f" inv={self.investigation_id}>"
        )


class MessageV2(Base):
    """A single message in a conversation.

    Three roles:
      - 'user':      what the human typed/spoke
      - 'assistant': the LLM's response text
      - 'tool':      a tool invocation result (structured data)

    Tool-calling flow is stored as:
      1. User message (role='user')
      2. Assistant message with tool_calls_json populated (role='assistant')
         — this is the LLM's *decision* to call tools, with its text reply
         (if any) in content.
      3. One or more tool-result messages (role='tool') — one per tool that
         was invoked, with tool_name and tool_result_json.
      4. Final assistant message (role='assistant') — the LLM's response
         after seeing tool results.

    This makes the full reasoning chain auditable without overloading a
    single row with findings, entity refs, and clarification state.
    """

    __tablename__ = "messages_v2"

    id = Column(Integer, primary_key=True)
    conversation_id = Column(
        Integer,
        ForeignKey("conversations_v2.id"),
        nullable=False,
        index=True,
    )

    role = Column(String, nullable=False)  # 'user' | 'assistant' | 'tool'
    content = Column(Text, nullable=True)  # text content (user input or LLM response)

    # --- Tool-calling fields ---
    # For role='assistant': JSON array of tool calls the LLM decided to make
    # e.g. [{"name": "search_person", "arguments": {"name": "Ravi"}, "call_id": "tc_1"}]
    tool_calls_json = Column(Text, nullable=True)

    # For role='tool': which tool produced this result
    tool_name = Column(String, nullable=True)
    # For role='tool': the structured result from the tool
    tool_result_json = Column(Text, nullable=True)
    # For role='tool': matches tool_calls_json[].call_id so the LLM can
    # correlate which call this result answers
    tool_call_id = Column(String, nullable=True)

    # --- Metadata ---
    # Extensible JSON: citations, suggested_questions, intent classification,
    # confidence, evidence refs, whatever future features need without schema changes.
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    conversation = relationship("ConversationV2", back_populates="messages")

    def __repr__(self):
        preview = (self.content or "")[:40]
        return f"<MessageV2 {self.id} [{self.role}]: '{preview}...'>"
