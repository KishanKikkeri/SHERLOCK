"""
SHERLOCK — Unified Graph Search API (Priority 18-23).

    GET /graph/search?q=...&case_id=...&limit=...

Single endpoint investigators use instead of internal node IDs. Accepts
any natural identifier (name, alias, vehicle number, phone, bank account,
weapon serial, FIR/crime number, org/gang name, address, location,
district, state, crime type) and returns ranked candidate nodes —
entity type is detected automatically, never chosen by the caller.

See backend/graph/search.py for the search/ranking implementation this
route wraps; this file only handles the HTTP surface (validation,
permission check, session lifecycle).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database.config import SessionLocal
from backend.graph.search import search_entities
from backend.security.permissions import RequirePermission, VIEW_CASE

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["graph-search"])


@router.get("/search")
def graph_search(
    q: str = Query(..., min_length=1, description="Any identifier: name, alias, vehicle number, phone, "
                                                    "bank account, weapon serial, FIR/crime number, org/gang "
                                                    "name, address, location, district, state, or crime type."),
    case_id: int | None = Query(None, description="Crime id of the currently-selected case, if any — "
                                                    "boosts ranking for entities already connected to it."),
    limit: int = Query(20, ge=1, le=100),
    ctx=Depends(RequirePermission(VIEW_CASE)),
):
    if not q.strip():
        raise HTTPException(status_code=422, detail="q must not be blank.")

    session = SessionLocal()
    try:
        results = search_entities(session, q, case_id=case_id, limit=limit)
        return {"query": q, "count": len(results), "results": results}
    except Exception:
        logger.exception("GET /graph/search failed for q=%r", q)
        raise HTTPException(status_code=500, detail="Graph search failed.")
    finally:
        session.close()
