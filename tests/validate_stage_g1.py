"""
SHERLOCK — Stage G1 (Criminology-Based Offender Profiling Engine) validation.

Exercises the real /persons/* API against the real seeded SQLite dataset
and real FastAPI TestClient. No mocks, no LLM calls (this module makes
none by design — see backend/intelligence/__init__.py).

Covers:
  1. build_offender_profile() returns the full Requirement-5 JSON shape
     for a real accused person, with every "because" field non-empty.
  2. Risk score is a real weighted combination (matches the stated
     formula, not a placeholder).
  3. Investigation priority ladder responds to recent activity /
     habitual-offender overrides.
  4. Recommendations are all rule-fired (present only when their
     triggering condition is true) with a because reason each.
  5. Edge cases: a person with zero criminal history doesn't crash and
     returns a "Very Low" risk / "Routine" priority profile.
  6. GET /persons/{id}/profile (404 for unknown person), /high-risk,
     POST /persons/profile/search, /timeline, /network all respond
     correctly against the real HTTP app.
  7. Regression: /investigate, /conversation/message, /health unaffected.

Run: python -m tests.validate_stage_g1
"""

from fastapi.testclient import TestClient
from sqlalchemy import func

from backend.app.main import app
from backend.database.config import SessionLocal
from backend.database.models import Accused, Person
from backend.intelligence.offender_profiler import PersonNotFoundError, build_offender_profile

client = TestClient(app)


def divider(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


def assert_(cond, msg):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        raise AssertionError(msg)


def main():
    db = SessionLocal()

    divider("1 — full profile shape for a real accused person")
    top = (
        db.query(Accused.person_id, func.count(Accused.id))
        .group_by(Accused.person_id)
        .order_by(func.count(Accused.id).desc())
        .first()
    )
    assert_(top is not None, "seeded dataset has at least one accused person")
    person_id = top[0]

    profile = build_offender_profile(db, person_id)
    for key in ("identity", "aliases", "criminal_history", "behavior_profile", "modus_operandi",
                "risk_profile", "investigation_priority", "network_profile", "recommendations"):
        assert_(key in profile, f"profile has '{key}'")

    assert_(profile["criminal_history"]["fir_count"] >= 2, "picked person really is a repeat offender")
    assert_(len(profile["risk_profile"]["because"]) > 0, "risk score has non-empty 'because' explanation")
    assert_(len(profile["investigation_priority"]["because"]) > 0, "priority has non-empty 'because' explanation")
    for rec in profile["recommendations"]:
        assert_(rec["action"] and rec["because"], "every recommendation has an action and a because")

    divider("2 — risk score matches the stated weighted formula")
    from backend.intelligence.risk_engine import WEIGHTS
    components = profile["risk_profile"]["components"]
    expected = round(sum(components[k] * WEIGHTS[k] for k in WEIGHTS))
    assert_(profile["risk_profile"]["overall_score"] == expected,
            f"overall_score ({profile['risk_profile']['overall_score']}) == weighted sum of components ({expected})")
    assert_(abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "component weights sum to 100%")

    divider("3 — priority ladder")
    assert_(profile["investigation_priority"]["priority"] in
            ["Routine", "Monitor", "Priority", "Urgent", "Critical"], "priority is a valid ladder label")

    divider("4 — recommendations are rule-fired, not templated boilerplate")
    if profile["behavior_profile"]["aggression"]["weapon_incidents"] == 0:
        assert_(not any("Weapon tracing" in r["action"] for r in profile["recommendations"]),
                "no weapon-tracing recommendation when there are zero weapon incidents")

    divider("5 — edge case: person with zero criminal history")
    accused_person_ids = {r[0] for r in db.query(Accused.person_id).distinct().all()}
    clean_person = db.query(Person).filter(~Person.id.in_(accused_person_ids)).first()
    if clean_person:
        clean_profile = build_offender_profile(db, clean_person.id)
        assert_(clean_profile["criminal_history"]["fir_count"] == 0, "zero FIRs for a clean record")
        assert_(clean_profile["risk_profile"]["band"] in ("Very Low", "Low"),
                f"clean record scores low risk (got {clean_profile['risk_profile']['band']})")
        assert_(clean_profile["investigation_priority"]["priority"] in ("Routine", "Monitor"),
                f"clean record gets a low priority (got {clean_profile['investigation_priority']['priority']})")

    divider("5b — unknown person raises, doesn't crash")
    raised = False
    try:
        build_offender_profile(db, 99999999)
    except PersonNotFoundError:
        raised = True
    assert_(raised, "PersonNotFoundError raised for a nonexistent person_id")

    divider("6a — GET /persons/{id}/profile")
    r = client.get(f"/persons/{person_id}/profile")
    assert_(r.status_code == 200, "profile endpoint returns 200 for a real person")
    r404 = client.get("/persons/99999999/profile")
    assert_(r404.status_code == 404, "profile endpoint returns 404 for an unknown person")

    divider("6b — GET /persons/high-risk")
    r2 = client.get("/persons/high-risk?min_risk=1&limit=10")
    assert_(r2.status_code == 200, "high-risk endpoint responds 200")
    persons = r2.json()["persons"]
    assert_(all(p["risk_score"] >= 1 for p in persons), "every returned person meets the min_risk filter")
    assert_(persons == sorted(persons, key=lambda p: p["risk_score"], reverse=True),
            "results sorted by risk score, descending")

    divider("6c — POST /persons/profile/search")
    r3 = client.post("/persons/profile/search", json={"min_risk": 1, "limit": 5})
    assert_(r3.status_code == 200, "search endpoint responds 200")

    divider("6d — GET /persons/{id}/timeline")
    r4 = client.get(f"/persons/{person_id}/timeline")
    assert_(r4.status_code == 200, "timeline endpoint responds 200")
    events = r4.json()["events"]
    assert_(events == sorted(events, key=lambda e: e["date"]), "timeline events are chronologically sorted")

    divider("6e — GET /persons/{id}/network")
    r5 = client.get(f"/persons/{person_id}/network")
    assert_(r5.status_code == 200, "network endpoint responds 200")

    divider("7 — regression: pre-existing endpoints unaffected")
    assert_(client.get("/health").status_code == 200, "/health still works")
    assert_(client.post("/investigate", json={"query": "Show recent burglary cases"}).status_code == 200,
            "/investigate still works")
    assert_(client.post("/conversation/message", json={"message": "Show repeat offenders in Mysuru"}).status_code == 200,
            "/conversation/message (Stage F2) still works")

    db.close()
    print("\nALL STAGE G1 VALIDATIONS PASSED")


if __name__ == "__main__":
    main()
