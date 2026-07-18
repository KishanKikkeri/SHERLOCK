"""
SHERLOCK — Stage E6 (Operational Security) validation.

Run:  python validate_stage_e6.py
"""

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


def run_part1():
    divider("Part 1 — headers, request IDs, health, CORS default (default config)")

    from fastapi.testclient import TestClient
    from backend.app.main import app

    client = TestClient(app)

    resp = client.get("/health")
    assert_(resp.status_code == 200, "GET /health still returns 200")
    body = resp.json()
    assert_(body["status"] == "operational" and body["system"] == "SHERLOCK",
            "the original /health contract (status, system) is unchanged")
    assert_(set(body["components"].keys()) == {"security", "database", "storage", "translation", "voice"},
            "the new components block covers exactly the 5 subsystems the brief names")
    assert_(body["components"]["database"]["status"] == "ok", "database health check passes against the real DB")

    # --- security headers ------------------------------------------------
    assert_(resp.headers.get("x-content-type-options") == "nosniff", "X-Content-Type-Options header is present")
    assert_(resp.headers.get("x-frame-options") == "DENY", "X-Frame-Options header is present")
    assert_(resp.headers.get("referrer-policy") == "no-referrer", "Referrer-Policy header is present")

    # --- request/correlation IDs -------------------------------------------
    assert_("x-request-id" in resp.headers, "X-Request-ID is generated and returned")
    assert_("x-correlation-id" in resp.headers, "X-Correlation-ID is generated and returned")
    assert_("x-response-time-ms" in resp.headers, "X-Response-Time-Ms is present")

    resp2 = client.get("/health", headers={"X-Correlation-ID": "test-correlation-abc"})
    assert_(resp2.headers.get("x-correlation-id") == "test-correlation-abc",
            "a caller-supplied X-Correlation-ID is forwarded rather than overwritten")

    resp3 = client.get("/health")
    assert_(resp.headers["x-request-id"] != resp3.headers["x-request-id"],
            "two separate requests get two different request IDs")

    # --- CORS default (wide open, unchanged from pre-E6) --------------------
    resp4 = client.options("/health", headers={
        "Origin": "https://example.com",
        "Access-Control-Request-Method": "GET",
    })
    assert_(resp4.headers.get("access-control-allow-origin") in ("*", "https://example.com"),
            "CORS default still allows any origin, matching pre-Stage-E6 behavior")


def run_part2():
    divider("Part 2 — configured CORS/trusted-hosts restriction (subprocess)")

    script = textwrap.dedent("""
        from fastapi.testclient import TestClient
        from backend.app.main import app

        client = TestClient(app)
        resp = client.get("/health", headers={"Origin": "https://not-allowed.example.com"})
        print("STATUS", resp.status_code)
        cors_header = resp.headers.get("access-control-allow-origin")
        print("CORS_HEADER", cors_header)
        assert resp.status_code == 200, "GET /health itself still works regardless of CORS origin restriction"
        assert cors_header != "https://not-allowed.example.com", "a non-allowed origin is not echoed back"
        print("PART2_OK")
    """)

    env = os.environ.copy()
    env["SHERLOCK_CORS_ORIGINS"] = "https://sherlock-frontend.example.com"
    env["PYTHONPATH"] = "."

    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    print(textwrap.indent(result.stdout, "  "))
    if result.returncode != 0 or "PART2_OK" not in result.stdout:
        print(textwrap.indent(result.stderr, "  "))
        raise AssertionError("Configured CORS restriction check failed.")


def run_part3():
    divider("Part 3 — rate limiting (enabled via env, subprocess)")

    script = textwrap.dedent("""
        from fastapi.testclient import TestClient
        from backend.database.config import SessionLocal, Base, engine
        from backend.database.models import User, Role, UserRole, SystemRole
        from backend.security.passwords import hash_password
        from backend.security.seed import seed_roles
        from backend.app.main import app

        Base.metadata.create_all(engine)
        db = SessionLocal()
        seed_roles(db)
        role = db.query(Role).filter(Role.name == SystemRole.INVESTIGATOR).first()
        u = User(username="rl_user", password_hash=hash_password("SuperSecret123!"))
        db.add(u); db.flush()
        db.add(UserRole(user_id=u.id, role_id=role.id))
        db.commit()

        client = TestClient(app)
        statuses = []
        for _ in range(10):
            resp = client.post("/auth/login", json={"username": "rl_user", "password": "wrong-password"})
            statuses.append(resp.status_code)

        print("STATUSES", statuses)
        assert 429 in statuses, f"expected at least one 429 (rate limited) response, got {statuses}"
        print("PART3_OK")
    """)

    env = os.environ.copy()
    env["SHERLOCK_AUTH_ENABLED"] = "true"
    env["SHERLOCK_RATE_LIMIT_ENABLED"] = "true"
    env["SHERLOCK_LOGIN_RATE_LIMIT"] = "3/minute"
    env["SHERLOCK_JWT_SECRET"] = "stage-e6-validation-secret-key-0123456789abcdef"
    env["PYTHONPATH"] = "."
    env["DATABASE_URL"] = "sqlite:///" + os.path.abspath("validate_e6_ratelimit.db")

    if os.path.exists("validate_e6_ratelimit.db"):
        os.remove("validate_e6_ratelimit.db")

    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    print(textwrap.indent(result.stdout, "  "))
    if result.returncode != 0 or "PART3_OK" not in result.stdout:
        print(textwrap.indent(result.stderr, "  "))
        raise AssertionError("Rate limiting check failed.")


def run_part4():
    divider("Part 4 — rate limiting disabled by default (regression)")

    script = textwrap.dedent("""
        from fastapi.testclient import TestClient
        from backend.database.config import SessionLocal, Base, engine
        from backend.database.models import User, Role, UserRole, SystemRole
        from backend.security.passwords import hash_password
        from backend.security.seed import seed_roles
        from backend.app.main import app

        Base.metadata.create_all(engine)
        db = SessionLocal()
        seed_roles(db)
        role = db.query(Role).filter(Role.name == SystemRole.INVESTIGATOR).first()
        u = User(username="rl_default_user", password_hash=hash_password("SuperSecret123!"))
        db.add(u); db.flush()
        db.add(UserRole(user_id=u.id, role_id=role.id))
        db.commit()

        client = TestClient(app)
        statuses = []
        for _ in range(10):
            resp = client.post("/auth/login", json={"username": "rl_default_user", "password": "wrong-password"})
            statuses.append(resp.status_code)

        print("STATUSES", statuses)
        assert 429 not in statuses, f"rate limiting must be OFF by default, got {statuses}"
        assert all(s == 401 for s in statuses), "all 10 rapid attempts are plain 401s with no rate limiting configured"
        print("PART4_OK")
    """)

    env = os.environ.copy()
    env["SHERLOCK_AUTH_ENABLED"] = "true"
    env["SHERLOCK_JWT_SECRET"] = "stage-e6-validation-secret-key-0123456789abcdef"
    env["PYTHONPATH"] = "."
    env["DATABASE_URL"] = "sqlite:///" + os.path.abspath("validate_e6_no_ratelimit.db")

    if os.path.exists("validate_e6_no_ratelimit.db"):
        os.remove("validate_e6_no_ratelimit.db")

    result = subprocess.run([sys.executable, "-c", script], env=env, capture_output=True, text=True)
    print(textwrap.indent(result.stdout, "  "))
    if result.returncode != 0 or "PART4_OK" not in result.stdout:
        print(textwrap.indent(result.stderr, "  "))
        raise AssertionError("Rate-limit-disabled-by-default regression check failed.")


def main():
    run_part1()
    run_part2()
    run_part3()
    run_part4()
    divider("STAGE E6 VALIDATION: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
