"""SHERLOCK — Stage A: Arrest. New AER entity, sources the ARRESTED_IN
graph edge (Phase A5)."""

from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import ArrestStatus


class Arrest(Base):
    __tablename__ = "arrests"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    fir_id = Column(Integer, ForeignKey("firs.id"), nullable=False, index=True)
    arresting_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True, index=True)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    arrest_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(Enum(ArrestStatus), nullable=False, default=ArrestStatus.ARRESTED)

    person = relationship("Person")
    fir = relationship("FIR", back_populates="arrests")
    arresting_officer = relationship("Officer", back_populates="arrests_made")
    location = relationship("Location")

    def __repr__(self):
        return f"<Arrest person={self.person_id} fir={self.fir_id} ({self.status})>"
