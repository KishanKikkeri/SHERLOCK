"""
SHERLOCK — NetworkX-backed Graph Intelligence Service (Phase 2C, dev/demo).

Implements the five core graph queries against an in-memory
`networkx.MultiDiGraph` built by `backend/graph/builder_networkx.py`.

This is the default backend (GRAPH_BACKEND=networkx or unset) — zero
external dependencies, runs anywhere. `service_neo4j.py` implements the
exact same interface against a real Neo4j instance.
"""

from collections import defaultdict

import networkx as nx

from backend.graph.builder_networkx import build_graph, compute_metrics
from backend.graph.service import GraphIntelligenceService
from backend.graph.schema import node_key


class NetworkXGraphService(GraphIntelligenceService):
    def __init__(self, session=None, graph: nx.MultiDiGraph = None):
        """
        Either pass a pre-built `graph`, or pass a SQLAlchemy `session` and
        the graph will be built from it on construction.
        """
        if graph is not None:
            self.G = graph
        elif session is not None:
            self.G = build_graph(session)
        else:
            raise ValueError("NetworkXGraphService requires either `graph` or `session`")

    # -----------------------------------------------------------------
    # Query 1: Repeat offenders
    # -----------------------------------------------------------------
    def find_repeat_offenders(self, min_crimes: int = 2, limit: int = 10):
        results = []
        for node, data in self.G.nodes(data=True):
            if data.get("label") != "Person":
                continue
            crime_count = sum(
                1 for _, _, edata in self.G.out_edges(node, data=True)
                if edata["type"] == "PERSON_COMMITTED_CRIME"
            )
            if crime_count >= min_crimes:
                results.append({
                    "person_id": data["id"],
                    "name": data["name"],
                    "crime_count": crime_count,
                })
        results.sort(key=lambda r: r["crime_count"], reverse=True)
        return results[:limit]

    # -----------------------------------------------------------------
    # Query 2: Associates
    # -----------------------------------------------------------------
    def find_associates(self, person_id: int, limit: int = 20):
        node = node_key("Person", person_id)
        if node not in self.G:
            return []

        results = []
        seen = set()
        rel_types = {"PERSON_ASSOCIATED_WITH", "PERSON_LINKED_TO_PERSON"}

        for _, v, edata in self.G.out_edges(node, data=True):
            if edata["type"] not in rel_types:
                continue
            vdata = self.G.nodes[v]
            dedupe_key = (v, edata["type"])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            results.append({
                "associate_id": vdata["id"],
                "name": vdata["name"],
                "edge_type": edata["type"],
                "relation_type": edata.get("relation_type"),
                "strength": edata.get("strength"),
            })

        # Sort: edges with an explicit strength first (highest first), then the rest
        results.sort(key=lambda r: (r["strength"] is None, -(r["strength"] or 0)))
        return results[:limit]

    # -----------------------------------------------------------------
    # Query 3: Financial network / money trail
    # -----------------------------------------------------------------
    def find_financial_network(self, account_id: int, max_hops: int = 1):
        node = node_key("BankAccount", account_id)
        if node not in self.G:
            return []

        results = []

        # Outgoing: this account -> Transaction -> receiver account
        for _, tx_node, edata in self.G.out_edges(node, data=True):
            if edata["type"] != "ACCOUNT_SENT_TRANSACTION":
                continue
            tx_data = self.G.nodes[tx_node]
            for _, receiver_node, edata2 in self.G.out_edges(tx_node, data=True):
                if edata2["type"] != "TRANSACTION_TO_ACCOUNT":
                    continue
                receiver_data = self.G.nodes[receiver_node]
                owner_name = self._account_owner_name(receiver_node)
                results.append({
                    "direction": "sent",
                    "transaction_id": tx_data["id"],
                    "amount": tx_data["amount"],
                    "timestamp": tx_data["timestamp"],
                    "is_suspicious": tx_data["is_suspicious"],
                    "counterparty_account_id": receiver_data["id"],
                    "counterparty_owner": owner_name,
                })

        # Incoming: sender account -> Transaction -> this account
        for tx_node, _, edata2 in self.G.in_edges(node, data=True):
            if edata2["type"] != "TRANSACTION_TO_ACCOUNT":
                continue
            tx_data = self.G.nodes[tx_node]
            for sender_node, _, edata in self.G.in_edges(tx_node, data=True):
                if edata["type"] != "ACCOUNT_SENT_TRANSACTION":
                    continue
                sender_data = self.G.nodes[sender_node]
                owner_name = self._account_owner_name(sender_node)
                results.append({
                    "direction": "received",
                    "transaction_id": tx_data["id"],
                    "amount": tx_data["amount"],
                    "timestamp": tx_data["timestamp"],
                    "is_suspicious": tx_data["is_suspicious"],
                    "counterparty_account_id": sender_data["id"],
                    "counterparty_owner": owner_name,
                })

        results.sort(key=lambda r: r["timestamp"], reverse=True)
        return results

    def _account_owner_name(self, account_node):
        for u, _, edata in self.G.in_edges(account_node, data=True):
            if edata["type"] == "PERSON_OWNS_ACCOUNT":
                return self.G.nodes[u]["name"]
        return None

    # -----------------------------------------------------------------
    # Query 4: Crime hotspot clusters
    # -----------------------------------------------------------------
    def find_location_clusters(self, crime_type: str = None, top_n: int = 10):
        from datetime import datetime

        cluster_counts = defaultdict(int)
        for node, data in self.G.nodes(data=True):
            if data.get("label") != "Crime":
                continue
            if crime_type and data["type"] != crime_type:
                continue
            month = datetime.fromisoformat(data["timestamp"]).month
            for _, loc_node, edata in self.G.out_edges(node, data=True):
                if edata["type"] != "CRIME_OCCURRED_AT":
                    continue
                district = self.G.nodes[loc_node]["district"]
                cluster_counts[(district, data["type"], month)] += 1

        results = [
            {"district": district, "crime_type": ctype, "month": month, "count": count}
            for (district, ctype, month), count in cluster_counts.items()
        ]
        results.sort(key=lambda r: r["count"], reverse=True)
        return results[:top_n]

    # -----------------------------------------------------------------
    # Query 5: Shortest connection between two persons
    # -----------------------------------------------------------------
    def find_connection(self, person_a_id: int, person_b_id: int, max_hops: int = 6):
        src = node_key("Person", person_a_id)
        dst = node_key("Person", person_b_id)
        if src not in self.G or dst not in self.G:
            return {"found": False, "hops": 0, "chain": []}

        UG = self.G.to_undirected()
        try:
            path = nx.shortest_path(UG, source=src, target=dst)
        except nx.NetworkXNoPath:
            return {"found": False, "hops": 0, "chain": []}

        if len(path) - 1 > max_hops:
            return {"found": False, "hops": len(path) - 1, "chain": []}

        chain = []
        for i, node in enumerate(path):
            data = self.G.nodes[node]
            entry = {
                "node_type": data["label"],
                "id": data["id"],
                "label": data.get("name") or data.get("fir_number") or data.get("number")
                         or data.get("account_number") or data.get("registration_number")
                         or f"{data['label']}:{data['id']}",
                "relationship_to_next": None,
            }
            if i < len(path) - 1:
                entry["relationship_to_next"] = self._edge_type_between(path[i], path[i + 1])
            chain.append(entry)

        return {"found": True, "hops": len(path) - 1, "chain": chain}

    def _edge_type_between(self, a, b):
        """Find a relationship type connecting a and b, checking both directions."""
        for _, v, edata in self.G.out_edges(a, data=True):
            if v == b:
                return edata["type"]
        for u, _, edata in self.G.out_edges(b, data=True):
            if u == a:
                return edata["type"]
        return "UNKNOWN"

    # -----------------------------------------------------------------
    # Metrics
    # -----------------------------------------------------------------
    def get_metrics(self):
        return compute_metrics(self.G)
