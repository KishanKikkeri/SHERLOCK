"""SHERLOCK — Stage A: Property. New AER entity — seized/recovered
evidence had no home at all in the legacy schema (flagged as a gap in
docs/DATABASE_ANALYSIS/06_SCHEMA_MIGRATION.md before this handover
existed). Sources the SEIZED_AT and RECOVERED_FROM graph edges (Phase A5).

Sprint B3 update: added a nullable `organization_id` — seized property
can belong to an organization (a seized company asset) rather than only
a person, needed by Organization Intelligence / Asset Link.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import PropertyStatus


class Property(Base):
    __tablename__ = "properties"

    id = Column(Integer, primary_key=True)
    fir_id = Column(Integer, ForeignKey("firs.id"), nullable=False, index=True)
    description = Column(String, nullable=False)
    category = Column(String, nullable=True)  # e.g. cash, jewellery, electronics, documents
    estimated_value = Column(Float, nullable=True)
    status = Column(Enum(PropertyStatus), nullable=False, default=PropertyStatus.SEIZED)
    seized_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)
    recovered_from_person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)
    custodian_officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True, index=True)
    seized_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    fir = relationship("FIR", back_populates="properties")
    seized_location = relationship("Location")
    recovered_from_person = relationship("Person")
    organization = relationship("Organization", back_populates="properties")
    custodian_officer = relationship("Officer", back_populates="property_in_custody")

    def __repr__(self):
        return f"<Property {self.description} ({self.status})>"
