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


def make_event(event_type: EventType, agent: str = None, message: str = None,
               data: Any = None) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type.value,
        "agent": agent,
        "message": message,
        "data": data,
    }
