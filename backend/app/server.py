"""
SHERLOCK — FastAPI static file serving.

Mounts the frontend's Vite production build so the entire system starts
with one command:
    cd frontend && npm run build   # produces frontend/dist/
    cd .. && python -m backend.app.server

Visit http://localhost:8000 for the Command Center.
API docs at http://localhost:8000/docs

For active frontend development, don't use this — run `npm run dev` in
frontend/ instead (hot reload, proxies /ws and /api to this backend per
frontend/vite.config.ts) and talk to this backend directly on :8000.
"""

import logging
import os
import sqlite3
from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.main import app
from backend.database.config import Base, engine

logger = logging.getLogger(__name__)

# Ensure tables exist on first start
Base.metadata.create_all(engine)

def _ensure_db_seeded():
    try:
        db_path = getattr(engine.url, "database", None)
        if db_path and os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            try:
                person_count = c.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
            except sqlite3.OperationalError:
                person_count = 0

            if person_count == 0:
                logger.info("Database is unpopulated. Populating seeded dataset from reset_database.sql...")
                reset_sql_path = Path(__file__).parent.parent.parent / "reset_database.sql"
                if reset_sql_path.exists():
                    c.executescript(reset_sql_path.read_text(encoding="utf-8"))
                    logger.info("Database successfully auto-seeded.")
            conn.close()
    except Exception as e:
        logger.warning("Auto-seed check failed: %s", e)

_ensure_db_seeded()

# NOTE: this must point at the *built* output (dist/), not the frontend/
# source tree — frontend/index.html is Vite's dev-mode entry (references
# /src/main.tsx directly, which only works under `vite dev`'s transform).
# Pointing this at frontend/ instead of frontend/dist/ was a real bug found
# during the stabilization pass: it silently served the unbuilt source and
# a nonexistent assets/ directory, so `python -m backend.app.server` never
# actually worked as a production entrypoint.
FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"

if (FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")
else:
    logger.warning(
        "%s not found — the frontend hasn't been built yet. "
        "Run `npm run build` in frontend/ before starting this server, "
        "or use `npm run dev` for local development instead.",
        FRONTEND_DIST / "assets",
    )


@app.get("/")
def serve_frontend():
    index_path = FRONTEND_DIST / "index.html"
    if not index_path.exists():
        raise HTTPException(
            status_code=503,
            detail="Frontend build not found. Run `npm run build` in frontend/ first.",
        )
    return FileResponse(str(index_path))


if __name__ == "__main__":
    import uvicorn

    # Catalyst AppSail assigns the port to listen on via this env var and
    # only routes traffic to it — it does not let the app choose its own
    # port. Falls back to 8000 for local dev / docker-compose, where this
    # var is unset. See DEPLOYMENT_PLAN.md, Phase 0.
    port = int(os.getenv("X_ZOHO_CATALYST_LISTEN_PORT", "8000"))

    print("\n  ╔══════════════════════════════════════════╗")
    print("  ║  SHERLOCK Crime Intelligence Platform    ║")
    print(f"  ║  Command Center: http://localhost:{port}   ║")
    print(f"  ║  API docs:       http://localhost:{port}/docs ║")
    print("  ╚══════════════════════════════════════════╝\n")

    uvicorn.run(
        "backend.app.server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
    )
