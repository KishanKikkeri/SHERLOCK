"""
SHERLOCK — Stage A: Location.

Kept flat (name/district/state/lat/lng), unchanged from the legacy schema.
The earlier Sprint A/B alignment docs (docs/DATABASE_ANALYSIS/06_SCHEMA_MIGRATION.md)
proposed decomposing this into a State -> District -> PoliceStation -> Unit ->
Beat -> Court hierarchy — but the Stage A handover's own AER file list only
specifies a single `location.py`, with Court broken out separately
(court.py) and no State/District/Unit/Beat tables mentioned. Following the
handover's actual scope here rather than the earlier proposal: that fuller
hierarchy is treated as future-stage work, not Stage A.
"""

from sqlalchemy import Column, Integer, String, Float
from sqlalchemy.orm import relationship

from backend.database.config import Base


class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    district = Column(String, nullable=False, index=True)
    state = Column(String, nullable=False, default="Karnataka")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    crimes = relationship("Crime", back_populates="location")

    def __repr__(self):
        return f"<Location {self.name}, {self.district}>"
