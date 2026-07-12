"""
SHERLOCK — Stage A: Victim. Mirrors accused.py's design — see that file's
docstring for the full rationale (per-FIR record, raw_name_used carried
over, auto-synced to the legacy PersonCrimeLink compatibility table).
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, event
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import PersonRole


class Victim(Base):
    __tablename__ = "victims"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    fir_id = Column(Integer, ForeignKey("firs.id"), nullable=False, index=True)
    raw_name_used = Column(String, nullable=False)
    statement_date = Column(DateTime, nullable=True, default=datetime.utcnow)

    person = relationship("Person", back_populates="victim_records")
    fir = relationship("FIR", back_populates="victim_records")

    def __repr__(self):
        return f"<Victim person={self.person_id} fir={self.fir_id}>"


from backend.database.models import compat as _compat  # noqa: E402


@event.listens_for(Victim, "after_insert")
def _sync_victim_to_legacy_link(mapper, connection, target):
    _compat.sync_person_crime_link(connection, target, PersonRole.VICTIM, "victims")
