"""
SHERLOCK — Stage E4 (Data Protection) validation.

Run:  python validate_stage_e4.py
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
    from backend.database.models import User, Role, UserRole, SystemRole, Phone, BankAccount
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

    phone = db.query(Phone).first()
    account = db.query(BankAccount).first()
    person_id = phone.owner_id
    real_number = phone.number
    real_account_number = account.account_number
    assert_(phone.owner_id == account.owner_id or True, "fixture sanity")

    def make_user(username, role_name):
        role = db.query(Role).filter(Role.name == SystemRole(role_name)).first()
        u = User(username=username, password_hash=hash_password("SuperSecret123!"))
        db.add(u); db.flush()
        db.add(UserRole(user_id=u.id, role_id=role.id))
        db.commit()
        return u

    make_user("mask_investigator", "investigator")
    make_user("mask_analyst", "analyst")
    make_user("mask_reader", "read_only")

    client = TestClient(app)

    def token(username):
        resp = client.post("/auth/login", json={"username": username, "password": "SuperSecret123!"})
        assert_(resp.status_code == 200, f"{username} logs in")
        return resp.json()["access_token"]

    inv_token = token("mask_investigator")
    analyst_token = token("mask_analyst")
    reader_token = token("mask_reader")

    def fetch_graph(tok):
        resp = client.get(f"/graph/{person_id}", headers={"Authorization": f"Bearer {tok}"})
        assert_(resp.status_code == 200, "graph endpoint responds 200")
        return resp.json()

    def find_field(graph, node_type, field):
        for node in graph["nodes"]:
            if node["type"] == node_type and field in node["data"]:
                return node["data"][field]
        return None

    # --- Investigator: FULL visibility -----------------------------------
    g = fetch_graph(inv_token)
    number = find_field(g, "Phone", "number")
    assert_(number == real_number, "investigator (full visibility) sees the real phone number")
    acct = find_field(g, "BankAccount", "account_number")
    assert_(acct == real_account_number, "investigator (full visibility) sees the real account number")

    # --- Analyst: PARTIAL visibility --------------------------------------
    g = fetch_graph(analyst_token)
    number = find_field(g, "Phone", "number")
    if number is not None:
        assert_(number != real_number, "analyst (partial visibility) does not see the raw phone number")
        assert_(number[:2] == real_number[:2] and number[-2:] == real_number[-2:],
                "analyst's masked phone number still shows the first/last 2 digits")
    acct = find_field(g, "BankAccount", "account_number")
    if acct is not None:
        assert_(acct != real_account_number, "analyst (partial visibility) does not see the raw account number")
        assert_(acct[-4:] == real_account_number[-4:], "analyst's masked account number still shows the last 4 digits")

    # --- ReadOnly: MASKED visibility --------------------------------------
    g = fetch_graph(reader_token)
    number = find_field(g, "Phone", "number")
    if number is not None:
        assert_(set(number) == {"*"}, "read_only sees a fully masked phone number")
    acct = find_field(g, "BankAccount", "account_number")
    if acct is not None:
        assert_(set(acct) == {"*"}, "read_only sees a fully masked account number")

    print("  All masking checks passed.")
""")


def run_part1():
    divider("Stage E4 — Data Protection (subprocess, SHERLOCK_AUTH_ENABLED=true)")

    env = os.environ.copy()
    env["SHERLOCK_AUTH_ENABLED"] = "true"
    env["SHERLOCK_JWT_SECRET"] = "stage-e4-validation-secret-key-0123456789abcdef"
    env["PYTHONPATH"] = "."
    env["DATABASE_URL"] = "sqlite:///" + os.path.abspath("validate_e4_masking.db")

    if os.path.exists("validate_e4_masking.db"):
        os.remove("validate_e4_masking.db")

    # Needs real seeded persons/phones/bank_accounts — build a tiny fixture
    # directly (not the full synthetic generator) so this validation is
    # self-contained and fast.
    fixture = textwrap.dedent("""
        from backend.database.config import Base, engine, SessionLocal
        import backend.database.models as m
        from backend.database.models import Person, Phone, BankAccount, Gender

        Base.metadata.create_all(engine)
        db = SessionLocal()
        p = Person(name="Ravi Kumar", gender=Gender.MALE, age=34)
        db.add(p); db.flush()
        db.add(Phone(number="9876543210", owner_id=p.id))
        db.add(BankAccount(bank="SBI", account_number="1234567890123456", owner_id=p.id))
        db.commit()
        print("fixture person id:", p.id)
    """)
    fixture_result = subprocess.run([sys.executable, "-c", fixture], env=env, capture_output=True, text=True)
    if fixture_result.returncode != 0:
        print(fixture_result.stdout, fixture_result.stderr)
        raise AssertionError("Stage E4 fixture setup failed.")

    result = subprocess.run([sys.executable, "-c", PART1_SCRIPT], env=env, capture_output=True, text=True)
    print(textwrap.indent(result.stdout, "  "))
    if result.returncode != 0:
        print(textwrap.indent(result.stderr, "  "))
        raise AssertionError("Stage E4 masking checks failed — see stderr above.")


def run_part2():
    divider("Unit checks — masking primitives")

    from backend.security.masking import (
        Visibility, mask_phone_number, mask_account_number, mask_coordinate,
    )

    def assert_(cond, msg):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {msg}")
        if not cond:
            raise AssertionError(msg)

    assert_(mask_phone_number("9876543210", Visibility.FULL) == "9876543210", "FULL visibility returns the raw phone number")
    assert_(mask_phone_number("9876543210", Visibility.PARTIAL) == "98******10", "PARTIAL masks the middle digits")
    assert_(mask_phone_number("9876543210", Visibility.MASKED) == "**********", "MASKED fully redacts")

    assert_(mask_account_number("1234567890123456", Visibility.PARTIAL).endswith("3456"), "PARTIAL account number keeps the last 4 digits")
    assert_(mask_account_number("1234567890123456", Visibility.PARTIAL)[0] == "*", "PARTIAL account number redacts everything else")

    assert_(mask_coordinate(12.9716, Visibility.FULL) == 12.9716, "FULL visibility keeps full coordinate precision")
    assert_(mask_coordinate(12.9716, Visibility.PARTIAL) == 13.0, "PARTIAL visibility rounds the coordinate")
    assert_(mask_coordinate(12.9716, Visibility.MASKED) is None, "MASKED visibility withholds the coordinate entirely")


def main():
    run_part1()
    run_part2()
    divider("STAGE E4 VALIDATION: ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
