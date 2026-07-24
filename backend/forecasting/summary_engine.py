"""
SHERLOCK — Alert Summary Engine (Forecasting & Early Warning Engine,
Requirement 8).

`generate_forecast_dashboard()` is the single entry point the
`/forecast/dashboard` endpoint and the frontend ForecastDashboard call —
everything else in this package is composed here into one payload:

    Executive Summary, Forecast Cards, Upcoming Hotspots,
    Emerging Crime Types, Gang Alerts, Repeat Alerts,
    Prediction Timeline, Recommendations

Purely a composition layer: every number in the output is produced by
TrendForecaster / HotspotForecaster / RepeatAlertEngine / GangAlertEngine
/ RiskForecaster / EarlyWarningEngine — nothing is computed fresh here.
"""

from __future__ import annotations

from backend.forecasting.early_warning_engine import EarlyWarningEngine
from backend.forecasting.gang_alert_engine import GangAlertEngine
from backend.forecasting.hotspot_forecaster import HotspotForecaster
from backend.forecasting.repeat_alert_engine import RepeatAlertEngine
from backend.forecasting.risk_forecaster import RiskForecaster
from backend.forecasting.trend_forecaster import TrendForecaster


def generate_forecast_dashboard(session) -> dict:
    trend = TrendForecaster(session)
    hotspot = HotspotForecaster(session)
    repeat = RepeatAlertEngine(session)
    gang = GangAlertEngine(session)
    risk = RiskForecaster(session)
    warning = EarlyWarningEngine(session)

    overall = trend.forecast_crime_volume()
    by_type = trend.forecast_by_type()
    upcoming_hotspots = hotspot.predict_hotspots(top_n=10)
    emerging_crime_types = [f for f in by_type if f["growth"] >= 15]
    gang_alerts = gang.get_gang_alerts()
    repeat_alerts = repeat.generate_alerts()
    prediction_timeline = trend.rolling_forecast(periods=3)
    warnings = warning.generate_warnings()

    executive_summary = _executive_summary(overall, upcoming_hotspots, emerging_crime_types, gang_alerts, repeat_alerts)
    recommendations = _recommendations(upcoming_hotspots, emerging_crime_types, gang_alerts, repeat_alerts)

    return {
        "executive_summary": executive_summary,
        "forecast_cards": {
            "overall": overall,
            "by_crime_type": by_type,
        },
        "upcoming_hotspots": upcoming_hotspots,
        "emerging_crime_types": emerging_crime_types,
        "gang_alerts": gang_alerts,
        "repeat_alerts": repeat_alerts,
        "prediction_timeline": prediction_timeline,
        "recommendations": recommendations,
        "early_warnings": warnings,
    }


def _executive_summary(overall, hotspots, emerging_types, gang_alerts, repeat_alerts) -> str:
    high_risk_districts = [h["district"] for h in hotspots if h["predicted_risk"] == "High"]
    parts = [
        f"Overall crime volume forecast: {overall['current']} -> {overall['predicted']} "
        f"({overall['growth']:+.1f}%, {overall['method']}, confidence {overall['confidence']:.0%})."
    ]
    if high_risk_districts:
        parts.append(f"High-risk districts for the coming month: {', '.join(high_risk_districts)}.")
    if emerging_types:
        names = ", ".join(f["crime_type"].replace("_", " ") for f in emerging_types[:3])
        parts.append(f"Emerging crime types (rising trend): {names}.")
    critical_gangs = [g for g in gang_alerts if g["risk"] == "Critical"]
    if critical_gangs:
        parts.append(f"{len(critical_gangs)} gang cluster(s) flagged Critical risk.")
    total_repeat = sum(len(v) for v in repeat_alerts.values())
    if total_repeat:
        parts.append(f"{total_repeat} repeat-pattern alert(s) across locations, MO, and victim groups.")
    return " ".join(parts)


def _recommendations(hotspots, emerging_types, gang_alerts, repeat_alerts) -> list[str]:
    recs = []
    for h in hotspots:
        if h["predicted_risk"] == "High":
            recs.append(f"Increase patrol allocation in {h['district']} — predicted High risk next period.")
    for f in emerging_types[:3]:
        recs.append(f"Review response capacity for {f['crime_type'].replace('_', ' ')} — {f['growth']:+.1f}% predicted growth.")
    for g in gang_alerts:
        if g["risk"] in ("Critical", "High"):
            recs.append(f"Prioritize surveillance for {g['gang_id']} ({g['category']}, {g['members']} members) in {g['district'] or 'unknown district'}.")
    for group_alerts in repeat_alerts.values():
        for a in group_alerts:
            if a["severity"] in ("Critical", "High"):
                recs.append(a["recommendation"])
    if not recs:
        recs.append("No high-priority patterns detected in the current data — maintain standard patrol allocation.")
    return recs[:15]
