"""
SHERLOCK — Stage F2 (Conversation Intelligence System): on-demand summary.

`ConversationMemoryService.maybe_summarize` (Stage C2, Sprint 2) already
does the real work of folding old turns into a rolling
`InvestigationSession.context_summary`, but only fires automatically
once a session passes 8 turns. A chat interface's "summarize this
conversation" command (routed by `router.py`) needs an answer on a
session of *any* length, including a 2-turn one — so this wraps the same
service with `threshold=0`, forcing every turn seen so far to fold in,
without duplicating its summarization logic.
"""

from __future__ import annotations

from backend.database.models import InvestigationSession
from backend.memory.conversation_memory import ConversationMemoryService


def summarize_now(db, session_id: int) -> dict:
    """Forces `ConversationMemoryService.maybe_summarize` to run
    regardless of the normal 8-turn threshold, then returns the
    resulting summary. Safe to call on an empty conversation (returns an
    honest "nothing to summarize yet" rather than an empty string)."""
    memory = ConversationMemoryService(db)
    turns = memory.get_history(session_id)

    if not turns:
        return {
            "session_id": session_id,
            "summary": None,
            "summary_through_turn": None,
            "turn_count": 0,
        }

    # keep_recent=0 so a forced "summarize now" folds in every turn,
    # including the most recent one — unlike the automatic path, which
    # deliberately leaves the last few turns unfolded for prompt-context
    # freshness. See maybe_summarize's own docstring for that rationale.
    memory.maybe_summarize(session_id, threshold=0, keep_recent=0)

    session_row = db.get(InvestigationSession, session_id)
    return {
        "session_id": session_id,
        "summary": session_row.context_summary if session_row else None,
        "summary_through_turn": session_row.context_summary_through_turn if session_row else None,
        "turn_count": len(turns),
    }
