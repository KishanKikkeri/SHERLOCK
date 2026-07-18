"""
SHERLOCK — Stage E1: Authentication.

New, additive tables only. Nothing here touches `Officer` (Stage A's
police-personnel entity, used by FIR/Investigation/Arrest/etc.) or
`SessionAssignment` (Stage C1's per-investigation-session role, i.e.
"who is working this case"). Those model *investigative* facts.

`User` models a different thing: a login account. An Officer is a person
who can be named as investigating/arresting/filing on a case whether or
not the system's authentication is even switched on (SHERLOCK ran for
Stages A-D with zero notion of a login). Stage E adds accounts on top,
optionally linked to the Officer they represent via `officer_id` — never
merged into Officer itself, so:

  * every pre-Stage-E foreign key that points at `officers.id` keeps
    working unchanged (Golden Rule 3);
  * SHERLOCK_AUTH_ENABLED=false continues to work with zero User rows
    at all (Golden Rule 4/5) — nothing in agents/, orchestrator/, or the
    existing routers ever queries `User`.

Four tables:
    User          — login identity (email/username + password hash)
    Role          — one row per SystemRole value (seeded, not user-editable)
    UserRole      — many-to-many User<->Role, so a user can hold >1 role
    RefreshToken  — one row per issued refresh token, so logout/revocation
                    is a real DB write instead of relying on JWT expiry alone
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Enum, UniqueConstraint
from sqlalchemy.orm import relationship

from backend.database.config import Base
from backend.database.models.enums import SystemRole


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False, unique=True, index=True)
    email = Column(String, nullable=True, unique=True, index=True)
    password_hash = Column(String, nullable=False)

    # Optional link to the police-personnel record this login represents.
    # Nullable: not every account needs a matching Officer row (e.g. a
    # PolicyMaker or Administrator account may have no field posting),
    # and every existing Officer row from Stages A-D has no login at all
    # until someone deliberately creates one.
    officer_id = Column(Integer, ForeignKey("officers.id"), nullable=True, index=True)

    is_active = Column(Boolean, nullable=False, default=True)
    full_name = Column(String, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)

    # Stage E5 (Governance) — soft delete, not physical deletion, per the
    # handover's "No physical deletion" rule. Added here now rather than
    # bolted on later so User never needs a destructive migration.
    deactivated_at = Column(DateTime, nullable=True)

    officer = relationship("Officer")
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan",
                          foreign_keys="UserRole.user_id")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.username} officer_id={self.officer_id}>"


class Role(Base):
    """One row per SystemRole. Seeded once (see backend/security/seed.py);
    not intended to be created/edited through the API — the vocabulary is
    fixed by the enum, matching the handover's closed role list."""

    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(Enum(SystemRole), nullable=False, unique=True)
    description = Column(String, nullable=True)

    users = relationship("UserRole", back_populates="role")

    def __repr__(self):
        return f"<Role {self.name}>"


class UserRole(Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False, index=True)
    granted_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    granted_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # audit: who assigned this role

    user = relationship("User", back_populates="roles", foreign_keys=[user_id])
    role = relationship("Role", back_populates="users")
    granted_by = relationship("User", foreign_keys=[granted_by_user_id])

    def __repr__(self):
        return f"<UserRole user={self.user_id} role_id={self.role_id}>"


class RefreshToken(Base):
    """One row per issued refresh token. Storing only a hash of the token
    (never the raw value) so a DB read/leak doesn't hand out live
    credentials — the same principle as password_hash on User. Real
    revocation (logout, `POST /auth/logout`, admin-forced revocation)
    is a `revoked_at` write here; JWT access tokens themselves stay
    short-lived and stateless (see backend/security/jwt.py)."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)

    issued_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    # Basic device/session context — useful for both E1 validation
    # ("revoke expired/revoked tokens") and E3's audit trail.
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)

    user = relationship("User", back_populates="refresh_tokens")

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.utcnow()

    def __repr__(self):
        return f"<RefreshToken user={self.user_id} revoked={self.revoked_at is not None}>"
