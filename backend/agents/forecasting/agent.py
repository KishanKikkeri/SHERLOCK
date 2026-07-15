"""
SHERLOCK — Forecasting Agent (Phase 5 baseline; Sprint B4 upgrade per
Stage B Division 13, "Predictive Intelligence").

Phase 5 baseline (unchanged): district hotspot forecasting via
`graph_service.find_location_clusters`, grouped by district/month, with a
least-squares linear trend fit and next-month projection.

Sprint B4 upgrade: the brief asks this agent to predict "district
hotspots, crime type, gangs, repeat offenders, officer workload" instead
of only the district view. Three of those five are added here as new
finding types, using data the AER migration made queryable:

    - Crime-type trend: same linear-fit method as the district view,
      applied across crime types instead of districts, so "which crime
      type is rising" is answered directly rather than only per-district.
    - Repeat-offender risk: surfaces accused persons whose own crime
      frequency is accelerating (reuses Behavioral Intelligence's
      escalation-score logic, applied here as a forward-looking flag
      rather than a descriptive score).
    - Officer workload forecast: officers whose active caseload is
      already high are flagged as approaching capacity — a genuine
      current-state read, not a real workload *projection* (see the
      method's docstring for why a true forecast isn't available yet).

Gang forecasting (also named in the brief) is NOT implemented: it would
need association data with real timestamps to trend growth over time,
and `PersonAssociation.strength` has no date field — there's nothing to
fit a trend against. Behavioral Intelligence's `gang_likelihood_score`
already gives a current-state read; forecasting its *change* over time
needs a schema addition (a `formed_date` or per-period association
snapshot) that wasn't added this sprint. Flagged as follow-up, not faked
with an invented trend.
"""

from collections import defaultdict

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Crime, Officer, Accused

RISING_SLOPE_THRESHOLD = 0.15
FALLING_SLOPE_THRESHOLD = -0.15
MIN_MONTHS_FOR_FIT = 3
WORKLOAD_AT_CAPACITY_THRESHOLD = 3  # active cases — a stated threshold, not derived from data


class ForecastingAgent(BaseAgent):
    name = "Forecasting"

    def __init__(self, graph_service, session=None):
        self.graph_service = graph_service
        self.session = session  # Sprint B4: needed for repeat-offender / officer-workload forecasts

    def run(self, state: dict):
        filters = state.get("investigation_plan", {}).get("filters", {})
        crime_type = filters.get("crime_type")
        district_filter = filters.get("district")

        if not filters.get("wants_forecast"):
            return []

        clusters = self.graph_service.find_location_clusters(crime_type=crime_type, top_n=500)
        if district_filter:
            clusters = [c for c in clusters if c["district"] == district_filter]

        findings = []

        if not clusters:
            findings.append(AgentFinding(
                agent_name=self.name,
                finding_type="hotspot_forecast",
                summary="Not enough historical data in scope to forecast district hotspots.",
                confidence=0.4,
            ))
        else:
            findings.extend(self._district_hotspot_forecast(clusters, crime_type))

        if self.session:
            findings.extend(self._crime_type_forecast())
            findings.extend(self._repeat_offender_risk_forecast(state))
            findings.extend(self._officer_workload_forecast())

        return findings

    def _district_hotspot_forecast(self, clusters, crime_type):
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
            trend = "rising" if slope > RISING_SLOPE_THRESHOLD else ("falling" if slope < FALLING_SLOPE_THRESHOLD else "stable")

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
                    "district": district, "slope": round(slope, 3), "predicted_next_month": predicted,
                    "history": dict(month_counts), "method": "least_squares_linear_fit",
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

    def _crime_type_forecast(self):
        """Sprint B4: same linear-fit method, applied per crime type
        instead of per district — answers "which crime type is rising"
        directly, across the whole database rather than one filtered slice."""
        crimes = self.session.query(Crime).all()
        by_type_month = defaultdict(lambda: defaultdict(int))
        for c in crimes:
            by_type_month[c.type.value][c.timestamp.month] += 1

        rising = []
        for ctype, month_counts in by_type_month.items():
            months = sorted(month_counts)
            if len(months) < MIN_MONTHS_FOR_FIT:
                continue
            slope, _ = self._linear_fit(months, [month_counts[m] for m in months])
            if slope > RISING_SLOPE_THRESHOLD:
                rising.append((ctype, slope, dict(month_counts)))

        if not rising:
            return []

        rising.sort(key=lambda r: r[1], reverse=True)
        summary = f"Crime-type trend: {', '.join(f'{c} (slope {s:+.2f})' for c, s, _ in rising[:3])} rising month-over-month."
        return [AgentFinding(
            agent_name=self.name,
            finding_type="predictive_forecast",
            summary=summary,
            evidence=[f"{c}: {h}" for c, s, h in rising[:5]],
            confidence=0.65,
            source_entities=[],
            metadata={"rising_crime_types": [{"type": c, "slope": round(s, 3)} for c, s, _ in rising]},
        )]

    def _repeat_offender_risk_forecast(self, state):
        """Sprint B4: flags accused persons whose OWN crime frequency is
        accelerating — same escalation logic as Behavioral Intelligence,
        applied here as a forward risk flag rather than a descriptive score."""
        gctx = state.get("graph_context", {})
        person_ids = gctx.get("accused_person_ids", [])
        if not person_ids:
            return []

        at_risk = []
        for pid in person_ids:
            records = self.session.query(Accused).filter_by(person_id=pid).all()
            crimes = sorted((a.fir.crime for a in records if a.fir and a.fir.crime), key=lambda c: c.timestamp)
            if len(crimes) < 3:
                continue
            gaps = [(crimes[i + 1].timestamp - crimes[i].timestamp).days for i in range(len(crimes) - 1)]
            if gaps[-1] < gaps[0]:  # most recent gap shorter than the first — accelerating
                at_risk.append((records[0].person.name, len(crimes), gaps))

        if not at_risk:
            return []

        summary = f"Repeat-offender risk: {len(at_risk)} person(s) in scope show accelerating reoffense frequency."
        return [AgentFinding(
            agent_name=self.name,
            finding_type="predictive_forecast",
            summary=summary,
            evidence=[f"{name}: {n} crimes, gaps {g} days (shrinking)" for name, n, g in at_risk],
            confidence=0.6,  # same caveat as Behavioral Intelligence's escalation score — a heuristic, not a validated risk model
            source_entities=[],
            metadata={"at_risk_count": len(at_risk)},
        )]

    def _officer_workload_forecast(self):
        """Sprint B4, honest scoping note: this reports CURRENT caseload
        against a stated capacity threshold, not a projection of future
        workload. A real forecast would need incoming-case-rate data per
        officer over time, which this schema doesn't track (FIR assignment
        has no "assigned_date" separate from filed_date). Flagged as
        current-state read, not disguised as a forecast."""
        officers = self.session.query(Officer).all()
        at_capacity = []
        for o in officers:
            active = len([f for f in o.firs_investigated if f.status.value not in ("closed", "convicted")])
            if active >= WORKLOAD_AT_CAPACITY_THRESHOLD:
                at_capacity.append((o.name, o.badge_number, active))

        if not at_capacity:
            return []

        summary = (
            f"Officer workload: {len(at_capacity)} officer(s) at or above {WORKLOAD_AT_CAPACITY_THRESHOLD} "
            f"active cases — current-state capacity flag, not a projected trend (see agent docstring)."
        )
        return [AgentFinding(
            agent_name=self.name,
            finding_type="predictive_forecast",
            summary=summary,
            evidence=[f"{name} (badge {badge}): {active} active case(s)" for name, badge, active in at_capacity],
            confidence=0.9,  # direct count, not a projection — high confidence in the fact, not in any forward claim
            source_entities=[],
            metadata={"at_capacity_officers": at_capacity, "threshold": WORKLOAD_AT_CAPACITY_THRESHOLD},
        )]

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
