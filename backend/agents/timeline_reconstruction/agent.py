"""
SHERLOCK — Timeline Intelligence Agent (Stage A: Phase 5 baseline;
Sprint B1: upgraded per Stage B Division 1).

Baseline (Phase 5, unchanged): orders the crimes in scope chronologically
and looks for a simple, real escalation signal — the time between
consecutive incidents shrinking over the sequence. No ML, just sorted
timestamps and pairwise deltas.

Sprint B1 upgrade: the crime-event timeline above only existed because
`Crime.timestamp` was the only dated fact the old schema had. The AER
migration added real process events with their own dates — FIR filing,
investigation open/close, arrests (including bail status), chargesheet
filing, and property seizure. This agent now merges all of those into one
chronological case-process timeline alongside the crime-sequence view,
scoped by the same `graph_context["crime_ids"]`. Court hearing dates
aren't included — no hearing-date field exists on ChargeSheet/Court in
the current schema (only a filing date), so "court hearings" from the
Stage B brief's list isn't representable yet without a further schema
addition.
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
            f"Reconstructed a {len(events)}-event crime timeline spanning {span_days} day(s), "
            f"from {first.timestamp:%Y-%m-%d} ({first.type.value}) to {last.timestamp:%Y-%m-%d} ({last.type.value})."
            + escalation_note
        )

        crime_timeline_finding = AgentFinding(
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

        findings = [crime_timeline_finding]

        case_process_finding = self._build_case_process_timeline(crimes)
        if case_process_finding:
            findings.append(case_process_finding)

        return findings

    def _build_case_process_timeline(self, crimes):
        """Sprint B1: merges FIR filing, investigation open/close, arrests
        (with bail status), chargesheet filing, and property seizure into
        one chronological process timeline per case in scope."""
        process_events = []

        for crime in crimes:
            fir = crime.fir
            if not fir:
                continue

            process_events.append({
                "date": fir.filed_date, "type": "fir_filed",
                "detail": f"FIR {fir.fir_number} registered ({fir.status.value})",
            })
            for inv in fir.investigations:
                process_events.append({
                    "date": inv.start_date, "type": "investigation_start",
                    "detail": f"Investigation opened by officer {inv.officer_id}",
                })
                if inv.end_date:
                    process_events.append({
                        "date": inv.end_date, "type": "investigation_end",
                        "detail": "Investigation closed",
                    })
            for arrest in fir.arrests:
                bail_note = " — released on bail" if arrest.status.value == "released_on_bail" else ""
                process_events.append({
                    "date": arrest.arrest_date, "type": "arrest",
                    "detail": f"Person {arrest.person_id} arrested{bail_note}",
                })
            for cs in fir.chargesheets:
                process_events.append({
                    "date": cs.filed_date, "type": "chargesheet_filed",
                    "detail": f"Chargesheet filed ({cs.status.value})",
                })
            for prop in fir.properties:
                process_events.append({
                    "date": prop.seized_date, "type": "property_seized",
                    "detail": f"{prop.category or 'item'} seized: {prop.description}",
                })
            for w in fir.witness_records:
                if w.statement_date:
                    process_events.append({
                        "date": w.statement_date, "type": "witness_statement",
                        "detail": f"Statement recorded from witness {w.raw_name_used}",
                    })

        if not process_events:
            return None

        process_events.sort(key=lambda e: e["date"])

        return AgentFinding(
            agent_name=self.name,
            finding_type="case_process_timeline",
            summary=(
                f"Case-process timeline: {len(process_events)} recorded event(s) "
                f"from {process_events[0]['detail']} to {process_events[-1]['detail']}."
            ),
            evidence=[f"{e['date']:%Y-%m-%d}: {e['detail']}" for e in process_events[:8]],
            confidence=0.95,  # direct roll-up of recorded dates, not an inference
            source_entities=[f"crime_{c.id}" for c in crimes],
            metadata={"process_events": [
                {**e, "date": e["date"].isoformat()} for e in process_events
            ]},
        )
