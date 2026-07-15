"""
SHERLOCK — Stage C5: Investigation Board Intelligence API.

    GET /sessions/{id}/board

Read-only. Returns suggestions (links, hidden connections, contradictions,
missing evidence, hypotheses, clusters) for the frontend board to turn
into `BoardCard`/`BoardLink` objects on user action — this endpoint never
writes board state itself. See `backend/intelligence/board_intelligence.py`
for what each field actually is and isn't.
"""

import logging

from fastapi import APIRouter, HTTPException

from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.graph.service import get_graph_service
from backend.intelligence.board_intelligence import BoardIntelligenceService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["investigation-board"])


@router.get("/{session_id}/board")
def get_board_intelligence(session_id: int):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        if svc.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")

        graph_service = get_graph_service(backend="networkx", session=session)
        board = BoardIntelligenceService(session, graph_service)
        return board.build(session_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/board failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to build board intelligence.")
    finally:
        session.close()
