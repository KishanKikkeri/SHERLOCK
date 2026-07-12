"""SHERLOCK — Stage A: ChargeSheet. New AER entity, sources the
CHARGESHEETED_IN graph edge (Phase A5)."""

from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import ChargeSheetStatus


class ChargeSheet(Base):
    __tablename__ = "chargesheets"

    id = Column(Integer, primary_key=True)
    fir_id = Column(Integer, ForeignKey("firs.id"), nullable=False, index=True)
    court_id = Column(Integer, ForeignKey("courts.id"), nullable=True, index=True)
    filing_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True, index=True)
    filed_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(Enum(ChargeSheetStatus), nullable=False, default=ChargeSheetStatus.PENDING)

    fir = relationship("FIR", back_populates="chargesheets")
    court = relationship("Court", back_populates="chargesheets")
    filing_officer = relationship("Officer", back_populates="chargesheets_filed")

    def __repr__(self):
        return f"<ChargeSheet fir={self.fir_id} ({self.status})>"
