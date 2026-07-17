"""
SHERLOCK — Stage C6: Collaboration.

New, additive tables — nothing here renames or restructures
`investigation_sessions`, `session_assignments`, or `session_activity`
(Stage C1's already-real slice of "shared investigations" and "audit
trail" — see investigation_session.py's own docstrings on
SessionAssignment/SessionActivity for why this sprint builds on those
instead of duplicating them).

Five tables:
    BoardObject     — shared notes/links/hypotheses on a session's board
    Comment          — attached to a finding, evidence item, entity, or BoardObject
    Notification     — assignment / mention / review request / review decision / board update
    ReviewRequest    — Draft -> In Review -> Approved/Rejected workflow, one row per cycle
    SessionPresence  — "currently viewing/editing", heartbeat-based, no CRDT (per the brief)

Every write through these tables also writes a `SessionActivity` row
(see backend/collaboration/service.py) — that table is Stage C1's
already-existing audit trail, extended with new `event_type` values
rather than a second, parallel audit mechanism.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum, Boolean
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import (
    ReviewStatus, NotificationType, CommentTargetType, BoardObjectType, PresenceStatus,
)


class BoardObject(Base):
    """A shared item on a session's investigation board. Stage C5 shipped
    a read-only board-*intelligence* endpoint (suggestions computed live
    from findings/graph, never persisted); this is the first persisted,
    writable board object — what an investigator actually pins, and what
    every other investigator assigned to the session then sees too."""

    __tablename__ = "board_objects"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("investigation_sessions.id"), nullable=False, index=True)

    object_type = Column(Enum(BoardObjectType), nullable=False)
    content = Column(Text, nullable=False)          # the note text / hypothesis text / link label
    payload = Column(Text, nullable=True)            # JSON: e.g. {"from": "person_12", "to": "account_9", "relation": "..."} for a link

    created_by_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("InvestigationSession")
    created_by = relationship("Officer")

    def __repr__(self):
        return f"<BoardObject {self.object_type} session={self.session_id}>"


class Comment(Base):
    """Attached to one of: a finding, an evidence item within a finding,
    an entity, or a BoardObject.

    `target_ref` is a generic string key rather than a foreign key,
    because findings/evidence don't have their own stable DB rows (they
    live as JSON inside `ConversationTurn.findings_json` /
    `final_report`) — same reasoning conversation_memory.py already
    applies to entity references. Format, by `target_type`:
        entity        "person_123" (same kind_id convention as everywhere else)
        finding        "{turn_index}:{finding_index}" — position within that turn's findings list
        evidence       "{turn_index}:{finding_index}:evidence:{evidence_index}"
        board_object   str(BoardObject.id)
    """

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("investigation_sessions.id"), nullable=False, index=True)

    target_type = Column(Enum(CommentTargetType), nullable=False)
    target_ref = Column(String, nullable=False)

    author_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True)
    body = Column(Text, nullable=False)   # may contain @mentions, parsed at write time — see collaboration/service.py

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    edited_at = Column(DateTime, nullable=True)

    session = relationship("InvestigationSession")
    author = relationship("Officer")

    def __repr__(self):
        return f"<Comment {self.target_type}:{self.target_ref} session={self.session_id}>"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    recipient_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=False, index=True)
    notification_type = Column(Enum(NotificationType), nullable=False)

    session_id = Column(Integer, ForeignKey("investigation_sessions.id"), nullable=True, index=True)
    related_comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    related_review_id = Column(Integer, ForeignKey("review_requests.id"), nullable=True)

    message = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)

    recipient = relationship("Officer")
    session = relationship("InvestigationSession")
    comment = relationship("Comment")

    def __repr__(self):
        return f"<Notification {self.notification_type} -> officer={self.recipient_officer_id}>"


class ReviewRequest(Base):
    """One review cycle: Draft -> In Review -> Approved/Rejected. Kept as
    its own row per cycle (rather than one status column on
    InvestigationSession) so a rejected-then-resubmitted session has a
    real history of every review round, not just its current state —
    matching SessionAssignment/SessionActivity's own append-only
    philosophy elsewhere in Stage C1/C2."""

    __tablename__ = "review_requests"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("investigation_sessions.id"), nullable=False, index=True)

    status = Column(Enum(ReviewStatus), nullable=False, default=ReviewStatus.DRAFT)
    requested_by_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True)
    reviewer_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True)

    notes = Column(Text, nullable=True)              # from the requester, at submission
    decision_notes = Column(Text, nullable=True)      # from the reviewer, at approval/rejection

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)

    session = relationship("InvestigationSession")
    requested_by = relationship("Officer", foreign_keys=[requested_by_officer_id])
    reviewer = relationship("Officer", foreign_keys=[reviewer_officer_id])

    def __repr__(self):
        return f"<ReviewRequest session={self.session_id} status={self.status}>"


class SessionPresence(Base):
    """"Currently viewing" / "currently editing", heartbeat-based: a
    client calls PUT /sessions/{id}/presence every ~20s while the session
    is open in its UI; a row older than PRESENCE_TTL_SECONDS (see
    collaboration/service.py) is treated as "no longer present" rather
    than being actively expired/deleted. No CRDT, no WebSocket presence
    channel — the brief explicitly says simple presence is sufficient."""

    __tablename__ = "session_presence"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey("investigation_sessions.id"), nullable=False, index=True)
    officer_id = Column(Integer, ForeignKey("officers.id"), nullable=False, index=True)
    status = Column(Enum(PresenceStatus), nullable=False, default=PresenceStatus.VIEWING)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    session = relationship("InvestigationSession")
    officer = relationship("Officer")

    def __repr__(self):
        return f"<SessionPresence session={self.session_id} officer={self.officer_id} {self.status}>"
