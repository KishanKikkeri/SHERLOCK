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
from backend.graph.service import get_graph_service
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


async def stream_investigation(query: str, send):
    """
    Run the investigation pipeline and call `send(event_dict)` after each
    node. `send` is an async callable (WebSocket.send_json or an SSE helper).

    Builds a fresh DB session and graph service per investigation so
    concurrent requests don't share state.
    """
    await send(make_event(EventType.INVESTIGATION_STARTED, message=f"Investigation started: {query}"))

    session = SessionLocal()
    try:
        graph_service = get_graph_service(backend="networkx", session=session)
        graph = build_investigation_graph(session, graph_service)

        initial_state = {
            "query": query,
            "conversation_id": "live",
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

    except Exception as e:
        logger.exception("Investigation pipeline failed for query: %r", query)
        await send(make_event(EventType.ERROR, message=str(e)))
    finally:
        session.close()
