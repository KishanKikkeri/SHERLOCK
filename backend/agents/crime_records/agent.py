"""
SHERLOCK — Crime Records Agent (Phase 5).

Pure retrieval. No analysis, no forecasting, no profiling. Given the
filters extracted by the Chief (crime type / district / festival season),
queries Postgres/SQLite for matching Crime + FIR records and reports the
raw facts.

Also stashes the matching crime/person IDs into `graph_context` so
downstream agents (Network Analysis, Pattern Analysis) can scope their
graph queries to this same record set.
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Crime, Location, FIR, PersonCrimeLink, PersonRole, CrimeType

FESTIVAL_MONTHS = {9, 10, 11}


class CrimeRecordsAgent(BaseAgent):
    name = "CrimeRecords"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict) -> list[AgentFinding]:
        filters = state.get("investigation_plan", {}).get("filters", {})
        crime_type = filters.get("crime_type")
        district = filters.get("district")
        festival_season = filters.get("festival_season")

        query = self.session.query(Crime).join(Location, Crime.location_id == Location.id)

        if crime_type:
            query = query.filter(Crime.type == CrimeType(crime_type))
        if district:
            query = query.filter(Location.district == district)

        crimes = query.all()
        if festival_season:
            crimes = [c for c in crimes if c.timestamp.month in FESTIVAL_MONTHS]

        crime_ids = [c.id for c in crimes]
        fir_numbers = [c.fir.fir_number for c in crimes if c.fir][:5]

        accused_links = (
            self.session.query(PersonCrimeLink)
            .filter(PersonCrimeLink.crime_id.in_(crime_ids), PersonCrimeLink.role == PersonRole.ACCUSED)
            .all() if crime_ids else []
        )
        accused_person_ids = sorted({l.person_id for l in accused_links})

        scope_desc_parts = []
        if crime_type:
            scope_desc_parts.append(crime_type.replace("_", " "))
        else:
            scope_desc_parts.append("crime")
        if district:
            scope_desc_parts.append(f"in {district}")
        if festival_season:
            scope_desc_parts.append("during festival season (Sep-Nov)")
        scope_desc = " ".join(scope_desc_parts)

        summary = f"Retrieved {len(crimes)} {scope_desc} FIR(s)."

        finding = AgentFinding(
            agent_name=self.name,
            finding_type="case_records",
            summary=summary,
            evidence=[f"Sample FIRs: {', '.join(fir_numbers)}"] if fir_numbers else [],
            confidence=1.0,  # direct DB facts
            source_entities=[f"crime_{cid}" for cid in crime_ids],
            metadata={
                "crime_ids": crime_ids,
                "accused_person_ids": accused_person_ids,
                "count": len(crimes),
                "filters": filters,
            },
        )

        # Pass to downstream agents via state update (not in-place mutation)
        extra = {"graph_context": {
            "crime_ids": crime_ids,
            "accused_person_ids": accused_person_ids,
        }}

        return [finding], extra
