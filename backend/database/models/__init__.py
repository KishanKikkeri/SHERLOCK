"""
SHERLOCK — Stage A: Database models package (Karnataka Police AER schema).

This __init__.py is Phase A7's compatibility layer. Every symbol that any
existing agent, graph builder, or dataset script imports from
`backend.database.models` is re-exported here, unchanged in name:

    Person, Location, Crime, FIR, Vehicle, Phone, BankAccount, Transaction,
    PersonCrimeLink, PersonRole, PersonAssociation, PersonAlias,
    Gender, CrimeType, FIRStatus, RelationType

(That list was extracted directly from every `from backend.database.models
import ...` statement in the codebase — see docs/AGENT_MAPPING.md and the
grep evidence referenced there.)

`PersonCrimeLink` is the one symbol whose *backing storage* changed
completely (see compat.py) — the AER models the same information as three
separate tables (Accused, Victim, Witness). Every other symbol above maps
directly onto a same-shaped AER table.

New AER entities not imported by any existing code, but present per the
Stage A handover's file list, are exported here too so DatabaseService,
loaders, and future agents can use them:

    Accused, Victim, Witness, Officer, Court, Property, Weapon,
    Organization, Arrest, ChargeSheet, Investigation, CallRecord
    OfficerRank, CourtLevel, PropertyStatus, ArrestStatus,
    ChargeSheetStatus, OrganizationType, WeaponType

Import order matters here only in that every mapped class must be
imported somewhere before SQLAlchemy resolves string-based relationship()
references (which happens lazily on first use, or explicitly via
`configure_mappers()` at the bottom of this file) — it does not need to
match FK dependency order, since relationships are declared as strings.
"""

from backend.database.config import Base  # noqa: F401

# Enums
from backend.database.models.enums import (  # noqa: F401
    Gender, CrimeType, FIRStatus, PersonRole, RelationType,
    OfficerRank, CourtLevel, PropertyStatus, ArrestStatus,
    ChargeSheetStatus, OrganizationType, WeaponType,
    InvestigationSessionStatus, InvestigationPriority,
)

# Core identity + compatibility tables (compat.py must load before
# accused/victim/witness, which import it for the sync listeners)
from backend.database.models.person import Person  # noqa: F401
from backend.database.models.location import Location  # noqa: F401
from backend.database.models.compat import PersonAlias, PersonCrimeLink  # noqa: F401

# Case core
from backend.database.models.crime import Crime  # noqa: F401
from backend.database.models.fir import FIR  # noqa: F401
from backend.database.models.officer import Officer  # noqa: F401

# Per-FIR role entities (AER replacement for the legacy role-tagged link table)
from backend.database.models.accused import Accused  # noqa: F401
from backend.database.models.victim import Victim  # noqa: F401
from backend.database.models.witness import Witness  # noqa: F401

# Process entities
from backend.database.models.investigation import Investigation  # noqa: F401
from backend.database.models.arrest import Arrest  # noqa: F401
from backend.database.models.chargesheet import ChargeSheet  # noqa: F401
from backend.database.models.court import Court  # noqa: F401
from backend.database.models.property import Property  # noqa: F401
from backend.database.models.weapon import Weapon  # noqa: F401

# Assets
from backend.database.models.vehicle import Vehicle  # noqa: F401
from backend.database.models.phone import Phone, CallRecord  # noqa: F401
from backend.database.models.bank_account import BankAccount, Transaction  # noqa: F401
from backend.database.models.organization import Organization  # noqa: F401
from backend.database.models.organization_membership import OrganizationMembership  # noqa: F401

# Relationships table (network graph, not case-role)
from backend.database.models.person_association import PersonAssociation  # noqa: F401

# Stage C1 — Investigation Lifecycle / Stage C2 — Conversation Memory (new, additive)
from backend.database.models.investigation_session import (  # noqa: F401
    InvestigationSession, SessionAssignment, SessionActivity,
)
from backend.database.models.conversation import ConversationTurn  # noqa: F401

from sqlalchemy.orm import configure_mappers

configure_mappers()

__all__ = [
    "Base",
    # Enums
    "Gender", "CrimeType", "FIRStatus", "PersonRole", "RelationType",
    "OfficerRank", "CourtLevel", "PropertyStatus", "ArrestStatus",
    "ChargeSheetStatus", "OrganizationType", "WeaponType",
    "InvestigationSessionStatus", "InvestigationPriority",
    # Legacy-compatible symbols (imported by existing agents/graph builders/datasets)
    "Person", "Location", "Crime", "FIR", "Vehicle", "Phone", "BankAccount",
    "Transaction", "PersonCrimeLink", "PersonAssociation", "PersonAlias",
    # New AER entities
    "Officer", "Accused", "Victim", "Witness", "Investigation", "Arrest",
    "ChargeSheet", "Court", "Property", "Weapon", "Organization", "CallRecord",
    "OrganizationMembership",
    # Stage C1/C2 — new, additive
    "InvestigationSession", "SessionAssignment", "SessionActivity", "ConversationTurn",
]
