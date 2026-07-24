"""
SHERLOCK — Early Warning Engine (Forecasting & Early Warning Engine,
Requirement 8).

Aggregates every other engine's output into one severity-tiered warning
feed (Critical/High/Medium/Low). Doesn't compute anything new — it's a
formatting/ranking layer over TrendForecaster, HotspotForecaster,
RepeatAlertEngine, GangAlertEngine, and AnomalyEngine, so every warning's
`evidence` list traces straight back to a real number one of those
engines produced.
"""

from __future__ import annotations

from backend.forecasting.anomaly_engine import AnomalyEngine
from backend.forecasting.gang_alert_engine import GangAlertEngine
from backend.forecasting.hotspot_forecaster import HotspotForecaster
from backend.forecasting.repeat_alert_engine import RepeatAlertEngine
from backend.forecasting.trend_forecaster import TrendForecaster, _add_months, _month_key, reference_now


class EarlyWarningEngine:
    def __init__(self, session):
        self.session = session
        self.trend = TrendForecaster(session)
        self.hotspot = HotspotForecaster(session)
        self.repeat = RepeatAlertEngine(session)
        self.gang = GangAlertEngine(session)
        self.anomaly = AnomalyEngine(session)

    def generate_warnings(self, top_n: int = 15) -> list[dict]:
        next_month = _add_months(_month_key(reference_now(self.session)), 1)
        warnings = []

        # Hotspot-driven warnings.
        for h in self.hotspot.predict_hotspots(top_n=5):
            if h["predicted_risk"] == "Low":
                continue
            warnings.append({
                "title": f"{h['district']} Crime Surge",
                "severity": h["predicted_risk"] if h["predicted_risk"] != "High" else "High",
                "confidence": h["confidence"],
                "predicted_date": next_month,
                "evidence": [
                    f"Currently a hotspot: {h['evidence']['currently_a_hotspot']}",
                    f"Trend growth: {h['evidence']['trend_growth_pct']}%",
                    f"Repeat offenders resident in district: {h['evidence']['repeat_offenders_in_district']}",
                    f"Festival-season share of historical crime: {h['evidence']['festival_season_share']:.0%}",
                ],
                "recommended_actions": [f"Increase patrol allocation in {h['district']} ahead of {next_month}."],
            })

        # Crime-type trend warnings.
        for f in self.trend.forecast_by_type():
            if f["growth"] < 15 or f["months_used"] < 3:
                continue
            severity = "Critical" if f["growth"] >= 40 else "High" if f["growth"] >= 20 else "Medium"
            warnings.append({
                "title": f"{f['crime_type'].replace('_', ' ').title()} Trending Up",
                "severity": severity,
                "confidence": f["confidence"],
                "predicted_date": next_month,
                "evidence": [f["reason"], f"Current: {f['current']}, predicted: {f['predicted']} ({f['method']})."],
                "recommended_actions": [f"Review resourcing for {f['crime_type'].replace('_', ' ')} response capacity."],
            })

        # Gang activity warnings.
        for g in self.gang.get_gang_alerts():
            if g["risk"] not in ("Critical", "High"):
                continue
            warnings.append({
                "title": f"Gang Activity — {g['gang_id']} ({g['category']})",
                "severity": g["risk"],
                "confidence": 0.7 if g["confirmed_org_membership"] else 0.55,
                "predicted_date": next_month,
                "evidence": [
                    f"{g['members']} member(s), activity growth {g['activity_growth']}%",
                    f"Recorded gang-org membership: {g['confirmed_org_membership']}",
                    f"District: {g['district']}",
                ],
                "recommended_actions": [f"Surveillance review for {g['gang_id']} in {g['district'] or 'affected districts'}."],
            })

        # Repeat-pattern warnings (locations + MO + crime-type clusters).
        alerts = self.repeat.generate_alerts()
        for group in ("repeat_locations", "repeat_mo", "repeat_crime_types"):
            for a in alerts[group]:
                if a["severity"] not in ("Critical", "High"):
                    continue
                warnings.append({
                    "title": a["alert"],
                    "severity": a["severity"],
                    "confidence": 0.65,
                    "predicted_date": next_month,
                    "evidence": [f"{a['occurrences']} occurrence(s) in {a['window_days']} day(s)."],
                    "recommended_actions": [a["recommendation"]],
                })

        # Statistical anomalies.
        for a in self.anomaly.detect_all()["by_district"]:
            if a["direction"] != "spike":
                continue
            warnings.append({
                "title": f"{a['label']} Anomalous Spike ({a['month']})",
                "severity": "High" if a["z_score"] >= 3 else "Medium",
                "confidence": round(min(0.5 + abs(a["z_score"]) * 0.1, 0.9), 2),
                "predicted_date": next_month,
                "evidence": [a["reason"]],
                "recommended_actions": [f"Investigate cause of the {a['month']} spike in {a['label']} before it repeats."],
            })

        severity_order = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        warnings.sort(key=lambda w: (severity_order.get(w["severity"], 4), -w["confidence"]))
        return warnings[:top_n]
