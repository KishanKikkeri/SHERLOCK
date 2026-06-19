"""
SHERLOCK — Core data models (Phase 1).

These are the "ground truth" entities that live in Postgres (or SQLite for
local dev). The Neo4j intelligence graph is built FROM this data — it is
not the source of truth, it's a derived view optimized for relationship
queries.

Two things are worth calling out for anyone extending this file:

1. PersonAlias / PersonCrimeLink exist specifically to support the
   Entity Resolution Agent. `PersonAlias` is the *ground truth* set of
   name variants for a canonical Person (used to score resolution
   accuracy in the demo). `PersonCrimeLink.raw_name_used` is the name as
   it would appear in a raw FIR/case record — i.e. what the agent
   actually has to work with before it knows which canonical Person it
   maps to.

2. Everything here is deliberately denormalized-friendly: every table has
   a simple integer PK and FKs are explicit, because the graph builder
   (Phase 4) will walk these tables to emit Neo4j nodes/relationships and
   wants predictable joins.
"""

import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    Boolean,
)
from sqlalchemy.orm import relationship

from backend.database.config import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class CrimeType(str, enum.Enum):
    THEFT = "theft"
    BURGLARY = "burglary"
    FRAUD = "fraud"
    CYBERCRIME = "cybercrime"
    ASSAULT = "assault"
    DRUG_TRAFFICKING = "drug_trafficking"


class FIRStatus(str, enum.Enum):
    OPEN = "open"
    UNDER_INVESTIGATION = "under_investigation"
    CHARGESHEET_FILED = "chargesheet_filed"
    CLOSED = "closed"
    CONVICTED = "convicted"


class PersonRole(str, enum.Enum):
    ACCUSED = "accused"
    VICTIM = "victim"
    WITNESS = "witness"


class RelationType(str, enum.Enum):
    FAMILY = "family"
    ASSOCIATE = "associate"
    CO_ACCUSED = "co_accused"
    NEIGHBOR = "neighbor"
    BUSINESS_PARTNER = "business_partner"


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)          # e.g. "Mysuru City"
    district = Column(String, nullable=False)      # e.g. "Mysuru"
    state = Column(String, nullable=False, default="Karnataka")
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    crimes = relationship("Crime", back_populates="location")

    def __repr__(self):
        return f"<Location {self.name}, {self.district}>"


# ---------------------------------------------------------------------------
# Person (canonical identity) + aliases
# ---------------------------------------------------------------------------

class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)           # canonical / preferred name
    gender = Column(Enum(Gender), nullable=False)
    age = Column(Integer, nullable=False)
    occupation = Column(String, nullable=True)
    home_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    home_location = relationship("Location")
    aliases = relationship("PersonAlias", back_populates="person", cascade="all, delete-orphan")
    crime_links = relationship("PersonCrimeLink", back_populates="person", cascade="all, delete-orphan")
    phones = relationship("Phone", back_populates="owner", cascade="all, delete-orphan")
    vehicles = relationship("Vehicle", back_populates="owner", cascade="all, delete-orphan")
    bank_accounts = relationship("BankAccount", back_populates="owner", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Person {self.id}: {self.name}>"


class PersonAlias(Base):
    """
    Ground-truth name variants for a canonical Person.

    e.g. Person(name="Ravi Kumar") might have aliases
    ["R Kumar", "R. Kumar", "Ravi K"].

    The Entity Resolution Agent never sees this table directly — it's used
    to (a) seed PersonCrimeLink.raw_name_used with realistic variants and
    (b) score the agent's resolution accuracy against ground truth.
    """
    __tablename__ = "person_aliases"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    alias_name = Column(String, nullable=False)

    person = relationship("Person", back_populates="aliases")

    def __repr__(self):
        return f"<PersonAlias {self.alias_name} -> person_id={self.person_id}>"


# ---------------------------------------------------------------------------
# Crime / FIR
# ---------------------------------------------------------------------------

class Crime(Base):
    __tablename__ = "crimes"

    id = Column(Integer, primary_key=True)
    type = Column(Enum(CrimeType), nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=False)
    modus_operandi = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    location = relationship("Location", back_populates="crimes")
    fir = relationship("FIR", back_populates="crime", uselist=False, cascade="all, delete-orphan")
    person_links = relationship("PersonCrimeLink", back_populates="crime", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Crime {self.id}: {self.type} @ {self.timestamp:%Y-%m-%d}>"


class FIR(Base):
    __tablename__ = "firs"

    id = Column(Integer, primary_key=True)
    crime_id = Column(Integer, ForeignKey("crimes.id"), nullable=False, unique=True)
    fir_number = Column(String, nullable=False, unique=True)
    status = Column(Enum(FIRStatus), nullable=False, default=FIRStatus.OPEN)
    investigating_officer = Column(String, nullable=False)
    filed_date = Column(DateTime, nullable=False, default=datetime.utcnow)

    crime = relationship("Crime", back_populates="fir")

    def __repr__(self):
        return f"<FIR {self.fir_number} ({self.status})>"


class PersonCrimeLink(Base):
    """
    Connects a Person to a Crime in a specific role (accused/victim/witness).

    `raw_name_used` is the name as it would literally appear on this FIR —
    this is the "messy real world" field the Entity Resolution Agent works
    on. It's deliberately allowed to be an alias/variant rather than the
    canonical Person.name.
    """
    __tablename__ = "person_crime_links"

    id = Column(Integer, primary_key=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    crime_id = Column(Integer, ForeignKey("crimes.id"), nullable=False)
    role = Column(Enum(PersonRole), nullable=False)
    raw_name_used = Column(String, nullable=False)

    person = relationship("Person", back_populates="crime_links")
    crime = relationship("Crime", back_populates="person_links")

    def __repr__(self):
        return f"<PersonCrimeLink person={self.person_id} crime={self.crime_id} role={self.role}>"


# ---------------------------------------------------------------------------
# Assets: vehicles, phones, bank accounts, transactions
# ---------------------------------------------------------------------------

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True)
    registration_number = Column(String, nullable=False, unique=True)
    owner_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    vehicle_type = Column(String, nullable=True)  # car, two-wheeler, etc.

    owner = relationship("Person", back_populates="vehicles")

    def __repr__(self):
        return f"<Vehicle {self.registration_number}>"


class Phone(Base):
    __tablename__ = "phones"

    id = Column(Integer, primary_key=True)
    number = Column(String, nullable=False, unique=True)
    owner_id = Column(Integer, ForeignKey("persons.id"), nullable=False)

    owner = relationship("Person", back_populates="phones")

    def __repr__(self):
        return f"<Phone {self.number}>"


class BankAccount(Base):
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True)
    bank = Column(String, nullable=False)
    account_number = Column(String, nullable=False, unique=True)
    owner_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    is_flagged_mule = Column(Boolean, nullable=False, default=False)

    owner = relationship("Person", back_populates="bank_accounts")
    sent_transactions = relationship(
        "Transaction", back_populates="sender_account",
        foreign_keys="Transaction.sender_account_id", cascade="all, delete-orphan",
    )
    received_transactions = relationship(
        "Transaction", back_populates="receiver_account",
        foreign_keys="Transaction.receiver_account_id", cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<BankAccount {self.account_number} @ {self.bank}>"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    sender_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False)
    receiver_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=False)
    is_suspicious = Column(Boolean, nullable=False, default=False)

    sender_account = relationship(
        "BankAccount", back_populates="sent_transactions", foreign_keys=[sender_account_id]
    )
    receiver_account = relationship(
        "BankAccount", back_populates="received_transactions", foreign_keys=[receiver_account_id]
    )

    def __repr__(self):
        return f"<Transaction {self.amount} {self.sender_account_id}->{self.receiver_account_id}>"


# ---------------------------------------------------------------------------
# Social network: person-to-person associations
# ---------------------------------------------------------------------------

class PersonAssociation(Base):
    """
    Undirected social/criminal network edge between two persons.
    Feeds the Network Analysis Agent's "association" relationships
    directly (PERSON_ASSOCIATED_WITH / PERSON_RELATED_TO_PERSON).
    """
    __tablename__ = "person_associations"

    id = Column(Integer, primary_key=True)
    person_a_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    person_b_id = Column(Integer, ForeignKey("persons.id"), nullable=False)
    relation_type = Column(Enum(RelationType), nullable=False)
    strength = Column(Float, nullable=False, default=1.0)  # 0-1, used for graph edge weight

    person_a = relationship("Person", foreign_keys=[person_a_id])
    person_b = relationship("Person", foreign_keys=[person_b_id])

    def __repr__(self):
        return f"<PersonAssociation {self.person_a_id}-{self.person_b_id} ({self.relation_type})>"
