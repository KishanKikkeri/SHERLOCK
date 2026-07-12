"""
SHERLOCK — Stage A: Accused.

New AER entity — replaces the legacy `PersonCrimeLink(role=accused)` rows
with a real, independently-attributed entity. A Person becomes "an
Accused" in the context of one specific FIR, not globally, so this is a
per-FIR record (person_id + fir_id), not a flag on Person.

`raw_name_used` is carried over from the legacy PersonCrimeLink — it's
still the field the Entity Resolution Agent's matching logic conceptually
needs (name as literally recorded on this FIR, which may differ from the
canonical Person.name). See compat.py for how this stays wired to the
agent unmodified.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, event
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import PersonRole


class Accused(Base):
    __tablename__ = "accused"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    fir_id = Column(Integer, ForeignKey("firs.id"), nullable=False, index=True)
    raw_name_used = Column(String, nullable=False)
    repeat_offender = Column(Boolean, nullable=False, default=False, index=True)
    custody_status = Column(String, nullable=True)

    person = relationship("Person", back_populates="accused_records")
    fir = relationship("FIR", back_populates="accused_records")

    def __repr__(self):
        return f"<Accused person={self.person_id} fir={self.fir_id}>"


# Phase A7 compatibility sync — see compat.py for the full explanation.
# Any Accused row created anywhere (loader, DatabaseService, ad-hoc script)
# automatically gets a mirrored PersonCrimeLink(role=accused) row so the
# Crime Records and Entity Resolution agents keep working unmodified.
from backend.database.models import compat as _compat  # noqa: E402


@event.listens_for(Accused, "after_insert")
def _sync_accused_to_legacy_link(mapper, connection, target):
    _compat.sync_person_crime_link(connection, target, PersonRole.ACCUSED, "accused")
