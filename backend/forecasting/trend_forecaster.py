"""
SHERLOCK — Trend Forecaster (Forecasting & Early Warning Engine, Requirement 8).

Deterministic. No LLM, no ML libraries — three textbook time-series
methods (moving average, weighted moving average, exponential smoothing)
fit to monthly crime counts built directly from `Crime.timestamp`.

Partial-month handling: the current calendar month is always excluded
from the historical series it fits against (it's incomplete by
definition — a forecast built from it would understate growth for any
month that hasn't finished yet). This is a deliberate choice, not an
oversight; see `_monthly_series`.

Every returned dict states which method produced it, how many months of
history backed the fit, and a confidence score derived from that history
(more months + lower month-to-month volatility -> higher confidence) —
never a fixed/invented number.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import func

from backend.database.models import Crime, Location

MIN_MONTHS_FOR_FORECAST = 3
DEFAULT_WINDOW = 6


def reference_now(session) -> datetime:
    """Anchor "now" to the latest recorded Crime.timestamp rather than
    wall-clock time. Every synthetic/demo dataset is generated relative
    to a fixed reference date that inevitably drifts behind real-world
    "now" the longer it sits unregenerated — window-based and recency
    logic (repeat alerts, gang activity growth, hotspot persistence)
    would silently go empty if anchored to wall-clock time instead.
    Falls back to wall-clock time only when there's no crime data at all."""
    latest = session.query(func.max(Crime.timestamp)).scalar()
    return latest if latest is not None else datetime.now(timezone.utc).replace(tzinfo=None)


def _month_key(dt: datetime) -> str:
    return f"{dt.year:04d}-{dt.month:02d}"


def _add_months(month_key: str, n: int) -> str:
    year, month = (int(x) for x in month_key.split("-"))
    total = (year * 12 + (month - 1)) + n
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


class TrendForecaster:
    def __init__(self, session):
        self.session = session

    # -- series construction ---------------------------------------------

    def _monthly_series(self, crime_type: str | None = None, district: str | None = None) -> dict[str, int]:
        """Real crime counts per month, current (incomplete) month excluded."""
        q = self.session.query(Crime.timestamp, Crime.type)
        if district:
            q = q.join(Location, Location.id == Crime.location_id).filter(Location.district == district)
        rows = q.all()

        counts: dict[str, int] = defaultdict(int)
        for ts, ctype in rows:
            if crime_type and ctype.value != crime_type:
                continue
            counts[_month_key(ts)] += 1

        current_month = _month_key(reference_now(self.session))
        counts.pop(current_month, None)
        return dict(sorted(counts.items()))

    # -- the three required methods --------------------------------------

    @staticmethod
    def moving_average(series: list[float], window: int = 3) -> float:
        if not series:
            return 0.0
        tail = series[-window:] if len(series) >= window else series
        return sum(tail) / len(tail)

    @staticmethod
    def weighted_moving_average(series: list[float], weights: list[float] | None = None) -> float:
        """Linearly increasing weights by default (most recent month
        counts most) — a stated choice, not a fitted parameter."""
        if not series:
            return 0.0
        if weights is None:
            n = min(len(series), 6)
            weights = list(range(1, n + 1))
            tail = series[-n:]
        else:
            tail = series[-len(weights):]
        total_weight = sum(weights)
        if total_weight == 0:
            return TrendForecaster.moving_average(series)
        return sum(v * w for v, w in zip(tail, weights)) / total_weight

    @staticmethod
    def exponential_smoothing(series: list[float], alpha: float = 0.3) -> float:
        if not series:
            return 0.0
        level = series[0]
        for value in series[1:]:
            level = alpha * value + (1 - alpha) * level
        return level

    def _apply(self, method: str, series: list[float]) -> float:
        if method == "moving_average":
            return self.moving_average(series)
        if method == "exponential_smoothing":
            return self.exponential_smoothing(series)
        return self.weighted_moving_average(series)  # default

    @staticmethod
    def _confidence(months: list[str], values: list[float]) -> float:
        """More history + lower relative volatility -> higher confidence.
        Bounded to [0.3, 0.95] so a forecast is never reported as
        certain, and never as worthless when the fit is reasonable."""
        history_weight = min(len(months) / 12, 1.0)  # full weight at 12+ months
        if len(values) >= 2 and statistics.mean(values) > 0:
            cv = statistics.pstdev(values) / statistics.mean(values)
            volatility_penalty = min(cv, 1.0)
        else:
            volatility_penalty = 0.5
        score = 0.35 + 0.4 * history_weight + 0.2 * (1 - volatility_penalty)
        return round(max(0.3, min(0.95, score)), 2)

    def _reason(self, months: list[str], values: list[float], growth: float) -> str:
        if len(months) < MIN_MONTHS_FOR_FORECAST:
            return f"Only {len(months)} month(s) of history — forecast is low-confidence by construction."
        direction = "Positive" if growth > 5 else "Negative" if growth < -5 else "Flat"
        return f"{direction} trend over the previous {len(months)} month(s) ({months[0]} to {months[-1]})."

    def _forecast_one(self, label: str, months_dict: dict[str, int], method: str, window: int) -> dict:
        months = list(months_dict.keys())[-window:]
        values = [float(months_dict[m]) for m in months]

        if len(months) < MIN_MONTHS_FOR_FORECAST:
            current = values[-1] if values else 0
            return {
                "label": label,
                "current": int(current),
                "predicted": int(current),
                "growth": 0.0,
                "confidence": 0.3,
                "method": method,
                "months_used": len(months),
                "reason": f"Only {len(months)} month(s) of history in scope — insufficient for a trend fit (need >= {MIN_MONTHS_FOR_FORECAST}).",
            }

        predicted = self._apply(method, values)
        current = values[-1]
        growth = ((predicted - current) / current * 100) if current else (100.0 if predicted else 0.0)

        return {
            "label": label,
            "current": int(current),
            "predicted": round(predicted, 1),
            "growth": round(growth, 1),
            "confidence": self._confidence(months, values),
            "method": method,
            "months_used": len(months),
            "reason": self._reason(months, values, growth),
        }

    # -- public API (exact names from the brief) --------------------------

    def forecast_crime_volume(self, method: str = "weighted_moving_average", window: int = DEFAULT_WINDOW) -> dict:
        series = self._monthly_series()
        result = self._forecast_one("overall", series, method, window)
        result["crime_type"] = None
        result["district"] = None
        return result

    def forecast_by_type(self, method: str = "weighted_moving_average", window: int = DEFAULT_WINDOW) -> list[dict]:
        crime_types = sorted({ctype.value for (ctype,) in self.session.query(Crime.type).distinct().all()})
        out = []
        for ctype in crime_types:
            series = self._monthly_series(crime_type=ctype)
            result = self._forecast_one(ctype, series, method, window)
            result["crime_type"] = ctype
            out.append(result)
        return out

    def forecast_by_district(self, method: str = "weighted_moving_average", window: int = DEFAULT_WINDOW) -> list[dict]:
        districts = sorted({d for (d,) in self.session.query(Location.district).distinct().all()})
        out = []
        for district in districts:
            series = self._monthly_series(district=district)
            result = self._forecast_one(district, series, method, window)
            result["district"] = district
            out.append(result)
        return out

    def forecast_next_month(self, crime_type: str | None = None, district: str | None = None,
                             method: str = "weighted_moving_average", window: int = DEFAULT_WINDOW) -> dict:
        series = self._monthly_series(crime_type=crime_type, district=district)
        label = crime_type or district or "overall"
        result = self._forecast_one(label, series, method, window)
        months = list(series.keys())
        result["target_month"] = _add_months(months[-1], 1) if months else None
        result["crime_type"] = crime_type
        result["district"] = district
        return result

    def forecast_next_quarter(self, crime_type: str | None = None, district: str | None = None,
                               method: str = "weighted_moving_average", window: int = DEFAULT_WINDOW) -> dict:
        """Iteratively forecasts 3 months ahead, feeding each month's
        forecast back into the series for the next — the standard way to
        extend a single-step method to a multi-step horizon. Confidence
        is taken from the first (least uncertain) step, not compounded,
        since compounding three heuristic confidences would imply false
        precision."""
        series = dict(self._monthly_series(crime_type=crime_type, district=district))
        label = crime_type or district or "overall"
        months = list(series.keys())

        if len(months) < MIN_MONTHS_FOR_FORECAST:
            base = self._forecast_one(label, series, method, window)
            base.update({"quarter_total": base["current"] * 3, "crime_type": crime_type, "district": district})
            return base

        first_step_confidence = None
        monthly_predictions = []
        working_series = dict(series)
        last_month = months[-1]
        for i in range(3):
            step = self._forecast_one(label, working_series, method, window)
            if first_step_confidence is None:
                first_step_confidence = step["confidence"]
            next_month = _add_months(last_month, 1)
            working_series[next_month] = step["predicted"]
            monthly_predictions.append({"month": next_month, "predicted": step["predicted"]})
            last_month = next_month

        current_quarter_total = sum(list(series.values())[-3:])
        predicted_quarter_total = sum(m["predicted"] for m in monthly_predictions)
        growth = ((predicted_quarter_total - current_quarter_total) / current_quarter_total * 100) if current_quarter_total else 0.0

        return {
            "label": label,
            "crime_type": crime_type,
            "district": district,
            "current": current_quarter_total,
            "predicted": round(predicted_quarter_total, 1),
            "quarter_total": round(predicted_quarter_total, 1),
            "monthly_breakdown": monthly_predictions,
            "growth": round(growth, 1),
            "confidence": first_step_confidence,
            "method": method,
            "months_used": len(months),
            "reason": f"Sum of 3 iteratively-forecast months, each fed back into the series (method: {method}).",
        }

    def rolling_forecast(self, crime_type: str | None = None, district: str | None = None,
                          method: str = "weighted_moving_average", window: int = DEFAULT_WINDOW,
                          periods: int = 3) -> list[dict]:
        """periods successive one-step-ahead forecasts, each appended to
        the series before computing the next — same iterative principle
        as forecast_next_quarter, generalized to N steps."""
        series = dict(self._monthly_series(crime_type=crime_type, district=district))
        label = crime_type or district or "overall"
        months = list(series.keys())
        if not months:
            return []

        results = []
        working_series = dict(series)
        last_month = months[-1]
        for i in range(periods):
            step = self._forecast_one(label, working_series, method, window)
            next_month = _add_months(last_month, 1)
            step["target_month"] = next_month
            results.append(step)
            working_series[next_month] = step["predicted"]
            last_month = next_month
        return results
