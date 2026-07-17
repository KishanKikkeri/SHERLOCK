"""
SHERLOCK — Stage C1: InvestigationSession.

The "working desk" concept the Stage C brief calls for:

    Case -> Investigation Session -> Conversation Memory -> Investigation
    Timeline -> Working Board -> Reports -> Archive

This is new, additive schema — it does NOT replace or rename `FIR` (the
legal case record, Stage A) or `Investigation` (a single officer's
assignment span, Stage A). An InvestigationSession is the operational
wrapper an investigator actually opens, works from, and closes: it points
at a FIR, carries session-level metadata (priority, ownership, status)
that FIR/Investigation never had, and is the anchor conversation memory
and the working board will attach to in later Stage C sprints.

One FIR may have many sessions over time (e.g. reopened investigations
each get their own session row instead of mutating history away).
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import InvestigationSessionStatus, InvestigationPriority


class InvestigationSession(Base):
    __tablename__ = "investigation_sessions"

    id = Column(Integer, primary_key=True)
    session_code = Column(String, nullable=False, unique=True, index=True)  # e.g. "SESSION-2026-0001"

    fir_id = Column(Integer, ForeignKey("firs.id"), nullable=True, index=True)  # nullable: a session can be opened before a FIR number exists
    title = Column(String, nullable=False)

    status = Column(Enum(InvestigationSessionStatus), nullable=False, default=InvestigationSessionStatus.OPEN)
    priority = Column(Enum(InvestigationPriority), nullable=False, default=InvestigationPriority.MEDIUM)

    opened_by_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True, index=True)
    owner_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True, index=True)

    opened_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)
    reopened_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    notes = Column(Text, nullable=True)

    # Stage C2 (Sprint 2): rolling compressed summary of turns older than
    # `context_summary_through_turn`, so a long session's prompt context
    # doesn't grow unboundedly. The full per-turn rows in `conversation_turns`
    # are NEVER deleted or altered by this — this is purely a compressed
    # *view* used when building prompt context; database history stays complete.
    context_summary = Column(Text, nullable=True)
    context_summary_through_turn = Column(Integer, nullable=True)  # highest turn_index folded into context_summary

    fir = relationship("FIR")
    opened_by = relationship("Officer", foreign_keys=[opened_by_officer_id])
    owner = relationship("Officer", foreign_keys=[owner_officer_id])

    assignments = relationship("SessionAssignment", back_populates="session", cascade="all, delete-orphan")
    activity_log = relationship("SessionActivity", back_populates="session", cascade="all, delete-orphan", order_by="SessionActivity.created_at")
    conversation_turns = relationship("ConversationTurn", back_populates="session", cascade="all, delete-orphan", order_by="ConversationTurn.created_at")

    def __repr__(self):
        return f"<InvestigationSession {self.session_code} ({self.status})>"


class SessionAssignment(Base):
    """One investigator assigned to a session. Kept as its own table
    (rather than a single owner_officer_id) so C1's 'assign investigators'
    (plural) and Stage C6's collaboration/audit-trail work have something
    real to build on without a schema change later."""

    __tablename__ = "session_assignments"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("investigation_sessions.id"), nullable=False, index=True)
    officer_id = Column(Integer, ForeignKey("officers.id"), nullable=False, index=True)
    role = Column(String, nullable=False, default="investigator")  # investigator | lead | reviewer
    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    unassigned_at = Column(DateTime, nullable=True)

    session = relationship("InvestigationSession", back_populates="assignments")
    officer = relationship("Officer")

    def __repr__(self):
        return f"<SessionAssignment session={self.session_id} officer={self.officer_id} role={self.role}>"


class SessionActivity(Base):
    """Append-only lifecycle/audit log for a session (opened, closed,
    reopened, archived, assigned, note added, ...). This is the minimal,
    real slice of Stage C6's 'audit trail' requirement — it is scoped to
    session lifecycle events only, not full multi-investigator
    collaboration (comments/shared-board editing), which Stage C6 proper
    still needs to build."""

    __tablename__ = "session_activity"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("investigation_sessions.id"), nullable=False, index=True)
    event_type = Column(String, nullable=False)   # opened | closed | reopened | archived | assigned | unassigned | note_added | metadata_changed
    actor_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    session = relationship("InvestigationSession", back_populates="activity_log")
    actor = relationship("Officer")

    def __repr__(self):
        return f"<SessionActivity {self.event_type} session={self.session_id}>"
