"""
Shared pytest fixtures for the SHERLOCK backend test suite.

Design notes (read before adding tests):

- `backend.database.config` reads DATABASE_URL and builds a module-level
  SQLAlchemy `engine` at IMPORT TIME. That means DATABASE_URL must be set
  *before* anything under `backend.*` is imported for the first time in
  this process. We do that at the top of this file, before any local
  imports, so every test module that imports `backend.*` picks up the
  isolated test database.
- The dataset is generated once per test session (session-scoped fixture)
  into a temp SQLite file, using a small persons/crimes count so the full
  suite runs in seconds, not minutes.
- No network services (Postgres, Neo4j, Anthropic API) are required to
  run this suite. Graph tests use the NetworkX backend. The Chief agent's
  narrative step automatically falls back to a deterministic template
  when ANTHROPIC_API_KEY is unset (see backend/agents/chief/agent.py),
  so the full LangGraph pipeline can be exercised end-to-end here.
"""

import os
import sys
import tempfile

# --- MUST happen before any `backend.*` import in this process ---
_tmp_dir = tempfile.mkdtemp(prefix="sherlock_test_")
_TEST_DB_PATH = os.path.join(_tmp_dir, "sherlock_test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["GRAPH_BACKEND"] = "networkx"
os.environ.pop("ANTHROPIC_API_KEY", None)  # force deterministic template narrative

import pytest  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.fixture(scope="session", autouse=True)
def synthetic_dataset():
    """Generate a small, deterministic synthetic dataset once for the whole suite."""
    # NOTE (stabilization finding): generate_synthetic_data.py only exposes a
    # CLI `main()` behind `argparse` — there's no importable `populate()` /
    # library-style entry point, so it can't be called in-process from a
    # fixture or from other code without shelling out. Fine for a one-off
    # dev script, but worth adding a proper function signature so tests and
    # other tooling (this fixture included) don't have to invoke it as a
    # subprocess. Flagged in FINDINGS.md under "Database".
    import subprocess
    subprocess.run(
        [
            sys.executable, "-m", "backend.datasets.generate_synthetic_data",
            "--persons", "40", "--crimes", "80", "--ring-size", "6",
            "--reset", "--seed", "42",
        ],
        cwd=REPO_ROOT,
        env=os.environ,
        check=True,
    )

    yield _TEST_DB_PATH


@pytest.fixture()
def db_session():
    from backend.database.config import SessionLocal
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def graph_service(db_session):
    from backend.graph.service import get_graph_service
    return get_graph_service(backend="networkx", session=db_session)


@pytest.fixture()
def api_client():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    return TestClient(app)
