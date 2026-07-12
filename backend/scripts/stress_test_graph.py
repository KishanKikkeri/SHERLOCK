"""
SHERLOCK — Graph Layer stress test (checklist item 5 / item 10 / item 11).

Not runnable in this sandbox: needs a live Neo4j instance (docker-compose
up) plus a larger synthetic dataset than is practical to spin up here.
Written so you can run it directly once you have both.

Usage:
    docker-compose -f docker/docker-compose.yml up -d neo4j
    python -m backend.datasets.generate_synthetic_data --persons 5000 --crimes 20000 --reset
    GRAPH_BACKEND=neo4j python backend/scripts/stress_test_graph.py

What it measures:
    - Graph build/connection time
    - find_repeat_offenders / find_associates / find_financial_network /
      find_location_clusters / find_connection latency at scale
    - Compares NetworkX vs Neo4j on the SAME dataset size, since the
      GraphIntelligenceService interface (backend/graph/service.py) makes
      both backends interchangeable — useful to know when NetworkX
      (in-memory, rebuilt every request — see FINDINGS.md "Performance")
      stops being viable and Neo4j becomes necessary.
"""

import os
import time
import statistics

from backend.database.config import SessionLocal
from backend.database.models import Person
from backend.graph.service import get_graph_service


def timed(label, fn, repeats=5):
    samples = []
    result = None
    for _ in range(repeats):
        start = time.perf_counter()
        result = fn()
        samples.append((time.perf_counter() - start) * 1000)
    print(f"{label:45s} min={min(samples):8.2f}ms  median={statistics.median(samples):8.2f}ms  max={max(samples):8.2f}ms")
    return result


def run(backend_name: str):
    print(f"\n=== backend={backend_name} ===")
    session = SessionLocal()
    try:
        build_start = time.perf_counter()
        graph_service = get_graph_service(backend=backend_name, session=session)
        print(f"{'graph build/connect':45s} {(time.perf_counter() - build_start) * 1000:8.2f}ms")

        sample_person = session.query(Person).first()
        if sample_person is None:
            print("No persons in DB — generate a dataset first (see module docstring).")
            return

        timed("find_repeat_offenders(min_crimes=3, limit=200)",
              lambda: graph_service.find_repeat_offenders(min_crimes=3, limit=200))
        timed("find_associates(sample_person)",
              lambda: graph_service.find_associates(sample_person.id, limit=50))
        timed("find_location_clusters(top_n=20)",
              lambda: graph_service.find_location_clusters(top_n=20))
        timed("get_metrics()",
              lambda: graph_service.get_metrics())

        other = session.query(Person).offset(200).first() or sample_person
        timed("find_connection(a, b, max_hops=6)",
              lambda: graph_service.find_connection(sample_person.id, other.id, max_hops=6))
    finally:
        session.close()


if __name__ == "__main__":
    requested = os.getenv("GRAPH_BACKEND")
    backends = [requested] if requested else ["networkx"]
    for b in backends:
        run(b)
    if not requested:
        print("\nTip: re-run with GRAPH_BACKEND=neo4j (after docker-compose up) to compare.")
