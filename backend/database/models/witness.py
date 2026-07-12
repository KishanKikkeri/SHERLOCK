"""
SHERLOCK — Stage A: Witness. Mirrors accused.py's design — see that file's
docstring for the full rationale.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, event
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import PersonRole


class Witness(Base):
    __tablename__ = "witnesses"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    fir_id = Column(Integer, ForeignKey("firs.id"), nullable=False, index=True)
    raw_name_used = Column(String, nullable=False)
    statement_date = Column(DateTime, nullable=True, default=datetime.utcnow)
    protection_flag = Column(Boolean, nullable=False, default=False)

    person = relationship("Person", back_populates="witness_records")
    fir = relationship("FIR", back_populates="witness_records")

    def __repr__(self):
        return f"<Witness person={self.person_id} fir={self.fir_id}>"


from backend.database.models import compat as _compat  # noqa: E402


@event.listens_for(Witness, "after_insert")
def _sync_witness_to_legacy_link(mapper, connection, target):
    _compat.sync_person_crime_link(connection, target, PersonRole.WITNESS, "witnesses")
