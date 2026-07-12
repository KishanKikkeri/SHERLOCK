"""
Graph Layer tests (checklist item 5).

Only exercises the NetworkX backend, since Neo4j requires a running
container. The Neo4j implementation (service_neo4j.py) shares the same
GraphIntelligenceService interface and dict-shaped return contract, so
these tests double as a spec for a parallel Neo4j test file once a
Neo4j instance is available in CI (see FINDINGS.md "Graph Layer").
"""


def test_get_metrics_shape(graph_service):
    metrics = graph_service.get_metrics()
    assert "nodes" in metrics and "relationships" in metrics
    assert isinstance(metrics["nodes"], dict)
    assert isinstance(metrics["relationships"], dict)
    assert sum(metrics["nodes"].values()) > 0


def test_find_repeat_offenders_ordering(graph_service):
    offenders = graph_service.find_repeat_offenders(min_crimes=1, limit=50)
    assert isinstance(offenders, list)
    for entry in offenders:
        assert {"person_id", "name", "crime_count"}.issubset(entry.keys())
    counts = [o["crime_count"] for o in offenders]
    assert counts == sorted(counts, reverse=True), "results must be ordered by crime_count desc"


def test_find_repeat_offenders_respects_min_crimes_threshold(graph_service):
    offenders = graph_service.find_repeat_offenders(min_crimes=3, limit=200)
    assert all(o["crime_count"] >= 3 for o in offenders)


def test_find_associates_shape(graph_service, db_session):
    from backend.database.models import Person
    person = db_session.query(Person).first()
    associates = graph_service.find_associates(person.id, limit=20)
    assert isinstance(associates, list)
    for entry in associates:
        assert {"associate_id", "name", "relation_type", "edge_type", "strength"}.issubset(entry.keys())
        assert entry["associate_id"] != person.id, "a person should never be their own associate"


def test_find_connection_same_person_is_trivial(graph_service, db_session):
    from backend.database.models import Person
    person = db_session.query(Person).first()
    result = graph_service.find_connection(person.id, person.id)
    assert result["found"] is True
    assert result["hops"] == 0


def test_find_connection_unreachable_pair_reports_not_found(graph_service):
    """
    Two IDs that don't exist in the graph at all should degrade to
    found=False rather than raising (e.g. KeyError from a raw NetworkX
    lookup). This is the kind of edge case the stabilization pass is
    meant to catch — run this before assuming it's safe.
    """
    result = graph_service.find_connection(999999998, 999999999)
    assert result["found"] is False


def test_find_location_clusters_ordering(graph_service):
    clusters = graph_service.find_location_clusters(top_n=10)
    counts = [c["count"] for c in clusters]
    assert counts == sorted(counts, reverse=True)
