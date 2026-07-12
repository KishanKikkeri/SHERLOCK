"""SHERLOCK — Stage A: Organization. New AER entity, per Phase A5's
target node list. Not consumed by any current agent — scaffolding only,
same status as Weapon."""

from sqlalchemy import Column, Integer, String, Enum

from backend.database.config import Base
from backend.database.models.enums import OrganizationType


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    org_type = Column(Enum(OrganizationType), nullable=False)
    registration_number = Column(String, nullable=True)
    address = Column(String, nullable=True)

    def __repr__(self):
        return f"<Organization {self.name} ({self.org_type})>"
