"""
SHERLOCK — Stage C6: Collaboration API.

Endpoints:
    POST /sessions/{id}/comments             add a comment (parses @mentions)
    GET  /sessions/{id}/comments             list comments, optionally filtered by target
    POST /sessions/{id}/board-objects         add a shared note/link/hypothesis
    GET  /sessions/{id}/board-objects         list the session's board objects
    PATCH /board-objects/{id}                 edit content/payload
    POST /sessions/{id}/reviews               request review (Draft -> In Review)
    POST /reviews/{id}/decide                 approve/reject
    GET  /sessions/{id}/reviews               review history for this session
    GET  /officers/{id}/notifications         an officer's notifications
    POST /notifications/{id}/read             mark one notification read
    PUT  /sessions/{id}/presence              heartbeat "I'm viewing/editing this"
    GET  /sessions/{id}/presence              who's currently present
    GET  /sessions/{id}/activity-feed         merged human/AI/session/discussion feed
"""

import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.database.models import CommentTargetType, BoardObjectType, PresenceStatus
from backend.security.permissions import RequirePermission, VIEW_CASE, PARTICIPATE_CASE, DECIDE_REVIEW
from backend.collaboration.service import CollaborationService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["collaboration"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class CommentRequest(BaseModel):
    target_type: str    # "finding" | "evidence" | "entity" | "board_object"
    target_ref: str
    body: str
    author_officer_id: int | None = None


class BoardObjectRequest(BaseModel):
    object_type: str     # "note" | "link" | "hypothesis"
    content: str
    payload: dict | None = None
    created_by_officer_id: int | None = None


class BoardObjectUpdateRequest(BaseModel):
    content: str | None = None
    payload: dict | None = None
    actor_officer_id: int | None = None


class ReviewRequestBody(BaseModel):
    requested_by_officer_id: int | None = None
    reviewer_officer_id: int | None = None
    notes: str | None = None


class ReviewDecisionRequest(BaseModel):
    approve: bool
    actor_officer_id: int | None = None
    decision_notes: str | None = None


class PresenceRequest(BaseModel):
    officer_id: int
    status: str = "viewing"   # "viewing" | "editing"


def _enum_or_400(enum_cls, value: str, field_name: str):
    try:
        return enum_cls(value)
    except ValueError:
        valid = ", ".join(e.value for e in enum_cls)
        raise HTTPException(status_code=422, detail=f"Invalid {field_name} {value!r}. Must be one of: {valid}")


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/comments")
def add_comment(session_id: int, body: CommentRequest, _ctx=Depends(RequirePermission(PARTICIPATE_CASE))):
    target_type = _enum_or_400(CommentTargetType, body.target_type, "target_type")
    session = SessionLocal()
    try:
        svc = CollaborationService(session)
        comment = svc.add_comment(session_id, target_type, body.target_ref, body.body, body.author_officer_id)
        if comment is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return {
            "id": comment.id, "session_id": comment.session_id,
            "target_type": comment.target_type.value, "target_ref": comment.target_ref,
            "author_officer_id": comment.author_officer_id, "body": comment.body,
            "created_at": comment.created_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /sessions/%s/comments failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to add comment.")
    finally:
        session.close()


@router.get("/sessions/{session_id}/comments")
def get_comments(session_id: int, target_type: str | None = None, target_ref: str | None = None, _ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        svc_db = DatabaseService(session)
        if svc_db.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        tt = _enum_or_400(CommentTargetType, target_type, "target_type") if target_type else None
        svc = CollaborationService(session)
        comments = svc.get_comments(session_id, target_type=tt, target_ref=target_ref)
        return [
            {
                "id": c.id, "target_type": c.target_type.value, "target_ref": c.target_ref,
                "author_officer_id": c.author_officer_id, "body": c.body,
                "created_at": c.created_at.isoformat(),
                "edited_at": c.edited_at.isoformat() if c.edited_at else None,
            }
            for c in comments
        ]
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/comments failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch comments.")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Board objects (shared notes / links / hypotheses)
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/board-objects")
def add_board_object(session_id: int, body: BoardObjectRequest, _ctx=Depends(RequirePermission(PARTICIPATE_CASE))):
    object_type = _enum_or_400(BoardObjectType, body.object_type, "object_type")
    session = SessionLocal()
    try:
        svc = CollaborationService(session)
        obj = svc.add_board_object(session_id, object_type, body.content, body.payload, body.created_by_officer_id)
        if obj is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return _serialize_board_object(obj)
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /sessions/%s/board-objects failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to add board object.")
    finally:
        session.close()


@router.get("/sessions/{session_id}/board-objects")
def get_board_objects(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        svc_db = DatabaseService(session)
        if svc_db.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        svc = CollaborationService(session)
        return [_serialize_board_object(o) for o in svc.get_board_objects(session_id)]
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/board-objects failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch board objects.")
    finally:
        session.close()


@router.patch("/board-objects/{board_object_id}")
def update_board_object(board_object_id: int, body: BoardObjectUpdateRequest, _ctx=Depends(RequirePermission(PARTICIPATE_CASE))):
    session = SessionLocal()
    try:
        svc = CollaborationService(session)
        obj = svc.update_board_object(board_object_id, body.actor_officer_id, body.content, body.payload)
        if obj is None:
            raise HTTPException(status_code=404, detail="Board object not found.")
        return _serialize_board_object(obj)
    except HTTPException:
        raise
    except Exception:
        logger.exception("PATCH /board-objects/%s failed", board_object_id)
        raise HTTPException(status_code=500, detail="Failed to update board object.")
    finally:
        session.close()


def _serialize_board_object(obj) -> dict:
    import json
    return {
        "id": obj.id, "session_id": obj.session_id, "object_type": obj.object_type.value,
        "content": obj.content, "payload": json.loads(obj.payload) if obj.payload else None,
        "created_by_officer_id": obj.created_by_officer_id,
        "created_at": obj.created_at.isoformat(), "updated_at": obj.updated_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Review workflow
# ---------------------------------------------------------------------------

@router.post("/sessions/{session_id}/reviews")
def request_review(session_id: int, body: ReviewRequestBody, _ctx=Depends(RequirePermission(PARTICIPATE_CASE))):
    session = SessionLocal()
    try:
        svc = CollaborationService(session)
        review = svc.request_review(session_id, body.requested_by_officer_id, body.reviewer_officer_id, body.notes)
        if review is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return _serialize_review(review)
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /sessions/%s/reviews failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to request review.")
    finally:
        session.close()


@router.post("/reviews/{review_id}/decide")
def decide_review(review_id: int, body: ReviewDecisionRequest, _ctx=Depends(RequirePermission(DECIDE_REVIEW))):
    session = SessionLocal()
    try:
        svc = CollaborationService(session)
        review = svc.decide_review(review_id, body.approve, body.actor_officer_id, body.decision_notes)
        if review is None:
            raise HTTPException(status_code=404, detail="Review request not found.")
        return _serialize_review(review)
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /reviews/%s/decide failed", review_id)
        raise HTTPException(status_code=500, detail="Failed to decide review.")
    finally:
        session.close()


@router.get("/sessions/{session_id}/reviews")
def get_reviews(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        svc_db = DatabaseService(session)
        if svc_db.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        svc = CollaborationService(session)
        return [_serialize_review(r) for r in svc.get_reviews(session_id)]
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/reviews failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch reviews.")
    finally:
        session.close()


def _serialize_review(review) -> dict:
    return {
        "id": review.id, "session_id": review.session_id, "status": review.status.value,
        "requested_by_officer_id": review.requested_by_officer_id,
        "reviewer_officer_id": review.reviewer_officer_id,
        "notes": review.notes, "decision_notes": review.decision_notes,
        "created_at": review.created_at.isoformat(),
        "decided_at": review.decided_at.isoformat() if review.decided_at else None,
    }


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@router.get("/officers/{officer_id}/notifications")
def get_notifications(officer_id: int, unread_only: bool = False, _ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        svc = CollaborationService(session)
        rows = svc.list_notifications(officer_id, unread_only=unread_only)
        return [
            {
                "id": n.id, "notification_type": n.notification_type.value,
                "session_id": n.session_id, "message": n.message,
                "created_at": n.created_at.isoformat(),
                "read_at": n.read_at.isoformat() if n.read_at else None,
            }
            for n in rows
        ]
    except Exception:
        logger.exception("GET /officers/%s/notifications failed", officer_id)
        raise HTTPException(status_code=500, detail="Failed to fetch notifications.")
    finally:
        session.close()


@router.post("/notifications/{notification_id}/read")
def mark_notification_read(notification_id: int, _ctx=Depends(RequirePermission(PARTICIPATE_CASE))):
    session = SessionLocal()
    try:
        svc = CollaborationService(session)
        n = svc.mark_notification_read(notification_id)
        if n is None:
            raise HTTPException(status_code=404, detail="Notification not found.")
        return {"id": n.id, "read_at": n.read_at.isoformat()}
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /notifications/%s/read failed", notification_id)
        raise HTTPException(status_code=500, detail="Failed to mark notification read.")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Presence
# ---------------------------------------------------------------------------

@router.put("/sessions/{session_id}/presence")
def heartbeat_presence(session_id: int, body: PresenceRequest, _ctx=Depends(RequirePermission(PARTICIPATE_CASE))):
    status = _enum_or_400(PresenceStatus, body.status, "status")
    session = SessionLocal()
    try:
        svc = CollaborationService(session)
        row = svc.heartbeat_presence(session_id, body.officer_id, status)
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return {"session_id": row.session_id, "officer_id": row.officer_id,
                "status": row.status.value, "last_seen_at": row.last_seen_at.isoformat()}
    except HTTPException:
        raise
    except Exception:
        logger.exception("PUT /sessions/%s/presence failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to update presence.")
    finally:
        session.close()


@router.get("/sessions/{session_id}/presence")
def get_presence(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        svc_db = DatabaseService(session)
        if svc_db.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        svc = CollaborationService(session)
        return [
            {"officer_id": p.officer_id, "status": p.status.value, "last_seen_at": p.last_seen_at.isoformat()}
            for p in svc.get_presence(session_id)
        ]
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/presence failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch presence.")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Merged activity feed
# ---------------------------------------------------------------------------

@router.get("/sessions/{session_id}/activity-feed")
def get_activity_feed(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        svc_db = DatabaseService(session)
        if svc_db.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        svc = CollaborationService(session)
        return svc.get_activity_feed(session_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/activity-feed failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch activity feed.")
    finally:
        session.close()
