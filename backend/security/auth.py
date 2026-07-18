"""
SHERLOCK — Stage E1: Authentication service.

Pure DB + business logic, no FastAPI imports here (kept separate from
backend/api/auth.py so it's independently unit-testable, matching the
DatabaseService / router split used everywhere else in this codebase).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models import User, Role, UserRole, RefreshToken
from backend.security.passwords import verify_password, hash_password, needs_rehash
from backend.security.jwt import (
    create_access_token, decode_access_token, generate_refresh_token,
    hash_refresh_token, TokenError,
)


class AuthError(Exception):
    """Raised for any authentication failure a caller should turn into
    HTTP 401 (bad credentials, inactive account, expired/revoked/unknown
    refresh token). Kept distinct from TokenError so callers can catch
    "the request itself was rejected" in one place regardless of whether
    the failure was at the password check or the token layer."""


def get_user_role_names(db: Session, user: User) -> list[str]:
    return [ur.role.name.value for ur in user.roles if ur.role is not None]


def authenticate(db: Session, username: str, password: str) -> User:
    """Verifies credentials only. Does not issue tokens or touch
    last_login_at — callers (backend/api/auth.py) do that after also
    writing the audit log entry (Sprint E3), so this function's
    responsibility stays limited to "are these credentials valid"."""
    user = db.query(User).filter(User.username == username).first()

    if user is None:
        # Run a hash comparison anyway against a fixed dummy hash so
        # "unknown username" and "wrong password" take the same amount
        # of time — a real timing side-channel is cheap to close.
        verify_password(password, "$argon2id$v=19$m=65536,t=3,p=4$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        raise AuthError("Invalid username or password.")

    if not user.is_active or user.deactivated_at is not None:
        raise AuthError("This account is deactivated.")

    if not verify_password(password, user.password_hash):
        raise AuthError("Invalid username or password.")

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.add(user)

    return user


def issue_tokens(db: Session, user: User, *, user_agent: str | None = None,
                  ip_address: str | None = None) -> tuple[str, str, datetime]:
    """Issues a fresh access + refresh token pair for `user`. Returns
    (access_token, raw_refresh_token, access_token_expires_at)."""
    roles = get_user_role_names(db, user)
    access_token, expires_at = create_access_token(user.id, user.username, roles)

    raw_refresh, refresh_hash, refresh_expires_at = generate_refresh_token()
    token_row = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=refresh_expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(token_row)

    user.last_login_at = datetime.utcnow()
    db.add(user)
    db.commit()

    return access_token, raw_refresh, expires_at


def refresh_access_token(db: Session, raw_refresh_token: str, *, user_agent: str | None = None,
                          ip_address: str | None = None) -> tuple[str, str, datetime]:
    """Validates a refresh token, revokes it, and issues a brand-new
    access + refresh pair (rotation — a used-and-replayed refresh token
    is always rejected, since the old hash is revoked before returning)."""
    token_hash = hash_refresh_token(raw_refresh_token)
    token_row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()

    if token_row is None:
        raise AuthError("Refresh token is invalid.")
    if token_row.revoked_at is not None:
        raise AuthError("Refresh token has been revoked.")
    if token_row.expires_at <= datetime.utcnow():
        raise AuthError("Refresh token has expired.")

    user = db.query(User).get(token_row.user_id)
    if user is None or not user.is_active or user.deactivated_at is not None:
        raise AuthError("This account is deactivated.")

    token_row.revoked_at = datetime.utcnow()
    db.add(token_row)

    return issue_tokens(db, user, user_agent=user_agent, ip_address=ip_address)


def revoke_refresh_token(db: Session, raw_refresh_token: str) -> None:
    """Logout: revoke one specific refresh token. Idempotent — revoking
    an already-revoked or unknown token is not an error, since the end
    state (this token can no longer be used) is already what the caller
    wants."""
    token_hash = hash_refresh_token(raw_refresh_token)
    token_row = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if token_row is not None and token_row.revoked_at is None:
        token_row.revoked_at = datetime.utcnow()
        db.add(token_row)
        db.commit()


def revoke_all_refresh_tokens(db: Session, user: User) -> int:
    """Used for 'logout everywhere' / admin-forced revocation. Returns
    the number of tokens revoked."""
    now = datetime.utcnow()
    count = 0
    for token_row in user.refresh_tokens:
        if token_row.revoked_at is None:
            token_row.revoked_at = now
            db.add(token_row)
            count += 1
    db.commit()
    return count


def get_user_from_access_token(db: Session, access_token: str) -> User:
    try:
        payload = decode_access_token(access_token)
    except TokenError as e:
        raise AuthError(str(e))

    user = db.query(User).get(int(payload["sub"]))
    if user is None or not user.is_active or user.deactivated_at is not None:
        raise AuthError("This account is deactivated.")
    return user
