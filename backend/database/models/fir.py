"""
SHERLOCK — Stage A: FIR.

Structural change from the legacy schema: `investigating_officer` (a plain
string) is replaced with `investigating_officer_id` (a real FK to
Officer). Everything else is unchanged. FIR remains the hub entity per the
handover's own relationship diagram:

    FIR -> Crime, Investigation, Arrest, ChargeSheet

and additionally -> Accused, Victim, Witness (via those tables' fir_id FK,
since Person -> Accused/Victim/Witness happens *in the context of* a
specific FIR, not in the abstract).
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import FIRStatus


class FIR(Base):
    __tablename__ = "firs"

    id = Column(Integer, primary_key=True)
    crime_id = Column(Integer, ForeignKey("crimes.id"), nullable=False, unique=True)
    fir_number = Column(String, nullable=False, unique=True)
    status = Column(Enum(FIRStatus), nullable=False, default=FIRStatus.OPEN)
    investigating_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True, index=True)
    filed_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    crime = relationship("Crime", back_populates="fir")
    investigating_officer = relationship("Officer", back_populates="firs_investigated")

    accused_records = relationship("Accused", back_populates="fir", cascade="all, delete-orphan")
    victim_records = relationship("Victim", back_populates="fir", cascade="all, delete-orphan")
    witness_records = relationship("Witness", back_populates="fir", cascade="all, delete-orphan")
    investigations = relationship("Investigation", back_populates="fir", cascade="all, delete-orphan")
    arrests = relationship("Arrest", back_populates="fir", cascade="all, delete-orphan")
    chargesheets = relationship("ChargeSheet", back_populates="fir", cascade="all, delete-orphan")
    properties = relationship("Property", back_populates="fir", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<FIR {self.fir_number} ({self.status})>"
