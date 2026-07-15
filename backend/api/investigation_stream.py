"""
SHERLOCK — Streaming investigation runner (Phase 6).

Wraps `run_investigation` to emit WebSocket events after each LangGraph
node completes, giving the frontend its live activity feed.

LangGraph's `.stream()` yields state diffs keyed by node name after each
node executes, which maps directly onto our AgentEvent protocol.
"""

import asyncio
import json
import logging

from backend.api.events import EventType, make_event
from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.graph.service import get_graph_service
from backend.memory.conversation_memory import ConversationMemoryService
from backend.orchestrator.graph import build_investigation_graph

logger = logging.getLogger(__name__)

# Node name -> display name for the activity feed.
#
# IMPORTANT: every value here must be unique. The frontend's investigation
# timeline (`useInvestigation.ts`) matches an incoming event's `agent` field
# against `AgentStep.name` to update the right row — if two node keys ever
# shared a display name again (as chief_plan/chief_synthesis once did, both
# as plain "Chief Investigation Officer"), the second node's completion
# event would silently overwrite the first node's row instead of updating
# its own, and that row would never receive its own update at all.
NODE_LABELS = {
    "chief_plan":              "Chief Investigation Officer — Planning",
    "crime_records":           "Crime Records Agent",
    "network_analysis":        "Network Analysis Agent",
    "entity_resolution":       "Entity Resolution Agent",
    "timeline_reconstruction": "Timeline Reconstruction Agent",
    "financial_agent":         "Financial Intelligence Agent",
    "similar_case":            "Similar Case Agent",
    "pattern_analysis":        "Pattern & MO Agent",
    "forecasting_agent":       "Forecasting Agent",
    "prevention_agent":        "Prevention Intelligence Agent",
    "evidence_validation":     "Evidence Validation Agent",
    "chief_synthesis":         "Chief Investigation Officer — Synthesis",
}


async def stream_investigation(query: str, send, session_id: int | None = None):
    """
    Run the investigation pipeline and call `send(event_dict)` after each
    node. `send` is an async callable (WebSocket.send_json or an SSE helper).

    Builds a fresh DB session and graph service per investigation so
    concurrent requests don't share state.

    `session_id` (Stage C2, optional): if provided, this must be an
    existing InvestigationSession id. The raw query is resolved against
    that session's conversation memory ("expand his network" ->
    "expand Ravi Kumar's network") before being handed to the Chief, and
    the finished turn is persisted so the next turn on the same session
    can resolve against it too. Omitting session_id (existing callers,
    e.g. demo scripts) behaves exactly as before this sprint.
    """
    await send(make_event(EventType.INVESTIGATION_STARTED, message=f"Investigation started: {query}"))

    session = SessionLocal()
    try:
        memory = ConversationMemoryService(session) if session_id is not None else None
        resolved_query = query
        if memory is not None:
            db = DatabaseService(session)
            if db.get_session(session_id) is None:
                await send(make_event(EventType.ERROR, message=f"Unknown session_id {session_id}."))
                return
            resolved_query = memory.resolve_query(session_id, query)
            if resolved_query != query:
                await send(make_event(
                    EventType.AGENT_COMPLETED,
                    agent="Conversation Memory",
                    message=f'Resolved "{query}" -> "{resolved_query}" from session history.',
                ))

        graph_service = get_graph_service(backend="networkx", session=session)
        graph = build_investigation_graph(session, graph_service)

        initial_state = {
            "query": resolved_query,
            "raw_query": query,
            "resolved_query": resolved_query,
            "conversation_id": "live",
            "session_id": session_id,
            "investigation_plan": {},
            "active_agents": [],
            "findings": [],
            "validated_findings": [],
            "evidence_log": [],
            "graph_context": {},
            "final_report": {},
            "audit_trail": [],
        }

        final_state = None
        for step in graph.stream(initial_state):
            node_name, node_state = next(iter(step.items()))
            display_name = NODE_LABELS.get(node_name, node_name)

            # Pull the latest audit entry for this node's message
            trail = node_state.get("audit_trail", [])
            message = trail[-1]["message"] if trail else f"{display_name} completed."
            status = trail[-1]["status"] if trail else "done"

            etype = (
                EventType.AGENT_SKIPPED if status == "skipped"
                else EventType.AGENT_FAILED if status == "failed"
                else EventType.AGENT_COMPLETED
            )

            # Attach new findings as data payload for the frontend
            new_findings = node_state.get("findings", [])
            validated = node_state.get("validated_findings")
            report = node_state.get("final_report")

            await send(make_event(
                etype,
                agent=display_name,
                message=message,
                data={
                    "new_findings": new_findings,
                    "validated_findings": validated,
                    "final_report": report,
                },
            ))

            # Small yield so the event loop can flush the send
            await asyncio.sleep(0.05)
            final_state = node_state

        # Emit the complete final report
        if final_state:
            combined_report = final_state.get("final_report") or {}
            await send(make_event(
                EventType.REPORT_READY,
                agent="Chief Investigation Officer",
                message="Investigation complete. Final report ready.",
                data={"final_report": combined_report},
            ))

            if memory is not None:
                memory.record_turn(session_id, raw_query=query, resolved_query=resolved_query,
                                    final_state=final_state)

    except Exception as e:
        logger.exception("Investigation pipeline failed for query: %r", query)
        await send(make_event(EventType.ERROR, message=str(e)))
    finally:
        session.close()


async def run_investigation_once(query: str, session_id: int | None = None) -> dict:
    """Convenience wrapper for callers that just want the finished
    report, not a live event feed — e.g. Stage C3's voice command router,
    which needs one synchronous-feeling result to hand back to the
    browser's TTS. Internally just drains `stream_investigation`'s events
    and returns the `report_ready` payload (or raises on `error`)."""
    events = []

    async def collect(event: dict):
        events.append(event)

    await stream_investigation(query, collect, session_id=session_id)

    error = next((e for e in events if e.get("event_type") == "error"), None)
    if error:
        raise RuntimeError(error.get("message", "Investigation failed."))

    report_event = next((e for e in events if e.get("event_type") == "report_ready"), None)
    if report_event is None:
        raise RuntimeError("Investigation did not produce a final report.")
    return report_event["data"]["final_report"]
