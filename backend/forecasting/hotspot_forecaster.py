"""
SHERLOCK — Hotspot Forecaster (Forecasting & Early Warning Engine, Requirement 8).

Predicts FUTURE district hotspots (as opposed to Network Analysis's
`find_location_clusters`, which reports CURRENT/historical ones).
Deterministic composite of four real signals:

    - persistence:      was this district already a hotspot in the most
                         recent complete month? (real, from Crime/Location)
    - trend growth:      TrendForecaster.forecast_by_district's growth % for
                         this district (real, fitted)
    - repeat incidents:  count of repeat-offender accused persons whose
                         home_location is in this district (real, from
                         Accused/Person — same FIR-tally definition used
                         in backend/intelligence/sociological_insights.py)
    - seasonal weighting: festival-season (Sep-Oct-Nov) share of this
                         district's historical crime, same FESTIVAL_MONTHS
                         convention as pattern_analysis/agent.py (real)

"Neighboring hotspot influence" (named in the brief) is NOT implemented:
Location has no geo-adjacency data (no lat/lng-based neighbor graph, no
district-adjacency table) to compute it from honestly. Flagged here as a
named gap rather than approximated with an invented adjacency.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from backend.database.models import Accused, Crime, Location, Person
from backend.forecasting.trend_forecaster import TrendForecaster, _month_key, reference_now

FESTIVAL_MONTHS = {9, 10, 11}  # same convention as pattern_analysis/agent.py

NEIGHBORING_HOTSPOT_GAP = (
    "Neighboring-hotspot influence is not computed: Location has no lat/lng-based "
    "adjacency or district-adjacency table to derive 'neighboring' from honestly. "
    "Extension point: feed a {district: [neighboring_districts]} map into "
    "HotspotForecaster.predict_hotspots(district_adjacency=...) once one exists."
)


class HotspotForecaster:
    def __init__(self, session):
        self.session = session
        self.trend = TrendForecaster(session)

    def predict_hotspots(self, top_n: int = 10, district_adjacency: dict[str, list[str]] | None = None) -> list[dict]:
        districts = sorted({d for (d,) in self.session.query(Location.district).distinct().all()})
        if not districts:
            return []

        persistence = self._current_hotspot_districts()
        trend_by_district = {r["district"]: r for r in self.trend.forecast_by_district()}
        repeat_counts = self._repeat_offender_counts_by_district()
        seasonal_share = self._festival_share_by_district()

        results = []
        for district in districts:
            trend = trend_by_district.get(district, {})
            growth = trend.get("growth", 0.0)
            is_persistent = district in persistence
            repeat_count = repeat_counts.get(district, 0)
            season_share = seasonal_share.get(district, 0.0)

            # Composite risk score — a stated weighted sum, not a fitted model.
            score = (
                (40 if is_persistent else 0)
                + max(0, min(growth, 100)) * 0.3
                + min(repeat_count * 5, 20)
                + season_share * 10
            )
            score = round(min(score, 100), 1)

            if score >= 65:
                risk_label = "High"
            elif score >= 35:
                risk_label = "Medium"
            else:
                risk_label = "Low"

            entry = {
                "district": district,
                "predicted_risk": risk_label,
                "probability": round(score / 100, 2),
                "expected_incidents": trend.get("predicted", trend.get("current", 0)),
                "confidence": trend.get("confidence", 0.4),
                "evidence": {
                    "currently_a_hotspot": is_persistent,
                    "trend_growth_pct": growth,
                    "repeat_offenders_in_district": repeat_count,
                    "festival_season_share": season_share,
                },
            }
            if district_adjacency:
                neighbors = district_adjacency.get(district, [])
                neighbor_scores = [trend_by_district.get(n, {}).get("growth", 0.0) for n in neighbors]
                entry["neighboring_hotspot_influence"] = {
                    "available": True,
                    "neighbors": neighbors,
                    "avg_neighbor_growth_pct": round(sum(neighbor_scores) / len(neighbor_scores), 1) if neighbor_scores else 0.0,
                }
            else:
                entry["neighboring_hotspot_influence"] = {"available": False, "reason": NEIGHBORING_HOTSPOT_GAP}

            results.append(entry)

        results.sort(key=lambda r: r["probability"], reverse=True)
        return results[:top_n]

    # -- signal builders ---------------------------------------------------

    def _current_hotspot_districts(self, top_fraction: float = 0.3) -> set[str]:
        """Districts in the top `top_fraction` by crime count in the most
        recent complete month."""
        rows = self.session.query(Crime.timestamp, Location.district).join(Location, Location.id == Crime.location_id).all()
        current_month = _month_key(reference_now(self.session))
        by_district = Counter()
        for ts, district in rows:
            mk = _month_key(ts)
            if mk == current_month:
                continue
            # only count the most recent complete month
            by_district[(mk, district)] += 1

        if not by_district:
            return set()
        latest_month = max(mk for mk, _ in by_district)
        month_counts = Counter({d: c for (mk, d), c in by_district.items() if mk == latest_month})
        if not month_counts:
            return set()
        n = max(1, round(len(month_counts) * top_fraction))
        return {d for d, _ in month_counts.most_common(n)}

    def _repeat_offender_counts_by_district(self) -> dict[str, int]:
        rows = (
            self.session.query(Person, Accused.fir_id)
            .join(Accused, Accused.person_id == Person.id)
            .join(Location, Location.id == Person.home_location_id)
            .all()
        )
        fir_counts = defaultdict(set)
        district_of_person = {}
        for person, fir_id in rows:
            fir_counts[person.id].add(fir_id)
            district_of_person[person.id] = person.home_location.district if person.home_location else None

        out = Counter()
        for person_id, fir_ids in fir_counts.items():
            if len(fir_ids) >= 2:
                district = district_of_person.get(person_id)
                if district:
                    out[district] += 1
        return dict(out)

    def _festival_share_by_district(self) -> dict[str, float]:
        rows = self.session.query(Crime.timestamp, Location.district).join(Location, Location.id == Crime.location_id).all()
        totals = Counter()
        festival = Counter()
        for ts, district in rows:
            totals[district] += 1
            if ts.month in FESTIVAL_MONTHS:
                festival[district] += 1
        return {d: round(festival[d] / totals[d], 2) for d in totals if totals[d] > 0}
