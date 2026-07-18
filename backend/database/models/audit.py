"""
SHERLOCK — Stage E3: Audit & Compliance.

`AuditLog` is system-wide and identity-centric ("who did what, where,
when, and did it succeed") — distinct from and complementary to Stage
C1's `SessionActivity`, which is per-session and case-centric ("what
happened to this investigation"). Many events end up in both: closing a
session writes a `SessionActivity` row (unchanged, Stage C1's job) *and*
an `AuditLog` row (new, this sprint) via `backend/security/audit.py`'s
`record` helper — the same way `RequirePermission` in Sprint E2 already
calls `permissions.audit_permission_denied`, which this sprint rebinds
to a real writer instead of leaving it as a no-op.

Not a duplication: SessionActivity has no `user`/`ip`/`success` concept
and no cross-session view; AuditLog has no case-lifecycle narrative. The
brief's "Build on it. Do not replace it." applies to both existing
tables (SessionActivity here, RefreshToken/User's own timestamps for
login) rather than reinventing session lifecycle logging from scratch.
"""

from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship

from backend.database.config import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)

    # Who. Nullable because some auditable events happen with no
    # authenticated actor at all (e.g. a failed login attempt against an
    # unknown username — there's no user_id to attach, but the attempt
    # itself is still worth a row). `username` is stored redundantly
    # (not just via the FK) so the row remains meaningful even if the
    # user is later deactivated or the username changes.
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    username = Column(String, nullable=True, index=True)

    # What. `action` is one of the fixed AuditAction enum values (see
    # backend/database/models/enums.py) stored as plain text so old rows
    # stay readable even if the enum's Python representation changes.
    action = Column(String, nullable=False, index=True)

    # On what. Free-form target description — "session:42", "user:7",
    # "role:investigator", etc. Deliberately a string, not a polymorphic
    # FK, since a single audit row can target very different table types
    # and this table must never block on a FK to a row that gets purged
    # under Sprint E5's retention policy.
    target = Column(String, nullable=True, index=True)

    success = Column(Boolean, nullable=False, default=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    # Free-form JSON-serializable detail specific to the action (e.g. the
    # permission string for a permission_denied row, the role granted for
    # a role_changed row). Stored as text, not a JSON column, so this
    # table has zero database-engine-specific requirements — the
    # brief's Sprint E6 health/logging goals lean toward "boring and
    # portable" over "clever."
    metadata_json = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Sprint E5 (Governance) — retention without physical deletion.
    archived_at = Column(DateTime, nullable=True)

    user = relationship("User")

    def __repr__(self):
        return f"<AuditLog action={self.action} user={self.username} success={self.success}>"
