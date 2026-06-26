"""
SHERLOCK — Pattern & MO Agent (Phase 5).

Uses `graph_service.find_location_clusters()` to detect crime hotspot
clusters and seasonal (festival-season) spikes. When the query implies a
forecast ("hotspot", "future", "predict"), also emits a simple
forward-looking finding based on the historical seasonal concentration —
a heuristic placeholder for the dedicated Forecasting Agent (Phase 6+).
"""

from collections import defaultdict

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding

FESTIVAL_MONTHS = {9, 10, 11}


class PatternAnalysisAgent(BaseAgent):
    name = "PatternAnalysis"

    def __init__(self, graph_service):
        self.graph_service = graph_service

    def run(self, state: dict):
        filters = state.get("investigation_plan", {}).get("filters", {})
        crime_type = filters.get("crime_type")
        district = filters.get("district")
        wants_forecast = filters.get("wants_forecast")

        clusters = self.graph_service.find_location_clusters(crime_type=crime_type, top_n=50)
        if district:
            clusters = [c for c in clusters if c["district"] == district]

        if not clusters:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="crime_pattern",
                summary="No crime clusters found for this query's scope.",
                confidence=0.5,
            )]

        # Aggregate by district to detect seasonal concentration
        by_district = defaultdict(lambda: {"festival": 0, "other": 0, "by_month": defaultdict(int)})
        for c in clusters:
            bucket = "festival" if c["month"] in FESTIVAL_MONTHS else "other"
            by_district[c["district"]][bucket] += c["count"]
            by_district[c["district"]]["by_month"][c["month"]] += c["count"]

        findings = []
        top_clusters = sorted(clusters, key=lambda c: c["count"], reverse=True)[:5]
        top_desc = ", ".join(f"{c['district']} (month {c['month']}, n={c['count']})" for c in top_clusters)

        ctype_label = (crime_type or "crime").replace("_", " ")
        findings.append(AgentFinding(
            agent_name=self.name,
            finding_type="crime_pattern",
            summary=f"Top {ctype_label} clusters: {top_desc}",
            evidence=[f"{c['count']} {ctype_label} cases in {c['district']} during month {c['month']}" for c in top_clusters[:3]],
            confidence=0.88,
            source_entities=[f"location_{c['district']}" for c in top_clusters],
            metadata={"clusters": top_clusters},
        ))

        # Seasonal spike detection
        for dist, agg in by_district.items():
            total = agg["festival"] + agg["other"]
            if total == 0:
                continue
            festival_share = agg["festival"] / total
            if festival_share >= 0.5 and agg["festival"] >= 5:
                findings.append(AgentFinding(
                    agent_name=self.name,
                    finding_type="seasonal_spike",
                    summary=(
                        f"{festival_share:.0%} of {ctype_label} cases in {dist} occur during "
                        f"festival season (Sep-Nov) — {agg['festival']} of {total} cases."
                    ),
                    evidence=[f"Month-by-month {ctype_label} counts in {dist}: "
                              + ", ".join(f"month {m}={n}" for m, n in sorted(agg["by_month"].items()))],
                    confidence=0.9,
                    source_entities=[f"location_{dist}"],
                    metadata={"festival_share": festival_share, "district": dist},
                ))

                if wants_forecast:
                    findings.append(AgentFinding(
                        agent_name=self.name,
                        finding_type="hotspot_forecast",
                        summary=(
                            f"Forecast: based on the historical festival-season concentration "
                            f"({festival_share:.0%}), {dist} is likely to see a similar "
                            f"{ctype_label} spike during the next Sep-Nov period. "
                            f"Recommend increased patrol presence ahead of the festival season."
                        ),
                        evidence=[f"Historical pattern: {agg['festival']} of {total} cases ({festival_share:.0%}) fell in Sep-Nov."],
                        confidence=0.7,  # heuristic forecast — lower confidence than observed pattern
                        source_entities=[f"location_{dist}"],
                        metadata={"district": dist, "basis": "historical_seasonal_concentration"},
                    ))

        return findings
