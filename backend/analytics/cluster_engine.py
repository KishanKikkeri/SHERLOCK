"""
SHERLOCK — Cluster Engine (Crime Pattern & Trend Analytics Agent).

"Emerging Crime Clusters" from the brief: sudden spikes, new crime
categories, repeat incidents, localized outbreaks — all via rolling
historical baselines, not a fixed hardcoded threshold. Reuses
trend_engine's bucketing so a "period" means the same thing across
every engine in this package.

Baseline method: trailing mean + population stdev over the N periods
*before* the one being tested (never including the tested period
itself, or a real spike would inflate its own baseline). z-score =
(current - trailing_mean) / trailing_stdev. When trailing_stdev is 0
(a flat history — e.g. always exactly 2/month, or always 0), a spike
is instead flagged by absolute delta vs that flat baseline, since a
z-score is undefined on zero variance.

Default threshold (z >= 2.0) is a starting point, not a validated
statistical choice for this domain — flagged here rather than presented
as tuned.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from backend.database.models import Crime, Location
from backend.analytics.trend_engine import (
    _bucket_key, _query_crimes, current_global_partial_period, VictimFilter, _victim_filtered_crime_ids,
)


def _drop_trailing_partial(ordered_keys: list[str], counts: list[int], partial_key: Optional[str]) -> tuple[list[str], list[int]]:
    """Drop the trailing bucket if it's the dataset's in-progress period
    (see trend_engine.current_global_partial_period) — an anomaly test
    run against a period that hasn't finished yet is testing incomplete
    data, which can produce a false negative (masks a real spike) just as
    easily as a false positive.
    """
    if partial_key and ordered_keys and ordered_keys[-1] == partial_key:
        return ordered_keys[:-1], counts[:-1]
    return ordered_keys, counts


def _zscore_flag(series: list[int], baseline_periods: int, z_threshold: float) -> Optional[dict]:
    """Test only the LAST point in `series` against the trailing
    `baseline_periods` before it. Returns None if there isn't enough
    history to form a baseline, or if the last point isn't anomalous.
    """
    if len(series) < baseline_periods + 1:
        return None

    baseline = series[-(baseline_periods + 1):-1]
    current = series[-1]
    mean = statistics.mean(baseline)
    stdev = statistics.pstdev(baseline)

    if stdev == 0:
        if current > mean:
            delta = current - mean
            if delta >= max(2, mean):  # at least double a nonzero baseline, or +2 over a zero baseline
                return {"z_score": None, "method": "flat_baseline_delta", "baseline_mean": mean,
                         "current": current, "delta": delta, "expected": round(mean, 2), "observed": current}
            return None
        return None

    z = (current - mean) / stdev
    if z >= z_threshold:
        return {"z_score": round(z, 2), "method": "zscore", "baseline_mean": round(mean, 2),
                "baseline_stdev": round(stdev, 2), "current": current,
                "expected": round(mean, 2), "observed": current}
    return None


def spike_detection(session: Session, granularity: str = "month",
                     crime_type: Optional[str] = None, district: Optional[str] = None,
                     baseline_periods: int = 6, z_threshold: float = 2.0,
                     victim_filter: Optional[VictimFilter] = None) -> list[dict]:
    """Flag a sudden spike in the most recent period vs. the trailing
    baseline, per crime type (all types if `crime_type` is None).
    -> [{"crime_type": str, "period": str, **_zscore_flag output}, ...]
    """
    crimes = _query_crimes(session, crime_type, district, victim_filter)
    by_type: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in crimes:
        ctype = c.type.value if hasattr(c.type, "value") else str(c.type)
        by_type[ctype][_bucket_key(c.timestamp, granularity)] += 1

    partial_key = current_global_partial_period(session, granularity)

    flags = []
    for ctype, buckets in by_type.items():
        ordered_keys = sorted(buckets.keys())
        counts = [buckets[k] for k in ordered_keys]
        ordered_keys, counts = _drop_trailing_partial(ordered_keys, counts, partial_key)
        flag = _zscore_flag(counts, baseline_periods, z_threshold)
        if flag:
            flags.append({"crime_type": ctype, "period": ordered_keys[-1], **flag})
    return flags


def localized_outbreaks(session: Session, granularity: str = "month",
                         crime_type: Optional[str] = None,
                         baseline_periods: int = 6, z_threshold: float = 2.0,
                         victim_filter: Optional[VictimFilter] = None) -> list[dict]:
    """Same z-score test as spike_detection, but grouped by district
    instead of crime type — a spike concentrated in one place rather
    than one category. -> [{"district": str, "period": str, **flag}, ...]
    """
    q = session.query(Crime).join(Location, Crime.location_id == Location.id)
    if crime_type:
        q = q.filter(Crime.type == crime_type)
    victim_ids = _victim_filtered_crime_ids(session, victim_filter)
    if victim_ids is not None:
        q = q.filter(Crime.id.in_(victim_ids))

    by_district: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for c in q.all():
        by_district[c.location.district][_bucket_key(c.timestamp, granularity)] += 1

    partial_key = current_global_partial_period(session, granularity)

    flags = []
    for district, buckets in by_district.items():
        ordered_keys = sorted(buckets.keys())
        counts = [buckets[k] for k in ordered_keys]
        ordered_keys, counts = _drop_trailing_partial(ordered_keys, counts, partial_key)
        flag = _zscore_flag(counts, baseline_periods, z_threshold)
        if flag:
            flags.append({"district": district, "period": ordered_keys[-1], **flag})
    return flags


def emerging_categories(session: Session, granularity: str = "month",
                         recency_periods: int = 3) -> list[dict]:
    """Crime types whose EARLIEST record on file falls within the most
    recent `recency_periods` buckets — a genuinely new category showing
    up in the data, not just a category that happens to be growing
    (that's `trend_engine.crimes_by_type_distribution`'s "emerging" list,
    which is month-over-month direction on categories that already
    existed). This is stricter: first-ever appearance, recently.
    -> [{"crime_type": str, "first_seen_period": str, "count_since_first_seen": int}, ...]
    """
    crimes = session.query(Crime).all()
    if not crimes:
        return []

    by_type_first_seen: dict[str, str] = {}
    by_type_counts: dict[str, int] = defaultdict(int)
    all_periods = set()
    for c in crimes:
        ctype = c.type.value if hasattr(c.type, "value") else str(c.type)
        period = _bucket_key(c.timestamp, granularity)
        all_periods.add(period)
        by_type_counts[ctype] += 1
        if ctype not in by_type_first_seen or period < by_type_first_seen[ctype]:
            by_type_first_seen[ctype] = period

    ordered_periods = sorted(all_periods)
    recent_cutoff_periods = set(ordered_periods[-recency_periods:]) if len(ordered_periods) >= recency_periods else set(ordered_periods)

    return [
        {"crime_type": ctype, "first_seen_period": first_seen, "count_since_first_seen": by_type_counts[ctype]}
        for ctype, first_seen in by_type_first_seen.items()
        if first_seen in recent_cutoff_periods
    ]


def repeat_incident_clusters(session: Session, crime_type: Optional[str] = None,
                              window_days: int = 30, min_occurrences: int = 3) -> list[dict]:
    """Same location + same crime type recurring `min_occurrences`+ times
    within any `window_days`-day rolling window — flags a single site
    being hit repeatedly (e.g. a shop targeted three times in a month),
    distinct from a district-wide outbreak.
    -> [{"location": str, "district": str, "crime_type": str,
         "occurrences": int, "window_start": str, "window_end": str}, ...]
    """
    q = session.query(Crime).join(Location, Crime.location_id == Location.id)
    if crime_type:
        q = q.filter(Crime.type == crime_type)

    by_site: dict[tuple, list] = defaultdict(list)
    for c in q.all():
        ctype = c.type.value if hasattr(c.type, "value") else str(c.type)
        by_site[(c.location_id, ctype)].append(c.timestamp)

    clusters = []
    for (location_id, ctype), timestamps in by_site.items():
        timestamps.sort()
        for i, start_ts in enumerate(timestamps):
            window_end = start_ts + timedelta(days=window_days)
            in_window = [t for t in timestamps[i:] if t <= window_end]
            if len(in_window) >= min_occurrences:
                loc = session.query(Location).get(location_id)
                clusters.append({
                    "location": loc.name, "district": loc.district, "crime_type": ctype,
                    "occurrences": len(in_window),
                    "window_start": start_ts.strftime("%Y-%m-%d"),
                    "window_end": in_window[-1].strftime("%Y-%m-%d"),
                })
                break  # one flag per site/type is enough; don't re-flag overlapping sub-windows

    clusters.sort(key=lambda c: c["occurrences"], reverse=True)
    return clusters
