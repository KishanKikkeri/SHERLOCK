"""
SHERLOCK — Stage E1: JWT access tokens + refresh token storage helpers.

Design:
  * Access tokens are short-lived (default 15 min), stateless JWTs signed
    with HS256. They carry `sub` (user id), `username`, and the user's
    role names at time of issue (so RBAC in Sprint E2 doesn't need a DB
    hit on every request — roles are re-read fresh on every login/refresh,
    so a role change takes effect at the user's next token refresh at the
    latest, which is an explicit, documented tradeoff, not an oversight).
  * Refresh tokens are opaque random strings. Only their SHA-256 hash is
    stored (RefreshToken.token_hash) — the raw token is returned to the
    client exactly once, at issue time, and never persisted anywhere.
    This is what makes `POST /auth/logout` and revocation real: deleting
    or expiring stateless JWTs isn't possible, but a DB-backed refresh
    token can always be marked revoked.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt as pyjwt

from backend.security.config import (
    JWT_SECRET_KEY, JWT_ALGORITHM, ACCESS_TOKEN_TTL_MINUTES, REFRESH_TOKEN_TTL_DAYS,
)


class TokenError(Exception):
    """Raised for any invalid/expired/malformed token. Callers map this
    to HTTP 401, never 500 — an untrusted client sending a bad token is
    an expected condition, not a server fault."""


def create_access_token(user_id: int, username: str, roles: list[str]) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=ACCESS_TOKEN_TTL_MINUTES)
    payload = {
        "sub": str(user_id),
        "username": username,
        "roles": roles,
        "iat": now,
        "exp": expires_at,
        "type": "access",
        "jti": secrets.token_urlsafe(16),  # unique per token; also guards against
                                            # two tokens issued in the same second
                                            # (e.g. immediate refresh) being identical
    }
    token = pyjwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = pyjwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except pyjwt.ExpiredSignatureError:
        raise TokenError("Access token has expired.")
    except pyjwt.InvalidTokenError:
        raise TokenError("Access token is invalid.")

    if payload.get("type") != "access":
        raise TokenError("Not an access token.")
    return payload


def generate_refresh_token() -> tuple[str, str, datetime]:
    """Returns (raw_token, token_hash, expires_at). Only token_hash is
    ever persisted; raw_token goes to the client once."""
    raw = secrets.token_urlsafe(48)
    token_hash = hash_refresh_token(raw)
    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_TTL_DAYS)
    return raw, token_hash, expires_at


def hash_refresh_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
