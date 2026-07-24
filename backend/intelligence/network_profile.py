"""
SHERLOCK — Stage G1: network profile.

Reuses the existing Graph Intelligence Service (`backend/graph/service.py`)
for associates rather than re-querying `PersonAssociation` directly — same
"agents never touch SQL/Cypher for graph facts, they call graph_service"
rule `network_analysis/agent.py` already follows.

Centrality / PageRank / community size are new here — the abstract
`GraphIntelligenceService` interface doesn't expose them (see that file's
five-method contract), and adding a sixth abstract method would require
implementing it in *both* backends (NetworkX and Neo4j) to avoid breaking
the Neo4j path, which is out of scope for this module. Instead: when the
active backend is the default NetworkX one, this reads its public `.G`
graph attribute directly (already a documented, intentional escape hatch
— `backend/app/main.py`'s own `GET /graph/{person_id}` does exactly this).
On the Neo4j backend, these fields degrade honestly to `None` with a
stated reason, rather than silently returning zero/fake values.
"""

from __future__ import annotations

from backend.database.models import BankAccount, OrganizationMembership, Transaction
from backend.graph.schema import node_key
from backend.graph.service_networkx import NetworkXGraphService

MAX_ASSOCIATES = 15


def compute_network_profile(session, person_id: int, graph_service) -> dict:
    associates = graph_service.find_associates(person_id, limit=MAX_ASSOCIATES)
    memberships = session.query(OrganizationMembership).filter_by(person_id=person_id).all()
    financial_links = _financial_links(session, person_id)
    shared_address = _shared_address(session, person_id)
    graph_metrics = _graph_metrics(graph_service, person_id)

    co_accused = [a for a in associates if a.get("relation_type") == "co_accused"]

    return {
        "associate_count": len(associates),
        "associates": associates,
        "repeat_collaborators": [a for a in co_accused],
        "organizations": [
            {"organization_id": m.organization_id, "name": m.organization.name if m.organization else None,
             "role": m.role}
            for m in memberships
        ],
        "financial_links": financial_links,
        "shared_address_with": shared_address,
        "graph_metrics": graph_metrics,
        "because": (
            f"{len(associates)} associate(s), {len(memberships)} organization membership(s), "
            f"{len(financial_links)} financial counterparty link(s) on record."
        ),
    }


def _financial_links(session, person_id: int) -> list[dict]:
    account_ids = [a.id for a in session.query(BankAccount).filter_by(owner_id=person_id).all()]
    if not account_ids:
        return []

    txns = (
        session.query(Transaction)
        .filter(
            (Transaction.sender_account_id.in_(account_ids)) | (Transaction.receiver_account_id.in_(account_ids))
        )
        .all()
    )

    links: dict[int, dict] = {}
    for t in txns:
        counterparty_account_id = (
            t.receiver_account_id if t.sender_account_id in account_ids else t.sender_account_id
        )
        if counterparty_account_id in account_ids:
            continue  # transfer between this person's own accounts
        counterparty = session.get(BankAccount, counterparty_account_id)
        if not counterparty or not counterparty.owner_id or counterparty.owner_id == person_id:
            continue
        entry = links.setdefault(counterparty.owner_id, {
            "person_id": counterparty.owner_id,
            "name": counterparty.owner.name if counterparty.owner else None,
            "transaction_count": 0,
            "suspicious_transaction_count": 0,
            "total_amount": 0.0,
        })
        entry["transaction_count"] += 1
        entry["total_amount"] += t.amount
        if t.is_suspicious:
            entry["suspicious_transaction_count"] += 1

    return sorted(links.values(), key=lambda e: e["transaction_count"], reverse=True)


def _shared_address(session, person_id: int) -> list[dict]:
    from backend.database.models import Person

    this_person = session.get(Person, person_id)
    if not this_person or not this_person.home_location_id:
        return []
    others = (
        session.query(Person)
        .filter(Person.home_location_id == this_person.home_location_id, Person.id != person_id)
        .limit(10)
        .all()
    )
    return [{"person_id": p.id, "name": p.name} for p in others]


def _graph_metrics(graph_service, person_id: int) -> dict:
    if not isinstance(graph_service, NetworkXGraphService):
        return {
            "available": False,
            "reason": "Centrality/PageRank are only computed against the NetworkX graph backend "
                      "in this build (GRAPH_BACKEND=neo4j does not expose them here).",
        }

    import networkx as nx

    G = graph_service.G
    node = node_key("Person", person_id)
    if node not in G:
        return {"available": False, "reason": "Person has no edges in the Crime Intelligence Graph."}

    undirected = G.to_undirected()
    # Full-graph PageRank/betweenness are cached per graph_service instance
    # implicitly by networkx's own call cost being fine at this dataset
    # scale (see docs/PERFORMANCE_REPORT.md) — not memoized here since a
    # profile request is already a single, bounded read.
    pagerank = nx.pagerank(G) if G.number_of_nodes() > 0 else {}
    degree_centrality = nx.degree_centrality(undirected) if undirected.number_of_nodes() > 1 else {}
    community = nx.node_connected_component(undirected, node)

    influence_score = round(pagerank.get(node, 0.0) * 1000, 2)  # scaled for readability, not a % or probability

    return {
        "available": True,
        "pagerank": round(pagerank.get(node, 0.0), 5),
        "degree_centrality": round(degree_centrality.get(node, 0.0), 4),
        "community_size": len(community),
        "influence_score": influence_score,
        "because": (
            f"PageRank {round(pagerank.get(node, 0.0), 5)} and degree centrality "
            f"{round(degree_centrality.get(node, 0.0), 4)} within a {len(community)}-node "
            f"connected component of the Crime Intelligence Graph."
        ),
    }
