"""
SHERLOCK — FastAPI static file serving.

Mounts the frontend `index.html` so the entire system starts with one command:
    python -m backend.app.server

Visit http://localhost:8000 for the Command Center.
API docs at http://localhost:8000/docs
"""

import os
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.main import app
from backend.database.config import Base, engine

# Ensure tables exist on first start
Base.metadata.create_all(engine)

FRONTEND = Path(__file__).parent.parent.parent / "frontend"

# Mount static assets if there are any (CSS, JS bundles etc in future)
if (FRONTEND / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND / "assets")), name="assets")


@app.get("/")
def serve_frontend():
    return FileResponse(str(FRONTEND / "index.html"))


if __name__ == "__main__":
    import uvicorn

    print("\n  ╔══════════════════════════════════════════╗")
    print("  ║  SHERLOCK Crime Intelligence Platform    ║")
    print("  ║  Command Center: http://localhost:8000   ║")
    print("  ║  API docs:       http://localhost:8000/docs ║")
    print("  ╚══════════════════════════════════════════╝\n")

    uvicorn.run(
        "backend.app.server:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
