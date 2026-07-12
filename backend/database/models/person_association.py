"""SHERLOCK — Stage A: PersonAssociation.

Judgment-call addition — not in the handover's Phase A1 file list, but
the Network Analysis Agent and both graph builders directly depend on it
(PERSON_ASSOCIATED_WITH edges) and it is genuinely AER-shaped already
(it's the source for the target `LINKED_WITH` edge in Phase A5's edge
list). Unchanged from the legacy schema.
"""

from sqlalchemy import Column, Integer, Float, ForeignKey, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import RelationType


class PersonAssociation(Base):
    __tablename__ = "person_associations"

    id = Column(Integer, primary_key=True)
    person_a_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    person_b_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)
    relation_type = Column(Enum(RelationType), nullable=False)
    strength = Column(Float, nullable=False, default=0.5)

    person_a = relationship("Person", foreign_keys=[person_a_id])
    person_b = relationship("Person", foreign_keys=[person_b_id])

    def __repr__(self):
        return f"<PersonAssociation {self.person_a_id}<->{self.person_b_id} ({self.relation_type})>"
