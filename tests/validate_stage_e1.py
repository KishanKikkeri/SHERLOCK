"""
SHERLOCK — Stage E1 (Authentication) validation.

Exercises real HTTP routes via FastAPI's TestClient against a real SQLite
database. No mocks. Two passes:

  Part 1 — SHERLOCK_AUTH_ENABLED unset (default / "false"): confirms
           every pre-Stage-E endpoint (and /auth/me itself) keeps working
           with zero login, proving Golden Rule 4 ("if authentication is
           disabled ... everything should continue working exactly like
           today").

  Part 2 — SHERLOCK_AUTH_ENABLED=true: full login / refresh / logout /
           expired-token / revoked-token lifecycle against real DB rows.

Because AUTH_ENABLED is read once at import time in
backend/security/config.py, Part 2 runs in a subprocess with the env var
set, rather than trying to flip a module-level constant mid-process.

Run:  python validate_stage_e1.py
"""

import json
import os
import subprocess
import sys
import textwrap


def divider(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


def assert_(cond, msg):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        raise AssertionError(msg)


# ---------------------------------------------------------------------------
# Part 1 — auth disabled (default): existing behaviour is unchanged
# ---------------------------------------------------------------------------

def run_part1():
    divider("Part 1 — SHERLOCK_AUTH_ENABLED unset (default)")

    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    resp = client.get("/health")
    assert_(resp.status_code == 200, "GET /health still works with no token")

    resp = client.get("/metrics")
    assert_(resp.status_code == 200, "GET /metrics (Stage A/B) still works with no token")

    # /auth/me is new in Stage E1, but must resolve to the synthetic
    # "system" identity rather than demanding a login, since AUTH_ENABLED
    # is false.
    resp = client.get("/auth/me")
    assert_(resp.status_code == 200, "GET /auth/me works with no token when auth is disabled")
    body = resp.json()
    assert_(body["username"] == "system", "identity reported is the synthetic system user")
    assert_(len(body["roles"]) == 6, "system identity is granted all 6 SystemRole values")

    # /auth/login still functions even when AUTH_ENABLED=false — tokens
    # can be issued, they're just not required by anything yet.
    resp = client.post("/auth/login", json={"username": "nobody", "password": "wrongpass123"})
    assert_(resp.status_code == 401, "POST /auth/login still rejects bad credentials")

    print("  Part 1 complete: zero-config behaviour is unchanged.")


# ---------------------------------------------------------------------------
# Part 2 — auth enabled: full token lifecycle (runs in a subprocess so
# AUTH_ENABLED, read at import time, actually takes effect)
# ---------------------------------------------------------------------------

PART2_SCRIPT = textwrap.dedent("""
    import sys
    from fastapi.testclient import TestClient

    from backend.database.config import SessionLocal, Base, engine
    from backend.database.models import User, Role, UserRole, RefreshToken, SystemRole
    from backend.security.passwords import hash_password
    from backend.security.seed import seed_roles
    from backend.app.main import app
    import time

    def assert_(cond, msg):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {msg}")
        if not cond:
            raise AssertionError(msg)

    Base.metadata.create_all(engine)
    db = SessionLocal()
    seed_roles(db)

    investigator_role = db.query(Role).filter(Role.name == SystemRole.INVESTIGATOR).first()
    user = User(username="officer.rao", password_hash=hash_password("CorrectHorseBattery9"))
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=investigator_role.id))
    db.commit()

    client = TestClient(app)

    # --- positive: login ---------------------------------------------
    resp = client.post("/auth/login", json={"username": "officer.rao", "password": "CorrectHorseBattery9"})
    assert_(resp.status_code == 200, "login with correct credentials succeeds")
    tokens = resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    assert_(bool(access_token) and bool(refresh_token), "login response includes both tokens")

    # --- negative: wrong password --------------------------------------
    resp = client.post("/auth/login", json={"username": "officer.rao", "password": "wrong"})
    assert_(resp.status_code == 401, "login with wrong password is rejected")

    # --- negative: unknown user -----------------------------------------
    resp = client.post("/auth/login", json={"username": "ghost", "password": "whatever123"})
    assert_(resp.status_code == 401, "login with unknown username is rejected")

    # --- positive: an unauthenticated request to a protected identity route is rejected
    resp = client.get("/auth/me")
    assert_(resp.status_code == 401, "GET /auth/me without a token is rejected when auth is enabled")

    # --- positive: authenticated request succeeds -----------------------
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert_(resp.status_code == 200, "GET /auth/me with a valid token succeeds")
    me = resp.json()
    assert_(me["username"] == "officer.rao", "identity matches the logged-in user")
    assert_(me["roles"] == ["investigator"], "roles reflect the granted role")

    # --- negative: garbage token ------------------------------------------
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert_(resp.status_code == 401, "a malformed/garbage bearer token is rejected")

    # --- positive: refresh rotates the token pair ------------------------
    resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert_(resp.status_code == 200, "refresh with a valid refresh token succeeds")
    new_tokens = resp.json()
    assert_(new_tokens["access_token"] != access_token, "refresh issues a new access token")
    assert_(new_tokens["refresh_token"] != refresh_token, "refresh rotates the refresh token")

    # --- negative: the OLD refresh token is now revoked (rotation) -------
    resp = client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert_(resp.status_code == 401, "a replayed (already-rotated) refresh token is rejected")

    # --- positive: logout revokes the current refresh token ---------------
    resp = client.post("/auth/logout", json={"refresh_token": new_tokens["refresh_token"]})
    assert_(resp.status_code == 200, "logout succeeds")

    # --- negative: revoked refresh token can no longer be used ------------
    resp = client.post("/auth/refresh", json={"refresh_token": new_tokens["refresh_token"]})
    assert_(resp.status_code == 401, "a revoked refresh token is rejected after logout")

    # --- negative: expired access token --------------------------------
    from backend.security import jwt as jwt_mod
    import jwt as pyjwt
    from datetime import datetime, timedelta, timezone
    expired_payload = {
        "sub": str(user.id), "username": user.username, "roles": ["investigator"],
        "iat": datetime.now(timezone.utc) - timedelta(minutes=30),
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        "type": "access",
    }
    expired_token = pyjwt.encode(expired_payload, jwt_mod.JWT_SECRET_KEY, algorithm=jwt_mod.JWT_ALGORITHM)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert_(resp.status_code == 401, "an expired access token is rejected")

    # --- regression: pre-Stage-E endpoints still work when authenticated --
    resp = client.get("/health", headers={"Authorization": f"Bearer {new_tokens['access_token']}"})
    assert_(resp.status_code == 200, "GET /health is unaffected by auth being enabled (not yet gated)")

    print("  Part 2 complete: full token lifecycle validated.")
""")


def run_part2():
    divider("Part 2 — SHERLOCK_AUTH_ENABLED=true (subprocess)")

    env = os.environ.copy()
    env["SHERLOCK_AUTH_ENABLED"] = "true"
    env["SHERLOCK_JWT_SECRET"] = "stage-e1-validation-secret-key-0123456789abcdef"
    env["PYTHONPATH"] = "."
    env["DATABASE_URL"] = "sqlite:///" + os.path.abspath("validate_e1_auth.db")

    if os.path.exists("validate_e1_auth.db"):
        os.remove("validate_e1_auth.db")

    result = subprocess.run(
        [sys.executable, "-c", PART2_SCRIPT],
        env=env, capture_output=True, text=True,
    )
    print(textwrap.indent(result.stdout, "  "))
    if result.returncode != 0:
        print(textwrap.indent(result.stderr, "  "))
        raise AssertionError("Part 2 (subprocess) failed — see stderr above.")


# ---------------------------------------------------------------------------
# Part 3 — password policy / hashing unit checks (no HTTP needed)
# ---------------------------------------------------------------------------

def run_part3():
    divider("Part 3 — password hashing")

    from backend.security.passwords import hash_password, verify_password, WeakPasswordError

    try:
        hash_password("short")
        assert_(False, "hash_password should reject passwords shorter than the minimum length")
    except WeakPasswordError:
        assert_(True, "hash_password rejects a too-short password")

    h = hash_password("a-reasonably-long-passphrase")
    assert_(verify_password("a-reasonably-long-passphrase", h), "verify_password accepts the correct password")
    assert_(not verify_password("wrong-passphrase-entirely", h), "verify_password rejects an incorrect password")
    assert_(h.startswith("$argon2id$"), "stored hash uses argon2id, never plain hashing")


def main():
    run_part1()
    run_part2()
    run_part3()
    divider("STAGE E1 VALIDATION: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
