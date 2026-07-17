"""
SHERLOCK — Stage C4: DiscussionRecord.

New, additive table — does not touch `conversation_turns`,
`investigation_sessions`, or any Stage A/B table. One row per investigation
turn that ran with Discussion Mode enabled, storing what the Discussion
Engine (backend/discussion/engine.py) computed from that turn's already-
validated findings: each agent's opinion, any disagreements found between
agents, and the resulting consensus.

`session_id` is nullable: Discussion Mode works standalone (no C2 session
required, same as the base investigation pipeline), but when a session_id
*is* given, this row is what Stage C6 "investigation replay" and a future
conversation-timeline entry would read from — the hook is here now so a
later sprint doesn't need another schema change to wire it in.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from backend.database.config import Base


class DiscussionRecord(Base):
    __tablename__ = "discussion_records"

    id = Column(Integer, primary_key=True)

    # Nullable — Discussion Mode doesn't require a Stage C2 session.
    session_id = Column(Integer, ForeignKey("investigation_sessions.id"), nullable=True, index=True)
    turn_index = Column(Integer, nullable=True)  # matches ConversationTurn.turn_index when session_id is set

    query = Column(Text, nullable=False)

    opinions_json = Column(Text, nullable=False)        # list[AgentOpinion] — see discussion/engine.py
    disagreements_json = Column(Text, nullable=False)    # list[Disagreement]
    consensus_json = Column(Text, nullable=False)         # ConsensusResult

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    session = relationship("InvestigationSession")
