"""
SHERLOCK — Graph Intelligence Service (Phase 2C).

This is the ONLY interface specialist agents (Network Analysis, Pattern/MO,
Financial Intelligence, Forecasting, etc.) use to read the Crime
Intelligence Graph. Agents never write Cypher or touch NetworkX directly —
they call one of these five methods and get back plain dicts/lists.

Two implementations exist:

- `NetworkXGraphService` (backend/graph/service_networkx.py) — in-memory,
  zero external dependencies, used for local dev and any environment
  without a running Neo4j instance. This is the DEFAULT.

- `Neo4jGraphService` (backend/graph/service_neo4j.py) — talks to a real
  Neo4j instance via Cypher. Used in the docker-compose / production setup.

Select the backend with the GRAPH_BACKEND env var (`networkx` | `neo4j`),
or pass `backend=` explicitly to `get_graph_service()`.
"""

import os
from abc import ABC, abstractmethod


class GraphIntelligenceService(ABC):
    """Common interface for both graph backends."""

    @abstractmethod
    def find_repeat_offenders(self, min_crimes: int = 2, limit: int = 10):
        """Return persons with >= min_crimes PERSON_COMMITTED_CRIME edges,
        ordered by crime_count desc.
        -> [{"person_id": int, "name": str, "crime_count": int}, ...]
        """

    @abstractmethod
    def find_associates(self, person_id: int, limit: int = 20):
        """Return direct associates of a person (PERSON_ASSOCIATED_WITH /
        PERSON_LINKED_TO_PERSON edges), ordered by relationship strength.
        -> [{"associate_id": int, "name": str, "relation_type": str,
             "edge_type": str, "strength": float}, ...]
        """

    @abstractmethod
    def find_financial_network(self, account_id: int, max_hops: int = 1):
        """Return transactions touching this account (sent and received),
        including counterparty account/owner info and suspicion flags.
        -> [{"direction": "sent"|"received", "transaction_id": int,
             "amount": float, "timestamp": str, "is_suspicious": bool,
             "counterparty_account_id": int, "counterparty_owner": str}, ...]
        """

    @abstractmethod
    def find_location_clusters(self, crime_type: str = None, top_n: int = 10):
        """Return crime hotspot clusters grouped by (district, crime_type,
        month), ordered by count desc. Optionally filter to one crime type.
        -> [{"district": str, "crime_type": str, "month": int, "count": int}, ...]
        """

    @abstractmethod
    def find_connection(self, person_a_id: int, person_b_id: int, max_hops: int = 6):
        """Return the shortest path between two persons through the graph,
        as a readable chain of (node, relationship) hops.
        -> {"found": bool, "hops": int,
             "chain": [{"node_type": str, "id": int, "label": str,
                        "relationship_to_next": str}, ...]}
        """

    @abstractmethod
    def get_metrics(self):
        """Return node/relationship counts for the build summary.
        -> {"nodes": {label: count, ...}, "relationships": {rel_type: count, ...}}
        """


def get_graph_service(backend: str = None, **kwargs) -> GraphIntelligenceService:
    """
    Factory. backend defaults to the GRAPH_BACKEND env var, falling back to
    'networkx' if unset.

    For backend='networkx', kwargs are passed to NetworkXGraphService
    (typically `session=<SQLAlchemy session>` to build the in-memory graph).

    For backend='neo4j', kwargs are passed to Neo4jGraphService (typically
    nothing — it reads connection details from NEO4J_URI / NEO4J_USER /
    NEO4J_PASSWORD env vars).
    """
    backend = backend or os.getenv("GRAPH_BACKEND", "networkx")

    if backend == "networkx":
        from backend.graph.service_networkx import NetworkXGraphService
        return NetworkXGraphService(**kwargs)
    elif backend == "neo4j":
        from backend.graph.service_neo4j import Neo4jGraphService
        return Neo4jGraphService(**kwargs)
    else:
        raise ValueError(f"Unknown GRAPH_BACKEND: {backend!r} (expected 'networkx' or 'neo4j')")
