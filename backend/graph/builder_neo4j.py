"""
SHERLOCK — Neo4j graph builder (Phase 2B, production backend).

Reads the SQL dataset via a SQLAlchemy session and writes it into Neo4j as
nodes/relationships per the frozen schema in `backend/graph/schema.py`,
using batched UNWIND + MERGE so this can be re-run safely (idempotent on
`id`).

Note on undirected relationships: PERSON_ASSOCIATED_WITH and
PERSON_LINKED_TO_PERSON are written ONCE per pair (not duplicated in both
directions, unlike the NetworkX builder which adds both directions for
traversal convenience). `service_neo4j.py` queries these with an
undirected pattern `-[r:TYPE]-` so both directions are matched.

Usage:
    from backend.database.config import SessionLocal
    from backend.graph.builder_neo4j import build_graph

    session = SessionLocal()
    metrics = build_graph(session)
"""

from backend.database.models import (
    Person, Location, Crime, FIR, Vehicle, Phone, BankAccount, Transaction,
    PersonCrimeLink, PersonRole, PersonAssociation,
)
from backend.graph.neo4j_client import Neo4jClient
from backend.graph.schema import CONSTRAINT_STATEMENTS, NODE_LABELS, RELATIONSHIP_TYPES


def _ensure_constraints(client: Neo4jClient):
    for stmt in CONSTRAINT_STATEMENTS:
        client.run_write(stmt)


# ---------------------------------------------------------------------------
# Node builders — each returns (label, cypher, rows)
# ---------------------------------------------------------------------------

def _node_batches(session):
    batches = []

    locations = [{
        "id": l.id, "name": l.name, "district": l.district,
        "state": l.state, "latitude": l.latitude, "longitude": l.longitude,
    } for l in session.query(Location).all()]
    batches.append(("Location", """
        UNWIND $rows AS row
        MERGE (n:Location {id: row.id})
        SET n.name = row.name, n.district = row.district, n.state = row.state,
            n.latitude = row.latitude, n.longitude = row.longitude
    """, locations))

    persons = [{
        "id": p.id, "name": p.name, "gender": p.gender.value,
        "age": p.age, "occupation": p.occupation,
    } for p in session.query(Person).all()]
    batches.append(("Person", """
        UNWIND $rows AS row
        MERGE (n:Person {id: row.id})
        SET n.name = row.name, n.gender = row.gender, n.age = row.age,
            n.occupation = row.occupation
    """, persons))

    crimes = [{
        "id": c.id, "type": c.type.value, "timestamp": c.timestamp.isoformat(),
        "modus_operandi": c.modus_operandi,
    } for c in session.query(Crime).all()]
    batches.append(("Crime", """
        UNWIND $rows AS row
        MERGE (n:Crime {id: row.id})
        SET n.type = row.type, n.timestamp = row.timestamp, n.modus_operandi = row.modus_operandi
    """, crimes))

    firs = [{
        "id": f.id, "fir_number": f.fir_number, "status": f.status.value,
        "investigating_officer": f.investigating_officer,
    } for f in session.query(FIR).all()]
    batches.append(("FIR", """
        UNWIND $rows AS row
        MERGE (n:FIR {id: row.id})
        SET n.fir_number = row.fir_number, n.status = row.status,
            n.investigating_officer = row.investigating_officer
    """, firs))

    phones = [{"id": p.id, "number": p.number} for p in session.query(Phone).all()]
    batches.append(("Phone", """
        UNWIND $rows AS row
        MERGE (n:Phone {id: row.id})
        SET n.number = row.number
    """, phones))

    vehicles = [{
        "id": v.id, "registration_number": v.registration_number, "vehicle_type": v.vehicle_type,
    } for v in session.query(Vehicle).all()]
    batches.append(("Vehicle", """
        UNWIND $rows AS row
        MERGE (n:Vehicle {id: row.id})
        SET n.registration_number = row.registration_number, n.vehicle_type = row.vehicle_type
    """, vehicles))

    accounts = [{
        "id": a.id, "bank": a.bank, "account_number": a.account_number,
        "is_flagged_mule": a.is_flagged_mule,
    } for a in session.query(BankAccount).all()]
    batches.append(("BankAccount", """
        UNWIND $rows AS row
        MERGE (n:BankAccount {id: row.id})
        SET n.bank = row.bank, n.account_number = row.account_number,
            n.is_flagged_mule = row.is_flagged_mule
    """, accounts))

    transactions = [{
        "id": t.id, "amount": t.amount, "timestamp": t.timestamp.isoformat(),
        "is_suspicious": t.is_suspicious,
    } for t in session.query(Transaction).all()]
    batches.append(("Transaction", """
        UNWIND $rows AS row
        MERGE (n:Transaction {id: row.id})
        SET n.amount = row.amount, n.timestamp = row.timestamp, n.is_suspicious = row.is_suspicious
    """, transactions))

    return batches


# ---------------------------------------------------------------------------
# Relationship builders — each returns (rel_type, cypher, rows)
# ---------------------------------------------------------------------------

def _relationship_batches(session):
    batches = []

    # CRIME_OCCURRED_AT
    rows = [{"crime_id": c.id, "location_id": c.location_id} for c in session.query(Crime).all()]
    batches.append(("CRIME_OCCURRED_AT", """
        UNWIND $rows AS row
        MATCH (c:Crime {id: row.crime_id}), (l:Location {id: row.location_id})
        MERGE (c)-[:CRIME_OCCURRED_AT]->(l)
    """, rows))

    # CRIME_LINKED_TO_FIR
    rows = [{"crime_id": f.crime_id, "fir_id": f.id} for f in session.query(FIR).all()]
    batches.append(("CRIME_LINKED_TO_FIR", """
        UNWIND $rows AS row
        MATCH (c:Crime {id: row.crime_id}), (f:FIR {id: row.fir_id})
        MERGE (c)-[:CRIME_LINKED_TO_FIR]->(f)
    """, rows))

    # PERSON_OWNS_PHONE / VEHICLE / ACCOUNT
    rows = [{"person_id": p.owner_id, "asset_id": p.id} for p in session.query(Phone).all()]
    batches.append(("PERSON_OWNS_PHONE", """
        UNWIND $rows AS row
        MATCH (p:Person {id: row.person_id}), (a:Phone {id: row.asset_id})
        MERGE (p)-[:PERSON_OWNS_PHONE]->(a)
    """, rows))

    rows = [{"person_id": v.owner_id, "asset_id": v.id} for v in session.query(Vehicle).all()]
    batches.append(("PERSON_OWNS_VEHICLE", """
        UNWIND $rows AS row
        MATCH (p:Person {id: row.person_id}), (a:Vehicle {id: row.asset_id})
        MERGE (p)-[:PERSON_OWNS_VEHICLE]->(a)
    """, rows))

    rows = [{"person_id": a.owner_id, "asset_id": a.id} for a in session.query(BankAccount).all()]
    batches.append(("PERSON_OWNS_ACCOUNT", """
        UNWIND $rows AS row
        MATCH (p:Person {id: row.person_id}), (a:BankAccount {id: row.asset_id})
        MERGE (p)-[:PERSON_OWNS_ACCOUNT]->(a)
    """, rows))

    # ACCOUNT_SENT_TRANSACTION / TRANSACTION_TO_ACCOUNT
    rows = [{"account_id": t.sender_account_id, "tx_id": t.id} for t in session.query(Transaction).all()]
    batches.append(("ACCOUNT_SENT_TRANSACTION", """
        UNWIND $rows AS row
        MATCH (a:BankAccount {id: row.account_id}), (t:Transaction {id: row.tx_id})
        MERGE (a)-[:ACCOUNT_SENT_TRANSACTION]->(t)
    """, rows))

    rows = [{"account_id": t.receiver_account_id, "tx_id": t.id} for t in session.query(Transaction).all()]
    batches.append(("TRANSACTION_TO_ACCOUNT", """
        UNWIND $rows AS row
        MATCH (t:Transaction {id: row.tx_id}), (a:BankAccount {id: row.account_id})
        MERGE (t)-[:TRANSACTION_TO_ACCOUNT]->(a)
    """, rows))

    # PERSON_COMMITTED_CRIME / PERSON_INVOLVED_IN_FIR (from PersonCrimeLink)
    committed, involved = [], []
    links_by_crime = {}
    for link in session.query(PersonCrimeLink).all():
        links_by_crime.setdefault(link.crime_id, []).append(link)
        if link.role == PersonRole.ACCUSED:
            committed.append({
                "person_id": link.person_id, "crime_id": link.crime_id,
                "raw_name_used": link.raw_name_used,
            })
        else:
            crime = session.get(Crime, link.crime_id)
            if crime and crime.fir:
                involved.append({
                    "person_id": link.person_id, "fir_id": crime.fir.id,
                    "role": link.role.value, "raw_name_used": link.raw_name_used,
                })

    batches.append(("PERSON_COMMITTED_CRIME", """
        UNWIND $rows AS row
        MATCH (p:Person {id: row.person_id}), (c:Crime {id: row.crime_id})
        MERGE (p)-[r:PERSON_COMMITTED_CRIME]->(c)
        SET r.raw_name_used = row.raw_name_used
    """, committed))

    batches.append(("PERSON_INVOLVED_IN_FIR", """
        UNWIND $rows AS row
        MATCH (p:Person {id: row.person_id}), (f:FIR {id: row.fir_id})
        MERGE (p)-[r:PERSON_INVOLVED_IN_FIR]->(f)
        SET r.role = row.role, r.raw_name_used = row.raw_name_used
    """, involved))

    # PERSON_LINKED_TO_PERSON — one undirected edge per co-occurring pair per crime
    linked_rows = []
    seen_pairs = set()
    for crime_id, links in links_by_crime.items():
        person_ids = sorted({l.person_id for l in links})
        for i in range(len(person_ids)):
            for j in range(i + 1, len(person_ids)):
                pair = (person_ids[i], person_ids[j], crime_id)
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                linked_rows.append({
                    "a": person_ids[i], "b": person_ids[j], "via_crime_id": crime_id,
                })
    batches.append(("PERSON_LINKED_TO_PERSON", """
        UNWIND $rows AS row
        MATCH (a:Person {id: row.a}), (b:Person {id: row.b})
        MERGE (a)-[r:PERSON_LINKED_TO_PERSON]-(b)
        SET r.via_crime_id = row.via_crime_id
    """, linked_rows))

    # PERSON_ASSOCIATED_WITH — one undirected edge per association row
    assoc_rows = [{
        "a": a.person_a_id, "b": a.person_b_id,
        "relation_type": a.relation_type.value, "strength": a.strength,
    } for a in session.query(PersonAssociation).all()]
    batches.append(("PERSON_ASSOCIATED_WITH", """
        UNWIND $rows AS row
        MATCH (a:Person {id: row.a}), (b:Person {id: row.b})
        MERGE (a)-[r:PERSON_ASSOCIATED_WITH]-(b)
        SET r.relation_type = row.relation_type, r.strength = row.strength
    """, assoc_rows))

    return batches


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_graph(session, client: Neo4jClient = None) -> dict:
    """Build (or refresh) the full Crime Intelligence Graph in Neo4j.
    Returns the same {"nodes": {...}, "relationships": {...}} metrics shape
    as the NetworkX builder's `compute_metrics`."""
    owns_client = client is None
    client = client or Neo4jClient()

    try:
        client.verify_connectivity()
        _ensure_constraints(client)

        node_counts = {label: 0 for label in NODE_LABELS}
        for label, cypher, rows in _node_batches(session):
            if rows:
                client.run_write_batch(cypher, rows)
            node_counts[label] = len(rows)

        rel_counts = {rel: 0 for rel in RELATIONSHIP_TYPES}
        for rel_type, cypher, rows in _relationship_batches(session):
            if rows:
                client.run_write_batch(cypher, rows)
            rel_counts[rel_type] = len(rows)

        return {"nodes": node_counts, "relationships": rel_counts}
    finally:
        if owns_client:
            client.close()


if __name__ == "__main__":
    from backend.database.config import SessionLocal

    s = SessionLocal()
    try:
        metrics = build_graph(s)
        print("Nodes:", metrics["nodes"])
        print("Relationships:", metrics["relationships"])
    finally:
        s.close()
