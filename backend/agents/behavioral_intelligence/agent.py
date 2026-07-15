"""
SHERLOCK — Behavioral Intelligence Agent (Sprint B4, Stage B Division 11).

Upgrades the informal "profiling" signals scattered across Network
Analysis (repeat-offender ranking) and Timeline Reconstruction
(escalation detection) into one consolidated per-person behavioral
profile, adding two genuinely new signals the AER migration made
possible: violence weighting by crime type, and gang likelihood from
association-graph density + Organization membership.

Every score below is a stated, transparent heuristic (0-100), not a
learned/calibrated model — the formula is in this docstring and in each
score's evidence line, not hidden in the arithmetic.

    - Escalation score: shrinking gaps between this person's own crimes
      over time (same logic as Timeline Reconstruction's crime-sequence
      check, applied per-accused rather than per-case-scope).
    - Violence score: weighted average of CrimeType severity across their
      accused records (see VIOLENCE_WEIGHTS — assault/drug_trafficking
      weighted highest, fraud/cybercrime lowest; this weighting is a
      judgment call, not a criminological standard, and is stated as such).
    - Repeat offender score: normalized count of distinct FIRs as accused
      (same underlying fact Network Analysis already surfaces at the
      graph level; this restates it as a comparable 0-100 score
      alongside the other four dimensions).
    - Gang likelihood: co_accused/associate ties in PersonAssociation,
      boosted if the person is an Organization member (Sprint B3 data).
    - Mobility pattern: count of distinct districts across their crimes —
      reported as a number/list, not scored 0-100, since "high mobility"
      isn't inherently a risk signal the way the other four are.
"""

from collections import Counter

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Crime, Accused, PersonAssociation, OrganizationMembership, RelationType

VIOLENCE_WEIGHTS = {
    "assault": 100, "drug_trafficking": 70, "burglary": 40,
    "theft": 30, "fraud": 20, "cybercrime": 15,
}
MAX_PERSONS = 6


class BehavioralIntelligenceAgent(BaseAgent):
    name = "BehavioralIntelligence"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        accused_person_ids = list(gctx.get("accused_person_ids", []) or [])[:MAX_PERSONS]

        if not accused_person_ids:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="behavioral_profile",
                summary="No accused persons in scope to build a behavioral profile from.",
                confidence=0.5,
            )]

        return [self._profile(pid) for pid in accused_person_ids]

    def _profile(self, person_id: int):
        accused_records = self.session.query(Accused).filter_by(person_id=person_id).all()
        crimes = sorted((a.fir.crime for a in accused_records if a.fir and a.fir.crime), key=lambda c: c.timestamp)
        if not crimes:
            return AgentFinding(
                agent_name=self.name,
                finding_type="behavioral_profile",
                summary=f"person_{person_id}: no crime records found to profile.",
                confidence=0.5,
                source_entities=[f"person_{person_id}"],
            )
        person = accused_records[0].person

        escalation_score = self._escalation_score(crimes)
        violence_score = round(sum(VIOLENCE_WEIGHTS.get(c.type.value, 25) for c in crimes) / len(crimes))
        repeat_score = min(len(accused_records) * 25, 100)
        gang_score, gang_notes = self._gang_likelihood(person_id)
        districts = sorted({c.location.district for c in crimes if c.location})

        summary = (
            f"{person.name}: violence {violence_score}/100, repeat-offender {repeat_score}/100, "
            f"gang likelihood {gang_score}/100, escalation {escalation_score}/100, "
            f"active across {len(districts)} district(s)."
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="behavioral_profile",
            summary=summary,
            evidence=[
                f"{len(accused_records)} accused record(s) across {len(crimes)} crime(s)",
                f"Crime types: {', '.join(sorted({c.type.value for c in crimes}))}",
                f"Districts: {', '.join(districts) or 'unknown'}",
            ] + gang_notes,
            confidence=0.75,  # composite heuristic, stated as such
            source_entities=[f"person_{person_id}"] + [f"crime_{c.id}" for c in crimes],
            metadata={
                "person_id": person_id,
                "name": person.name,
                "violence_score": violence_score,
                "repeat_offender_score": repeat_score,
                "gang_likelihood_score": gang_score,
                "escalation_score": escalation_score,
                "mobility_districts": districts,
                "crime_count": len(crimes),
            },
        )

    @staticmethod
    def _escalation_score(crimes):
        if len(crimes) < 3:
            return 0
        gaps = [(crimes[i + 1].timestamp - crimes[i].timestamp).days for i in range(len(crimes) - 1)]
        shrinking_steps = sum(1 for i in range(len(gaps) - 1) if gaps[i + 1] < gaps[i])
        return round(shrinking_steps / max(len(gaps) - 1, 1) * 100)

    def _gang_likelihood(self, person_id: int):
        assocs = (
            self.session.query(PersonAssociation)
            .filter(
                (PersonAssociation.person_a_id == person_id) | (PersonAssociation.person_b_id == person_id)
            ).all()
        )
        co_accused_ties = [a for a in assocs if a.relation_type == RelationType.CO_ACCUSED]
        is_org_member = self.session.query(OrganizationMembership).filter_by(person_id=person_id).first() is not None

        score = min(len(co_accused_ties) * 20 + len(assocs) * 5, 100)
        notes = [f"{len(assocs)} known association(s) on record, {len(co_accused_ties)} co-accused tie(s)"]
        if is_org_member:
            score = min(score + 30, 100)
            notes.append("Organization membership on record — boosts gang likelihood")
        return score, notes
