"""
SHERLOCK — Stage C1: Investigation Session lifecycle API.

New router, mounted additively in app/main.py. Does not touch any
existing endpoint, model, or agent.

Endpoints:
    POST   /sessions                      Open a new investigation session ("Sherlock, open a new case")
    GET    /sessions                      List sessions (optionally filter by status/owner)
    GET    /sessions/{id}                 Get one session
    PATCH  /sessions/{id}                 Update metadata (title/priority/notes)
    PATCH  /sessions/{id}/case            Set/clear the case (fir_id) this session is scoped to
    POST   /sessions/{id}/close           Close
    POST   /sessions/{id}/reopen          Reopen
    POST   /sessions/{id}/archive         Archive (terminal)
    POST   /sessions/{id}/assign          Assign an investigator
    POST   /sessions/{id}/unassign        Unassign an investigator
    GET    /sessions/{id}/activity        Session audit trail
"""

import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.database.models import InvestigationSessionStatus, InvestigationPriority
from backend.security.permissions import RequirePermission, VIEW_CASE, MANAGE_CASE

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


class SetCaseRequest(BaseModel):
    fir_id: int | None = None  # None = "All Cases" (clear case scope)
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
    fir_num = row.fir.fir_number if getattr(row, "fir", None) else (f"FIR-{row.fir_id}" if row.fir_id else None)
    title = f"[FIR #{fir_num}] {row.title}" if fir_num and not row.title.startswith("[FIR #") else row.title
    return {
        "id": row.id,
        "session_code": row.session_code,
        "title": title,
        "fir_id": row.fir_id,
        "fir_number": fir_num,
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



def _serialize_v2_as_session(inv) -> dict:
    return {
        "id": inv.id,
        "session_code": f"INV2-{inv.id:04d}",
        "title": inv.title,
        "fir_id": None,
        "status": "open" if inv.status.value == "active" else inv.status.value,
        "priority": "medium",
        "opened_by_officer_id": inv.created_by_officer_id,
        "owner_officer_id": inv.created_by_officer_id,
        "opened_at": inv.created_at.isoformat() if inv.created_at else None,
        "closed_at": None,
        "reopened_at": None,
        "archived_at": inv.archived_at.isoformat() if inv.archived_at else None,
        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
        "notes": inv.description,
    }


@router.post("")
def open_session(body: OpenSessionRequest, _ctx=Depends(RequirePermission(MANAGE_CASE))):
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
def list_sessions(status: str | None = None, owner_officer_id: int | None = None, _ctx=Depends(RequirePermission(VIEW_CASE))):
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
        if not rows:
            from backend.database.models.investigation_v2 import InvestigationV2
            v2_rows = session.query(InvestigationV2).order_by(InvestigationV2.updated_at.desc()).all()
            return [_serialize_v2_as_session(r) for r in v2_rows]
        return [_serialize(r) for r in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions failed")
        raise HTTPException(status_code=500, detail="Failed to list sessions.")
    finally:
        session.close()


@router.get("/{session_id}")
def get_session(session_id: int, ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        row = svc.get_session(session_id)
        if row is None:
            from backend.database.models.investigation_v2 import InvestigationV2
            inv = session.get(InvestigationV2, session_id)
            if inv is not None:
                return _serialize_v2_as_session(inv)
            raise HTTPException(status_code=404, detail="Session not found.")
        from backend.security import audit as security_audit
        from backend.database.models import AuditAction
        security_audit.record(
            session, AuditAction.INVESTIGATION_VIEWED,
            user_id=ctx.user_id, username=ctx.username, target=f"session:{session_id}", success=True,
        )
        return _serialize(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /sessions/%s failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to fetch session.")
    finally:
        session.close()


@router.patch("/{session_id}")
def update_session(session_id: int, body: UpdateSessionRequest, _ctx=Depends(RequirePermission(MANAGE_CASE))):
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


@router.patch("/{session_id}/case")
def set_session_case(session_id: int, body: SetCaseRequest, _ctx=Depends(RequirePermission(MANAGE_CASE))):
    """Priority 5 (case scoping): bind this conversation session to a case
    (fir_id), or pass fir_id=null for "All Cases". Every subsequent turn on
    this session — SQL, graph, analytics, forecasting, financial, etc. —
    is scoped to it (see stream_investigation in investigation_stream.py)."""
    session = SessionLocal()
    try:
        svc = DatabaseService(session)
        try:
            row = svc.update_session_case(session_id, body.fir_id, actor_officer_id=body.actor_officer_id)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        return _serialize(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("PATCH /sessions/%s/case failed", session_id)
        raise HTTPException(status_code=500, detail="Failed to update session case.")
    finally:
        session.close()


@router.post("/{session_id}/close")
def close_session(session_id: int, body: LifecycleActionRequest = LifecycleActionRequest(), _ctx=Depends(RequirePermission(MANAGE_CASE))):
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
def reopen_session(session_id: int, body: LifecycleActionRequest = LifecycleActionRequest(), _ctx=Depends(RequirePermission(MANAGE_CASE))):
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
def archive_session(session_id: int, body: LifecycleActionRequest = LifecycleActionRequest(), _ctx=Depends(RequirePermission(MANAGE_CASE))):
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
def assign_investigator(session_id: int, body: AssignRequest, _ctx=Depends(RequirePermission(MANAGE_CASE))):
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
def unassign_investigator(session_id: int, body: AssignRequest, _ctx=Depends(RequirePermission(MANAGE_CASE))):
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
def get_session_activity(session_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
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
