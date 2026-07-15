"""
SHERLOCK — lightweight query filter extraction (Phase 5).

Rule-based NLU shared by the Chief (for planning + filters) and the
specialist agents (for scoping their graph/DB queries). Deliberately
simple — this is the seed of what an LLM-based planner would eventually
replace, but keeps the v1 pipeline fully deterministic and dependency-free.
"""

from backend.database.models import CrimeType

KARNATAKA_DISTRICTS = [
    "Mysuru", "Bengaluru Urban", "Dharwad", "Dakshina Kannada",
    "Belagavi", "Tumakuru", "Davanagere", "Ballari",
]

FINANCIAL_KEYWORDS = ["money", "transaction", "account", "financial", "fraud", "mule", "bank"]
FORECAST_KEYWORDS = ["forecast", "future", "predict", "hotspot", "next"]
FESTIVAL_KEYWORDS = ["festival", "dasara", "diwali", "seasonal", "season"]
REPEAT_KEYWORDS = ["repeat", "habitual", "recurring", "serial"]
# Sprint B2: Investigation Assignment answers a different question ("who
# should get this case") than every other agent ("what do we know about
# this case") — gated on explicit assignment intent rather than run
# unconditionally, unlike the Sprint B1/B2/B3 case-scoped agents below.
ASSIGNMENT_KEYWORDS = ["assign", "who should investigate", "which officer", "recommend an officer", "reassign"]


def extract_filters(query: str) -> dict:
    q = query.lower()

    crime_type = None
    for ct in CrimeType:
        label = ct.value.replace("_", " ")
        if label in q or ct.value in q:
            crime_type = ct.value
            break

    district = None
    for d in KARNATAKA_DISTRICTS:
        # match on the city-ish part of the district name too (e.g. "Mysuru" in "Mysuru City")
        if d.lower() in q or d.lower().split()[0] in q:
            district = d
            break

    return {
        "crime_type": crime_type,
        "district": district,
        "festival_season": any(k in q for k in FESTIVAL_KEYWORDS),
        "wants_forecast": any(k in q for k in FORECAST_KEYWORDS),
        "wants_repeat_offenders": any(k in q for k in REPEAT_KEYWORDS),
        "is_financial": any(k in q for k in FINANCIAL_KEYWORDS),
        "wants_assignment": any(k in q for k in ASSIGNMENT_KEYWORDS),
    }


def plan_agents(filters: dict) -> dict:
    """Decide which specialist agents the investigation needs."""
    agents = ["CrimeRecords"]

    # NetworkAnalysis, EntityResolution, TimelineReconstruction and (Sprint
    # B1) CaseIntelligence run for ALL investigation types — cheap, broadly
    # useful, no filter gating needed. CaseIntelligence specifically is
    # "the core of every investigation" per the Stage B brief, so it's
    # unconditional like the others, not filter-gated.
    agents.append("NetworkAnalysis")
    agents.append("EntityResolution")
    agents.append("TimelineReconstruction")
    agents.append("CaseIntelligence")

    # Sprint B2/B3: Officer/Witness/Property/Weapon/Organization Intelligence
    # follow the same pattern as CaseIntelligence — scoped to whatever's
    # already in graph_context, and every one of them returns a graceful
    # "nothing on record" finding rather than an error when its data isn't
    # present, so running them unconditionally costs almost nothing and
    # avoids a second layer of filter-gating logic to keep in sync with
    # what each agent actually needs.
    agents.append("OfficerIntelligence")
    agents.append("WitnessIntelligence")
    agents.append("PropertyIntelligence")
    agents.append("WeaponIntelligence")
    agents.append("OrganizationIntelligence")
    agents.append("BehavioralIntelligence")
    agents.append("SociologicalIntelligence")

    if filters["is_financial"]:
        agents.append("FinancialAgent")

    if filters["crime_type"]:
        # MO comparison is only meaningful once scoped to a specific crime type
        agents.append("SimilarCase")

    if (filters["wants_repeat_offenders"] or filters["wants_forecast"]
            or filters["crime_type"] or filters["festival_season"]
            or filters["is_financial"]):
        agents.append("PatternAnalysis")

    if filters["wants_forecast"]:
        agents.append("Forecasting")

    # Sprint B2: Investigation Assignment — distinct question, gated separately
    if filters["wants_assignment"]:
        agents.append("InvestigationAssignment")

    # Prevention Intelligence always fires — converts findings into actions
    agents.append("PreventionAgent")
    # Sprint B5: Decision Support always fires too — same "always useful,
    # degrades gracefully" reasoning as the Sprint B1-B4 case-scoped agents
    agents.append("DecisionSupport")

    return {"agents": agents, "filters": filters}
