"""
SHERLOCK — Stage E1: Security configuration.

Every setting here is optional and has a safe default, per Golden Rules
4 and 5 ("everything must degrade gracefully" / "all new features must
be optional"). With zero environment configuration:

    SHERLOCK_AUTH_ENABLED defaults to "false" -> every existing endpoint
    behaves exactly as it did at the end of Stage D. No login is
    required, backend/security/dependencies.py's `get_current_user`
    dependency resolves to a synthetic "system" identity, and RBAC/audit
    (Sprints E2/E3) simply have nothing to enforce or log against.

Set SHERLOCK_AUTH_ENABLED=true (see .env.example) to turn authentication
on for a real deployment.
"""

import os


def _bool_env(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


# --- Master switch ---------------------------------------------------------
AUTH_ENABLED = _bool_env("SHERLOCK_AUTH_ENABLED", False)

# --- JWT ---------------------------------------------------------------
# Generated fresh per-process if unset, so the app never fails to start —
# but that also means tokens won't survive a restart in that case. A
# production deployment with AUTH_ENABLED=true should always set this.
JWT_SECRET_KEY = os.getenv("SHERLOCK_JWT_SECRET")
if not JWT_SECRET_KEY:
    import secrets
    JWT_SECRET_KEY = secrets.token_urlsafe(48)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MINUTES = int(os.getenv("SHERLOCK_ACCESS_TOKEN_TTL_MINUTES", "15"))
REFRESH_TOKEN_TTL_DAYS = int(os.getenv("SHERLOCK_REFRESH_TOKEN_TTL_DAYS", "14"))

# --- Passwords ---------------------------------------------------------
# argon2id via argon2-cffi: the OWASP-recommended default for new systems
# (bcrypt remains supported as a verification fallback in passwords.py
# only for hashes created by some future external import, never for new
# hashes created by this codebase).
MIN_PASSWORD_LENGTH = int(os.getenv("SHERLOCK_MIN_PASSWORD_LENGTH", "10"))

# --- Bootstrap admin (optional) -----------------------------------------
# If set, `backend/security/seed.py` creates this account on first run
# (only if no Administrator user exists yet) so a freshly deployed,
# auth-enabled instance isn't locked out with no way to log in.
BOOTSTRAP_ADMIN_USERNAME = os.getenv("SHERLOCK_BOOTSTRAP_ADMIN_USERNAME")
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("SHERLOCK_BOOTSTRAP_ADMIN_PASSWORD")
