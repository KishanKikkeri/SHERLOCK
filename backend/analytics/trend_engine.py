"""
SHERLOCK — Trend Engine (Crime Pattern & Trend Analytics Agent).

Computes real time-bucketed aggregations, rolling averages, and
growth/decline indicators from `Crime` records. This module does not
touch the LLM or the LangGraph pipeline — it's pure computation over
the database, called by the Crime Pattern & Trend Analytics agent (and
directly by an analytics API route) so the frontend gets numbers and
series, never a paragraph to re-parse.

Schema note: `Crime.location` only carries district (not police
station / ward / city — see `backend/database/models/location.py`).
Every function here that reports "location" reports district; there
is no finer granularity to compute from until that schema gap is
closed. `crimes_by_district` is written now; `crimes_by_station`,
`crimes_by_ward`, `crimes_by_city` are deliberately not stubbed here —
see hotspot_engine.py's module docstring for the same gap noted once,
not repeated per function.
"""

from __future__ import annotations

import calendar
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database.models import Crime, Location, FIR, Victim, Person

Granularity = str  # "day" | "week" | "month" | "quarter" | "year"


@dataclass(frozen=True)
class VictimFilter:
    """Optional victim-demographic filter — Crime -> FIR -> Victim -> Person,
    the only path to gender/age in this schema (see module docstring:
    there's no demographic column on Crime itself). Threaded through as
    one object rather than three loose params so every engine function
    that accepts filtering takes the same shape.
    """
    gender: Optional[str] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None

    def is_empty(self) -> bool:
        return self.gender is None and self.age_min is None and self.age_max is None


def _victim_filtered_crime_ids(session: Session, victim_filter: Optional[VictimFilter]) -> Optional[set]:
    """Crime IDs with at least one victim matching `victim_filter`, or
    None if no demographic filter was given (meaning: don't restrict).
    Every engine that wants gender/age filtering applies this the same
    way: `if ids is not None: q = q.filter(Crime.id.in_(ids))`.
    """
    if victim_filter is None or victim_filter.is_empty():
        return None
    q = (
        session.query(Crime.id)
        .join(FIR, FIR.crime_id == Crime.id)
        .join(Victim, Victim.fir_id == FIR.id)
        .join(Person, Person.id == Victim.person_id)
    )
    if victim_filter.gender:
        q = q.filter(Person.gender == victim_filter.gender)
    if victim_filter.age_min is not None:
        q = q.filter(Person.age >= victim_filter.age_min)
    if victim_filter.age_max is not None:
        q = q.filter(Person.age <= victim_filter.age_max)
    return {row[0] for row in q.all()}


def _bucket_key(ts: datetime, granularity: Granularity) -> str:
    """Return a sortable string key identifying the bucket `ts` falls into."""
    if granularity == "day":
        return ts.strftime("%Y-%m-%d")
    if granularity == "week":
        iso_year, iso_week, _ = ts.isocalendar()
        return f"{iso_year}-W{iso_week:02d}"
    if granularity == "month":
        return ts.strftime("%Y-%m")
    if granularity == "quarter":
        q = (ts.month - 1) // 3 + 1
        return f"{ts.year}-Q{q}"
    if granularity == "year":
        return str(ts.year)
    raise ValueError(f"Unsupported granularity: {granularity}")


def _dataset_latest_timestamp(session: Session) -> Optional[datetime]:
    """Latest crime timestamp across the WHOLE table (unfiltered) — the
    stand-in for wall-clock 'now'. Fixture/demo data has no real 'today'
    to compare a bucket's completeness against, so the dataset's own
    most recent record is the only honest reference point.
    """
    return session.query(func.max(Crime.timestamp)).scalar()


def _period_is_complete(period_key: str, granularity: Granularity, latest_ts: datetime) -> bool:
    """True if the bucket `period_key` (which must be the bucket
    containing `latest_ts`) has fully elapsed as of `latest_ts`. Only
    meaningful for the LAST bucket in a series — every earlier bucket is
    provably complete, since a later crime (`latest_ts`) exists past it.
    """
    if granularity == "day":
        return True  # a day-bucket is whole regardless of time-of-day
    if granularity == "week":
        return latest_ts.isocalendar()[2] == 7  # ISO weekday 7 = Sunday, week's last day
    if granularity == "month":
        last_day = calendar.monthrange(latest_ts.year, latest_ts.month)[1]
        return latest_ts.day == last_day
    if granularity == "quarter":
        q_end_month = ((latest_ts.month - 1) // 3 + 1) * 3
        last_day = calendar.monthrange(latest_ts.year, q_end_month)[1]
        return latest_ts.month == q_end_month and latest_ts.day == last_day
    if granularity == "year":
        return latest_ts.month == 12 and latest_ts.day == 31
    return True


def current_global_partial_period(session: Session, granularity: Granularity) -> Optional[str]:
    """The dataset-wide 'in progress' bucket for this granularity, if
    the most recent crime on record falls short of that period's end —
    e.g. the latest crime is dated May 3rd, so "2026-05" hasn't actually
    finished and shouldn't be compared against complete prior periods.
    Returns None once/if the dataset extends to a period's real end.
    Computed once per call, independent of crime_type/district filters,
    since "is May 2026 over yet" is a single calendar fact, not
    scoped to any subset of crimes.
    """
    latest_ts = _dataset_latest_timestamp(session)
    if latest_ts is None:
        return None
    current_key = _bucket_key(latest_ts, granularity)
    return None if _period_is_complete(current_key, granularity, latest_ts) else current_key


def _confidence_tier(history_counts: list[int]) -> dict:
    """How much a growth/direction reading should be trusted, derived
    from sample size and variance in the history behind it — a rule-based
    tier, not a model, matching every other threshold in this package
    (see cluster_engine's z-score default for the same "starting point,
    not tuned" caveat):
      - "high":   >=6 periods of history, mean count >=5, and low
                  period-to-period variance (coefficient of variation <= 0.5)
      - "medium": >=3 periods of history and mean count >=2
      - "low":    everything short of that — thin history and/or small,
                  noisy counts, where a single unusual period can swing
                  the percentage a lot
    -> {"tier": "high"|"medium"|"low", "periods_of_history": int, "reason": str}
    """
    n = len(history_counts)
    mean = statistics.mean(history_counts) if history_counts else 0.0
    stdev = statistics.pstdev(history_counts) if n > 1 else 0.0
    cv = (stdev / mean) if mean else float("inf")

    if n >= 6 and mean >= 5 and cv <= 0.5:
        return {"tier": "high", "periods_of_history": n,
                "reason": f"{n} periods of stable history, averaging {round(mean, 1)}/period"}
    if n >= 3 and mean >= 2:
        return {"tier": "medium", "periods_of_history": n,
                "reason": f"{n} periods of history, moderate sample size"}
    return {"tier": "low", "periods_of_history": n,
            "reason": f"only {n} period(s) of history and/or small counts — treat with caution"}



def _query_crimes(session: Session, crime_type: Optional[str] = None,
                   district: Optional[str] = None, victim_filter: Optional[VictimFilter] = None):
    q = session.query(Crime)
    if district:
        q = q.join(Location, Crime.location_id == Location.id).filter(Location.district == district)
    if crime_type:
        q = q.filter(Crime.type == crime_type)
    victim_ids = _victim_filtered_crime_ids(session, victim_filter)
    if victim_ids is not None:
        q = q.filter(Crime.id.in_(victim_ids))
    return q.all()


def rolling_average(ordered_counts: list[int], window: int = 3) -> list[float]:
    """Trailing rolling average, same length as input. First `window - 1`
    points average over however many periods are actually available
    (no NaNs — a short history is more useful to a dashboard than a gap)."""
    out = []
    for i in range(len(ordered_counts)):
        lo = max(0, i - window + 1)
        chunk = ordered_counts[lo:i + 1]
        out.append(round(sum(chunk) / len(chunk), 2))
    return out


def growth_indicator(ordered_counts: list[int], partial_last: bool = False) -> dict:
    """Compare the most recent COMPLETE bucket to the one before it.
    If `partial_last` is True, the trailing count is an in-progress
    period (see `current_global_partial_period`) and is dropped first —
    comparing a still-accumulating period against a finished one produces
    a false "down 83%" the moment a new period starts. `partial_excluded`
    tells the caller whether that trim happened. `confidence` reflects how
    much history backs this particular reading — see `_confidence_tier`.
    -> {"direction": "up"|"down"|"flat", "pct_change": float,
        "current": int, "previous": int, "partial_excluded": bool,
        "confidence": {...}}
    """
    counts = ordered_counts[:-1] if partial_last and ordered_counts else ordered_counts
    confidence = _confidence_tier(counts)
    if len(counts) < 2:
        return {"direction": "flat", "pct_change": 0.0,
                "current": counts[-1] if counts else 0, "previous": 0,
                "partial_excluded": partial_last, "confidence": confidence}
    current, previous = counts[-1], counts[-2]
    if previous == 0:
        pct = 100.0 if current > 0 else 0.0
    else:
        pct = round((current - previous) / previous * 100, 1)
    direction = "up" if pct > 0 else "down" if pct < 0 else "flat"
    return {"direction": direction, "pct_change": pct, "current": current, "previous": previous,
            "partial_excluded": partial_last, "confidence": confidence}


def crime_trend(session: Session, granularity: Granularity = "month",
                 crime_type: Optional[str] = None, district: Optional[str] = None,
                 rolling_window: int = 3, victim_filter: Optional[VictimFilter] = None) -> dict:
    """Core time-series trend for one crime type / district / victim-demographic scope.

    -> {
         "granularity": str,
         "series": [{"period": str, "count": int, "rolling_avg": float, "partial": bool}, ...],  # chronological
         "growth": {...},         # see growth_indicator() — excludes a trailing partial period
         "total": int,
         "partial_period": str | None,   # e.g. "2026-05" if the last bucket is still in progress
       }
    """
    crimes = _query_crimes(session, crime_type, district, victim_filter)
    buckets: dict[str, int] = defaultdict(int)
    for c in crimes:
        buckets[_bucket_key(c.timestamp, granularity)] += 1

    ordered_keys = sorted(buckets.keys())
    counts = [buckets[k] for k in ordered_keys]
    avgs = rolling_average(counts, window=rolling_window)

    partial_key = current_global_partial_period(session, granularity)
    is_last_partial = bool(ordered_keys) and ordered_keys[-1] == partial_key

    series = [
        {"period": k, "count": c, "rolling_avg": a, "partial": (k == partial_key)}
        for k, c, a in zip(ordered_keys, counts, avgs)
    ]

    return {
        "granularity": granularity,
        "crime_type": crime_type,
        "district": district,
        "series": series,
        "growth": growth_indicator(counts, partial_last=is_last_partial),
        "total": sum(counts),
        "partial_period": partial_key if is_last_partial else None,
    }


def year_over_year(session: Session, crime_type: Optional[str] = None,
                    district: Optional[str] = None, victim_filter: Optional[VictimFilter] = None) -> dict:
    """Month-by-month comparison of this year vs last year (calendar years,
    based on the latest crime timestamp on record — not wall-clock 'today',
    since fixture/demo data may not extend to the actual current date).

    -> {"current_year": int, "previous_year": int,
        "months": [{"month": int, "current": int, "previous": int, "pct_change": float}, ...],
        "current_year_total": int, "previous_year_total": int, "yoy_pct_change": float}
    """
    crimes = _query_crimes(session, crime_type, district, victim_filter)
    if not crimes:
        return {"current_year": None, "previous_year": None, "months": [],
                "current_year_total": 0, "previous_year_total": 0, "yoy_pct_change": 0.0}

    latest_year = max(c.timestamp.year for c in crimes)
    prev_year = latest_year - 1

    current_by_month: dict[int, int] = defaultdict(int)
    prev_by_month: dict[int, int] = defaultdict(int)
    for c in crimes:
        if c.timestamp.year == latest_year:
            current_by_month[c.timestamp.month] += 1
        elif c.timestamp.year == prev_year:
            prev_by_month[c.timestamp.month] += 1

    months = []
    for m in range(1, 13):
        cur, prev = current_by_month.get(m, 0), prev_by_month.get(m, 0)
        if prev == 0:
            pct = 100.0 if cur > 0 else 0.0
        else:
            pct = round((cur - prev) / prev * 100, 1)
        months.append({"month": m, "current": cur, "previous": prev, "pct_change": pct})

    cur_total, prev_total = sum(current_by_month.values()), sum(prev_by_month.values())
    yoy_pct = round((cur_total - prev_total) / prev_total * 100, 1) if prev_total else (100.0 if cur_total else 0.0)

    return {
        "current_year": latest_year, "previous_year": prev_year,
        "months": months,
        "current_year_total": cur_total, "previous_year_total": prev_total,
        "yoy_pct_change": yoy_pct,
    }


def crimes_by_type_distribution(session: Session, district: Optional[str] = None,
                                 victim_filter: Optional[VictimFilter] = None) -> dict:
    """Distribution across crime types, plus which types grew vs shrank
    over the most recent two COMPLETE months on record (an "emerging
    categories" signal — a full anomaly model lives in cluster_engine.py;
    this is the plain distribution + trend view for the type-breakdown
    chart). A still-in-progress current month is excluded from the
    comparison — see `current_global_partial_period` — so a category
    doesn't look "declining" just because the month isn't over yet.

    `type_growth` carries the actual percentage + confidence per type
    (e.g. "robbery, up 18%, confidence: high") — `emerging`/`declining`
    are kept as plain name lists for callers that just want the two sets.

    -> {"distribution": {type: count, ...},
        "emerging": [type, ...], "declining": [type, ...],
        "type_growth": [{"crime_type": str, "direction": str, "pct_change": float,
                          "current": int, "previous": int, "confidence": {...}}, ...],
        "excluded_partial_period": str | None}
    """
    crimes = _query_crimes(session, None, district, victim_filter)
    distribution: dict[str, int] = defaultdict(int)
    by_type_month: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in crimes:
        ctype = c.type.value if hasattr(c.type, "value") else str(c.type)
        distribution[ctype] += 1
        by_type_month[ctype][_bucket_key(c.timestamp, "month")] += 1

    partial_key = current_global_partial_period(session, "month")

    emerging, declining, type_growth = [], [], []
    for ctype, months in by_type_month.items():
        keys = sorted(months.keys())
        if partial_key and keys and keys[-1] == partial_key:
            keys = keys[:-1]
        if len(keys) < 2:
            continue
        prev, cur = months[keys[-2]], months[keys[-1]]
        pct = round((cur - prev) / prev * 100, 1) if prev else (100.0 if cur else 0.0)
        direction = "up" if cur > prev else "down" if cur < prev else "flat"
        confidence = _confidence_tier([months[k] for k in keys])
        type_growth.append({"crime_type": ctype, "direction": direction, "pct_change": pct,
                              "current": cur, "previous": prev, "confidence": confidence})
        if cur > prev:
            emerging.append(ctype)
        elif cur < prev:
            declining.append(ctype)

    type_growth.sort(key=lambda t: abs(t["pct_change"]), reverse=True)

    return {"distribution": dict(distribution), "emerging": emerging, "declining": declining,
            "type_growth": type_growth, "excluded_partial_period": partial_key}


def crimes_by_district(session: Session, crime_type: Optional[str] = None,
                        victim_filter: Optional[VictimFilter] = None) -> list[dict]:
    """Ranked district table — the geographic granularity actually
    available in the current schema (see module docstring)."""
    crimes = session.query(Crime).join(Location, Crime.location_id == Location.id)
    if crime_type:
        crimes = crimes.filter(Crime.type == crime_type)
    victim_ids = _victim_filtered_crime_ids(session, victim_filter)
    if victim_ids is not None:
        crimes = crimes.filter(Crime.id.in_(victim_ids))

    counts: dict[str, int] = defaultdict(int)
    for c in crimes.all():
        counts[c.location.district] += 1

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return [{"district": d, "count": n} for d, n in ranked]
