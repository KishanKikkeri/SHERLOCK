"""
SHERLOCK — Stage C2: Conversation history + timeline read API.

Turns are written by `stream_investigation` (backend/api/investigation_stream.py)
when a `session_id` is supplied over the `/ws/investigate` WebSocket — this
router only exposes read access to that history, e.g. for a frontend
"conversation so far" panel or for replaying what was asked.

Sprint 2 adds item 6 of the Stage C2 remaining-work list — three timeline
views over the same underlying `ConversationTurn` rows, each answering a
different question:
    /conversation           every turn, in order, as asked          (Sprint 1)
    /timeline/conversation   same, but with clarification/reset flags surfaced
    /timeline/entities       "when was each entity mentioned"
    /timeline/decisions      "what did the Chief actually conclude, and when"
"""

import logging

from fastapi import APIRouter, HTTPException, Depends
import json

from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.memory.conversation_memory import ConversationMemoryService
from backend.security.permissions import RequirePermission, VIEW_CASE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["conversation-memory"])


@router.get("/{session_id}/conversation")
def get_conversation(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
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


@router.get("/{session_id}/context")
def get_context_summary(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    """The compressed rolling summary maintained by
    `ConversationMemoryService.maybe_summarize` (Sprint 2, item 3), plus
    which turn it covers up to. Sessions under the summarization
    threshold (8 turns) simply have `summary: null` — nothing to
    compress yet, not an error."""
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        row = svc.get_session(session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return {
            "session_id": session_id,
            "summary": row.context_summary,
            "summary_through_turn": row.context_summary_through_turn,
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/context failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch context summary.")
    finally:
        session.close()


@router.get("/{session_id}/timeline/conversation")
def get_conversation_timeline(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    """Sprint 2, item 6: every turn in order, with clarification
    questions and topic resets surfaced as first-class timeline events
    rather than hidden inside raw_query text."""
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        if svc.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")

        memory = ConversationMemoryService(session)
        events = []
        for t in memory.get_history(session_id):
            entry = {
                "turn_index": t.turn_index,
                "created_at": t.created_at.isoformat(),
                "raw_query": t.raw_query,
                "resolved_query": t.resolved_query,
            }
            if t.topic_reset:
                entry["type"] = "topic_reset"
                entry["reset_phrase"] = t.topic_reset
            elif t.pending_clarification_json:
                entry["type"] = "clarification_asked"
                entry["clarification"] = json.loads(t.pending_clarification_json)
            elif t.response_summary:
                entry["type"] = "answered"
                entry["response_summary"] = t.response_summary
            else:
                entry["type"] = "answered_no_summary"
            events.append(entry)
        return events
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/timeline/conversation failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch conversation timeline.")
    finally:
        session.close()


@router.get("/{session_id}/timeline/entities")
def get_entity_timeline(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    """Sprint 2, item 6: every entity mentioned across the session,
    grouped by (kind, id), with the ordered list of turns it appeared
    in. Built from `entity_mentions_json` (every mention, not just the
    'last one' resolution uses) — see conversation_memory.py."""
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        if svc.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")

        memory = ConversationMemoryService(session)
        by_entity: dict[tuple, dict] = {}
        for t in memory.get_history(session_id):
            if not t.entity_mentions_json:
                continue
            for m in json.loads(t.entity_mentions_json):
                key = (m["kind"], m["id"])
                bucket = by_entity.setdefault(key, {
                    "kind": m["kind"], "id": m["id"], "label": m["label"], "turns": [],
                })
                bucket["turns"].append(t.turn_index)
        return sorted(by_entity.values(), key=lambda e: e["turns"][0])
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/timeline/entities failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch entity timeline.")
    finally:
        session.close()


@router.get("/{session_id}/timeline/decisions")
def get_decision_timeline(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    """Sprint 2, item 6: turns where the Chief actually produced a
    conclusion (as opposed to a clarification question or a bare topic
    reset), with the accepted/rejected finding counts for that turn so
    an investigator can scan "what did SHERLOCK conclude, and when"
    without re-reading full transcripts."""
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        if svc.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")

        memory = ConversationMemoryService(session)
        decisions = []
        for t in memory.get_history(session_id):
            if not t.response_summary:
                continue
            findings = json.loads(t.findings_json) if t.findings_json else []
            decisions.append({
                "turn_index": t.turn_index,
                "created_at": t.created_at.isoformat(),
                "query": t.resolved_query or t.raw_query,
                "conclusion": t.response_summary,
                "finding_count": len(findings),
            })
        return decisions
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/timeline/decisions failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch decision timeline.")
    finally:
        session.close()
