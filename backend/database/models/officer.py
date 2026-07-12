"""
SHERLOCK — Stage A: Officer (new AER entity).

Previously `FIR.investigating_officer` was a free-text string with no
accountability chain. This replaces that with a real entity so
INVESTIGATED_BY, WORKS_AT, and REPORTS_TO (Phase A5 graph edges) have
something to point at.

Field-level detail (rank vocabulary, posting fields) is an assumption —
see enums.py's note on OfficerRank. `unit`/`posting_station` are kept as
plain strings rather than FKs to a Unit/Station table, since Stage A's
own file list doesn't include those tables (see location.py's note).
"""

from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import OfficerRank


class Officer(Base):
    __tablename__ = "officers"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    badge_number = Column(String, nullable=False, unique=True)
    rank = Column(Enum(OfficerRank), nullable=False)
    posting_station = Column(String, nullable=True)
    contact_number = Column(String, nullable=True)

    firs_investigated = relationship("FIR", back_populates="investigating_officer")
    investigations = relationship("Investigation", back_populates="officer")
    arrests_made = relationship("Arrest", back_populates="arresting_officer")
    chargesheets_filed = relationship("ChargeSheet", back_populates="filing_officer")
    property_in_custody = relationship("Property", back_populates="custodian_officer")

    def __repr__(self):
        return f"<Officer {self.badge_number}: {self.name} ({self.rank})>"
