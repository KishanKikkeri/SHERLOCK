"""
SHERLOCK — Stage C1: Investigation Session lifecycle API.

New router, mounted additively in app/main.py. Does not touch any
existing endpoint, model, or agent.

Endpoints:
    POST   /sessions                      Open a new investigation session ("Sherlock, open a new case")
    GET    /sessions                      List sessions (optionally filter by status/owner)
    GET    /sessions/{id}                 Get one session
    PATCH  /sessions/{id}                 Update metadata (title/priority/notes)
    POST   /sessions/{id}/close           Close
    POST   /sessions/{id}/reopen          Reopen
    POST   /sessions/{id}/archive         Archive (terminal)
    POST   /sessions/{id}/assign          Assign an investigator
    POST   /sessions/{id}/unassign        Unassign an investigator
    GET    /sessions/{id}/activity        Session audit trail
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.database.models import InvestigationSessionStatus, InvestigationPriority

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sessions", tags=["investigation-sessions"])


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------

class OpenSessionRequest(BaseModel):
    title: str
    fir_id: int | None = None
    opened_by_officer_id: int | None = None
    priority: str | None = None   # "low" | "medium" | "high" | "critical"
    notes: str | None = None


class UpdateSessionRequest(BaseModel):
    title: str | None = None
    priority: str | None = None
    notes: str | None = None
    actor_officer_id: int | None = None


class LifecycleActionRequest(BaseModel):
    actor_officer_id: int | None = None
    detail: str | None = None


class AssignRequest(BaseModel):
    officer_id: int
    role: str = "investigator"
    actor_officer_id: int | None = None


def _priority_or_400(value: str | None):
    if value is None:
        return None
    try:
        return InvestigationPriority(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid priority '{value}'. Must be one of: "
                                                      f"{[p.value for p in InvestigationPriority]}")


def _serialize(row) -> dict:
    return {
        "id": row.id,
        "session_code": row.session_code,
        "title": row.title,
        "fir_id": row.fir_id,
        "status": row.status.value,
        "priority": row.priority.value,
        "opened_by_officer_id": row.opened_by_officer_id,
        "owner_officer_id": row.owner_officer_id,
        "opened_at": row.opened_at.isoformat() if row.opened_at else None,
        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
        "reopened_at": row.reopened_at.isoformat() if row.reopened_at else None,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "notes": row.notes,
    }


@router.post("")
def open_session(body: OpenSessionRequest):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        priority = _priority_or_400(body.priority)
        row = svc.open_case(
            title=body.title,
            fir_id=body.fir_id,
            opened_by_officer_id=body.opened_by_officer_id,
            priority=priority,
            notes=body.notes,
        )
        return _serialize(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /sessions failed")
        raise HTTPException(status_code=500, detail="Failed to open session.")
    finally:
        session.close()


@router.get("")
def list_sessions(status: str | None = None, owner_officer_id: int | None = None):
    session = SessionLocal()
    try:
        status_enum = None
        if status is not None:
            try:
                status_enum = InvestigationSessionStatus(status)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid status '{status}'.")
        svc = DatabaseService(session)
        rows = svc.list_sessions(status=status_enum, owner_officer_id=owner_officer_id)
        return [_serialize(r) for r in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions failed")
        raise HTTPException(status_code=500, detail="Failed to list sessions.")
    finally:
        session.close()


@router.get("/{session_id}")
def get_session(session_id: int):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        row = svc.get_session(session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return _serialize(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch session.")
    finally:
        session.close()


@router.patch("/{session_id}")
def update_session(session_id: int, body: UpdateSessionRequest):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        priority = _priority_or_400(body.priority)
        row = svc.update_session_metadata(
            session_id, actor_officer_id=body.actor_officer_id,
            title=body.title, priority=priority, notes=body.notes,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return _serialize(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("PATCH /sessions/%s failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to update session.")
    finally:
        session.close()


@router.post("/{session_id}/close")
def close_session(session_id: int, body: LifecycleActionRequest = LifecycleActionRequest()):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        row = svc.close_case(session_id, actor_officer_id=body.actor_officer_id, detail=body.detail)
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return _serialize(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /sessions/%s/close failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to close session.")
    finally:
        session.close()


@router.post("/{session_id}/reopen")
def reopen_session(session_id: int, body: LifecycleActionRequest = LifecycleActionRequest()):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        row = svc.reopen_case(session_id, actor_officer_id=body.actor_officer_id, detail=body.detail)
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return _serialize(row)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception:
        logger.exception("POST /sessions/%s/reopen failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to reopen session.")
    finally:
        session.close()


@router.post("/{session_id}/archive")
def archive_session(session_id: int, body: LifecycleActionRequest = LifecycleActionRequest()):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        row = svc.archive_case(session_id, actor_officer_id=body.actor_officer_id, detail=body.detail)
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return _serialize(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /sessions/%s/archive failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to archive session.")
    finally:
        session.close()


@router.post("/{session_id}/assign")
def assign_investigator(session_id: int, body: AssignRequest):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        assignment = svc.assign_investigator(
            session_id, officer_id=body.officer_id, role=body.role,
            actor_officer_id=body.actor_officer_id,
        )
        if assignment is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return {
            "id": assignment.id, "session_id": assignment.session_id,
            "officer_id": assignment.officer_id, "role": assignment.role,
            "assigned_at": assignment.assigned_at.isoformat(),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /sessions/%s/assign failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to assign investigator.")
    finally:
        session.close()


@router.post("/{session_id}/unassign")
def unassign_investigator(session_id: int, body: AssignRequest):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        ok = svc.unassign_investigator(session_id, officer_id=body.officer_id,
                                        actor_officer_id=body.actor_officer_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Session or active assignment not found.")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception:
        logger.exception("POST /sessions/%s/unassign failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to unassign investigator.")
    finally:
        session.close()


@router.get("/{session_id}/activity")
def get_session_activity(session_id: int):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        if svc.get_session(session_id) is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        rows = svc.get_session_activity(session_id)
        return [
            {
                "id": r.id, "event_type": r.event_type,
                "actor_officer_id": r.actor_officer_id,
                "detail": r.detail, "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s/activity failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch session activity.")
    finally:
        session.close()
