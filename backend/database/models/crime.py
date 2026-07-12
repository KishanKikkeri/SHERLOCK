"""
SHERLOCK — Stage A: Crime.

Unchanged in shape from the legacy schema. `type` stays a flat CrimeType
enum rather than the Crime Head / Sub Head / Act / Section decomposition
proposed in the earlier alignment docs — that's explicitly future work
("Legal Intelligence Agent" is listed under "What Comes After" in the
Stage A handover, not Stage A itself).
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import CrimeType


class Crime(Base):
    __tablename__ = "crimes"

    id = Column(Integer, primary_key=True)
    type = Column(Enum(CrimeType), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False, index=True)
    modus_operandi = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    location = relationship("Location", back_populates="crimes")
    fir = relationship("FIR", back_populates="crime", uselist=False, cascade="all, delete-orphan")

    # Back-compat only — see compat.py. Not part of the AER.
    person_links = relationship("PersonCrimeLink", back_populates="crime", viewonly=True)

    def __repr__(self):
        return f"<Crime {self.id}: {self.type} @ {self.timestamp:%Y-%m-%d}>"
