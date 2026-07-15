"""
SHERLOCK — Sociological Intelligence Agent (Sprint B4, Stage B Division 12).

Schema gap, stated up front rather than worked around: the brief names
six dimensions — gender, age, occupation, education, migration,
urbanization. `Person` only has three of these (gender, age, occupation).
There is no education field, no migration/origin field, and no
urban/rural classification anywhere in the AER schema built in Stage A.
Rather than fake those three with a placeholder or silently drop them
from the output, this agent explicitly reports them as "not available in
current schema" in its metadata, so a report consumer sees the gap
instead of an unexplained absence. Adding them would be a real (small)
schema change — flagged as follow-up work, not done here without a
concrete reason to add fields three other agents also wouldn't use yet.

What IS produced: a real demographic breakdown of the accused persons in
scope (gender split, age-bracket distribution, top occupations) —
described in the brief as a "Risk map." This agent produces the
underlying breakdown data; it does not draw an actual choropleth/map
(that's a frontend rendering concern, out of scope per every prior
sprint's "no frontend changes" boundary — the data shape here is exactly
what a district-level risk map would need to render from).
"""

from collections import Counter

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Accused, Person

AGE_BRACKETS = [(0, 18, "under 18"), (18, 25, "18-24"), (25, 35, "25-34"), (35, 50, "35-49"), (50, 200, "50+")]

SCHEMA_GAP_NOTE = (
    "education, migration, and urbanization are named in the Stage B brief but have no "
    "corresponding field in the current AER schema — reported as unavailable, not estimated."
)


class SociologicalIntelligenceAgent(BaseAgent):
    name = "SociologicalIntelligence"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        accused_person_ids = gctx.get("accused_person_ids")

        query = self.session.query(Person)
        if accused_person_ids:
            query = query.filter(Person.id.in_(accused_person_ids))
        else:
            # No specific scope — profile everyone currently on record as
            # an accused, not the whole persons table (victims/witnesses
            # aren't what a risk-map query is asking about).
            accused_ids = {a.person_id for a in self.session.query(Accused).all()}
            if not accused_ids:
                return [AgentFinding(
                    agent_name=self.name,
                    finding_type="sociological_profile",
                    summary="No accused persons on record to build a demographic profile from.",
                    confidence=0.5,
                )]
            query = query.filter(Person.id.in_(accused_ids))

        persons = query.all()
        if not persons:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="sociological_profile",
                summary="No accused persons in scope to build a demographic profile from.",
                confidence=0.5,
            )]

        gender_counts = Counter(p.gender.value for p in persons)
        occupation_counts = Counter(p.occupation or "unspecified" for p in persons)
        bracket_counts = Counter(self._bracket(p.age) for p in persons)

        top_occupation, top_occ_count = occupation_counts.most_common(1)[0]
        dominant_bracket, bracket_count = bracket_counts.most_common(1)[0]

        summary = (
            f"Demographic profile of {len(persons)} accused person(s) in scope: "
            f"{dict(gender_counts)}, most common age bracket {dominant_bracket} "
            f"({bracket_count}/{len(persons)}), most common occupation '{top_occupation}' "
            f"({top_occ_count}/{len(persons)}). {SCHEMA_GAP_NOTE}"
        )

        return [AgentFinding(
            agent_name=self.name,
            finding_type="sociological_profile",
            summary=summary,
            evidence=[
                f"Gender distribution: {dict(gender_counts)}",
                f"Age brackets: {dict(bracket_counts)}",
                f"Top occupations: {occupation_counts.most_common(3)}",
            ],
            confidence=0.9,  # direct tabulation of recorded fields, not an inference
            source_entities=[f"person_{p.id}" for p in persons],
            metadata={
                "sample_size": len(persons),
                "gender_distribution": dict(gender_counts),
                "age_bracket_distribution": dict(bracket_counts),
                "occupation_distribution": dict(occupation_counts),
                "unavailable_dimensions": ["education", "migration", "urbanization"],
                "schema_gap_note": SCHEMA_GAP_NOTE,
            },
        )]

    @staticmethod
    def _bracket(age: int) -> str:
        for lo, hi, label in AGE_BRACKETS:
            if lo <= age < hi:
                return label
        return "unknown"
