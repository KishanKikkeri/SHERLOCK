"""
SHERLOCK — Neo4j-backed Graph Intelligence Service (Phase 2C, production).

Implements the same five-method interface as `service_networkx.py`, against
a real Neo4j instance via Cypher. Select with GRAPH_BACKEND=neo4j (requires
`docker compose up` from `docker/docker-compose.yml` and the graph to have
been built via `backend.graph.builder_neo4j.build_graph`).

PERSON_ASSOCIATED_WITH and PERSON_LINKED_TO_PERSON are stored as a single
relationship per pair (see builder_neo4j.py), so all queries here traverse
them with the undirected pattern `-[r:TYPE]-`.
"""

from backend.graph.neo4j_client import Neo4jClient
from backend.graph.service import GraphIntelligenceService
from backend.graph.schema import NODE_LABELS, RELATIONSHIP_TYPES


class Neo4jGraphService(GraphIntelligenceService):
    def __init__(self, client: Neo4jClient = None):
        self.client = client or Neo4jClient()

    # -----------------------------------------------------------------
    # Query 1: Repeat offenders
    # -----------------------------------------------------------------
    def find_repeat_offenders(self, min_crimes: int = 2, limit: int = 10):
        query = """
            MATCH (p:Person)-[:PERSON_COMMITTED_CRIME]->(c:Crime)
            WITH p, count(c) AS crime_count
            WHERE crime_count >= $min_crimes
            RETURN p.id AS person_id, p.name AS name, crime_count
            ORDER BY crime_count DESC
            LIMIT $limit
        """
        return self.client.run_query(query, {"min_crimes": min_crimes, "limit": limit})

    # -----------------------------------------------------------------
    # Query 2: Associates
    # -----------------------------------------------------------------
    def find_associates(self, person_id: int, limit: int = 20):
        query = """
            MATCH (p:Person {id: $person_id})-[r:PERSON_ASSOCIATED_WITH|PERSON_LINKED_TO_PERSON]-(a:Person)
            RETURN a.id AS associate_id, a.name AS name, type(r) AS edge_type,
                   r.relation_type AS relation_type, r.strength AS strength
            ORDER BY r.strength IS NULL, r.strength DESC
            LIMIT $limit
        """
        return self.client.run_query(query, {"person_id": person_id, "limit": limit})

    # -----------------------------------------------------------------
    # Query 3: Financial network / money trail
    # -----------------------------------------------------------------
    def find_financial_network(self, account_id: int, max_hops: int = 1):
        query = """
            MATCH (a:BankAccount {id: $account_id})-[:ACCOUNT_SENT_TRANSACTION]->(t:Transaction)
                  -[:TRANSACTION_TO_ACCOUNT]->(r:BankAccount)
            OPTIONAL MATCH (owner:Person)-[:PERSON_OWNS_ACCOUNT]->(r)
            RETURN 'sent' AS direction, t.id AS transaction_id, t.amount AS amount,
                   t.timestamp AS timestamp, t.is_suspicious AS is_suspicious,
                   r.id AS counterparty_account_id, owner.name AS counterparty_owner

            UNION

            MATCH (s:BankAccount)-[:ACCOUNT_SENT_TRANSACTION]->(t:Transaction)
                  -[:TRANSACTION_TO_ACCOUNT]->(a:BankAccount {id: $account_id})
            OPTIONAL MATCH (owner:Person)-[:PERSON_OWNS_ACCOUNT]->(s)
            RETURN 'received' AS direction, t.id AS transaction_id, t.amount AS amount,
                   t.timestamp AS timestamp, t.is_suspicious AS is_suspicious,
                   s.id AS counterparty_account_id, owner.name AS counterparty_owner

            ORDER BY timestamp DESC
        """
        return self.client.run_query(query, {"account_id": account_id})

    # -----------------------------------------------------------------
    # Query 4: Crime hotspot clusters
    # -----------------------------------------------------------------
    def find_location_clusters(self, crime_type: str = None, top_n: int = 10):
        query = """
            MATCH (c:Crime)-[:CRIME_OCCURRED_AT]->(l:Location)
            WHERE $crime_type IS NULL OR c.type = $crime_type
            WITH l.district AS district, c.type AS crime_type,
                 toInteger(substring(c.timestamp, 5, 2)) AS month, count(c) AS count
            RETURN district, crime_type, month, count
            ORDER BY count DESC
            LIMIT $top_n
        """
        return self.client.run_query(query, {"crime_type": crime_type, "top_n": top_n})

    # -----------------------------------------------------------------
    # Query 5: Shortest connection between two persons
    # -----------------------------------------------------------------
    def find_connection(self, person_a_id: int, person_b_id: int, max_hops: int = 6):
        query = f"""
            MATCH path = shortestPath((a:Person {{id: $a}})-[*..{max_hops}]-(b:Person {{id: $b}}))
            RETURN path
        """
        with self.client._driver.session() as session:
            result = session.run(query, {"a": person_a_id, "b": person_b_id})
            record = result.single()

        if not record or record["path"] is None:
            return {"found": False, "hops": 0, "chain": []}

        path = record["path"]
        nodes = list(path.nodes)
        rels = list(path.relationships)

        chain = []
        for i, node in enumerate(nodes):
            label = list(node.labels)[0]
            display = (
                node.get("name") or node.get("fir_number") or node.get("number")
                or node.get("account_number") or node.get("registration_number")
                or f"{label}:{node.get('id')}"
            )
            entry = {
                "node_type": label,
                "id": node.get("id"),
                "label": display,
                "relationship_to_next": rels[i].type if i < len(rels) else None,
            }
            chain.append(entry)

        return {"found": True, "hops": len(rels), "chain": chain}

    # -----------------------------------------------------------------
    # Metrics
    # -----------------------------------------------------------------
    def get_metrics(self):
        node_counts = {label: 0 for label in NODE_LABELS}
        for row in self.client.run_query("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count"):
            if row["label"] in node_counts:
                node_counts[row["label"]] = row["count"]

        rel_counts = {rel: 0 for rel in RELATIONSHIP_TYPES}
        for row in self.client.run_query("MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count"):
            if row["rel_type"] in rel_counts:
                rel_counts[row["rel_type"]] = row["count"]

        return {"nodes": node_counts, "relationships": rel_counts}
