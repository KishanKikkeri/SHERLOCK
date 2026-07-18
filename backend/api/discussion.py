"""
SHERLOCK — Stage C4: Discussion Mode read API.

DiscussionRecord rows are written by `run_discussion` (backend/api/
investigation_stream.py) only when a turn ran with `enable_discussion=True`.
This router only exposes read access — for a frontend "agent discussion"
panel, or for Stage C6's "investigation replay should include discussion"
goal, which can read `/sessions/{id}/discussions` alongside C2's
conversation timeline.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Depends

from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.database.models import DiscussionRecord
from backend.security.permissions import RequirePermission, VIEW_CASE

logger = logging.getLogger(__name__)
router = APIRouter(tags=["discussion"])


def _serialize(record: DiscussionRecord) -> dict:
    return {
        "id": record.id,
        "session_id": record.session_id,
        "turn_index": record.turn_index,
        "query": record.query,
        "opinions": json.loads(record.opinions_json),
        "disagreements": json.loads(record.disagreements_json),
        "consensus": json.loads(record.consensus_json),
        "created_at": record.created_at.isoformat(),
    }


@router.get("/discussions/{discussion_id}")
def get_discussion(discussion_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        record = session.get(DiscussionRecord, discussion_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Discussion record not found.")
        return _serialize(record)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /discussions/%s failed", discussion_id)
        raise HTTPException(status_code=500, detail="Failed to fetch discussion record.")
    finally:
        session.close()


@router.get("/sessions/{session_id}/discussions")
def get_session_discussions(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    """Every discussion run for this session, in turn order — the
    replay view Stage C6 will eventually surface alongside the
    conversation timeline."""
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        if svc.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")

        records = (
            session.query(DiscussionRecord)
            .filter_by(session_id=session_id)
            .order_by(DiscussionRecord.turn_index)
            .all()
        )
        return [_serialize(r) for r in records]
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/discussions failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch session discussions.")
    finally:
        session.close()
