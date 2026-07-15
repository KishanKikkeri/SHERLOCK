"""
SHERLOCK — Officer Intelligence Agent (Sprint B2, Stage B Division 2).

Answers the brief's example directly: workload, closure rate,
specialization, average closure time — for the officer(s) attached to
the case(s) in scope. Runs on whichever officers are actually
investigating the FIRs the Chief already scoped (via
`graph_context["crime_ids"]`), not on every officer in the database,
since "tell me about this case" implicitly means "tell me about who's
running it."

Definitions used (stated explicitly since none of these are given a
formula in the brief):
    - Workload = count of FIRs currently assigned where status is not
      closed/convicted.
    - Success rate = chargesheets filed / FIRs assigned (a chargesheet is
      the furthest process signal this schema tracks toward "solved";
      Court trial outcomes aren't modeled yet — see docs/AGENT_MAPPING.md).
    - Specialization = the single most common Crime.type across the
      officer's assigned FIRs.
    - Average closure = mean days between FIR.filed_date and
      ChargeSheet.filed_date, for cases that have reached that stage.
"""

from collections import Counter

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Crime, Officer

MAX_OFFICERS = 5


class OfficerIntelligenceAgent(BaseAgent):
    name = "OfficerIntelligence"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        crime_ids = gctx.get("crime_ids")

        query = self.session.query(Crime)
        if crime_ids:
            query = query.filter(Crime.id.in_(crime_ids))
        crimes = query.all()

        officer_ids = {c.fir.investigating_officer_id for c in crimes if c.fir and c.fir.investigating_officer_id}
        if not officer_ids:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="officer_profile",
                summary="No investigating officer on record for the case(s) in scope.",
                confidence=0.5,
            )]

        officers = self.session.query(Officer).filter(Officer.id.in_(officer_ids)).limit(MAX_OFFICERS).all()
        return [self._profile(o) for o in officers]

    def _profile(self, officer: Officer):
        firs = officer.firs_investigated
        total_cases = len(firs)
        open_cases = [f for f in firs if f.status.value not in ("closed", "convicted")]
        chargesheeted = [f for f in firs if f.chargesheets]

        success_rate = round(len(chargesheeted) / total_cases * 100) if total_cases else 0

        crime_types = Counter(f.crime.type.value for f in firs if f.crime)
        specialization = crime_types.most_common(1)[0][0] if crime_types else "none on record"

        closure_days = [
            (cs.filed_date - f.filed_date).days
            for f in firs for cs in f.chargesheets
        ]
        avg_closure = round(sum(closure_days) / len(closure_days)) if closure_days else None

        summary = (
            f"{officer.name} ({officer.rank.value}, badge {officer.badge_number}): "
            f"{len(open_cases)} active case(s) of {total_cases} total, "
            f"{success_rate}% chargesheet rate, specialization: {specialization}"
            + (f", average closure {avg_closure}d." if avg_closure is not None else ", no chargesheeted cases yet.")
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="officer_profile",
            summary=summary,
            evidence=[f"FIR {f.fir_number}: {f.status.value}" + (" (chargesheeted)" if f.chargesheets else "") for f in firs[:6]],
            confidence=0.9,
            source_entities=[f"officer_{officer.id}"] + [f"fir_{f.id}" for f in firs],
            metadata={
                "officer_id": officer.id,
                "name": officer.name,
                "badge_number": officer.badge_number,
                "rank": officer.rank.value,
                "posting_station": officer.posting_station,
                "total_cases": total_cases,
                "active_cases": len(open_cases),
                "chargesheet_rate_pct": success_rate,
                "specialization": specialization,
                "avg_closure_days": avg_closure,
            },
        )
