"""
SHERLOCK — Stage A: shared enumerations for the Karnataka Police AER schema.

Kept from the legacy schema unchanged: Gender, CrimeType, FIRStatus,
PersonRole, RelationType — none of these needed to change shape for
Stage A (Crime Head/Sub Head decomposition and RBAC-style role tables are
explicitly future-stage work per the handover, not Stage A).

New for Stage A: OfficerRank, CourtLevel, PropertyStatus, ArrestStatus,
ChargeSheetStatus, OrganizationType, WeaponType — one enum per new
AER entity that has a natural fixed vocabulary. Field-level detail for
these (which ranks, which statuses) was not supplied in the handover, so
these lists follow standard Karnataka Police / CCTNS convention and are
flagged here as an assumption to verify against the real AER document.
"""

import enum


# ---------------------------------------------------------------------------
# Carried over unchanged from the legacy schema
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
    """Used by the PersonCrimeLink compatibility table (see compat.py) —
    the AER itself expresses this as three separate tables (Accused,
    Victim, Witness), not a role column."""
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
# New for the Stage A AER schema — ASSUMPTION, verify against real AER doc
# ---------------------------------------------------------------------------

class OfficerRank(str, enum.Enum):
    CONSTABLE = "constable"
    HEAD_CONSTABLE = "head_constable"
    ASI = "asi"                    # Assistant Sub-Inspector
    SI = "si"                      # Sub-Inspector
    PI = "pi"                      # Police Inspector
    DYSP = "dysp"                  # Deputy Superintendent of Police
    SP = "sp"                      # Superintendent of Police
    DGP = "dgp"                    # Director General of Police


class CourtLevel(str, enum.Enum):
    MAGISTRATE = "magistrate"
    SESSIONS = "sessions"
    HIGH_COURT = "high_court"


class PropertyStatus(str, enum.Enum):
    SEIZED = "seized"
    IN_CUSTODY = "in_custody"
    RELEASED = "released"
    DISPOSED = "disposed"


class ArrestStatus(str, enum.Enum):
    ARRESTED = "arrested"
    RELEASED_ON_BAIL = "released_on_bail"
    JUDICIAL_CUSTODY = "judicial_custody"


class ChargeSheetStatus(str, enum.Enum):
    FILED = "filed"
    PENDING = "pending"
    WITHDRAWN = "withdrawn"


class OrganizationType(str, enum.Enum):
    GANG = "gang"
    COMPANY = "company"
    NGO = "ngo"
    OTHER = "other"


class WeaponType(str, enum.Enum):
    FIREARM = "firearm"
    BLADE = "blade"
    BLUNT = "blunt"
    EXPLOSIVE = "explosive"
    OTHER = "other"
