"""
SHERLOCK — WebSocket event protocol (Phase 6).

Every event pushed to the frontend during an investigation follows this
structure. The frontend Activity Feed listens for these and renders them
live as the agent pipeline executes.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any


class EventType(str, Enum):
    INVESTIGATION_STARTED = "investigation_started"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_SKIPPED = "agent_skipped"
    AGENT_FAILED = "agent_failed"  # one agent errored; the investigation continues without it
    FINDING_PRODUCED = "finding_produced"
    VALIDATION_COMPLETE = "validation_complete"
    REPORT_READY = "report_ready"
    ERROR = "error"

    # Stage C2, Sprint 2 — additive, existing clients that don't handle
    # these simply won't render them (frontend Activity Feed already
    # ignores unrecognized agent labels rather than crashing).
    CLARIFICATION_NEEDED = "clarification_needed"
    TOPIC_RESET = "topic_reset"

    # Stage C4, Sprint 3 — additive. Only ever sent when Discussion Mode
    # is explicitly enabled for a turn; existing callers that never pass
    # enable_discussion=True never see these.
    DISCUSSION_STARTED = "discussion_started"
    DISCUSSION_OPINION = "discussion_opinion"
    DISCUSSION_DISAGREEMENT = "discussion_disagreement"
    DISCUSSION_CONSENSUS = "discussion_consensus"

    # Stage D, Sprint 1/2 — additive. Only ever sent when the incoming
    # query is in a non-English language (detected or explicitly
    # requested); existing English-only callers never see this event.
    QUERY_TRANSLATED = "query_translated"


def make_event(event_type: EventType, agent: str = None, message: str = None,
               data: Any = None) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type.value,
        "agent": agent,
        "message": message,
        "data": data,
    }
