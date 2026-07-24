"""
SHERLOCK — Sprint B5, Stage B Division 15: Explainability enrichment.

Why this is centralized here instead of touching every agent file: the
brief asks for Evidence -> Reasoning -> Confidence -> Supporting Graph ->
Related Documents on every finding, from every one of the ~16 agents in
the pipeline. Two ways to get there: (a) edit every agent to construct
these three extra fields itself, or (b) derive them once, centrally,
from what every finding already carries (finding_type, source_entities,
metadata). (b) was chosen because it's zero-risk to the Golden Rule
established back in Stage A — no agent's actual analysis logic changes,
and it guarantees consistency (every finding gets real reasoning text,
not whatever a given agent's author remembered to write). The one cost:
`REASONING_BY_FINDING_TYPE` below has to be kept in sync with new finding
types as agents are added — flagged, not hidden, as the maintenance
tradeoff of this approach.

Called once per finding, from the Evidence Validation Agent (the one
node that already sees every finding regardless of source).
"""

import re

from backend.agents.base.finding import AgentFinding
from backend.graph.schema import node_key

# One real sentence per finding_type, describing the actual method the
# producing agent uses — pulled from each agent's own module docstring,
# not invented. Keys are the finding_type strings currently in use across
# Stage A/B1/B2/B3; a type not listed here gets a generic fallback rather
# than a crash, since new agents will add new types over time.
REASONING_BY_FINDING_TYPE = {
    "case_records": "Direct SQL filter/join against Crime, FIR, and Location — no inference.",
    "repeat_offender_network": "Graph traversal counting PERSON_COMMITTED_CRIME edges per person, ranked by count.",
    "criminal_association": "Graph traversal over PERSON_ASSOCIATED_WITH / PERSON_LINKED_TO_PERSON edges.",
    "entity_resolution": "Three-tier name matching: exact match, then progressively fuzzier matching against raw_name_used.",
    "entity_resolution_flag": "Same matching pipeline as entity_resolution, flagged where confidence was below the exact-match tier.",
    "investigation_timeline": "Crimes in scope sorted chronologically; escalation flagged via shrinking inter-incident gaps.",
    "case_process_timeline": "FIR filing, investigation, arrest, chargesheet, and seizure dates merged and sorted chronologically.",
    "financial_network": "Mule accounts identified by is_flagged_mule; hub identified by highest incoming transaction count.",
    "suspicious_pattern": "Fan-in structure inferred from multiple distinct senders converging on one hub account.",
    "bank_network": "Fan-in/fan-out degree computed per flagged account from Transaction rows.",
    "asset_flow": "Vehicles and recovered property cross-referenced against flagged-account owners.",
    "similar_case": "Multi-signal comparison: MO text similarity (SequenceMatcher) plus accused/officer/location overlap.",
    "crime_pattern": "Location-cluster analysis grouped by district and month via graph_service.",
    "seasonal_spike": "Same clustering as crime_pattern, filtered to the festival-season window.",
    "hotspot_forecast": "Location clusters projected forward from historical concentration, wider pool than pattern analysis.",
    "prevention_recommendation": "Derived directly from upstream findings (network/pattern/financial) — not an independent query.",
    "patrol_strategy": "Derived from repeat-offender and hotspot findings.",
    "surveillance_action": "Derived from network findings identifying high-centrality individuals.",
    "case_summary": "Direct roll-up of FIR, Investigation, Arrest, ChargeSheet, and Property records for the case.",
    "officer_profile": "Aggregated directly from the officer's assigned FIRs, chargesheets, and crime types.",
    "witness_reliability": "Heuristic score from testimony count and cross-check against Accused records for the same person.",
    "witness_network": "Graph-style traversal: witness -> FIR -> co-occurring accused/victim/witness persons.",
    "property_recovery": "Direct status roll-up of Property records for the case.",
    "asset_link": "Vehicles and bank accounts cross-referenced against persons with recovered property.",
    "weapon_history": "Weapon rows grouped by serial_number across the whole database to detect reuse across cases.",
    "organization_profile": "Organization traced via OrganizationMembership to members' cases and flagged bank accounts.",
    "assignment_recommendation": "Transparent point-scoring: specialization match, district match, active caseload tiebreaker.",
    "validation_summary": "Rule-based acceptance check applied to every finding in this investigation.",
    "behavioral_profile": "Composite score from crime escalation, crime-type severity weighting, and association-graph density.",
    "sociological_profile": "Demographic breakdown (gender/age-bracket/occupation) of the accused (and linked victim) persons in scope.",
    "social_risk_factors": "Repeat-offender counts from Accused-table FIR tallies, family links from PersonAssociation(relation_type=family), gang indicators from recorded OrganizationMembership(org_type=gang), community vulnerability as a crime-density-by-district proxy.",
    "socioeconomic_correlation": "Cross-tabulation of accused-person occupation (the only socio-economic attribute in the schema) against the crime type of the FIR they're linked to.",
    "predictive_forecast": "District/crime-type/officer-workload projection from historical case-graph clustering.",
    "decision_support": "Synthesized directly from this investigation's own findings — no new querying beyond what's already been established.",
}

DEFAULT_REASONING = "Derived from the producing agent's stated method; see its evidence list for the specific facts used."

# source_entities prefix -> graph node label (backend/graph/schema.py NODE_LABELS)
PREFIX_TO_LABEL = {
    "person": "Person", "crime": "Crime", "fir": "FIR", "officer": "Officer",
    "account": "BankAccount", "property": "Property", "weapon": "Weapon",
    "organization": "Organization", "vehicle": "Vehicle", "phone": "Phone",
    "witness": "Witness", "accused": "Accused", "victim": "Victim", "court": "Court",
}

FIR_NUMBER_PATTERN = re.compile(r"\bFIR[-\w]*\d[-\w]*\b", re.IGNORECASE)


def enrich(finding: AgentFinding) -> AgentFinding:
    """Populates reasoning / supporting_graph / related_documents on a
    finding that's already been produced. Mutates and returns the same
    object — called once per finding at Evidence Validation time."""
    finding.reasoning = REASONING_BY_FINDING_TYPE.get(finding.finding_type, DEFAULT_REASONING)
    finding.supporting_graph = _build_supporting_graph(finding.source_entities)
    finding.related_documents = _extract_related_documents(finding)
    return finding


def _build_supporting_graph(source_entities: list) -> dict:
    """Groups raw source_entities strings ("person_1", "fir_3", ...) by
    graph node label and converts each to the canonical node_key() format
    used by the actual Crime Intelligence Graph — so a UI showing this
    finding could highlight the exact nodes it's based on."""
    grouped = {}
    for entity in source_entities:
        if "_" not in entity:
            continue
        prefix, _, raw_id = entity.rpartition("_")
        label = PREFIX_TO_LABEL.get(prefix)
        if not label or not raw_id.isdigit():
            continue
        grouped.setdefault(label, []).append(node_key(label, raw_id))
    return grouped


def _extract_related_documents(finding: AgentFinding) -> list:
    """Real FIR numbers only — pulled from metadata (where an agent
    already stored one, e.g. CaseIntelligence's fir_number) or, failing
    that, pattern-matched out of the evidence text. Never invented."""
    docs = set()

    for value in finding.metadata.values():
        if isinstance(value, str) and value.upper().startswith("FIR"):
            docs.add(value)

    for line in finding.evidence:
        for match in FIR_NUMBER_PATTERN.findall(line):
            docs.add(match)

    return sorted(docs)
