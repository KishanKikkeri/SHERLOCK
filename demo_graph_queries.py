"""
SHERLOCK — Graph Intelligence milestone demo (Phase 2 deliverable).

Builds the Crime Intelligence Graph from the SQL dataset and runs the five
core graph queries through the Graph Intelligence Service abstraction —
proving graph construction, relationship discovery, network analysis,
financial trail analysis, and shortest-connection discovery all work
end to end.

Usage:
    python demo_graph_queries.py                 # NetworkX backend (default, no setup needed)
    GRAPH_BACKEND=neo4j python demo_graph_queries.py   # Neo4j backend (requires docker-compose up)

Prerequisite: generate the dataset first if you haven't already:
    python -m backend.datasets.generate_synthetic_data --persons 500 --crimes 1000 --reset
"""

import os
import sys

from backend.database.config import SessionLocal
from backend.database.models import BankAccount, Transaction
from backend.graph.service import get_graph_service


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def main():
    backend = os.getenv("GRAPH_BACKEND", "networkx")
    session = SessionLocal()

    section(f"Building Crime Intelligence Graph (backend={backend})")
    if backend == "networkx":
        service = get_graph_service(backend="networkx", session=session)
    else:
        from backend.graph.builder_neo4j import build_graph
        build_graph(session)
        service = get_graph_service(backend="neo4j")

    metrics = service.get_metrics()
    print("\nNodes:")
    for label, count in metrics["nodes"].items():
        print(f"  {label:15s} {count}")
    print("\nRelationships:")
    total_rels = 0
    for rel, count in metrics["relationships"].items():
        print(f"  {rel:28s} {count}")
        total_rels += count
    print(f"\n  TOTAL relationships created: {total_rels}")

    # -----------------------------------------------------------------
    # Query 1: Repeat offenders
    # -----------------------------------------------------------------
    section("Query 1 — find_repeat_offenders()")
    offenders = service.find_repeat_offenders(min_crimes=5, limit=5)
    for o in offenders:
        print(f"  {o['name']:25s} (person_id={o['person_id']:4d})  crimes committed: {o['crime_count']}")

    if not offenders:
        print("  (none found — try lowering min_crimes)")
        return

    # -----------------------------------------------------------------
    # Query 2: Associates of the top repeat offender
    # -----------------------------------------------------------------
    top_offender = offenders[0]
    section(f"Query 2 — find_associates({top_offender['name']}, person_id={top_offender['person_id']})")
    associates = service.find_associates(top_offender["person_id"], limit=10)
    if associates:
        for a in associates:
            strength = f"{a['strength']:.2f}" if a["strength"] is not None else "—"
            rtype = a["relation_type"] or a["edge_type"]
            print(f"  {a['name']:25s} (person_id={a['associate_id']:4d})  via {rtype:15s} strength={strength}")
    else:
        print("  (no direct associates found)")

    # -----------------------------------------------------------------
    # Query 3: Financial network around the money-mule hub account
    # -----------------------------------------------------------------
    section("Query 3 — find_financial_network(hub mule account)")
    hub_account = (
        session.query(BankAccount)
        .filter_by(is_flagged_mule=True)
        .all()
    )
    # pick the flagged account with the most *received* transactions = the hub
    hub_account = max(hub_account, key=lambda a: len(a.received_transactions), default=None)

    if hub_account:
        print(f"  Hub account: {hub_account.account_number} @ {hub_account.bank} (owner: {hub_account.owner.name})")
        network = service.find_financial_network(hub_account.id)
        for tx in network[:10]:
            arrow = "<-" if tx["direction"] == "received" else "->"
            flag = " [SUSPICIOUS]" if tx["is_suspicious"] else ""
            print(f"  {arrow} Rs.{tx['amount']:>10,.2f}  {tx['direction']:8s} "
                  f"counterparty={tx['counterparty_owner']!s:25s}{flag}")
        print(f"  ... {len(network)} transaction(s) total")
    else:
        print("  (no flagged mule accounts found)")

    # -----------------------------------------------------------------
    # Query 4: Crime hotspot clusters (burglary, looking for festival spike)
    # -----------------------------------------------------------------
    section("Query 4 — find_location_clusters(crime_type='burglary')")
    clusters = service.find_location_clusters(crime_type="burglary", top_n=8)
    for c in clusters:
        print(f"  {c['district']:20s} month={c['month']:2d}  burglaries={c['count']}")

    # -----------------------------------------------------------------
    # Query 5: Shortest connection between two mule-ring members
    # -----------------------------------------------------------------
    section("Query 5 — find_connection() between two fraud-ring members")
    mule_accounts = (
        session.query(BankAccount)
        .filter_by(is_flagged_mule=True)
        .all()
    )
    mule_owners = [a.owner for a in mule_accounts if a.id != hub_account.id]
    if len(mule_owners) >= 2:
        person_a, person_b = mule_owners[0], mule_owners[1]
        print(f"  Finding connection: {person_a.name} (id={person_a.id})  <-->  {person_b.name} (id={person_b.id})")
        connection = service.find_connection(person_a.id, person_b.id)
        if connection["found"]:
            print(f"\n  Path found ({connection['hops']} hop(s)):\n")
            for i, hop in enumerate(connection["chain"]):
                print(f"    {hop['node_type']:12s} {hop['label']}")
                if hop["relationship_to_next"]:
                    print(f"        |\n        | {hop['relationship_to_next']}\n        v")
        else:
            print("  No connection found within max_hops.")
    else:
        print("  (not enough mule-ring members to demo)")

    section("DONE — Crime Intelligence Graph is operational")
    session.close()


if __name__ == "__main__":
    main()
