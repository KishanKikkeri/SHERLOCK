"""
SHERLOCK — Forecasting Agent (Phase 5, Criminal Intelligence Division).

The dedicated forecasting agent the codebase's own FUTURE_ROADMAP.md and
`PatternAnalysisAgent`'s docstring called for, to replace the "heuristic
placeholder" that lived inline in Pattern Analysis. Same underlying data
(`graph_service.find_location_clusters`, grouped by district/month), but
now an actual per-district time series with a least-squares linear trend
fit and a next-month projection — still stdlib-only (no numpy/pandas;
this codebase is deliberately dependency-light), but a real fit rather
than a single "festival season" heuristic.

Only runs when the query implies a forecast (`filters["wants_forecast"]`)
— gated by `plan_agents()`, checked again here defensively.
"""

from collections import defaultdict

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding

RISING_SLOPE_THRESHOLD = 0.15
FALLING_SLOPE_THRESHOLD = -0.15
MIN_MONTHS_FOR_FIT = 3


class ForecastingAgent(BaseAgent):
    name = "Forecasting"

    def __init__(self, graph_service):
        self.graph_service = graph_service

    def run(self, state: dict):
        filters = state.get("investigation_plan", {}).get("filters", {})
        crime_type = filters.get("crime_type")
        district_filter = filters.get("district")

        if not filters.get("wants_forecast"):
            return []

        clusters = self.graph_service.find_location_clusters(crime_type=crime_type, top_n=500)
        if district_filter:
            clusters = [c for c in clusters if c["district"] == district_filter]

        if not clusters:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="hotspot_forecast",
                summary="Not enough historical data in scope to forecast.",
                confidence=0.4,
            )]

        by_district_month = defaultdict(lambda: defaultdict(int))
        for c in clusters:
            by_district_month[c["district"]][c["month"]] += c["count"]

        ctype_label = (crime_type or "crime").replace("_", " ")
        findings = []

        for district, month_counts in by_district_month.items():
            months = sorted(month_counts)
            if len(months) < MIN_MONTHS_FOR_FIT:
                continue

            xs = months
            ys = [month_counts[m] for m in months]
            slope, intercept = self._linear_fit(xs, ys)
            next_month = (max(months) % 12) + 1
            predicted = max(0, round(slope * next_month + intercept))

            if slope > RISING_SLOPE_THRESHOLD:
                trend = "rising"
            elif slope < FALLING_SLOPE_THRESHOLD:
                trend = "falling"
            else:
                trend = "stable"

            if trend != "rising":
                continue  # only surface actionable (rising) trends as findings

            findings.append(AgentFinding(
                agent_name=self.name,
                finding_type="hotspot_forecast",
                summary=(
                    f"{district}: {ctype_label} incidents show a rising month-over-month trend "
                    f"(slope {slope:+.2f}/month over {len(months)} months); "
                    f"projecting roughly {predicted} case(s) next month."
                ),
                evidence=[f"Month {m}: {month_counts[m]} case(s)" for m in months],
                confidence=0.68,  # linear trend on sparse monthly data — deliberately moderate, not overstated
                source_entities=[f"location_{district}"],
                metadata={
                    "district": district,
                    "slope": round(slope, 3),
                    "predicted_next_month": predicted,
                    "history": dict(month_counts),
                    "method": "least_squares_linear_fit",
                },
            ))

        if not findings:
            findings.append(AgentFinding(
                agent_name=self.name,
                finding_type="hotspot_forecast",
                summary=f"No district shows a statistically notable rising {ctype_label} trend in this scope.",
                confidence=0.6,
            ))

        return findings

    @staticmethod
    def _linear_fit(xs: list, ys: list) -> tuple:
        """Ordinary least squares, stdlib-only. Returns (slope, intercept)."""
        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        den = sum((x - mean_x) ** 2 for x in xs) or 1e-9
        slope = num / den
        intercept = mean_y - slope * mean_x
        return slope, intercept
