"""SHERLOCK — Stage A: Phone, plus CallRecord.

Phone is unchanged from the legacy schema. CallRecord is a judgment-call
addition, not in the handover's Phase A1 file list — it exists solely
because Phase A5 explicitly names `CALLS` as a target graph edge, and
there is no way to produce that edge without a CDR-shaped table. Kept
minimal (no telecom-provider metadata) since no agent consumes it yet;
this is scaffolding for the future CDR Agent proposed in
docs/AGENT_MAPPING.md, Part 2.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from backend.database.config import Base


class Phone(Base):
    __tablename__ = "phones"

    id = Column(Integer, primary_key=True)
    number = Column(String, nullable=False, unique=True)
    owner_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)

    owner = relationship("Person", back_populates="phones")

    def __repr__(self):
        return f"<Phone {self.number}>"


class CallRecord(Base):
    __tablename__ = "call_records"

    id = Column(Integer, primary_key=True)
    caller_phone_id = Column(Integer, ForeignKey("phones.id"), nullable=False, index=True)
    receiver_phone_id = Column(Integer, ForeignKey("phones.id"), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    duration_seconds = Column(Integer, nullable=False, default=0)

    caller_phone = relationship("Phone", foreign_keys=[caller_phone_id])
    receiver_phone = relationship("Phone", foreign_keys=[receiver_phone_id])

    def __repr__(self):
        return f"<CallRecord {self.caller_phone_id} -> {self.receiver_phone_id}>"
