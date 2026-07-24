"""
SHERLOCK — Modus Operandi Engine (Crime Pattern & Trend Analytics Agent).

Schema reality (see trend_engine.py's module docstring for the same
convention): there is no structured MO taxonomy in the database.
`Crime.modus_operandi` is a single free-text `String` — no separate
"entry method" / "scam pattern" / "digital attack vector" fields to
query. Everything here that reports those categories is doing
keyword/phrase frequency mining over that free text, not querying a
classified field. It's a first pass, not a classifier — if MO gets a
structured schema later (e.g. an `mo_tags` table), swap the mining
functions below for real filters and this module gets much simpler
and much more accurate.

Weapon and Vehicle ARE structured (Weapon.weapon_type, a real enum;
Vehicle.vehicle_type, a string), but linked to a Crime only indirectly:
Crime -> FIR (1:1) -> Weapon/Vehicle (via `used_in_fir_id`). Every
weapon/vehicle function here goes through that FIR hop.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Optional

from sqlalchemy.orm import Session

from backend.database.models import Crime, FIR, Weapon, Vehicle, Victim, Person
from backend.analytics.trend_engine import _bucket_key, _query_crimes, VictimFilter, _victim_filtered_crime_ids

# Minimal stopword list — enough to keep frequency counts from being
# dominated by function words, not a full NLP pipeline.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "at", "with", "from",
    "was", "were", "is", "are", "by", "for", "into", "through", "using", "used",
    "then", "after", "before", "his", "her", "their", "victim", "victims",
}

_TOKEN_RE = re.compile(r"[a-zA-Z]{3,}")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS]


def top_modus_operandi(session: Session, crime_type: Optional[str] = None,
                        district: Optional[str] = None, top_n: int = 15,
                        victim_filter: Optional[VictimFilter] = None) -> list[dict]:
    """Keyword frequency across every `modus_operandi` string in scope.
    -> [{"keyword": str, "count": int}, ...] sorted by count desc.

    This is a bag-of-words count, not phrase extraction — "broke window
    at night" contributes "broke", "window", "night" as three separate
    hits, not one phrase. Good enough to surface a dominant MO signal
    ("forced", "phishing", "impersonation" spiking) without needing an
    NLP dependency; not a substitute for a real classifier.
    """
    crimes = _query_crimes(session, crime_type, district, victim_filter)
    counter = Counter()
    for c in crimes:
        counter.update(_tokenize(c.modus_operandi))
    return [{"keyword": kw, "count": n} for kw, n in counter.most_common(top_n)]


def mo_pattern_evolution(session: Session, crime_type: Optional[str] = None,
                          granularity: str = "month", top_n_per_period: int = 5) -> list[dict]:
    """Top MO keywords per time period, so a dashboard can show how the
    dominant MO language shifts over time (e.g. "phishing" overtaking
    "skimming" quarter over quarter).
    -> [{"period": str, "top_keywords": [{"keyword": str, "count": int}, ...]}, ...]
       chronological.
    """
    crimes = _query_crimes(session, crime_type, None)
    by_period: dict[str, Counter] = defaultdict(Counter)
    for c in crimes:
        period = _bucket_key(c.timestamp, granularity)
        by_period[period].update(_tokenize(c.modus_operandi))

    return [
        {"period": period, "top_keywords": [{"keyword": kw, "count": n} for kw, n in counter.most_common(top_n_per_period)]}
        for period, counter in sorted(by_period.items())
    ]


def weapon_usage(session: Session, crime_type: Optional[str] = None) -> list[dict]:
    """Weapon type distribution across crimes that have an FIR with a
    linked weapon. -> [{"weapon_type": str, "count": int}, ...] desc.
    """
    q = session.query(Weapon).join(FIR, Weapon.used_in_fir_id == FIR.id).join(Crime, FIR.crime_id == Crime.id)
    if crime_type:
        q = q.filter(Crime.type == crime_type)

    counter = Counter()
    for w in q.all():
        wtype = w.weapon_type.value if hasattr(w.weapon_type, "value") else str(w.weapon_type)
        counter[wtype] += 1
    return [{"weapon_type": wt, "count": n} for wt, n in counter.most_common()]


def vehicle_usage(session: Session, crime_type: Optional[str] = None) -> list[dict]:
    """Vehicle type distribution across crimes that have an FIR with a
    linked vehicle. -> [{"vehicle_type": str, "count": int}, ...] desc.
    """
    q = session.query(Vehicle).join(FIR, Vehicle.used_in_fir_id == FIR.id).join(Crime, FIR.crime_id == Crime.id)
    if crime_type:
        q = q.filter(Crime.type == crime_type)

    counter = Counter()
    for v in q.all():
        counter[v.vehicle_type] += 1
    return [{"vehicle_type": vt, "count": n} for vt, n in counter.most_common()]


def similar_cases(session: Session, crime_id: int, top_n: int = 5,
                   require_same_type: bool = True) -> list[dict]:
    """Rank other crimes by MO text similarity to `crime_id` (Jaccard
    similarity over tokenized `modus_operandi`), optionally restricted to
    the same crime type. A same-type, high-token-overlap match is the
    "similar case" signal the brief asks for — a real embedding-based
    similarity would do better, but that's a model dependency this
    engine deliberately doesn't take on.
    -> [{"crime_id": int, "similarity": float, "modus_operandi": str}, ...] desc.
    """
    target = session.query(Crime).get(crime_id)
    if target is None or not target.modus_operandi:
        return []

    target_tokens = set(_tokenize(target.modus_operandi))
    if not target_tokens:
        return []

    q = session.query(Crime).filter(Crime.id != crime_id)
    if require_same_type:
        q = q.filter(Crime.type == target.type)

    scored = []
    for c in q.all():
        if not c.modus_operandi:
            continue
        tokens = set(_tokenize(c.modus_operandi))
        if not tokens:
            continue
        overlap = target_tokens & tokens
        union = target_tokens | tokens
        similarity = len(overlap) / len(union) if union else 0.0
        if similarity > 0:
            scored.append({"crime_id": c.id, "similarity": round(similarity, 3), "modus_operandi": c.modus_operandi})

    scored.sort(key=lambda s: s["similarity"], reverse=True)
    return scored[:top_n]


def _age_band(age: int) -> str:
    """Coarse age bands for victim-demographic reporting. Fixed cutoffs,
    not derived from the data — adequate for a "common victim" summary
    line, not a substitute for a real cohort analysis."""
    if age < 18:
        return "under 18"
    if age <= 30:
        return "18-30"
    if age <= 45:
        return "31-45"
    if age <= 60:
        return "46-60"
    return "60+"


def mo_enrichment_summary(session: Session, crime_type: Optional[str] = None,
                           district: Optional[str] = None) -> dict:
    """The richer "feels intelligent" MO summary: top weapon/vehicle with
    real percentages (not just raw counts — see weapon_usage/vehicle_usage
    above), a peak-hour window, and common victim demographics. Two things
    this deliberately does NOT invent, per the same "don't fake it"
    convention as the rest of this package:

    - "Preferred escape route" — there's no route/direction field
      anywhere in the schema (Crime, FIR, Location all lack one). Rather
      than guess from MO free text, this key is always None with an
      explicit `available: False` note.
    - Peak hour is computed for real from `Crime.timestamp`'s hour
      component, which the schema supports — but the current synthetic
      fixture data (`generate_synthetic_data.py`) sets every crime's
      timestamp to midnight (no time-of-day randomization). So on today's
      demo dataset every "peak hour" would read as 00:00, which is a
      fixture artifact, not a real finding. `peak_hour_data_quality` flags
      this explicitly instead of presenting a fake-precise peak.

    -> {"top_weapon": {"weapon_type": str, "pct": float} | None,
        "top_vehicle": {"vehicle_type": str, "pct": float} | None,
        "peak_hour_window": {"start_hour": int, "end_hour": int, "share": float} | None,
        "peak_hour_data_quality": str | None,  # set only when timestamps lack real hour variation
        "common_victim": {"gender": str, "age_band": str, "pct": float} | None,
        "preferred_escape_route": None, "preferred_escape_route_available": False}
    """
    weapons = weapon_usage(session, crime_type)
    vehicles = vehicle_usage(session, crime_type)
    weapon_total = sum(w["count"] for w in weapons)
    vehicle_total = sum(v["count"] for v in vehicles)

    top_weapon = None
    if weapons and weapon_total:
        top_weapon = {"weapon_type": weapons[0]["weapon_type"], "pct": round(weapons[0]["count"] / weapon_total * 100, 1)}

    top_vehicle = None
    if vehicles and vehicle_total:
        top_vehicle = {"vehicle_type": vehicles[0]["vehicle_type"], "pct": round(vehicles[0]["count"] / vehicle_total * 100, 1)}

    # Peak hour: sliding 4-hour circular window over hour-of-day counts.
    crimes = _query_crimes(session, crime_type, district)
    hour_counts = [0] * 24
    for c in crimes:
        hour_counts[c.timestamp.hour] += 1
    total_crimes = sum(hour_counts)

    peak_hour_window = None
    peak_hour_data_quality = None
    if total_crimes:
        distinct_hours_used = sum(1 for h in hour_counts if h > 0)
        if distinct_hours_used <= 1:
            peak_hour_data_quality = (
                "All crime timestamps in scope share the same hour-of-day — the current fixture data "
                "(generate_synthetic_data.py) doesn't randomize time-of-day, so this isn't a real pattern yet."
            )
        else:
            best_start, best_sum = 0, -1
            for start in range(24):
                window_sum = sum(hour_counts[(start + i) % 24] for i in range(4))
                if window_sum > best_sum:
                    best_start, best_sum = start, window_sum
            peak_hour_window = {
                "start_hour": best_start, "end_hour": (best_start + 4) % 24,
                "share": round(best_sum / total_crimes, 3),
            }

    # Common victim demographics: Crime -> FIR -> Victim -> Person.
    victim_q = (
        session.query(Person.gender, Person.age)
        .join(Victim, Victim.person_id == Person.id)
        .join(FIR, Victim.fir_id == FIR.id)
        .join(Crime, FIR.crime_id == Crime.id)
    )
    if crime_type:
        victim_q = victim_q.filter(Crime.type == crime_type)
    victim_rows = victim_q.all()

    common_victim = None
    if victim_rows:
        demo_counter = Counter()
        for gender, age in victim_rows:
            gender_val = gender.value if hasattr(gender, "value") else str(gender)
            demo_counter[(gender_val, _age_band(age))] += 1
        (top_gender, top_band), top_count = demo_counter.most_common(1)[0]
        common_victim = {"gender": top_gender, "age_band": top_band, "pct": round(top_count / len(victim_rows) * 100, 1)}

    return {
        "top_weapon": top_weapon,
        "top_vehicle": top_vehicle,
        "peak_hour_window": peak_hour_window,
        "peak_hour_data_quality": peak_hour_data_quality,
        "common_victim": common_victim,
        "preferred_escape_route": None,
        "preferred_escape_route_available": False,
    }
