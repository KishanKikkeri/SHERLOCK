"""
SHERLOCK — Case Intelligence Agent (Sprint B1, Stage B Division 1).

The brief calls this "the core of every investigation" and puts it first
in Stage B for a concrete reason: every other agent answers a narrow
question (is there a network? a financial trail? a pattern?) but nothing
in the Stage A pipeline answers the most basic investigator question —
"what's the state of this case, right now, as a whole?" This agent
answers that, using entities that simply didn't exist before the AER
migration (Officer, Investigation, Arrest, ChargeSheet, Property).

Runs per-FIR (a "case" in this schema is a FIR — see
DatabaseService.get_case). Scope comes from `graph_context["crime_ids"]`,
set by Crime Records Agent; each crime's FIR becomes one case profile.
Deliberately capped (MAX_CASES) so a broad, unscoped query doesn't produce
a wall of one finding per case.
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Crime, ArrestStatus
from backend.database.service import DatabaseService

MAX_CASES = 5

# Investigation stage ladder — used to compute a rough "% complete" and to
# name the current stage. Reflects FIR -> Investigation -> Arrest ->
# ChargeSheet as the real process the AER schema tracks (Court trial stage
# isn't modeled yet — ChargeSheet.status is as far as this schema goes).
STAGES = ["registered", "under_investigation", "arrest_made", "chargesheet_filed"]


class CaseIntelligenceAgent(BaseAgent):
    name = "CaseIntelligence"

    def __init__(self, session):
        self.session = session
        self.db = DatabaseService(session)

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        crime_ids = gctx.get("crime_ids")

        query = self.session.query(Crime)
        if crime_ids:
            query = query.filter(Crime.id.in_(crime_ids))
        crimes = query.limit(MAX_CASES).all()

        cases_with_firs = [c for c in crimes if c.fir]
        if not cases_with_firs:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="case_summary",
                summary="No registered FIR in scope to build a case profile from.",
                confidence=0.5,
            )]

        findings = []
        for crime in cases_with_firs:
            findings.append(self._build_case_profile(crime.fir))
        return findings

    def _build_case_profile(self, fir):
        stage, progress_pct = self._investigation_stage(fir)
        pending = self._pending_tasks(fir, stage)
        evidence_count = len(fir.properties)
        officer = fir.investigating_officer
        health = self._case_health(fir, pending)

        officer_line = (
            f"{officer.name} (badge {officer.badge_number}, {officer.rank.value})"
            if officer else "unassigned"
        )

        summary = (
            f"Case {fir.fir_number}: {health} — stage '{stage}' (~{progress_pct}% through "
            f"registration→chargesheet), {evidence_count} item(s) of property on record, "
            f"investigating officer {officer_line}."
        )

        accused_names = [a.raw_name_used for a in fir.accused_records]
        victim_names = [v.raw_name_used for v in fir.victim_records]
        witness_names = [w.raw_name_used for w in fir.witness_records]

        return AgentFinding(
            agent_name=self.name,
            finding_type="case_summary",
            summary=summary,
            evidence=[
                f"FIR {fir.fir_number}, filed {fir.filed_date:%Y-%m-%d}, status={fir.status.value}",
                f"Accused: {', '.join(accused_names) or 'none on record'}",
                f"Victims: {', '.join(victim_names) or 'none on record'}",
                f"Witnesses: {', '.join(witness_names) or 'none on record'}",
            ] + [f"Pending: {p}" for p in pending],
            confidence=0.95,  # this is a direct roll-up of recorded facts, not an inference
            source_entities=[f"fir_{fir.id}", f"crime_{fir.crime_id}"],
            metadata={
                "fir_id": fir.id,
                "fir_number": fir.fir_number,
                "case_health": health,
                "investigation_stage": stage,
                "progress_pct": progress_pct,
                "evidence_count": evidence_count,
                "officer_assignment": officer_line,
                "pending_tasks": pending,
                "accused_count": len(accused_names),
                "victim_count": len(victim_names),
                "witness_count": len(witness_names),
            },
        )

    @staticmethod
    def _investigation_stage(fir):
        reached = 0  # index into STAGES of the furthest stage reached
        if fir.investigations:
            reached = max(reached, 1)
        if fir.arrests:
            reached = max(reached, 2)
        if fir.chargesheets:
            reached = max(reached, 3)
        stage = STAGES[reached]
        progress_pct = round((reached + 1) / len(STAGES) * 100)
        return stage, progress_pct

    @staticmethod
    def _pending_tasks(fir, stage):
        tasks = []
        if fir.investigating_officer_id is None:
            tasks.append("No investigating officer assigned")
        if not fir.investigations:
            tasks.append("Investigation not yet formally opened")
        if not fir.properties:
            tasks.append("No property/evidence logged yet")
        if not fir.arrests and stage != "registered":
            tasks.append("No arrests recorded despite active investigation")
        if fir.arrests and any(a.status == ArrestStatus.RELEASED_ON_BAIL for a in fir.arrests) and not fir.chargesheets:
            tasks.append("Accused on bail with no chargesheet filed yet — flight/tampering risk window")
        if not fir.chargesheets and stage == "arrest_made":
            tasks.append("Chargesheet not yet filed following arrest")
        return tasks

    @staticmethod
    def _case_health(fir, pending):
        if fir.status.value in ("closed", "convicted"):
            return "resolved"
        if len(pending) >= 3:
            return "stalled"
        if fir.status.value == "open" and not fir.investigations:
            return "newly registered"
        return "active"
