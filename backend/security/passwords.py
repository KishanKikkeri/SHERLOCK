"""
SHERLOCK — Stage E1: Password hashing.

argon2id (via argon2-cffi) for every new hash. Never plain hashing, never
reversible encryption — per the Sprint E1 brief.
"""

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHash

from backend.security.config import MIN_PASSWORD_LENGTH

_hasher = PasswordHasher()


class WeakPasswordError(ValueError):
    """Raised when a password fails the minimum policy check."""


def validate_password_strength(password: str) -> None:
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters long."
        )


def hash_password(password: str) -> str:
    validate_password_strength(password)
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Returns True/False rather than raising, so callers (login,
    dependencies) can treat "wrong password" and "malformed hash" the
    same way: a failed login, not a 500."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHash):
        return False


def needs_rehash(password_hash: str) -> bool:
    """True if the stored hash was made with weaker-than-current argon2
    parameters (e.g. after a policy upgrade) and should be silently
    re-hashed on next successful login."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHash:
        return False
