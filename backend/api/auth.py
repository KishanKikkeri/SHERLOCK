"""
SHERLOCK — Stage E1: Authentication API.

New router, mounted additively in app/main.py. Does not touch any
existing endpoint, model, or agent (Golden Rule 1/3).

Endpoints:
    POST /auth/login     Username/password -> access + refresh token pair
    POST /auth/refresh    Refresh token -> new access + refresh token pair (rotated)
    POST /auth/logout     Revoke one refresh token
    GET  /auth/me         Current caller's identity (works whether or not
                          SHERLOCK_AUTH_ENABLED is set — see AuthContext)

If SHERLOCK_AUTH_ENABLED=false (the default), /auth/login and
/auth/refresh still work exactly as below (there's no reason to disable
issuing tokens), but no *other* route in the app requires the token they
return — see backend/security/dependencies.py.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from backend.security.dependencies import get_db, get_current_user, AuthContext
from backend.security.auth import (
    authenticate, issue_tokens, refresh_access_token, revoke_refresh_token,
    get_user_role_names, AuthError,
)
from backend.security.passwords import WeakPasswordError
from backend.database.models import User, AuditAction
from backend.security.schemas import (
    LoginRequest, RefreshRequest, LogoutRequest, TokenResponse, UserOut,
)
from backend.security import audit
from backend.security.rate_limit import limiter, LOGIN_RATE_LIMIT, REFRESH_RATE_LIMIT

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    return user_agent, ip_address


@router.post("/login", response_model=TokenResponse)
@limiter.limit(LOGIN_RATE_LIMIT)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user_agent, ip_address = _client_meta(request)
    try:
        user = authenticate(db, payload.username, payload.password)
    except AuthError as e:
        logger.info("Failed login attempt for username=%r", payload.username)
        audit.record(db, AuditAction.LOGIN_FAILED, username=payload.username, target=f"user:{payload.username}",
                     success=False, ip_address=ip_address, user_agent=user_agent)
        raise HTTPException(status_code=401, detail=str(e))

    access_token, refresh_token, expires_at = issue_tokens(
        db, user, user_agent=user_agent, ip_address=ip_address
    )
    audit.record(db, AuditAction.LOGIN, user_id=user.id, username=user.username, target=f"user:{user.id}",
                 success=True, ip_address=ip_address, user_agent=user_agent)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_at=expires_at)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(REFRESH_RATE_LIMIT)
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    user_agent, ip_address = _client_meta(request)
    try:
        access_token, refresh_token, expires_at = refresh_access_token(
            db, payload.refresh_token, user_agent=user_agent, ip_address=ip_address
        )
    except AuthError as e:
        audit.record(db, AuditAction.TOKEN_REFRESH, success=False, ip_address=ip_address,
                     user_agent=user_agent, metadata={"error": str(e)})
        raise HTTPException(status_code=401, detail=str(e))

    audit.record(db, AuditAction.TOKEN_REFRESH, success=True, ip_address=ip_address, user_agent=user_agent)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token, expires_at=expires_at)


@router.post("/logout")
def logout(payload: LogoutRequest, request: Request, db: Session = Depends(get_db)):
    user_agent, ip_address = _client_meta(request)
    revoke_refresh_token(db, payload.refresh_token)
    audit.record(db, AuditAction.LOGOUT, success=True, ip_address=ip_address, user_agent=user_agent)
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
def me(ctx: AuthContext = Depends(get_current_user), db: Session = Depends(get_db)):
    if ctx.is_system:
        # AUTH_ENABLED=false: there is no real User row for the caller.
        # Report the synthetic system identity rather than 404/500 — a
        # caller probing "who am I" should get an honest, coherent answer
        # in either mode.
        return UserOut(
            id=0, username="system", email=None, full_name="Authentication disabled",
            officer_id=None, is_active=True, roles=ctx.roles,
        )

    user = db.query(User).get(ctx.user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    return UserOut(
        id=user.id, username=user.username, email=user.email, full_name=user.full_name,
        officer_id=user.officer_id, is_active=user.is_active,
        roles=get_user_role_names(db, user),
    )
