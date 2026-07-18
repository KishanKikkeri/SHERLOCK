"""
SHERLOCK — Stage E3 (Audit & Compliance) validation.

Run:  python validate_stage_e3.py
"""

import os
import subprocess
import sys
import textwrap


def divider(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


PART1_SCRIPT = textwrap.dedent("""
    from fastapi.testclient import TestClient

    from backend.database.config import SessionLocal, Base, engine
    from backend.database.models import User, Role, UserRole, SystemRole, AuditLog
    from backend.database.service import DatabaseService
    from backend.security.passwords import hash_password
    from backend.security.seed import seed_roles
    from backend.app.main import app

    def assert_(cond, msg):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {msg}")
        if not cond:
            raise AssertionError(msg)

    Base.metadata.create_all(engine)
    db = SessionLocal()
    seed_roles(db)

    def make_user(username, role_name):
        role = db.query(Role).filter(Role.name == SystemRole(role_name)).first()
        u = User(username=username, password_hash=hash_password("SuperSecret123!"))
        db.add(u); db.flush()
        db.add(UserRole(user_id=u.id, role_id=role.id))
        db.commit()
        return u

    admin = make_user("audit_admin", "administrator")
    investigator = make_user("audit_investigator", "investigator")
    readonly = make_user("audit_reader", "read_only")

    client = TestClient(app)

    def login(username, password="SuperSecret123!"):
        return client.post("/auth/login", json={"username": username, "password": password})

    def auth(token):
        return {"Authorization": f"Bearer {token}"}

    # --- successful login is audited ------------------------------------
    resp = login("audit_investigator")
    assert_(resp.status_code == 200, "investigator logs in")
    inv_token = resp.json()["access_token"]

    row_count_before = db.query(AuditLog).filter(AuditLog.action == "login", AuditLog.success == True).count()
    assert_(row_count_before >= 1, "a successful login wrote a LOGIN audit row")

    # --- failed login is audited -----------------------------------------
    resp = login("audit_investigator", password="WrongPassword!")
    assert_(resp.status_code == 401, "wrong password is rejected")
    failed_rows = db.query(AuditLog).filter(AuditLog.action == "login_failed").count()
    assert_(failed_rows >= 1, "a failed login wrote a LOGIN_FAILED audit row")

    # --- permission denial is audited -------------------------------------
    admin_resp = login("audit_admin")
    admin_token = admin_resp.json()["access_token"]

    svc = DatabaseService(db)
    session_row = svc.open_case(title="E3 validation case")
    sid = session_row.id

    resp = client.post(f"/sessions/{sid}/close", json={}, headers=auth(inv_token))
    # investigator HAS manage_case, so this should succeed - use read_only instead
    reader_resp = login("audit_reader")
    reader_token = reader_resp.json()["access_token"]
    resp = client.post(f"/sessions/{sid}/close", json={}, headers=auth(reader_token))
    assert_(resp.status_code == 403, "read_only is denied manage_case (as expected)")

    denied_rows = db.query(AuditLog).filter(AuditLog.action == "permission_denied").all()
    assert_(len(denied_rows) >= 1, "the permission denial wrote a PERMISSION_DENIED audit row")
    assert_(denied_rows[-1].username == "audit_reader", "the denial row is attributed to the correct user")
    assert_(denied_rows[-1].success is False, "a permission denial is recorded as unsuccessful")

    # --- investigation viewed / evidence viewed are audited ---------------
    resp = client.get(f"/sessions/{sid}", headers=auth(inv_token))
    assert_(resp.status_code == 200, "investigator can view the session")
    viewed_rows = db.query(AuditLog).filter(AuditLog.action == "investigation_viewed").count()
    assert_(viewed_rows >= 1, "viewing a session wrote an INVESTIGATION_VIEWED audit row")

    resp = client.get(f"/sessions/{sid}/board", headers=auth(inv_token))
    assert_(resp.status_code == 200, "investigator can view the board")
    evidence_rows = db.query(AuditLog).filter(AuditLog.action == "evidence_viewed").count()
    assert_(evidence_rows >= 1, "viewing the board wrote an EVIDENCE_VIEWED audit row")

    # --- role change is audited --------------------------------------------
    resp = client.post("/admin/users", json={"username": "audit_new_analyst", "password": "AnotherSecret456!",
                                              "roles": ["analyst"]}, headers=auth(admin_token))
    assert_(resp.status_code == 200, "admin creates a new user")
    new_id = resp.json()["id"]

    resp = client.post(f"/admin/users/{new_id}/roles", params={"role": "investigator"}, headers=auth(admin_token))
    assert_(resp.status_code == 200, "admin grants an additional role")
    role_change_rows = db.query(AuditLog).filter(AuditLog.action == "role_changed").count()
    assert_(role_change_rows >= 1, "granting a role wrote a ROLE_CHANGED audit row")

    # --- logout is audited ---------------------------------------------------
    refresh_token = login("audit_investigator").json()["refresh_token"]
    resp = client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert_(resp.status_code == 200, "logout succeeds")
    logout_rows = db.query(AuditLog).filter(AuditLog.action == "logout").count()
    assert_(logout_rows >= 1, "logout wrote a LOGOUT audit row")

    # --- GET /audit requires view_audit, filters correctly ------------------
    resp = client.get("/audit", headers=auth(inv_token))
    assert_(resp.status_code == 403, "investigator (lacks view_audit) cannot read the audit log")

    resp = client.get("/audit", headers=auth(admin_token))
    assert_(resp.status_code == 200, "administrator can read the audit log")
    body = resp.json()
    assert_(body["total"] >= 5, "audit log has accumulated multiple rows across this run")

    resp = client.get("/audit", params={"action": "role_changed"}, headers=auth(admin_token))
    assert_(resp.status_code == 200, "GET /audit accepts an action filter")
    assert_(all(r["action"] == "role_changed" for r in resp.json()["results"]), "action filter returns only matching rows")

    resp = client.get("/audit", params={"success": False}, headers=auth(admin_token))
    assert_(resp.status_code == 200, "GET /audit accepts a success filter")
    assert_(all(r["success"] is False for r in resp.json()["results"]), "success=false filter returns only failed events")

    print("  All audit checks passed.")
""")


def run_part1():
    divider("Stage E3 — Audit & Compliance (subprocess, SHERLOCK_AUTH_ENABLED=true)")

    env = os.environ.copy()
    env["SHERLOCK_AUTH_ENABLED"] = "true"
    env["SHERLOCK_JWT_SECRET"] = "stage-e3-validation-secret-key-0123456789abcdef"
    env["PYTHONPATH"] = "."
    env["DATABASE_URL"] = "sqlite:///" + os.path.abspath("validate_e3_audit.db")

    if os.path.exists("validate_e3_audit.db"):
        os.remove("validate_e3_audit.db")

    result = subprocess.run([sys.executable, "-c", PART1_SCRIPT], env=env, capture_output=True, text=True)
    print(textwrap.indent(result.stdout, "  "))
    if result.returncode != 0:
        print(textwrap.indent(result.stderr, "  "))
        raise AssertionError("Stage E3 audit checks failed — see stderr above.")


def run_part2():
    divider("Regression — SHERLOCK_AUTH_ENABLED unset: audit writes nothing new required, routes still work")

    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    def assert_(cond, msg):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {msg}")
        if not cond:
            raise AssertionError(msg)

    resp = client.get("/audit")
    assert_(resp.status_code == 200, "GET /audit works with no token when auth is disabled (system context passes view_audit)")


def main():
    run_part1()
    run_part2()
    divider("STAGE E3 VALIDATION: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
