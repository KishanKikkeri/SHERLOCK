"""
SHERLOCK — Stage E2 (Role Based Access Control) validation.

Runs with SHERLOCK_AUTH_ENABLED=true in a subprocess (permissions have no
teeth at all with auth disabled — that's Part 1's point, tested once and
not repeated per-role here). Creates one real user per SystemRole against
a real DB, logs each in for a real token, and checks what each role can
and cannot do against real routes.

Run:  python validate_stage_e2.py
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
    from backend.database.models import User, Role, UserRole, SystemRole
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
        db.add(u)
        db.flush()
        db.add(UserRole(user_id=u.id, role_id=role.id))
        db.commit()
        return u

    admin = make_user("admin1", "administrator")
    supervisor = make_user("supervisor1", "supervisor")
    investigator = make_user("investigator1", "investigator")
    analyst = make_user("analyst1", "analyst")
    policy_maker = make_user("policy1", "policy_maker")
    readonly = make_user("reader1", "read_only")

    client = TestClient(app)

    def login(username):
        resp = client.post("/auth/login", json={"username": username, "password": "SuperSecret123!"})
        assert_(resp.status_code == 200, f"login succeeds for {username}")
        return resp.json()["access_token"]

    tokens = {name: login(name) for name in
              ["admin1", "supervisor1", "investigator1", "analyst1", "policy1", "reader1"]}

    def auth(name):
        return {"Authorization": f"Bearer {tokens[name]}"}

    # Seed one real investigation session to exercise VIEW_CASE / MANAGE_CASE against.
    svc = DatabaseService(db)
    session_row = svc.open_case(title="E2 validation case")
    sid = session_row.id

    # --- VIEW_CASE: every role except none should be able to read -------
    for name in ["admin1", "supervisor1", "investigator1", "analyst1", "policy1", "reader1"]:
        resp = client.get(f"/sessions/{sid}", headers=auth(name))
        assert_(resp.status_code == 200, f"{name} (has view_case) can GET /sessions/{{id}}")

    # --- no token at all is rejected (auth is enabled) -------------------
    resp = client.get(f"/sessions/{sid}")
    assert_(resp.status_code == 401, "an unauthenticated request to a protected route is rejected")

    # --- MANAGE_CASE: read_only and policy_maker cannot close a session --
    resp = client.post(f"/sessions/{sid}/close", json={}, headers=auth("reader1"))
    assert_(resp.status_code == 403, "read_only cannot close a session (lacks manage_case)")

    resp = client.post(f"/sessions/{sid}/close", json={}, headers=auth("policy1"))
    assert_(resp.status_code == 403, "policy_maker cannot close a session (lacks manage_case)")

    # --- MANAGE_CASE: investigator and supervisor and admin all can ------
    resp = client.post(f"/sessions/{sid}/close", json={}, headers=auth("investigator1"))
    assert_(resp.status_code == 200, "investigator (has manage_case) can close a session")

    resp = client.post(f"/sessions/{sid}/reopen", json={}, headers=auth("supervisor1"))
    assert_(resp.status_code == 200, "supervisor (has manage_case) can reopen a session")

    # --- RUN_INVESTIGATION: read_only cannot ------------------------------
    resp = client.post("/investigate", json={"query": "Show repeat offenders"}, headers=auth("reader1"))
    assert_(resp.status_code == 403, "read_only cannot run an investigation (lacks run_investigation)")

    # --- RUN_INVESTIGATION: investigator can ------------------------------
    resp = client.post("/investigate", json={"query": "Show repeat offenders"}, headers=auth("investigator1"))
    assert_(resp.status_code == 200, "investigator can run an investigation")

    # --- EXPORT_PDF: policy_maker cannot (view_case + view_audit only) ---
    resp = client.post("/export/pdf", json={"final_report": {}}, headers=auth("policy1"))
    assert_(resp.status_code == 403, "policy_maker cannot export a PDF (lacks export_pdf)")

    # --- MANAGE_USERS: only Administrator ---------------------------------
    resp = client.get("/admin/users", headers=auth("investigator1"))
    assert_(resp.status_code == 403, "investigator cannot list users (lacks manage_users)")

    resp = client.get("/admin/users", headers=auth("admin1"))
    assert_(resp.status_code == 200, "administrator can list users")
    assert_(len(resp.json()) == 6, "admin/users lists all 6 seeded validation users")

    # --- Administrator can create + grant a role --------------------------
    resp = client.post("/admin/users", json={
        "username": "new.investigator", "password": "AnotherSecret456!", "roles": ["investigator"],
    }, headers=auth("admin1"))
    assert_(resp.status_code == 200, "administrator can create a new user")
    new_user_id = resp.json()["id"]
    assert_(resp.json()["roles"] == ["investigator"], "new user has the requested role")

    resp = client.post(f"/admin/users/{new_user_id}/roles", params={"role": "analyst"}, headers=auth("admin1"))
    assert_(resp.status_code == 200, "administrator can grant an additional role")
    assert_(set(resp.json()["roles"]) == {"investigator", "analyst"}, "user now has both roles")

    resp = client.delete(f"/admin/users/{new_user_id}/roles/analyst", headers=auth("admin1"))
    assert_(resp.status_code == 200, "administrator can revoke a role")
    assert_(resp.json()["roles"] == ["investigator"], "role was actually revoked")

    # --- non-admin cannot create users ------------------------------------
    resp = client.post("/admin/users", json={
        "username": "sneaky", "password": "ShouldNotWork123!",
    }, headers=auth("supervisor1"))
    assert_(resp.status_code == 403, "supervisor cannot create users (lacks manage_users)")

    # --- soft-delete only: deactivate, never physically delete ------------
    resp = client.post(f"/admin/users/{new_user_id}/deactivate", headers=auth("admin1"))
    assert_(resp.status_code == 200, "administrator can deactivate a user")
    assert_(resp.json()["is_active"] is False, "deactivated user is marked inactive")

    still_exists = db.query(User).get(new_user_id)
    assert_(still_exists is not None, "deactivated user row still exists in the DB (no physical delete)")

    # A deactivated account can no longer log in.
    resp = client.post("/auth/login", json={"username": "new.investigator", "password": "AnotherSecret456!"})
    assert_(resp.status_code == 401, "a deactivated account can no longer log in")

    print("  All RBAC checks passed.")
""")


def run_part1():
    divider("Stage E2 — RBAC (subprocess, SHERLOCK_AUTH_ENABLED=true)")

    env = os.environ.copy()
    env["SHERLOCK_AUTH_ENABLED"] = "true"
    env["SHERLOCK_JWT_SECRET"] = "stage-e2-validation-secret-key-0123456789abcdef"
    env["PYTHONPATH"] = "."
    env["DATABASE_URL"] = "sqlite:///" + os.path.abspath("validate_e2_rbac.db")

    if os.path.exists("validate_e2_rbac.db"):
        os.remove("validate_e2_rbac.db")

    result = subprocess.run([sys.executable, "-c", PART1_SCRIPT], env=env, capture_output=True, text=True)
    print(textwrap.indent(result.stdout, "  "))
    if result.returncode != 0:
        print(textwrap.indent(result.stderr, "  "))
        raise AssertionError("Stage E2 RBAC checks failed — see stderr above.")


def run_part2():
    divider("Regression — SHERLOCK_AUTH_ENABLED unset: RBAC has no effect")

    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    def assert_(cond, msg):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {msg}")
        if not cond:
            raise AssertionError(msg)

    resp = client.get("/sessions")
    assert_(resp.status_code == 200, "GET /sessions works with no token when auth is disabled")

    resp = client.get("/admin/users")
    assert_(resp.status_code == 200, "GET /admin/users (Administrator-only) also degrades to open access when auth is disabled")


def main():
    run_part1()
    run_part2()
    divider("STAGE E2 VALIDATION: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
