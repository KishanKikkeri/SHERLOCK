"""
SHERLOCK — Seasonal Engine (Crime Pattern & Trend Analytics Agent).

Generalizes the festival-season logic that already exists inline in
`backend/agents/pattern_analysis/agent.py` (`FESTIVAL_MONTHS = {9, 10, 11}`,
>=50% festival-share + >=5 cases heuristic) into a reusable module,
rather than a second hardcoded copy. That agent can be pointed at
`FESTIVAL_MONTHS` / `festival_season_concentration()` here in a later
cleanup pass — not changed in this commit, to avoid touching agent
behavior as a side effect of adding this engine.

Two dataset gaps, same convention as the other engines in this package:

1. Meteorological seasons (summer/monsoon/winter) are hardcoded by
   calendar month below for the northern-India climate pattern. This is
   a coarse default, not location-aware — Karnataka's actual monsoon
   timing, for instance, differs somewhat from the north. If per-state
   season calendars matter, this needs a state -> season-months lookup,
   which doesn't exist yet.
2. "Festivals / holidays" beyond the Sep-Nov festival-season heuristic
   (specific dates like Diwali, Eid, Independence Day) have no dataset
   in this schema at all. `HOLIDAY_CALENDAR` below is the plug-in point
   — empty until real dates are supplied — matching the same
   "unavailable now, wire in later" pattern used for event-based
   analysis in the brief.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from backend.database.models import Crime, Location
from backend.analytics.trend_engine import _query_crimes, VictimFilter, _victim_filtered_crime_ids

# Coarse calendar-month seasons — see module docstring gap #1.
SEASON_MONTHS = {
    "summer": {3, 4, 5},
    "monsoon": {6, 7, 8, 9},
    "winter": {10, 11, 12, 1, 2},
}

# Matches the existing PatternAnalysisAgent heuristic — see module docstring.
FESTIVAL_MONTHS = {9, 10, 11}

# Plug-in point — see module docstring gap #2. Populate with real dates,
# e.g. {"diwali": [date(2025, 10, 20)], "eid": [date(2025, 3, 31)]}, to
# activate `crimes_near_holidays`.
HOLIDAY_CALENDAR: dict[str, list[date]] = {}


def season_of(ts: datetime) -> str:
    for season, months in SEASON_MONTHS.items():
        if ts.month in months:
            return season
    return "unknown"  # unreachable given SEASON_MONTHS covers all 12 months, kept defensive


def seasonal_distribution(session: Session, crime_type: Optional[str] = None,
                           district: Optional[str] = None,
                           victim_filter: Optional[VictimFilter] = None) -> dict:
    """Crime counts by meteorological season.
    -> {"distribution": {"summer": int, "monsoon": int, "winter": int},
        "dominant_season": str, "dominant_share": float}
    """
    crimes = _query_crimes(session, crime_type, district, victim_filter)
    counts: dict[str, int] = defaultdict(int)
    for c in crimes:
        counts[season_of(c.timestamp)] += 1

    total = sum(counts.values())
    if total == 0:
        return {"distribution": dict(counts), "dominant_season": None, "dominant_share": 0.0}

    dominant_season, dominant_count = max(counts.items(), key=lambda kv: kv[1])
    return {
        "distribution": dict(counts),
        "dominant_season": dominant_season,
        "dominant_share": round(dominant_count / total, 3),
    }


def weekend_vs_weekday(session: Session, crime_type: Optional[str] = None,
                        district: Optional[str] = None,
                        victim_filter: Optional[VictimFilter] = None) -> dict:
    """Raw counts AND a per-day-of-week average rate — raw counts alone
    would understate weekends (5 weekdays vs. 2 weekend days per week),
    so both are returned and the rate is what should drive any "crime
    spikes on weekends" claim.
    -> {"weekend_total": int, "weekday_total": int,
        "weekend_avg_per_day": float, "weekday_avg_per_day": float,
        "distinct_weekend_days": int, "distinct_weekday_days": int}
    """
    crimes = _query_crimes(session, crime_type, district, victim_filter)
    weekend_days, weekday_days = set(), set()
    weekend_total = weekday_total = 0
    for c in crimes:
        day_key = c.timestamp.date()
        if c.timestamp.weekday() >= 5:  # Sat=5, Sun=6
            weekend_total += 1
            weekend_days.add(day_key)
        else:
            weekday_total += 1
            weekday_days.add(day_key)

    return {
        "weekend_total": weekend_total,
        "weekday_total": weekday_total,
        "weekend_avg_per_day": round(weekend_total / len(weekend_days), 2) if weekend_days else 0.0,
        "weekday_avg_per_day": round(weekday_total / len(weekday_days), 2) if weekday_days else 0.0,
        "distinct_weekend_days": len(weekend_days),
        "distinct_weekday_days": len(weekday_days),
    }


def festival_season_concentration(session: Session, crime_type: Optional[str] = None,
                                   festival_months: set[int] = FESTIVAL_MONTHS,
                                   min_festival_cases: int = 5,
                                   share_threshold: float = 0.5,
                                   victim_filter: Optional[VictimFilter] = None) -> list[dict]:
    """Per-district festival-season share, generalized from the inline
    version in PatternAnalysisAgent (same thresholds by default: >=50%
    share and >=5 festival-season cases to flag a district).
    -> [{"district": str, "festival_count": int, "total": int,
         "festival_share": float, "flagged": bool}, ...] desc by share.
    """
    query = session.query(Crime).join(Location, Crime.location_id == Location.id)
    if crime_type:
        query = query.filter(Crime.type == crime_type)
    victim_ids = _victim_filtered_crime_ids(session, victim_filter)
    if victim_ids is not None:
        query = query.filter(Crime.id.in_(victim_ids))

    by_district: dict[str, dict] = defaultdict(lambda: {"festival": 0, "total": 0})
    for c in query.all():
        entry = by_district[c.location.district]
        entry["total"] += 1
        if c.timestamp.month in festival_months:
            entry["festival"] += 1

    results = []
    for district, agg in by_district.items():
        share = agg["festival"] / agg["total"] if agg["total"] else 0.0
        results.append({
            "district": district, "festival_count": agg["festival"], "total": agg["total"],
            "festival_share": round(share, 3),
            "flagged": share >= share_threshold and agg["festival"] >= min_festival_cases,
        })

    results.sort(key=lambda r: r["festival_share"], reverse=True)
    return results


def crimes_near_holidays(session: Session, window_days: int = 2,
                          crime_type: Optional[str] = None) -> list[dict]:
    """Crime counts within `window_days` of each configured holiday date.
    Returns an empty list (not an error) while `HOLIDAY_CALENDAR` is
    unpopulated — see module docstring gap #2. This is the plug-in point
    for "Event-based Analysis" (elections, festivals with real dates,
    public gatherings) once a dataset is wired in.
    -> [{"holiday": str, "date": str, "count": int}, ...]
    """
    if not HOLIDAY_CALENDAR:
        return []

    crimes = _query_crimes(session, crime_type, None)
    results = []
    for holiday_name, dates in HOLIDAY_CALENDAR.items():
        for d in dates:
            count = sum(1 for c in crimes if abs((c.timestamp.date() - d).days) <= window_days)
            results.append({"holiday": holiday_name, "date": d.isoformat(), "count": count})
    return results
