"""SHERLOCK — Sprint B3: OrganizationMembership.

The one genuinely new table this sprint adds to the schema (everything
else in B2/B3 reads existing Stage A tables). Connects `Person` to
`Organization` — without this, Organization Intelligence (Stage B
Division 7) would have nothing to query and the agent would be
permanently empty. Kept minimal: role + join date, no exit date/status,
since nothing in the current agent set needs former-membership history.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from backend.database.config import Base


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False, index=True)
    role = Column(String, nullable=True)  # e.g. "leader", "member", "financier"
    joined_date = Column(DateTime, nullable=True, default=datetime.utcnow)

    person = relationship("Person")
    organization = relationship("Organization", back_populates="memberships")

    def __repr__(self):
        return f"<OrganizationMembership person={self.person_id} org={self.organization_id} role={self.role}>"
