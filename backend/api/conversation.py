"""
SHERLOCK — Stage C2: Conversation history read API.

Turns are written by `stream_investigation` (backend/api/investigation_stream.py)
when a `session_id` is supplied over the `/ws/investigate` WebSocket — this
router only exposes read access to that history, e.g. for a frontend
"conversation so far" panel or for replaying what was asked.
"""

import logging

from fastapi import APIRouter, HTTPException

from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.memory.conversation_memory import ConversationMemoryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["conversation-memory"])


@router.get("/{session_id}/conversation")
def get_conversation(session_id: int):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        if svc.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")

        memory = ConversationMemoryService(session)
        turns = memory.get_history(session_id)
        return [
            {
                "turn_index": t.turn_index,
                "raw_query": t.raw_query,
                "resolved_query": t.resolved_query,
                "last_person_name": t.last_person_name,
                "last_fir_id": t.last_fir_id,
                "last_account_id": t.last_account_id,
                "response_summary": t.response_summary,
                "created_at": t.created_at.isoformat(),
            }
            for t in turns
        ]
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/conversation failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch conversation history.")
    finally:
        session.close()
