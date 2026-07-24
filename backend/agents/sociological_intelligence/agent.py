"""
SHERLOCK — Sociological Intelligence Agent (Sprint B4 -> Agent 2 upgrade).

Sprint B4 baseline: a single demographic tabulation (gender/age/occupation)
of accused persons in scope, with education/migration/urbanization named
as schema gaps rather than faked.

Agent 2 upgrade adds, on top of that same honesty baseline: victim
demographics, occupation-crime (socio-economic) correlation, and social
risk factors (repeat-offender communities, family crime links, gang
indicators via recorded Organization membership, and a community-
vulnerability crime-density proxy). All of the actual computation lives
in backend/intelligence/sociological_insights.py — this file only turns
that computation into AgentFinding objects for the investigation
pipeline. Urbanization, migration, economic-stress, and education stay
schema gaps (still no such fields anywhere in the AER schema) but each
now has a real extension-point method on the service, documented there.

What IS produced: real demographic + social-risk-factor breakdowns of
the accused (and, where relevant, victim) persons in scope — described
in the brief as a "Risk map." This agent produces the underlying
breakdown data; it does not draw an actual choropleth/map (a frontend
rendering concern — see frontend/src/sociological/ for the dashboard
that renders this data instead).
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Accused
from backend.intelligence.sociological_insights import SociologicalInsightsService


class SociologicalIntelligenceAgent(BaseAgent):
    name = "SociologicalIntelligence"

    def __init__(self, session):
        self.session = session
        self.service = SociologicalInsightsService(session)

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        accused_person_ids = gctx.get("accused_person_ids")

        if not accused_person_ids and self.session.query(Accused.id).first() is None:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="sociological_profile",
                summary="No accused persons on record to build a demographic profile from.",
                confidence=0.5,
            )]

        dashboard = self.service.build_dashboard(accused_person_ids)
        accused_demo = dashboard["demographics"]["accused"]
        if accused_demo["sample_size"] == 0:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="sociological_profile",
                summary="No accused persons in scope to build a demographic profile from.",
                confidence=0.5,
            )]

        scope_ids = accused_person_ids or sorted(self._all_accused_ids())

        findings = [
            self._demographic_finding(scope_ids, dashboard),
            self._risk_factor_finding(scope_ids, dashboard),
        ]
        socio_finding = self._socioeconomic_finding(scope_ids, dashboard)
        if socio_finding:
            findings.append(socio_finding)
        return findings

    # -- findings ---------------------------------------------------------

    def _demographic_finding(self, scope_ids, dashboard):
        demo = dashboard["demographics"]["accused"]
        gender = demo["gender_distribution"]
        brackets = demo["age_bracket_distribution"]
        occupations = demo["occupation_distribution"]
        top_occupation = max(occupations, key=occupations.get) if occupations else "unspecified"
        dominant_bracket = max(brackets, key=brackets.get) if brackets else "unknown"

        gaps = sorted(k for k, v in dashboard["data_availability"].items() if "unavailable" in v)
        victim_n = dashboard["demographics"]["victims"]["sample_size"]

        summary = (
            f"Demographic profile of {demo['sample_size']} accused person(s) in scope "
            f"(plus {victim_n} linked victim(s)): {gender}, most common age bracket "
            f"{dominant_bracket} ({brackets.get(dominant_bracket, 0)}/{demo['sample_size']}), "
            f"most common occupation '{top_occupation}' ({occupations.get(top_occupation, 0)}/"
            f"{demo['sample_size']}). Unavailable in current schema: {', '.join(gaps)}."
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="sociological_profile",
            summary=summary,
            evidence=[
                f"Gender distribution: {gender}",
                f"Age brackets: {brackets}",
                f"Top occupations: {occupations}",
            ],
            confidence=0.9,  # direct tabulation of recorded fields, not an inference
            source_entities=[f"person_{pid}" for pid in scope_ids],
            metadata={
                "sample_size": demo["sample_size"],
                "gender_distribution": gender,
                "age_bracket_distribution": brackets,
                "occupation_distribution": occupations,
                "victim_sample_size": victim_n,
                "victim_demographics": dashboard["demographics"]["victims"],
                "unavailable_dimensions": gaps,
            },
        )

    def _risk_factor_finding(self, scope_ids, dashboard):
        risk = dashboard["social_risk_factors"]
        ro = risk["repeat_offender_communities"]
        fam = risk["family_crime_links"]
        gang = risk["gang_indicators"]
        vuln = risk["community_vulnerability"]["by_district_crime_density"]
        top_district = vuln[0]["district"] if vuln else "unknown"

        summary = (
            f"{ro['count']} repeat offender(s), {fam['count']} family-linked accused pair(s), "
            f"and {gang['count']} gang-affiliated accused person(s) identified in scope. "
            f"Highest recorded crime concentration: {top_district}."
        )

        source_entities = {f"person_{pid}" for pid in ro["person_ids"]}
        source_entities.update(f"person_{pid}" for pid in gang["person_ids"])
        for link in fam["links"]:
            source_entities.add(f"person_{link['person_a']}")
            source_entities.add(f"person_{link['person_b']}")

        return AgentFinding(
            agent_name=self.name,
            finding_type="social_risk_factors",
            summary=summary,
            evidence=[
                ro["method"], fam["method"], gang["method"], risk["community_vulnerability"]["method"],
            ],
            confidence=0.85,
            source_entities=sorted(source_entities),
            metadata=risk,
        )

    def _socioeconomic_finding(self, scope_ids, dashboard):
        socio = dashboard["socioeconomic_analysis"]
        occ_crime = socio["occupation_crime_correlation"]
        if not occ_crime:
            return None

        summary = (
            f"Occupation-crime correlation computed across {len(occ_crime)} occupation "
            f"categor{'y' if len(occ_crime) == 1 else 'ies'} (the only socio-economic attribute "
            f"the current schema records). Income group, employment status, housing type, and "
            f"economic category are not available — see metadata for extension points."
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="socioeconomic_correlation",
            summary=summary,
            evidence=[f"{occ}: {counts}" for occ, counts in list(occ_crime.items())[:5]],
            confidence=0.8,
            source_entities=[f"person_{pid}" for pid in scope_ids],
            metadata=socio,
        )

    def _all_accused_ids(self):
        return {row[0] for row in self.session.query(Accused.person_id).distinct().all()}
