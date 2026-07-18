"""
SHERLOCK — Stage E3: Audit read API.

    GET /audit?user_id=&username=&action=&target=&success=&since=&until=&limit=&offset=

Requires `view_audit` (Supervisor, PolicyMaker, Administrator — see
backend/security/permissions.py). Read-only; nothing here writes to
AuditLog — every write happens at the point of the audited action
itself, via backend/security/audit.py's `record`.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.security.dependencies import get_db
from backend.security.permissions import RequirePermission, VIEW_AUDIT
from backend.security.audit import serialize
from backend.database.models import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit_log(
    user_id: int | None = Query(None),
    username: str | None = Query(None),
    action: str | None = Query(None),
    target: str | None = Query(None),
    success: bool | None = Query(None),
    since: datetime | None = Query(None),
    until: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _ctx=Depends(RequirePermission(VIEW_AUDIT)),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)

    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    if username is not None:
        q = q.filter(AuditLog.username == username)
    if action is not None:
        q = q.filter(AuditLog.action == action)
    if target is not None:
        q = q.filter(AuditLog.target == target)
    if success is not None:
        q = q.filter(AuditLog.success == success)
    if since is not None:
        q = q.filter(AuditLog.created_at >= since)
    if until is not None:
        q = q.filter(AuditLog.created_at <= until)

    total = q.count()
    rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [serialize(r) for r in rows],
    }
