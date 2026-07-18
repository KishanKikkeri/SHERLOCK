"""
SHERLOCK — Stage E5: Governance & Retention.

"No physical deletion" applies uniformly across the platform. Three
tables already had (or, in ConversationTurn's case, now have) an
`archived_at` / `deactivated_at` column before this sprint touched
anything:

  - `InvestigationSession.archived_at` — Stage C1, already existed
  - `User.deactivated_at` — Sprint E1
  - `AuditLog.archived_at` — Sprint E3
  - `ConversationTurn.archived_at` — added this sprint (additive column,
    see backend/database/models/conversation.py)

This module's job is not to invent soft-delete — it already existed in
pieces — but to give it a single, declarative, configurable *policy*
("archive investigation sessions closed more than N days ago") instead
of leaving each table's soft-delete column set only by hand via ad hoc
route logic. `apply_retention_policy` is the one function that walks
all four tables; nothing in this module ever calls `.delete()`.
"""

import logging
import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.database.models import InvestigationSession, ConversationTurn, AuditLog

logger = logging.getLogger(__name__)


def _int_env(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else default
    except ValueError:
        return default


# Defaults are deliberately generous (measured in years, not months) —
# retention policy is meant to eventually archive stale operational
# clutter, not to aggressively purge a live investigation's history.
# All three are independently configurable per the brief's implicit
# expectation that different record types warrant different windows.
SESSION_RETENTION_DAYS = _int_env("SHERLOCK_SESSION_RETENTION_DAYS", 730)         # ~2 years after closing
CONVERSATION_RETENTION_DAYS = _int_env("SHERLOCK_CONVERSATION_RETENTION_DAYS", 730)  # currently informational
                                                                                       # (turns follow their session's
                                                                                       # archival directly — see
                                                                                       # archive_stale_conversation_turns)
AUDIT_RETENTION_DAYS = _int_env("SHERLOCK_AUDIT_RETENTION_DAYS", 1825)            # ~5 years, a common compliance floor


def get_retention_policy() -> dict:
    return {
        "investigation_sessions_days": SESSION_RETENTION_DAYS,
        "conversation_turns_days": CONVERSATION_RETENTION_DAYS,
        "audit_log_days": AUDIT_RETENTION_DAYS,
        "deletion_mode": "soft (archived_at/deactivated_at only — no row is ever physically deleted)",
    }


def archive_stale_sessions(db: Session, *, now: datetime | None = None) -> int:
    """Archives (sets archived_at) any closed InvestigationSession whose
    `closed_at` is older than SESSION_RETENTION_DAYS and isn't already
    archived. A session that was never closed is never auto-archived —
    retention counts from closure, not from opening."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=SESSION_RETENTION_DAYS)

    rows = (
        db.query(InvestigationSession)
        .filter(InvestigationSession.archived_at.is_(None))
        .filter(InvestigationSession.closed_at.isnot(None))
        .filter(InvestigationSession.closed_at < cutoff)
        .all()
    )
    for row in rows:
        row.archived_at = now
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def archive_stale_conversation_turns(db: Session, *, now: datetime | None = None) -> int:
    """Archives ConversationTurn rows belonging to a session that has
    itself been archived (by `archive_stale_sessions` or manually).
    Turns never outlive their session's own retention decision — they
    follow it directly (archived in the same sweep the session is
    archived in), rather than running an independent second clock on
    top of it."""
    now = now or datetime.utcnow()

    stale_session_ids = (
        db.query(InvestigationSession.id)
        .filter(InvestigationSession.archived_at.isnot(None))
        .subquery()
    )
    rows = (
        db.query(ConversationTurn)
        .filter(ConversationTurn.archived_at.is_(None))
        .filter(ConversationTurn.session_id.in_(stale_session_ids.select()))
        .all()
    )
    for row in rows:
        row.archived_at = now
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def archive_stale_audit_log(db: Session, *, now: datetime | None = None) -> int:
    """Archives AuditLog rows older than AUDIT_RETENTION_DAYS. Archived
    audit rows are still queryable via GET /audit (no filter excludes
    them by default) — 'archived' means 'eligible for external cold
    storage / compliance export', not 'hidden'."""
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=AUDIT_RETENTION_DAYS)

    rows = (
        db.query(AuditLog)
        .filter(AuditLog.archived_at.is_(None))
        .filter(AuditLog.created_at < cutoff)
        .all()
    )
    for row in rows:
        row.archived_at = now
        db.add(row)
    if rows:
        db.commit()
    return len(rows)


def apply_retention_policy(db: Session, *, now: datetime | None = None) -> dict:
    """Runs all three sweeps. Never deletes a row. Safe to call
    repeatedly (idempotent — already-archived rows are skipped via the
    `archived_at IS NULL` filter in each sweep)."""
    now = now or datetime.utcnow()
    sessions_archived = archive_stale_sessions(db, now=now)
    turns_archived = archive_stale_conversation_turns(db, now=now)
    audit_rows_archived = archive_stale_audit_log(db, now=now)

    result = {
        "sessions_archived": sessions_archived,
        "conversation_turns_archived": turns_archived,
        "audit_rows_archived": audit_rows_archived,
        "ran_at": now.isoformat(),
    }
    logger.info("Retention sweep: %r", result)
    return result
