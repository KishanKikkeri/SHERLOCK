"""
SHERLOCK — Stage F2 (Conversation Intelligence System): intent routing.

`backend/agents/base/query_parser.py` already decides *which specialist
agents* an investigation query needs. This module sits one level above
that: it decides whether an incoming chat message is an investigation
query at all, or a "meta" command about the conversation itself
("summarize this", "export this as a PDF", "clear this conversation") —
the kind of thing a chat interface's own manager should handle directly
rather than handing to the Chief Investigation Officer as if it were a
crime-intelligence question.

Same philosophy as query_parser.py and conversation_memory.py: a fixed,
documented set of phrases, not a general-purpose LLM intent classifier.
Ambiguous or unmatched text always falls through to INVESTIGATE — a
missed meta-command just gets investigated (and the investigation
pipeline degrades honestly for a nonsense query), which is a safer
failure mode than silently swallowing a real investigative question
because it loosely resembled a command word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class ConversationIntent(str, Enum):
    INVESTIGATE = "investigate"      # default — run the investigation pipeline
    SUMMARIZE = "summarize"          # "summarize this conversation / where are we"
    EXPORT_PDF = "export_pdf"        # "export this as a pdf / give me a report"
    CLEAR_HISTORY = "clear_history"  # "clear this conversation / start fresh"


@dataclass
class RoutedIntent:
    intent: ConversationIntent
    matched_phrase: str | None = None


_SUMMARIZE_RE = re.compile(
    r"\b(summari[sz]e (this|the|our)?\s*(conversation|session|investigation|so far)?|"
    r"what('s| is| have we) (covered|discussed|found) so far|recap|catch me up)\b",
    re.IGNORECASE,
)

_EXPORT_RE = re.compile(
    r"\b(export (this|it|the report)?\s*(as|to)?\s*(a )?pdf|"
    r"(give|generate|download|create) (me )?(a |the )?(pdf|report)|"
    r"pdf (report|export))\b",
    re.IGNORECASE,
)

_CLEAR_RE = re.compile(
    r"\b(clear (this|the)?\s*(conversation|history|chat)|"
    r"wipe (the )?(conversation|history)|delete (this )?(conversation|history))\b",
    re.IGNORECASE,
)


def route(message: str) -> RoutedIntent:
    """Classifies a raw chat message. Order matters only in that all
    three meta patterns are checked before defaulting to INVESTIGATE —
    they're mutually exclusive by construction (no phrase matches more
    than one), so there's no real precedence question between them."""
    text = (message or "").strip()

    m = _CLEAR_RE.search(text)
    if m:
        return RoutedIntent(ConversationIntent.CLEAR_HISTORY, m.group(0))

    m = _EXPORT_RE.search(text)
    if m:
        return RoutedIntent(ConversationIntent.EXPORT_PDF, m.group(0))

    m = _SUMMARIZE_RE.search(text)
    if m:
        return RoutedIntent(ConversationIntent.SUMMARIZE, m.group(0))

    return RoutedIntent(ConversationIntent.INVESTIGATE, None)
