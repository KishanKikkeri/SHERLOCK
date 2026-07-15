"""SHERLOCK — Stage A: Organization. New AER entity, per Phase A5's
target node list.

Sprint B3 update: was pure scaffolding through Stage A/B1/B2 — zero
consumers, zero relationships. Organization Intelligence (Stage B
Division 7) needs it to actually connect to something, so this sprint
adds the minimum additive link: `OrganizationMembership` (person <->
organization, see organization_membership.py) plus optional
`organization_id` FKs on `BankAccount` and `Property` (an account or
seized asset can belong to an org instead of, or in addition to, a
person). Nothing existing changes shape — these are new, nullable
columns/tables, so every Stage A/B1/B2 query is unaffected.
"""

from sqlalchemy import Column, Integer, String, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import OrganizationType


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    org_type = Column(Enum(OrganizationType), nullable=False)
    registration_number = Column(String, nullable=True)
    address = Column(String, nullable=True)

    memberships = relationship("OrganizationMembership", back_populates="organization")
    bank_accounts = relationship("BankAccount", back_populates="organization")
    properties = relationship("Property", back_populates="organization")

    def __repr__(self):
        return f"<Organization {self.name} ({self.org_type})>"
