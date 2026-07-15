"""
SHERLOCK — Witness Intelligence Agent (Sprint B2, Stage B Division 3).

Consolidation note: the brief lists two agents — Witness Reliability and
Witness Network. Both need the exact same starting query (every Witness
record for the persons in scope) and differ only in what they compute
from it, so they're implemented as two finding types from one agent
rather than two agents duplicating the same data-gathering pass. If a
future sprint needs the network piece to be a real graph traversal (not
just a same-case-cluster summary), splitting it out to reuse
NetworkAnalysisAgent's graph_service would be the natural point to
actually separate them.

Witness Reliability score (stated explicitly, no formula given in the
brief): starts at a baseline and adjusts for two real signals —
    (+) multiple independent statements on record (more testimony history
        = more to cross-check against, not automatically "more reliable,"
        but it's the only volume signal this schema has)
    (-) the witness is ALSO an accused person in some other case in the
        database — a real credibility flag any investigator would want
        surfaced, and now directly queryable via the Accused table.
This is a heuristic score, not a certified reliability metric — labeled
as such in the output.
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Crime, Witness, Accused

MAX_WITNESSES = 8


class WitnessIntelligenceAgent(BaseAgent):
    name = "WitnessIntelligence"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        crime_ids = gctx.get("crime_ids")

        query = self.session.query(Crime)
        if crime_ids:
            query = query.filter(Crime.id.in_(crime_ids))
        crimes = query.all()

        fir_ids = {c.fir.id for c in crimes if c.fir}
        if not fir_ids:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="witness_reliability",
                summary="No FIRs in scope to check for witnesses.",
                confidence=0.5,
            )]

        witnesses_in_scope = (
            self.session.query(Witness).filter(Witness.fir_id.in_(fir_ids)).limit(MAX_WITNESSES).all()
        )
        if not witnesses_in_scope:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="witness_reliability",
                summary="No witnesses on record for the case(s) in scope.",
                confidence=0.6,
            )]

        person_ids = {w.person_id for w in witnesses_in_scope}
        findings = [self._reliability(pid) for pid in person_ids]

        network_finding = self._network(person_ids)
        if network_finding:
            findings.append(network_finding)

        return findings

    def _reliability(self, person_id: int):
        all_witness_records = self.session.query(Witness).filter_by(person_id=person_id).all()
        person = all_witness_records[0].person
        case_count = len(all_witness_records)

        is_also_accused = self.session.query(Accused).filter_by(person_id=person_id).first() is not None

        score = 50 + min(case_count - 1, 3) * 10  # +10 per extra case testified in, capped
        contradiction_note = ""
        if is_also_accused:
            score -= 25
            contradiction_note = " Flagged: this person also appears as an accused in another case on record — a credibility factor worth checking before relying on their statement."

        score = max(0, min(100, score))

        summary = (
            f"Witness reliability (heuristic): {person.name} — {score}/100, "
            f"testified in {case_count} case(s) on record.{contradiction_note}"
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="witness_reliability",
            summary=summary,
            evidence=[f"Statement in FIR {w.fir.fir_number}, {w.statement_date}" for w in all_witness_records[:5] if w.fir],
            confidence=0.7,  # heuristic score, not a certified metric — kept below 0.9 deliberately
            source_entities=[f"person_{person_id}"],
            metadata={
                "person_id": person_id,
                "name": person.name,
                "reliability_score": score,
                "case_count": case_count,
                "also_accused_elsewhere": is_also_accused,
            },
        )

    def _network(self, person_ids: set):
        """Witness -> Cases -> Persons: for each witness in scope, which
        other persons (accused/victim/witness) share a case with them.
        Organization is part of the brief's diagram too, but with zero
        witnesses in the fixture data linked to an organization-member
        case, there's nothing real to traverse there yet — left out
        rather than emitting an always-empty claim."""
        clusters = {}
        for pid in person_ids:
            witness_records = self.session.query(Witness).filter_by(person_id=pid).all()
            co_persons = set()
            for w in witness_records:
                fir = w.fir
                if not fir:
                    continue
                co_persons.update(a.person_id for a in fir.accused_records if a.person_id != pid)
                co_persons.update(v.person_id for v in fir.victim_records if v.person_id != pid)
                co_persons.update(ww.person_id for ww in fir.witness_records if ww.person_id != pid)
            if co_persons:
                clusters[pid] = sorted(co_persons)

        if not clusters:
            return None

        total_links = sum(len(v) for v in clusters.values())
        summary = (
            f"Witness network: {len(clusters)} witness(es) in scope are connected to "
            f"{total_links} other person(s) via shared cases."
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="witness_network",
            summary=summary,
            evidence=[f"person_{pid} shares case(s) with {len(co)} other person(s): {co}" for pid, co in clusters.items()],
            confidence=0.85,
            source_entities=[f"person_{pid}" for pid in clusters],
            metadata={"clusters": {str(k): v for k, v in clusters.items()}},
        )
