"""
SHERLOCK — Stage E1: FastAPI dependencies.

`get_current_user` is the one seam every secured route (Sprint E1 routes
now, every RBAC-protected route in Sprint E2) depends on. Its behaviour
is entirely governed by `SHERLOCK_AUTH_ENABLED` (Golden Rule 4/5):

  * AUTH_ENABLED = False (default): no Authorization header is required
    at all. The dependency returns a synthetic `AuthContext` representing
    an unauthenticated "system" caller with every SystemRole implicitly
    granted, so nothing that previously worked without a login (every
    Stage A-D endpoint, and Sprint E2's RequirePermission checks) starts
    demanding one. This is what "everything should continue working
    exactly like today" means concretely.

  * AUTH_ENABLED = True: a valid, non-expired, non-revoked-account
    Bearer access token is required, or the request gets a 401.
"""

from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.database.config import SessionLocal
from backend.database.models import SystemRole
from backend.security.config import AUTH_ENABLED
from backend.security.auth import get_user_from_access_token, AuthError, get_user_role_names

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    """Uniform "who is making this request" shape, whether or not
    authentication is switched on. RBAC (Sprint E2) and the audit log
    (Sprint E3) depend only on this, never on User/AUTH_ENABLED directly,
    so both sprints work identically in either mode."""
    user_id: int | None
    username: str
    roles: list[str] = field(default_factory=list)
    officer_id: int | None = None
    is_system: bool = False   # True only when AUTH_ENABLED=False

    def has_role(self, role: SystemRole | str) -> bool:
        name = role.value if isinstance(role, SystemRole) else role
        return self.is_system or name in self.roles


def _system_context() -> AuthContext:
    return AuthContext(
        user_id=None,
        username="system",
        roles=[r.value for r in SystemRole],
        officer_id=None,
        is_system=True,
    )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    if not AUTH_ENABLED:
        return _system_context()

    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated.",
                             headers={"WWW-Authenticate": "Bearer"})

    try:
        user = get_user_from_access_token(db, credentials.credentials)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e),
                             headers={"WWW-Authenticate": "Bearer"})

    return AuthContext(
        user_id=user.id,
        username=user.username,
        roles=get_user_role_names(db, user),
        officer_id=user.officer_id,
        is_system=False,
    )


def get_optional_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext | None:
    """For routes that behave differently for logged-in vs anonymous
    callers even when AUTH_ENABLED=True, without hard-requiring a token.
    Not used by any Sprint E1 route yet; provided for Sprint E2/E4."""
    if not AUTH_ENABLED:
        return _system_context()
    if credentials is None or not credentials.credentials:
        return None
    try:
        return get_current_user(request, credentials, db)
    except HTTPException:
        return None
