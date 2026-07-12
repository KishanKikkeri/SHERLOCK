"""
SHERLOCK — Crime Intelligence Graph schema.

Phase 2A froze the original 8-node graph below. Stage A (AER migration,
Phase A5) extends it additively — every original label and relationship
type is kept exactly as-is, since Network Analysis Agent and both graph
builders still read them directly (see backend/graph/builder_networkx.py).
Nothing was removed or renamed; only new labels/types were appended.

Both the NetworkX (dev/demo) and Neo4j (production) backends use these
exact names, so a graph built with one backend is structurally identical
to a graph built with the other — the agents never need to know which one
they're talking to.

Original node labels (Phase 2A, unchanged)
-------------------------------------------
Person, Crime, FIR, Location, Vehicle, Phone, BankAccount, Transaction

New node labels (Stage A / Phase A5)
-------------------------------------
Accused, Victim, Witness, Officer, Court, Property, Weapon, Organization

Original relationship types (Phase 2A, unchanged)
----------------------------------------------------
PERSON_COMMITTED_CRIME     (Person)-->(Crime)              [role-based, accused only]
PERSON_INVOLVED_IN_FIR      (Person)-->(FIR)                [victim / witness]
PERSON_ASSOCIATED_WITH      (Person)-->(Person)             [from PersonAssociation table]
PERSON_LINKED_TO_PERSON     (Person)-->(Person)             [co-occurrence on same crime,
                                                              any role combination]
PERSON_OWNS_PHONE           (Person)-->(Phone)
PERSON_OWNS_ACCOUNT         (Person)-->(BankAccount)
PERSON_OWNS_VEHICLE         (Person)-->(Vehicle)
CRIME_OCCURRED_AT           (Crime)-->(Location)
CRIME_LINKED_TO_FIR         (Crime)-->(FIR)
ACCOUNT_SENT_TRANSACTION     (BankAccount)-->(Transaction)
TRANSACTION_TO_ACCOUNT       (Transaction)-->(BankAccount)

New relationship types (Stage A / Phase A5)
-----------------------------------------------
ACCUSED_IN                  (Accused)-->(FIR)               [from Accused table]
VICTIM_IN                   (Victim)-->(FIR)                [from Victim table]
WITNESS_OF                  (Witness)-->(FIR)                [from Witness table]
INVESTIGATED_BY              (FIR)-->(Officer)               [FIR.investigating_officer_id]
ARRESTED_IN                  (Person)-->(FIR)                [from Arrest table]
CHARGESHEETED_IN             (FIR)-->(Court)                 [from ChargeSheet table]
SEIZED_AT                    (Property)-->(Location)          [Property.seized_location_id]
RECOVERED_FROM                (Property/Weapon)-->(Person)     [*.recovered_from_person_id]
CALLS                        (Phone)-->(Phone)                [from CallRecord table]
USES                          (Weapon)-->(FIR)                 [Weapon.used_in_fir_id]

Note: the handover's Phase A5 also names OWNS, USES, TRANSFERRED_TO, and
LINKED_WITH as target edges. Those are intentionally *not* added as new
types here — they'd duplicate the existing PERSON_OWNS_*, CRIME_OCCURRED_AT,
ACCOUNT_SENT_TRANSACTION/TRANSACTION_TO_ACCOUNT, and PERSON_ASSOCIATED_WITH
types above under different names. Renaming the originals would break
Network Analysis Agent's direct references to them (a Golden Rule
violation), so the existing names were kept as the canonical ones instead.
"""

NODE_LABELS = [
    # Phase 2A — unchanged
    "Person",
    "Crime",
    "FIR",
    "Location",
    "Vehicle",
    "Phone",
    "BankAccount",
    "Transaction",
    # Stage A / Phase A5 — new
    "Accused",
    "Victim",
    "Witness",
    "Officer",
    "Court",
    "Property",
    "Weapon",
    "Organization",
]

RELATIONSHIP_TYPES = [
    # Phase 2A — unchanged
    "PERSON_COMMITTED_CRIME",
    "PERSON_INVOLVED_IN_FIR",
    "PERSON_ASSOCIATED_WITH",
    "PERSON_LINKED_TO_PERSON",
    "PERSON_OWNS_PHONE",
    "PERSON_OWNS_ACCOUNT",
    "PERSON_OWNS_VEHICLE",
    "CRIME_OCCURRED_AT",
    "CRIME_LINKED_TO_FIR",
    "ACCOUNT_SENT_TRANSACTION",
    "TRANSACTION_TO_ACCOUNT",
    # Stage A / Phase A5 — new
    "ACCUSED_IN",
    "VICTIM_IN",
    "WITNESS_OF",
    "INVESTIGATED_BY",
    "ARRESTED_IN",
    "CHARGESHEETED_IN",
    "SEIZED_AT",
    "RECOVERED_FROM",
    "CALLS",
    "USES",
]

# Cypher uniqueness constraints — run once against Neo4j before loading data.
# Keeping `id` unique per label lets the builder MERGE on (label, id) and be
# safely re-run without creating duplicates.
CONSTRAINT_STATEMENTS = [
    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE"
    for label in NODE_LABELS
]


def node_key(label, entity_id):
    """Canonical string key used as the NetworkX node identifier.
    Neo4j addresses nodes by (label, id) directly and doesn't need this,
    but exposing it here keeps the two backends' addressing scheme
    conceptually aligned."""
    return f"{label}:{entity_id}"
