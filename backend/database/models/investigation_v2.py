"""
SHERLOCK — Conversation V2: InvestigationV2.

An Investigation is a user-curated workspace — a collection of explicitly
selected entities (FIRs, persons, accounts, locations, organizations) and
their graph/analytics state. It is NOT a conversation, NOT a session, and
NEVER automatically created by sending a message.

Core principle:
    Investigation ≠ Conversation.
    Conversations belong to an Investigation, but an Investigation's
    identity is its selected entities, not its chat history.

Entity selections are stored as JSON arrays of IDs rather than junction
tables. This makes the selection model simple and the schema lightweight.
The user (not the system) controls what belongs in an investigation.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum, Boolean
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import InvestigationV2Status


class InvestigationV2(Base):
    __tablename__ = "investigations_v2"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    status = Column(
        Enum(InvestigationV2Status),
        nullable=False,
        default=InvestigationV2Status.ACTIVE,
    )

    created_by_officer_id = Column(
        Integer, ForeignKey("officers.id"), nullable=True, index=True
    )

    # --- Explicit entity selections (user-controlled, never auto-added) ---
    # Each is a JSON-encoded list of integer IDs, e.g. [1, 5, 23].
    # Null means "no selection" (not "all").
    selected_fir_ids_json = Column(Text, nullable=True)
    selected_person_ids_json = Column(Text, nullable=True)
    selected_account_ids_json = Column(Text, nullable=True)
    selected_location_ids_json = Column(Text, nullable=True)
    selected_org_ids_json = Column(Text, nullable=True)

    # Serialized graph/analytics state snapshot (optional)
    graph_state_json = Column(Text, nullable=True)

    # Extensible metadata (language preferences, tags, etc.)
    metadata_json = Column(Text, nullable=True)

    # --- Timestamps ---
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    archived_at = Column(DateTime, nullable=True)

    # --- Relationships ---
    created_by = relationship("Officer", foreign_keys=[created_by_officer_id])
    conversations = relationship(
        "ConversationV2",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="ConversationV2.created_at",
    )

    def __repr__(self):
        return f"<InvestigationV2 {self.id}: {self.title} ({self.status})>"
