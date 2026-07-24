"""
SHERLOCK — Anomaly Engine (Forecasting & Early Warning Engine,
Requirement 8).

Statistical (z-score) anomaly detection over monthly crime counts —
"is this month unusual for this district/crime type", as distinct from
`repeat_alert_engine.py`'s fixed-threshold repeat-pattern detection.
Deterministic: population mean/stdev of a district or crime type's own
historical monthly counts (current, incomplete month excluded), then
flags any month whose z-score exceeds `z_threshold`.

Needs >= MIN_MONTHS_FOR_ZSCORE complete months of history to compute a
meaningful stdev; below that, reports "insufficient history" rather than
a z-score computed from 1-2 points (which is not statistically meaningful).
"""

from __future__ import annotations

import statistics

from backend.database.models import Crime, Location
from backend.forecasting.trend_forecaster import TrendForecaster

MIN_MONTHS_FOR_ZSCORE = 4
DEFAULT_Z_THRESHOLD = 2.0


class AnomalyEngine:
    def __init__(self, session):
        self.session = session
        self.trend = TrendForecaster(session)

    def _flag_series(self, label: str, months_dict: dict[str, int], z_threshold: float) -> list[dict]:
        months = list(months_dict.keys())
        values = [float(months_dict[m]) for m in months]
        if len(values) < MIN_MONTHS_FOR_ZSCORE:
            return []

        mean = statistics.mean(values)
        stdev = statistics.pstdev(values)
        if stdev == 0:
            return []

        anomalies = []
        for month, value in zip(months, values):
            z = (value - mean) / stdev
            if abs(z) >= z_threshold:
                anomalies.append({
                    "label": label,
                    "month": month,
                    "count": int(value),
                    "mean": round(mean, 1),
                    "stdev": round(stdev, 1),
                    "z_score": round(z, 2),
                    "direction": "spike" if z > 0 else "drop",
                    "reason": f"{int(value)} in {month} vs a historical mean of {mean:.1f} ± {stdev:.1f} (z={z:.2f}).",
                })
        return anomalies

    def detect_crime_type_anomalies(self, z_threshold: float = DEFAULT_Z_THRESHOLD) -> list[dict]:
        crime_types = sorted({ctype.value for (ctype,) in self.session.query(Crime.type).distinct().all()})
        out = []
        for ctype in crime_types:
            series = self.trend._monthly_series(crime_type=ctype)
            out.extend(self._flag_series(ctype, series, z_threshold))
        return out

    def detect_district_anomalies(self, z_threshold: float = DEFAULT_Z_THRESHOLD) -> list[dict]:
        districts = sorted({d for (d,) in self.session.query(Location.district).distinct().all()})
        out = []
        for district in districts:
            series = self.trend._monthly_series(district=district)
            out.extend(self._flag_series(district, series, z_threshold))
        return out

    def detect_overall_anomalies(self, z_threshold: float = DEFAULT_Z_THRESHOLD) -> list[dict]:
        series = self.trend._monthly_series()
        return self._flag_series("overall", series, z_threshold)

    def detect_all(self, z_threshold: float = DEFAULT_Z_THRESHOLD) -> dict:
        return {
            "overall": self.detect_overall_anomalies(z_threshold),
            "by_crime_type": self.detect_crime_type_anomalies(z_threshold),
            "by_district": self.detect_district_anomalies(z_threshold),
        }
