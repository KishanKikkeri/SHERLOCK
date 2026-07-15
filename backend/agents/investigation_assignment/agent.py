"""
SHERLOCK — Investigation Assignment Agent (Sprint B2, Stage B Division 2).

Different shape from every other agent in the pipeline: it doesn't
analyze an existing case, it recommends who should be assigned a new
one. Gated on the query implying an assignment decision (see
ASSIGNMENT_KEYWORDS in query_parser.py) — running this unconditionally
on every investigation query would be noise; "who should investigate
this" is a distinct question from "what do we know about this case,"
even though it draws on the same Officer data as Officer Intelligence.

Scoring (stated explicitly — the brief names the factors, not a
formula): for each officer, +2 points if their specialization (most
common crime type across assigned FIRs — same definition as
OfficerIntelligenceAgent) matches the query's crime type, +1 point if
their posting_station's district matches the query's district, then
ranked with active caseload as a tiebreaker (fewer active cases wins —
an officer buried in open cases is a worse pick even with matching
specialization). This is a transparent, inspectable heuristic, not a
learned model — every point is in the evidence list.
"""

from collections import Counter

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Officer

MAX_CANDIDATES = 3


class InvestigationAssignmentAgent(BaseAgent):
    name = "InvestigationAssignment"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        filters = state.get("investigation_plan", {}).get("filters", {})
        crime_type = filters.get("crime_type")
        district = filters.get("district")

        officers = self.session.query(Officer).all()
        if not officers:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="assignment_recommendation",
                summary="No officers on record to recommend for assignment.",
                confidence=0.5,
            )]

        scored = [self._score(o, crime_type, district) for o in officers]
        scored.sort(key=lambda s: (-s["score"], s["active_cases"]))
        top = scored[:MAX_CANDIDATES]

        best = top[0]
        summary = (
            f"Recommended for assignment: {best['name']} (badge {best['badge_number']}) — "
            f"score {best['score']} ({', '.join(best['reasons']) or 'no specific match, ranked by lowest current workload'}), "
            f"currently {best['active_cases']} active case(s)."
        )

        return [AgentFinding(
            agent_name=self.name,
            finding_type="assignment_recommendation",
            summary=summary,
            evidence=[
                f"{c['name']} (badge {c['badge_number']}): score {c['score']}, "
                f"{c['active_cases']} active case(s), specialization={c['specialization']}"
                for c in top
            ],
            confidence=0.75,  # transparent heuristic, not a validated assignment model
            source_entities=[f"officer_{c['officer_id']}" for c in top],
            metadata={"candidates": top, "query_crime_type": crime_type, "query_district": district},
        )]

    def _score(self, officer: Officer, crime_type: str, district: str):
        firs = officer.firs_investigated
        active_cases = len([f for f in firs if f.status.value not in ("closed", "convicted")])
        crime_types = Counter(f.crime.type.value for f in firs if f.crime)
        specialization = crime_types.most_common(1)[0][0] if crime_types else None

        score = 0
        reasons = []
        if crime_type and specialization == crime_type:
            score += 2
            reasons.append(f"specialization matches ({specialization})")
        if district and officer.posting_station and district.split()[0].lower() in officer.posting_station.lower():
            score += 1
            reasons.append(f"posted in matching district ({officer.posting_station})")

        return {
            "officer_id": officer.id,
            "name": officer.name,
            "badge_number": officer.badge_number,
            "rank": officer.rank.value,
            "specialization": specialization or "none on record",
            "active_cases": active_cases,
            "score": score,
            "reasons": reasons,
        }
