"""
SHERLOCK — Stage F2 (Conversation Intelligence System): session helper.

A chat turn always needs an `InvestigationSession` to attach conversation
memory to (Stage C1/C2). Every existing entry point (WebSocket, voice
router, `/investigate`) makes the caller pass an already-open
`session_id` or leaves memory disabled. A chat-first interface can't
reasonably ask "which session id?" before the very first message, so
this module's only job is: given an optional session_id, return a real,
open `InvestigationSession`, opening a new one on first use.

No new table, no new columns — this is a thin convenience over
`DatabaseService.open_case` / `get_session`, which already do the real
work (and already write the session's own `SessionActivity` audit row).
"""

from __future__ import annotations

import logging

from backend.database.models import InvestigationSession
from backend.database.service import DatabaseService

logger = logging.getLogger(__name__)

DEFAULT_SESSION_TITLE = "Conversation"


def get_or_create_session(
    db,
    session_id: int | None,
    officer_id: int | None = None,
    title: str | None = None,
) -> InvestigationSession:
    """Returns the InvestigationSession for `session_id`, or opens a new
    one (title defaults to "Conversation" — renamed later from the
    board/investigations screen like any other session) if `session_id`
    is None or doesn't resolve to a real row.

    Deliberately permissive about a stale/unknown session_id (opens a
    fresh session rather than raising) because a chat client's local
    state can outlive a session someone else archived elsewhere; the
    alternative (hard 404) would strand the conversation mid-message.
    """
    svc = DatabaseService(db)

    if session_id is not None:
        existing = svc.get_session(session_id)
        if existing is not None:
            return existing
        logger.info("Conversation session_id=%s not found — opening a new session instead.", session_id)

    return svc.open_case(
        title=title or DEFAULT_SESSION_TITLE,
        opened_by_officer_id=officer_id,
    )
