"""SHERLOCK — Stage A: Court. New AER entity, sources the TRIED_IN /
CHARGESHEETED_IN graph edges (Phase A5)."""

from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import CourtLevel


class Court(Base):
    __tablename__ = "courts"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    level = Column(Enum(CourtLevel), nullable=False)
    district = Column(String, nullable=False)

    chargesheets = relationship("ChargeSheet", back_populates="court")

    def __repr__(self):
        return f"<Court {self.name} ({self.level})>"
