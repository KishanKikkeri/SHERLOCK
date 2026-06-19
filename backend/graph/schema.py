"""
SHERLOCK — Crime Intelligence Graph schema (FROZEN, Phase 2A).

This module is the single source of truth for node labels and relationship
types. Both the NetworkX (dev/demo) and Neo4j (production) backends use
these exact names, so a graph built with one backend is structurally
identical to a graph built with the other — the agents never need to know
which one they're talking to.

Node labels
-----------
Person, Crime, FIR, Location, Vehicle, Phone, BankAccount, Transaction

Relationship types
-------------------
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
"""

NODE_LABELS = [
    "Person",
    "Crime",
    "FIR",
    "Location",
    "Vehicle",
    "Phone",
    "BankAccount",
    "Transaction",
]

RELATIONSHIP_TYPES = [
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
