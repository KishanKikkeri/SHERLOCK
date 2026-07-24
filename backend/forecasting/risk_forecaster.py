"""
SHERLOCK — Risk Forecaster (Forecasting & Early Warning Engine,
Requirement 8).

Aggregates the other engines into four forward-looking risk views:
offender, hotspot, district, and crime-type risk. Doesn't introduce new
raw signals — composes `TrendForecaster` and `HotspotForecaster` output,
plus a per-accused escalation check (shrinking gaps between a person's
own crimes over time — same logic as
`backend/agents/behavioral_intelligence/agent.py`'s escalation score,
recomputed here directly against Accused/FIR/Crime rather than imported,
to keep this package's only dependency on `backend.agents` at zero).
"""

from __future__ import annotations

from collections import defaultdict

from backend.database.models import Accused, FIR, Person
from backend.forecasting.hotspot_forecaster import HotspotForecaster
from backend.forecasting.trend_forecaster import TrendForecaster

MIN_CRIMES_FOR_ESCALATION = 3


class RiskForecaster:
    def __init__(self, session):
        self.session = session
        self.trend = TrendForecaster(session)
        self.hotspot = HotspotForecaster(session)

    def crime_type_risk(self) -> list[dict]:
        forecasts = self.trend.forecast_by_type()
        out = []
        for f in forecasts:
            growth = f["growth"]
            risk = "High" if growth >= 20 else "Medium" if growth >= 5 else "Low"
            out.append({**f, "risk": risk})
        out.sort(key=lambda r: r["growth"], reverse=True)
        return out

    def district_risk(self) -> list[dict]:
        return self.hotspot.predict_hotspots(top_n=len(self._all_districts()))

    def hotspot_risk(self, top_n: int = 10) -> list[dict]:
        return self.hotspot.predict_hotspots(top_n=top_n)

    def offender_risk(self, min_crimes: int = 2, limit: int = 20) -> list[dict]:
        rows = self.session.query(Accused.person_id, Accused.fir_id).all()
        firs_by_person = defaultdict(set)
        for pid, fir_id in rows:
            firs_by_person[pid].add(fir_id)
        repeat_ids = [pid for pid, firs in firs_by_person.items() if len(firs) >= min_crimes]
        if not repeat_ids:
            return []

        persons = {p.id: p for p in self.session.query(Person).filter(Person.id.in_(repeat_ids)).all()}
        out = []
        for pid in repeat_ids:
            fir_ids = firs_by_person[pid]
            firs = self.session.query(FIR).filter(FIR.id.in_(fir_ids)).all()
            crimes = sorted((f.crime for f in firs if f.crime), key=lambda c: c.timestamp)
            escalating = self._is_escalating(crimes)
            crime_count = len(crimes)

            risk_score = min(crime_count * 15, 60) + (25 if escalating else 0)
            risk = "Critical" if risk_score >= 70 else "High" if risk_score >= 45 else "Medium" if risk_score >= 20 else "Low"

            person = persons.get(pid)
            out.append({
                "person_id": pid,
                "name": person.name if person else None,
                "crime_count": crime_count,
                "escalating": escalating,
                "risk": risk,
                "risk_score": risk_score,
                "reason": (
                    f"{crime_count} distinct FIR(s) as accused" +
                    (", with shrinking gaps between offenses (escalating pattern)" if escalating else "")
                ),
            })
        out.sort(key=lambda r: r["risk_score"], reverse=True)
        return out[:limit]

    def _is_escalating(self, crimes: list) -> bool:
        if len(crimes) < MIN_CRIMES_FOR_ESCALATION:
            return False
        gaps = [(crimes[i + 1].timestamp - crimes[i].timestamp).days for i in range(len(crimes) - 1)]
        shrinking_steps = sum(1 for i in range(len(gaps) - 1) if gaps[i + 1] < gaps[i])
        return shrinking_steps / max(len(gaps) - 1, 1) >= 0.5

    def _all_districts(self):
        from backend.database.models import Location
        return {d for (d,) in self.session.query(Location.district).distinct().all()}

    def generate_all(self) -> dict:
        return {
            "crime_type_risk": self.crime_type_risk(),
            "district_risk": self.district_risk(),
            "offender_risk": self.offender_risk(),
        }
