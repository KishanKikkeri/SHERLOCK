"""
SHERLOCK — Stage C2: ConversationTurn.

Persisted memory for a multi-turn investigation conversation, scoped to
one InvestigationSession, so a session survives process restarts and
"tell me about Ravi" -> "expand his network" style follow-ups keep
working across the whole investigation, not just one WebSocket
connection's lifetime.

This table only stores the conversational record and the lightweight
entity-reference state needed to resolve pronouns/follow-ups
(`last_person_ref` etc.). It intentionally does NOT duplicate
`findings`/`final_report` — those already live in each turn's
`SherlockState` and are large; `raw_state_ref` is left as a hook for a
future sprint to persist full per-turn state (e.g. to blob storage) once
that's actually needed, per the Stage C6 "investigation replay" goal.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from backend.database.config import Base


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("investigation_sessions.id"), nullable=False, index=True)

    turn_index = Column(Integer, nullable=False)          # 0, 1, 2, ... within this session
    raw_query = Column(Text, nullable=False)               # what the user actually typed/said
    resolved_query = Column(Text, nullable=True)           # after pronoun/reference resolution, if different from raw_query

    # Lightweight "what was this turn about" pointers, used to resolve the
    # *next* turn's pronouns ("him", "that account", "the case"). Kept as
    # plain nullable columns rather than a generic key/value table because
    # there are exactly three reference kinds Stage C2's examples call for.
    last_person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)
    last_person_name = Column(String, nullable=True)
    last_fir_id = Column(Integer, ForeignKey("firs.id"), nullable=True)
    last_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=True)

    response_summary = Column(Text, nullable=True)         # short text summary of what the Chief reported back

    # Stage C5 (Investigation Board): the full `final_report["findings"]`
    # list for this turn, JSON-encoded. Added here rather than a new table
    # because board intelligence (suggested links, contradictions, gaps,
    # clusters) needs the actual finding contents, not just the three
    # entity-ref pointers above — and a turn's findings belong to that
    # turn, same lifecycle as everything else on this row.
    findings_json = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    session = relationship("InvestigationSession", back_populates="conversation_turns")

    def __repr__(self):
        return f"<ConversationTurn session={self.session_id} #{self.turn_index}>"
