"""
SHERLOCK — Stage A: Person (AER base identity entity).

Unchanged in shape from the legacy schema. Person remains the canonical
identity — Accused, Victim, and Witness (accused.py, victim.py, witness.py)
are now separate per-FIR role records that reference a Person, rather than
role being a column on a generic link table. This is the one structural
change Phase A2 requires here, and it's what accused.py/victim.py/witness.py
implement.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Enum
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import Gender


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    gender = Column(Enum(Gender), nullable=False)
    age = Column(Integer, nullable=False)
    occupation = Column(String, nullable=True)
    home_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True, index=True)

    home_location = relationship("Location")
    aliases = relationship("PersonAlias", back_populates="person", cascade="all, delete-orphan")
    phones = relationship("Phone", back_populates="owner", cascade="all, delete-orphan")
    vehicles = relationship("Vehicle", back_populates="owner", cascade="all, delete-orphan")
    bank_accounts = relationship("BankAccount", back_populates="owner", cascade="all, delete-orphan")

    accused_records = relationship("Accused", back_populates="person", cascade="all, delete-orphan")
    victim_records = relationship("Victim", back_populates="person", cascade="all, delete-orphan")
    witness_records = relationship("Witness", back_populates="person", cascade="all, delete-orphan")

    # Back-compat only — see compat.py. Not part of the AER.
    crime_links = relationship("PersonCrimeLink", back_populates="person", viewonly=True)

    def __repr__(self):
        return f"<Person {self.id}: {self.name}>"
