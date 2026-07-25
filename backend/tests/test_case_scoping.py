"""
SHERLOCK — case-scoping regression test.

Covers the v3 -> v5 merge restoration: GET /conversation/cases and
PATCH /sessions/{id}/case, plus the DatabaseService methods behind them
(list_cases, update_session_case). This feature existed in v3, was
silently dropped in v5 (service methods, both API endpoints, and the
frontend hooks all missing), and was restored during the merge — this
test exists so a future refactor can't drop it again without a test
failure.
"""

from backend.database.models import FIR


def test_list_cases_endpoint_returns_seeded_firs(api_client, db_session):
    resp = api_client.get("/conversation/cases")
    assert resp.status_code == 200
    cases = resp.json()
    assert isinstance(cases, list)
    assert len(cases) > 0
    first = cases[0]
    assert set(first.keys()) == {
        "fir_id", "fir_number", "status", "crime_type", "district", "filed_date",
    }
    # Matches what's actually in the DB, not just a well-shaped response.
    seeded_fir = db_session.query(FIR).order_by(FIR.filed_date.desc()).first()
    assert first["fir_id"] == seeded_fir.id


def test_list_cases_search_filters_by_fir_number(api_client, db_session):
    any_fir = db_session.query(FIR).first()
    resp = api_client.get(f"/conversation/cases?search={any_fir.fir_number}")
    assert resp.status_code == 200
    cases = resp.json()
    assert any(c["fir_number"] == any_fir.fir_number for c in cases)


def test_set_and_clear_session_case_scope(api_client, db_session):
    fir = db_session.query(FIR).first()
    assert fir is not None

    opened = api_client.post("/sessions", json={"title": "Case-scope smoke test session"})
    assert opened.status_code == 200
    session_id = opened.json()["id"]

    # Bind to a case.
    bound = api_client.patch(f"/sessions/{session_id}/case", json={"fir_id": fir.id})
    assert bound.status_code == 200
    assert bound.json()["fir_id"] == fir.id

    fetched = api_client.get(f"/sessions/{session_id}")
    assert fetched.status_code == 200
    assert fetched.json()["fir_id"] == fir.id

    # Clear back to "All Cases".
    cleared = api_client.patch(f"/sessions/{session_id}/case", json={"fir_id": None})
    assert cleared.status_code == 200
    assert cleared.json()["fir_id"] is None


def test_set_session_case_rejects_unknown_fir(api_client):
    opened = api_client.post("/sessions", json={"title": "Bad case-scope smoke test session"})
    session_id = opened.json()["id"]

    resp = api_client.patch(f"/sessions/{session_id}/case", json={"fir_id": 999999999})
    assert resp.status_code == 422


def test_set_session_case_unknown_session_returns_404(api_client, db_session):
    fir = db_session.query(FIR).first()
    resp = api_client.patch("/sessions/999999999/case", json={"fir_id": fir.id})
    assert resp.status_code == 404
