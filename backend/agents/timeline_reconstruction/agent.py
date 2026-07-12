"""
SHERLOCK — Timeline Reconstruction Agent (Phase 5, Intelligence Division).

Orders the crimes in scope (from `graph_context["crime_ids"]`, set by the
Crime Records Agent) chronologically, and looks for a simple, real
escalation signal: the time between consecutive incidents shrinking over
the sequence. No ML — just sorted timestamps and pairwise deltas, applied
to genuine `Crime.timestamp` / `FIR` data.
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Crime


class TimelineReconstructionAgent(BaseAgent):
    name = "TimelineReconstruction"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        crime_ids = gctx.get("crime_ids")

        query = self.session.query(Crime)
        if crime_ids:
            query = query.filter(Crime.id.in_(crime_ids))
        crimes = query.order_by(Crime.timestamp).all()

        if not crimes:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="investigation_timeline",
                summary="No crimes in scope to sequence into a timeline.",
                confidence=0.5,
            )]

        events = []
        for c in crimes:
            events.append({
                "crime_id": c.id,
                "type": c.type.value,
                "timestamp": c.timestamp.isoformat(),
                "district": c.location.district if c.location else None,
                "fir_number": c.fir.fir_number if c.fir else None,
                "fir_status": c.fir.status.value if c.fir else None,
            })

        first, last = crimes[0], crimes[-1]
        span_days = (last.timestamp - first.timestamp).days

        escalation_note = ""
        if len(crimes) >= 3:
            gaps = [(crimes[i + 1].timestamp - crimes[i].timestamp).days for i in range(len(crimes) - 1)]
            monotonic_shrinking = all(gaps[i] >= gaps[i + 1] for i in range(len(gaps) - 1)) and gaps[0] > gaps[-1]
            if monotonic_shrinking:
                escalation_note = (
                    f" Time between incidents is shrinking ({gaps[0]}d \u2192 {gaps[-1]}d) "
                    f"across the sequence \u2014 a possible escalation pattern worth flagging."
                )

        summary = (
            f"Reconstructed a {len(events)}-event timeline spanning {span_days} day(s), "
            f"from {first.timestamp:%Y-%m-%d} ({first.type.value}) to {last.timestamp:%Y-%m-%d} ({last.type.value})."
            + escalation_note
        )

        finding = AgentFinding(
            agent_name=self.name,
            finding_type="investigation_timeline",
            summary=summary,
            evidence=[
                f"{e['timestamp'][:10]}: {e['type']} in {e['district'] or 'unknown district'}"
                + (f" ({e['fir_number']})" if e["fir_number"] else "")
                for e in events[:6]
            ],
            confidence=0.92 if not escalation_note else 0.8,  # escalation call is a heuristic, so slightly lower
            source_entities=[f"crime_{e['crime_id']}" for e in events],
            metadata={"events": events, "span_days": span_days},
        )

        return [finding]
