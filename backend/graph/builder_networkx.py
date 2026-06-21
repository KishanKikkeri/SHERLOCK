"""
SHERLOCK — NetworkX graph builder (dev/demo backend, Phase 2B).

Reads the SQL dataset (via a SQLAlchemy session) and constructs an in-memory
`networkx.MultiDiGraph` following the frozen schema in `backend/graph/schema.py`.

This is the zero-dependency path: no Docker, no Neo4j, runs anywhere. It's
also a useful reference implementation for `builder_neo4j.py`, since both
walk the same SQL tables and emit the same node/relationship shapes.
"""

import networkx as nx

from backend.database.models import (
    Person, Location, Crime, FIR, Vehicle, Phone, BankAccount, Transaction,
    PersonCrimeLink, PersonRole, PersonAssociation,
)
from backend.graph.schema import node_key, NODE_LABELS, RELATIONSHIP_TYPES


def add_rel(G, u, v, rel_type, **attrs):
    """Add an edge, storing the relationship type both as the multi-edge
    key (avoids duplicate parallel edges with the same type between the
    same pair of nodes) and as a 'type' attribute (so it's readable via
    G.edges(data=True))."""
    G.add_edge(u, v, key=rel_type, type=rel_type, **attrs)


def build_graph(session) -> nx.MultiDiGraph:
    """Build and return the full in-memory Crime Intelligence Graph."""
    G = nx.MultiDiGraph()

    # --- Nodes ---
    for loc in session.query(Location).all():
        G.add_node(node_key("Location", loc.id), label="Location", id=loc.id,
                   name=loc.name, district=loc.district, state=loc.state,
                   latitude=loc.latitude, longitude=loc.longitude)

    for person in session.query(Person).all():
        G.add_node(node_key("Person", person.id), label="Person", id=person.id,
                   name=person.name, gender=person.gender.value,
                   age=person.age, occupation=person.occupation)

    for crime in session.query(Crime).all():
        G.add_node(node_key("Crime", crime.id), label="Crime", id=crime.id,
                   type=crime.type.value, timestamp=crime.timestamp.isoformat(),
                   modus_operandi=crime.modus_operandi)
        add_rel(G, node_key("Crime", crime.id), node_key("Location", crime.location_id),
                "CRIME_OCCURRED_AT")

    for fir in session.query(FIR).all():
        G.add_node(node_key("FIR", fir.id), label="FIR", id=fir.id,
                   fir_number=fir.fir_number, status=fir.status.value,
                   investigating_officer=fir.investigating_officer)
        add_rel(G, node_key("Crime", fir.crime_id), node_key("FIR", fir.id),
                "CRIME_LINKED_TO_FIR")

    for phone in session.query(Phone).all():
        G.add_node(node_key("Phone", phone.id), label="Phone", id=phone.id, number=phone.number)
        add_rel(G, node_key("Person", phone.owner_id), node_key("Phone", phone.id),
                "PERSON_OWNS_PHONE")

    for vehicle in session.query(Vehicle).all():
        G.add_node(node_key("Vehicle", vehicle.id), label="Vehicle", id=vehicle.id,
                   registration_number=vehicle.registration_number, vehicle_type=vehicle.vehicle_type)
        add_rel(G, node_key("Person", vehicle.owner_id), node_key("Vehicle", vehicle.id),
                "PERSON_OWNS_VEHICLE")

    for account in session.query(BankAccount).all():
        G.add_node(node_key("BankAccount", account.id), label="BankAccount", id=account.id,
                   bank=account.bank, account_number=account.account_number,
                   is_flagged_mule=account.is_flagged_mule)
        add_rel(G, node_key("Person", account.owner_id), node_key("BankAccount", account.id),
                "PERSON_OWNS_ACCOUNT")

    for tx in session.query(Transaction).all():
        G.add_node(node_key("Transaction", tx.id), label="Transaction", id=tx.id,
                   amount=tx.amount, timestamp=tx.timestamp.isoformat(),
                   is_suspicious=tx.is_suspicious)
        add_rel(G, node_key("BankAccount", tx.sender_account_id), node_key("Transaction", tx.id),
                "ACCOUNT_SENT_TRANSACTION")
        add_rel(G, node_key("Transaction", tx.id), node_key("BankAccount", tx.receiver_account_id),
                "TRANSACTION_TO_ACCOUNT")

    # --- Person <-> Crime/FIR links ---
    # Group links by crime to derive PERSON_LINKED_TO_PERSON co-occurrence edges
    links_by_crime = {}
    for link in session.query(PersonCrimeLink).all():
        links_by_crime.setdefault(link.crime_id, []).append(link)

        if link.role == PersonRole.ACCUSED:
            add_rel(G, node_key("Person", link.person_id), node_key("Crime", link.crime_id),
                    "PERSON_COMMITTED_CRIME", raw_name_used=link.raw_name_used)
        else:
            crime = session.get(Crime, link.crime_id)
            if crime and crime.fir:
                add_rel(G, node_key("Person", link.person_id), node_key("FIR", crime.fir.id),
                        "PERSON_INVOLVED_IN_FIR", role=link.role.value,
                        raw_name_used=link.raw_name_used)

    # PERSON_LINKED_TO_PERSON: any two distinct persons appearing on the same crime
    seen_pairs = set()
    for crime_id, links in links_by_crime.items():
        person_ids = sorted({l.person_id for l in links})
        for i in range(len(person_ids)):
            for j in range(i + 1, len(person_ids)):
                pair = (person_ids[i], person_ids[j], crime_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                add_rel(G, node_key("Person", person_ids[i]), node_key("Person", person_ids[j]),
                        "PERSON_LINKED_TO_PERSON", via_crime_id=crime_id)
                add_rel(G, node_key("Person", person_ids[j]), node_key("Person", person_ids[i]),
                        "PERSON_LINKED_TO_PERSON", via_crime_id=crime_id)

    # --- PERSON_ASSOCIATED_WITH (from PersonAssociation table) ---
    for assoc in session.query(PersonAssociation).all():
        add_rel(G, node_key("Person", assoc.person_a_id), node_key("Person", assoc.person_b_id),
                "PERSON_ASSOCIATED_WITH", relation_type=assoc.relation_type.value,
                strength=assoc.strength)
        add_rel(G, node_key("Person", assoc.person_b_id), node_key("Person", assoc.person_a_id),
                "PERSON_ASSOCIATED_WITH", relation_type=assoc.relation_type.value,
                strength=assoc.strength)

    return G


def compute_metrics(G: nx.MultiDiGraph) -> dict:
    """Node/relationship counts, broken down by label/type, matching the
    format the Neo4j builder also produces."""
    node_counts = {label: 0 for label in NODE_LABELS}
    for _, data in G.nodes(data=True):
        node_counts[data["label"]] = node_counts.get(data["label"], 0) + 1

    rel_counts = {rel: 0 for rel in RELATIONSHIP_TYPES}
    for _, _, data in G.edges(data=True):
        rel_counts[data["type"]] = rel_counts.get(data["type"], 0) + 1

    return {"nodes": node_counts, "relationships": rel_counts}
