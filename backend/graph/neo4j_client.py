"""
SHERLOCK — Neo4j client (Phase 2A).

Thin wrapper around the official `neo4j` driver. Reads connection details
from environment variables so the rest of the codebase never hardcodes
credentials:

    NEO4J_URI       (default: bolt://localhost:7687)
    NEO4J_USER      (default: neo4j)
    NEO4J_PASSWORD  (default: sherlock123)

Pairs with `docker/docker-compose.yml`, which stands up a local Neo4j
instance with that default user/password.
"""

import os
from neo4j import GraphDatabase


class Neo4jClient:
    def __init__(self, uri=None, user=None, password=None):
        self.uri = uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "sherlock123")
        self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))

    def close(self):
        self._driver.close()

    def verify_connectivity(self):
        self._driver.verify_connectivity()

    def run_query(self, query, parameters=None):
        """Run a read query, return a list of dict records."""
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]

    def run_write(self, query, parameters=None):
        """Run a write query in an explicit transaction, return summary counters."""
        with self._driver.session() as session:
            result = session.run(query, parameters or {})
            summary = result.consume()
            return summary.counters

    def run_write_batch(self, query, rows, batch_size=500):
        """
        Run a write query with UNWIND $rows over a list of parameter dicts,
        in batches. Used by the graph builder for bulk node/relationship
        creation.
        """
        total = {"nodes_created": 0, "relationships_created": 0, "properties_set": 0}
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            counters = self.run_write(query, {"rows": batch})
            total["nodes_created"] += counters.nodes_created
            total["relationships_created"] += counters.relationships_created
            total["properties_set"] += counters.properties_set
        return total

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
