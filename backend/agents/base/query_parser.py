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
    }


def plan_agents(filters: dict) -> dict:
    """Decide which specialist agents the investigation needs."""
    agents = ["CrimeRecords"]

    # NetworkAnalysis, EntityResolution and TimelineReconstruction run for
    # ALL investigation types — cheap, broadly useful, no filter gating needed.
    agents.append("NetworkAnalysis")
    agents.append("EntityResolution")
    agents.append("TimelineReconstruction")

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

    # Prevention Intelligence always fires — converts findings into actions
    agents.append("PreventionAgent")

    return {"agents": agents, "filters": filters}
