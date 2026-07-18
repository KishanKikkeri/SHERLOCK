"""
SHERLOCK — Stage E5 (Governance & Retention) validation.

Run:  python validate_stage_e5.py
"""

import os
import subprocess
import sys
import textwrap


def divider(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


PART1_SCRIPT = textwrap.dedent("""
    from datetime import datetime, timedelta
    from fastapi.testclient import TestClient

    from backend.database.config import SessionLocal, Base, engine
    from backend.database.models import (
        User, Role, UserRole, SystemRole, InvestigationSession, ConversationTurn,
        AuditLog, InvestigationSessionStatus, InvestigationPriority,
    )
    from backend.security.passwords import hash_password
    from backend.security.seed import seed_roles
    from backend.security.retention import apply_retention_policy, SESSION_RETENTION_DAYS
    from backend.app.main import app

    def assert_(cond, msg):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {msg}")
        if not cond:
            raise AssertionError(msg)

    Base.metadata.create_all(engine)
    db = SessionLocal()
    seed_roles(db)

    admin_role = db.query(Role).filter(Role.name == SystemRole.ADMINISTRATOR).first()
    admin = User(username="gov_admin", password_hash=hash_password("SuperSecret123!"))
    db.add(admin); db.flush()
    db.add(UserRole(user_id=admin.id, role_id=admin_role.id))

    investigator_role = db.query(Role).filter(Role.name == SystemRole.INVESTIGATOR).first()
    investigator = User(username="gov_investigator", password_hash=hash_password("SuperSecret123!"))
    db.add(investigator); db.flush()
    db.add(UserRole(user_id=investigator.id, role_id=investigator_role.id))
    db.commit()

    now = datetime.utcnow()

    # A session closed long ago -> should be archived by the sweep.
    old_session = InvestigationSession(
        session_code="SESSION-E5-OLD", title="Old closed case",
        status=InvestigationSessionStatus.CLOSED, priority=InvestigationPriority.MEDIUM,
        opened_at=now - timedelta(days=SESSION_RETENTION_DAYS + 60),
        closed_at=now - timedelta(days=SESSION_RETENTION_DAYS + 30),
    )
    # A session closed recently -> should NOT be archived.
    recent_session = InvestigationSession(
        session_code="SESSION-E5-RECENT", title="Recently closed case",
        status=InvestigationSessionStatus.CLOSED, priority=InvestigationPriority.MEDIUM,
        opened_at=now - timedelta(days=10), closed_at=now - timedelta(days=1),
    )
    # A session that's still open -> should NEVER be auto-archived, no matter its age.
    ancient_open_session = InvestigationSession(
        session_code="SESSION-E5-OPEN", title="Still open, very old",
        status=InvestigationSessionStatus.OPEN, priority=InvestigationPriority.MEDIUM,
        opened_at=now - timedelta(days=SESSION_RETENTION_DAYS + 365),
    )
    db.add_all([old_session, recent_session, ancient_open_session])
    db.commit()

    old_turn = ConversationTurn(session_id=old_session.id, turn_index=0, raw_query="test query")
    db.add(old_turn)
    db.commit()

    old_audit_row = AuditLog(action="login", username="gov_investigator", success=True,
                              created_at=now - timedelta(days=3000))
    recent_audit_row = AuditLog(action="login", username="gov_investigator", success=True,
                                 created_at=now - timedelta(days=1))
    db.add_all([old_audit_row, recent_audit_row])
    db.commit()

    old_session_id, recent_session_id, ancient_open_session_id = old_session.id, recent_session.id, ancient_open_session.id
    old_turn_id = old_turn.id
    old_audit_id, recent_audit_id = old_audit_row.id, recent_audit_row.id

    client = TestClient(app)

    def token(username):
        resp = client.post("/auth/login", json={"username": username, "password": "SuperSecret123!"})
        assert_(resp.status_code == 200, f"{username} logs in")
        return resp.json()["access_token"]

    admin_token = token("gov_admin")
    inv_token = token("gov_investigator")

    # --- non-admin cannot view or run governance ---------------------------
    resp = client.get("/governance/retention-policy", headers={"Authorization": f"Bearer {inv_token}"})
    assert_(resp.status_code == 403, "investigator cannot view the retention policy (lacks administer_system)")

    resp = client.post("/governance/retention/run", headers={"Authorization": f"Bearer {inv_token}"})
    assert_(resp.status_code == 403, "investigator cannot run the retention sweep")

    # --- admin can view policy -----------------------------------------------
    resp = client.get("/governance/retention-policy", headers={"Authorization": f"Bearer {admin_token}"})
    assert_(resp.status_code == 200, "administrator can view the retention policy")
    policy = resp.json()
    assert_("no row is ever physically deleted" in policy["deletion_mode"], "policy explicitly states no physical deletion")

    # --- admin runs the sweep ------------------------------------------------
    resp = client.post("/governance/retention/run", headers={"Authorization": f"Bearer {admin_token}"})
    assert_(resp.status_code == 200, "administrator can run the retention sweep")
    result = resp.json()
    assert_(result["sessions_archived"] >= 1, "the sweep archived at least the one stale closed session")
    assert_(result["conversation_turns_archived"] >= 1, "the sweep archived the conversation turn belonging to the archived session")
    assert_(result["audit_rows_archived"] >= 1, "the sweep archived the one stale audit row")

    db.expire_all()

    # --- verify actual DB state: archived_at set, rows still present -------
    old_s = db.query(InvestigationSession).get(old_session_id)
    assert_(old_s.archived_at is not None, "the old closed session now has archived_at set")
    assert_(old_s is not None, "the old session row still exists in the DB (no physical delete)")

    recent_s = db.query(InvestigationSession).get(recent_session_id)
    assert_(recent_s.archived_at is None, "the recently-closed session was NOT archived (inside the retention window)")

    open_s = db.query(InvestigationSession).get(ancient_open_session_id)
    assert_(open_s.archived_at is None, "a still-open session is never auto-archived, regardless of age")
    assert_(open_s is not None, "the still-open session row still exists")

    old_t = db.query(ConversationTurn).get(old_turn_id)
    assert_(old_t is not None, "the conversation turn row still exists (no physical delete)")
    assert_(old_t.archived_at is not None, "the conversation turn belonging to an archived session is itself archived")

    old_a = db.query(AuditLog).get(old_audit_id)
    assert_(old_a is not None, "the old audit row still exists (no physical delete)")
    assert_(old_a.archived_at is not None, "the old audit row is archived")

    recent_a = db.query(AuditLog).get(recent_audit_id)
    assert_(recent_a.archived_at is None, "the recent audit row is NOT archived (inside the retention window)")

    # Archived audit rows remain fully queryable via GET /audit (archived != hidden).
    resp = client.get("/audit", params={"username": "gov_investigator"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert_(resp.status_code == 200, "GET /audit still works")
    assert_(any(r["id"] == old_audit_id for r in resp.json()["results"]),
            "an archived audit row is still returned by GET /audit — archived means eligible for cold storage, not hidden")

    # --- idempotency: running it again archives nothing new ----------------
    resp = client.post("/governance/retention/run", headers={"Authorization": f"Bearer {admin_token}"})
    result2 = resp.json()
    assert_(result2["sessions_archived"] == 0, "running the sweep again archives no additional sessions (idempotent)")
    assert_(result2["audit_rows_archived"] == 0, "running the sweep again archives no additional audit rows (idempotent)")

    print("  All governance/retention checks passed.")
""")


def run_part1():
    divider("Stage E5 — Governance & Retention (subprocess, SHERLOCK_AUTH_ENABLED=true)")

    env = os.environ.copy()
    env["SHERLOCK_AUTH_ENABLED"] = "true"
    env["SHERLOCK_JWT_SECRET"] = "stage-e5-validation-secret-key-0123456789abcdef"
    env["PYTHONPATH"] = "."
    env["DATABASE_URL"] = "sqlite:///" + os.path.abspath("validate_e5_governance.db")

    if os.path.exists("validate_e5_governance.db"):
        os.remove("validate_e5_governance.db")

    result = subprocess.run([sys.executable, "-c", PART1_SCRIPT], env=env, capture_output=True, text=True)
    print(textwrap.indent(result.stdout, "  "))
    if result.returncode != 0:
        print(textwrap.indent(result.stderr, "  "))
        raise AssertionError("Stage E5 governance checks failed — see stderr above.")


def run_part2():
    divider("Regression — SHERLOCK_AUTH_ENABLED unset: governance routes still degrade to open access")

    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    def assert_(cond, msg):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {msg}")
        if not cond:
            raise AssertionError(msg)

    resp = client.get("/governance/retention-policy")
    assert_(resp.status_code == 200, "GET /governance/retention-policy works with no token when auth is disabled")


def main():
    run_part1()
    run_part2()
    divider("STAGE E5 VALIDATION: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
