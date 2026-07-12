"""SHERLOCK — Stage A: Investigation. New AER entity — tracks the
investigation process itself (officer assignment, timeframe), distinct
from the Timeline Reconstruction Agent's crime-event timeline. Sources
the INVESTIGATED_BY graph edge (Phase A5), alongside FIR.investigating_officer_id."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from backend.database.config import Base


class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(Integer, primary_key=True)
    fir_id = Column(Integer, ForeignKey("firs.id"), nullable=False, index=True)
    officer_id = Column(Integer, ForeignKey("officers.id"), nullable=False, index=True)
    start_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_date = Column(DateTime, nullable=True)
    status = Column(String, nullable=False, default="ongoing")
    notes = Column(Text, nullable=True)

    fir = relationship("FIR", back_populates="investigations")
    officer = relationship("Officer", back_populates="investigations")

    def __repr__(self):
        return f"<Investigation fir={self.fir_id} officer={self.officer_id}>"
