"""
SHERLOCK — Stage F2 (Conversation Intelligence System): suggested questions.

The CIS proposal's `SuggestedQuestions` frontend component needs
something to show under the composer after each turn. In keeping with
this codebase's stated preference for templated, evidence-grounded
output over freely-generated LLM text (see ChiefAgent's synthesis and
ConversationMemoryService's summarizer, both of which only reach for an
LLM when `ANTHROPIC_API_KEY` is set and fall back to deterministic
templates otherwise), suggestions here are template-based and derived
directly from what the *last turn actually found* — never invented.

This intentionally only suggests questions the existing reference-
resolution patterns in `backend/memory/conversation_memory.py` can
already answer ("expand his network", "freeze that account"), so a
suggestion is never a dead end.
"""

from __future__ import annotations

from backend.database.models import ConversationTurn

MAX_SUGGESTIONS = 4

_GENERIC_STARTERS = [
    "Show recent burglary cases in Mysuru",
    "Which accounts show suspicious transaction patterns?",
    "Who are the top repeat offenders this year?",
    "Show festival-season crime hotspots",
]


def suggest_questions(last_turn: ConversationTurn | None) -> list[str]:
    """Suggestions for the *next* message, given the most recent turn
    (or None, for a brand-new conversation)."""
    if last_turn is None:
        return _GENERIC_STARTERS[:MAX_SUGGESTIONS]

    suggestions: list[str] = []

    if last_turn.last_person_name:
        name = last_turn.last_person_name
        suggestions.append(f"Expand {name}'s network")
        suggestions.append(f"Show {name}'s FIR history")

    if last_turn.last_account_id:
        suggestions.append("Trace this account's transaction history")

    if last_turn.last_fir_id:
        suggestions.append("Reconstruct the timeline for this case")

    if not suggestions:
        suggestions.append("Summarize this conversation")

    # Round out with generic starters if a turn only produced one or two
    # entity-grounded suggestions, without ever exceeding MAX_SUGGESTIONS.
    for starter in _GENERIC_STARTERS:
        if len(suggestions) >= MAX_SUGGESTIONS:
            break
        if starter not in suggestions:
            suggestions.append(starter)

    return suggestions[:MAX_SUGGESTIONS]
