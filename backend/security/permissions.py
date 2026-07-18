"""
SHERLOCK — Stage E2: Role Based Access Control.

Per the Sprint E2 brief: "Permissions should be declarative ... Never
scatter permission checks throughout the code." This module is the one
place that vocabulary and the role -> permission map live. Every
protected route depends on `RequirePermission("some_permission")` and
nothing else — no route ever inspects `ctx.roles` or a SystemRole
directly to decide what to allow.

This builds on Stage A/C1's existing officer/session-assignment concept
rather than duplicating it: RBAC here answers "can this account use this
*kind* of route at all" (a system-wide, role-based question). "Is this
specific officer assigned to this specific session" remains
`SessionAssignment`'s job (Stage C1) and is unchanged — the two are
complementary, not competing, layers.

When SHERLOCK_AUTH_ENABLED=false, `AuthContext.is_system` is True and
`AuthContext.has_role(...)` always returns True (see
backend/security/dependencies.py), so every `RequirePermission` check
passes automatically — this is what "everything should continue working
exactly like today" means for Sprint E2 specifically.
"""

import logging
from typing import Callable

from fastapi import Depends, HTTPException

from backend.database.models import SystemRole
from backend.security.dependencies import get_current_user, AuthContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Permission vocabulary
# ---------------------------------------------------------------------------
# One string per distinct capability the brief and the route inventory
# actually need. Kept flat and small deliberately — a long list of
# near-duplicate permissions is exactly the "scattered" outcome the brief
# warns against; each of these should map cleanly onto "does this route
# let you read investigative material, change it, move it externally, or
# administer the system."

VIEW_CASE = "view_case"                    # read sessions, comments, board, discussion, timeline, presence
PARTICIPATE_CASE = "participate_case"      # comment, add board objects, request review, presence heartbeat
MANAGE_CASE = "manage_case"                # open/update/close/reopen/archive a session, assign/unassign
DECIDE_REVIEW = "decide_review"            # approve/reject a review request
USE_VOICE = "use_voice"                    # voice command/transcribe/speak/query
RUN_INVESTIGATION = "run_investigation"    # POST /investigate, /ws/investigate
EXPORT_PDF = "export_pdf"                  # POST /export/pdf
VIEW_AUDIT = "view_audit"                  # GET /audit (Sprint E3)
MANAGE_USERS = "manage_users"              # create/deactivate users, assign roles (Sprint E2 admin routes)
ADMINISTER_SYSTEM = "administer_system"    # anything else administrative

ALL_PERMISSIONS = {
    VIEW_CASE, PARTICIPATE_CASE, MANAGE_CASE, DECIDE_REVIEW, USE_VOICE,
    RUN_INVESTIGATION, EXPORT_PDF, VIEW_AUDIT, MANAGE_USERS, ADMINISTER_SYSTEM,
}

# ---------------------------------------------------------------------------
# Role -> permission map
# ---------------------------------------------------------------------------
# Administrator implicitly has everything (see RequirePermission below)
# rather than being listed out — a role that's supposed to mean "can do
# anything" shouldn't rely on someone remembering to add every future
# permission to its row too.

ROLE_PERMISSIONS: dict[SystemRole, set[str]] = {
    SystemRole.ADMINISTRATOR: set(ALL_PERMISSIONS),  # superset; also see has_permission()
    SystemRole.SUPERVISOR: {
        VIEW_CASE, PARTICIPATE_CASE, MANAGE_CASE, DECIDE_REVIEW,
        USE_VOICE, RUN_INVESTIGATION, EXPORT_PDF, VIEW_AUDIT,
    },
    SystemRole.INVESTIGATOR: {
        VIEW_CASE, PARTICIPATE_CASE, MANAGE_CASE,
        USE_VOICE, RUN_INVESTIGATION, EXPORT_PDF,
    },
    SystemRole.ANALYST: {
        VIEW_CASE, PARTICIPATE_CASE,
        USE_VOICE, RUN_INVESTIGATION, EXPORT_PDF,
    },
    SystemRole.POLICY_MAKER: {
        VIEW_CASE, VIEW_AUDIT,
    },
    SystemRole.READ_ONLY: {
        VIEW_CASE,
    },
}


def has_permission(ctx: AuthContext, permission: str) -> bool:
    if ctx.is_system:
        return True
    if permission not in ALL_PERMISSIONS:
        # A typo'd permission string should fail loudly in development,
        # not silently deny (or worse, silently allow) every request.
        raise ValueError(f"Unknown permission: {permission!r}")
    if SystemRole.ADMINISTRATOR.value in ctx.roles:
        return True
    for role_name in ctx.roles:
        try:
            role = SystemRole(role_name)
        except ValueError:
            continue
        if permission in ROLE_PERMISSIONS.get(role, set()):
            return True
    return False


# Sprint E3 replaces this with a real AuditLog write. Kept as a plain
# module-level hook (rather than importing AuditLog here) so E2 has zero
# dependency on E3's table — Sprint E3 rebinds this reference once, and
# every RequirePermission call site is instrumented automatically.
audit_permission_denied: Callable[[AuthContext, str], None] | None = None


def RequirePermission(permission: str):
    """Returns a FastAPI dependency that 403s unless the caller's roles
    grant `permission`. Usage:

        @router.post("/sessions/{id}/close")
        def close_session(session_id: int, ctx: AuthContext = Depends(RequirePermission(MANAGE_CASE))):
            ...

    The dependency also hands back the resolved `AuthContext`, so routes
    that need to know *who* is calling (e.g. to stamp an audit row) don't
    need a second, separate `Depends(get_current_user)`.
    """
    if permission not in ALL_PERMISSIONS:
        raise ValueError(f"Unknown permission: {permission!r}")

    def _check(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if not has_permission(ctx, permission):
            logger.info(
                "Permission denied: user=%r roles=%r permission=%r",
                ctx.username, ctx.roles, permission,
            )
            if audit_permission_denied is not None:
                try:
                    audit_permission_denied(ctx, permission)
                except Exception:
                    logger.exception("audit_permission_denied hook failed")
            raise HTTPException(status_code=403, detail=f"Missing required permission: {permission}")
        return ctx

    return _check
