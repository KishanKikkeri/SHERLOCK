"""
API-level tests for Priority 18-23 (Unified Graph Search & Navigation).

Covers: GET /graph/search, GET /graph/node/{node_type}/{entity_id}.
Runs against the same session-scoped synthetic dataset as test_api.py.
"""


def test_search_finds_person_by_exact_name(api_client, db_session):
    from backend.database.models import Person
    person = db_session.query(Person).first()
    assert person is not None

    resp = api_client.get("/graph/search", params={"q": person.name})
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] > 0
    top = body["results"][0]
    assert top["type"] == "Person"
    assert top["id"] == person.id
    assert top["score"] == 1.0


def test_search_finds_vehicle_by_normalized_plate(api_client, db_session):
    from backend.database.models import Vehicle
    vehicle = db_session.query(Vehicle).first()
    assert vehicle is not None

    # Spaces/dashes shouldn't matter — Priority 22 (fuzzy search: mixed
    # casing, extra spaces).
    messy = " ".join(vehicle.registration_number).lower()
    resp = api_client.get("/graph/search", params={"q": messy})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(r["type"] == "Vehicle" and r["id"] == vehicle.id and r["score"] == 1.0 for r in results)


def test_search_finds_fir_by_number(api_client, db_session):
    from backend.database.models import FIR
    fir = db_session.query(FIR).first()
    assert fir is not None

    resp = api_client.get("/graph/search", params={"q": fir.fir_number})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert any(r["type"] == "FIR" and r["id"] == fir.id for r in results)


def test_search_blank_query_rejected(api_client):
    resp = api_client.get("/graph/search", params={"q": "   "})
    assert resp.status_code == 422


def test_search_no_match_returns_empty_not_error(api_client):
    resp = api_client.get("/graph/search", params={"q": "zzzznonexistentquery9999"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["count"] == 0


def test_entity_subgraph_matches_legacy_person_route(api_client, db_session):
    """/graph/node/Person/{id} must return the same shape as the
    legacy /graph/{id} route it was generalized from."""
    from backend.database.models import Person
    person = db_session.query(Person).first()

    legacy = api_client.get(f"/graph/{person.id}")
    generic = api_client.get(f"/graph/node/Person/{person.id}")
    assert legacy.status_code == generic.status_code == 200
    assert legacy.json() == generic.json()


def test_entity_subgraph_supports_non_person_type(api_client, db_session):
    """Priority 21 — centering on a non-Person node (e.g. a Vehicle)
    must work, not just Person."""
    from backend.database.models import Vehicle
    vehicle = db_session.query(Vehicle).first()
    assert vehicle is not None

    resp = api_client.get(f"/graph/node/Vehicle/{vehicle.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["center"] == f"Vehicle:{vehicle.id}"
    assert any(n["id"] == f"Vehicle:{vehicle.id}" for n in body["nodes"])


def test_entity_subgraph_rejects_unknown_node_type(api_client):
    resp = api_client.get("/graph/node/NotARealType/1")
    assert resp.status_code == 422
