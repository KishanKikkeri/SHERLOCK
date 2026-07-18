"""
SHERLOCK — Stage E3: Audit recording.

`record(...)` is the one function that writes an `AuditLog` row.
Callers (auth.py's login/logout/refresh, admin.py's role changes,
main.py's export/investigate, voice.py's voice commands, and Sprint
E2's `RequirePermission` via the rebind at the bottom of this module)
never construct an `AuditLog` row themselves — same "declarative, not
scattered" principle Sprint E2 applied to permissions.

Failures inside `record` itself are swallowed (logged, not raised) —
an audit-logging bug must never be able to break the request it's
trying to observe. This mirrors the brief's "graceful degradation" rule
applied to the audit layer itself, not just to auth being disabled.
"""

import json
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models import AuditLog, AuditAction

logger = logging.getLogger(__name__)


def record(
    db: Session,
    action: AuditAction,
    *,
    user_id: int | None = None,
    username: str | None = None,
    target: str | None = None,
    success: bool = True,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict | None = None,
) -> None:
    try:
        row = AuditLog(
            user_id=user_id,
            username=username,
            action=action.value if isinstance(action, AuditAction) else str(action),
            target=target,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
    except Exception:
        logger.exception("Failed to write audit log row for action=%r", action)
        try:
            db.rollback()
        except Exception:
            pass


def serialize(row: AuditLog) -> dict:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "username": row.username,
        "action": row.action,
        "target": row.target,
        "success": row.success,
        "ip_address": row.ip_address,
        "user_agent": row.user_agent,
        "metadata": json.loads(row.metadata_json) if row.metadata_json else None,
        "created_at": row.created_at.isoformat(),
    }


def _handle_permission_denied(ctx, permission: str) -> None:
    """Rebound onto backend.security.permissions.audit_permission_denied
    (see the assignment at the bottom of this module). RequirePermission
    calls this with no DB session of its own, so this opens and closes
    a short-lived one just for the audit write."""
    from backend.database.config import SessionLocal

    db = SessionLocal()
    try:
        record(
            db, AuditAction.PERMISSION_DENIED,
            user_id=ctx.user_id, username=ctx.username,
            target=f"permission:{permission}", success=False,
            metadata={"roles": ctx.roles},
        )
    finally:
        db.close()


# Rebind Sprint E2's no-op hook to a real writer. Done here (not in
# permissions.py) so E2 has zero import-time dependency on the AuditLog
# table / this module — importing backend.security.audit at least once
# (main.py does, at startup) is what activates real permission-failure
# auditing.
from backend.security import permissions as _permissions_module  # noqa: E402
_permissions_module.audit_permission_denied = _handle_permission_denied
