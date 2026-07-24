"""
SHERLOCK — Repeat Crime Alert Engine (Forecasting & Early Warning Engine,
Requirement 8).

Deterministic threshold-based repeat-pattern detection — distinct from
`anomaly_engine.py`'s statistical (z-score) anomaly detection. This
module answers "has X happened here/to them/this way again and again",
not "is this month unusual". Everything below is a direct count against
recorded data within a stated rolling window; nothing is estimated.

Detects repeats across, per the brief:
    - locations       (same specific Location, not just district)
    - accused         (same person, >= N distinct FIRs)
    - modus operandi   (same MO text + district)
    - victim groups    (same victim gender + age-bracket + district)
    - crime types      (same crime type + district, occurrence threshold)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from backend.database.models import Accused, Crime, FIR, Location, Person, Victim
from backend.forecasting.trend_forecaster import reference_now

DEFAULT_WINDOW_DAYS = 28


def _bracket(age: int) -> str:
    for lo, hi, label in ((0, 18, "under 18"), (18, 25, "18-24"), (25, 35, "25-34"), (35, 50, "35-49"), (50, 200, "50+")):
        if lo <= age < hi:
            return label
    return "unknown"


def _severity(count: int, thresholds=(3, 5, 8)) -> str:
    low, med, high = thresholds
    if count >= high:
        return "Critical"
    if count >= med:
        return "High"
    if count >= low:
        return "Medium"
    return "Low"


class RepeatAlertEngine:
    def __init__(self, session):
        self.session = session

    def _crimes_in_window(self, window_days: int):
        cutoff = reference_now(self.session) - timedelta(days=window_days)
        return (
            self.session.query(Crime)
            .filter(Crime.timestamp >= cutoff)
            .all()
        )

    def detect_repeat_locations(self, window_days: int = DEFAULT_WINDOW_DAYS, min_occurrences: int = 3) -> list[dict]:
        crimes = self._crimes_in_window(window_days)
        by_location = defaultdict(list)
        for c in crimes:
            if c.location:
                by_location[c.location].append(c)

        alerts = []
        for location, group in by_location.items():
            if len(group) < min_occurrences:
                continue
            crime_types = sorted({c.type.value for c in group})
            alerts.append({
                "alert": f"Repeat Crime at {location.name}",
                "severity": _severity(len(group)),
                "location": location.name,
                "district": location.district,
                "occurrences": len(group),
                "window_days": window_days,
                "crime_types": crime_types,
                "recommendation": f"Increase patrol presence at {location.name} ({location.district}) — {len(group)} incident(s) in {window_days} days.",
            })
        alerts.sort(key=lambda a: a["occurrences"], reverse=True)
        return alerts

    def detect_repeat_accused(self, min_crimes: int = 2) -> list[dict]:
        rows = self.session.query(Accused.person_id, Accused.fir_id).all()
        fir_ids_by_person = defaultdict(set)
        for person_id, fir_id in rows:
            fir_ids_by_person[person_id].add(fir_id)

        repeat_ids = {pid: len(firs) for pid, firs in fir_ids_by_person.items() if len(firs) >= min_crimes}
        if not repeat_ids:
            return []

        persons = self.session.query(Person).filter(Person.id.in_(repeat_ids)).all()
        alerts = []
        for person in persons:
            count = repeat_ids[person.id]
            alerts.append({
                "alert": f"Repeat Offender: {person.name}",
                "severity": _severity(count, thresholds=(2, 4, 6)),
                "person_id": person.id,
                "name": person.name,
                "occurrences": count,
                "window_days": None,  # lifetime count, not windowed
                "recommendation": f"Prioritize case review for {person.name} — accused in {count} distinct FIR(s).",
            })
        alerts.sort(key=lambda a: a["occurrences"], reverse=True)
        return alerts

    def detect_repeat_mo(self, window_days: int = 60, min_occurrences: int = 3) -> list[dict]:
        crimes = self._crimes_in_window(window_days)
        by_mo_district = defaultdict(list)
        for c in crimes:
            if c.modus_operandi and c.location:
                by_mo_district[(c.modus_operandi, c.location.district)].append(c)

        alerts = []
        for (mo, district), group in by_mo_district.items():
            if len(group) < min_occurrences:
                continue
            alerts.append({
                "alert": f"Repeat MO Pattern: {mo}",
                "severity": _severity(len(group)),
                "modus_operandi": mo,
                "district": district,
                "occurrences": len(group),
                "window_days": window_days,
                "recommendation": f"Cross-reference open cases in {district} matching MO '{mo}' — possible serial pattern.",
            })
        alerts.sort(key=lambda a: a["occurrences"], reverse=True)
        return alerts

    def detect_repeat_victim_groups(self, window_days: int = 60, min_occurrences: int = 3) -> list[dict]:
        cutoff = reference_now(self.session) - timedelta(days=window_days)
        rows = (
            self.session.query(Victim, Person, Crime, Location)
            .join(Person, Person.id == Victim.person_id)
            .join(FIR, FIR.id == Victim.fir_id)
            .join(Crime, Crime.id == FIR.crime_id)
            .join(Location, Location.id == Crime.location_id)
            .filter(Crime.timestamp >= cutoff)
            .all()
        )

        by_group = defaultdict(list)
        for victim, person, crime, location in rows:
            key = (person.gender.value, _bracket(person.age), location.district)
            by_group[key].append(crime)

        alerts = []
        for (gender, bracket, district), group in by_group.items():
            if len(group) < min_occurrences:
                continue
            alerts.append({
                "alert": f"Repeat Victim Profile: {gender}, {bracket} in {district}",
                "severity": _severity(len(group)),
                "victim_gender": gender,
                "victim_age_bracket": bracket,
                "district": district,
                "occurrences": len(group),
                "window_days": window_days,
                "recommendation": f"Consider targeted community outreach/awareness for {gender} victims aged {bracket} in {district}.",
            })
        alerts.sort(key=lambda a: a["occurrences"], reverse=True)
        return alerts

    def detect_repeat_crime_types(self, window_days: int = 30, min_occurrences: int = 5) -> list[dict]:
        crimes = self._crimes_in_window(window_days)
        by_type_district = defaultdict(list)
        for c in crimes:
            if c.location:
                by_type_district[(c.type.value, c.location.district)].append(c)

        alerts = []
        for (ctype, district), group in by_type_district.items():
            if len(group) < min_occurrences:
                continue
            alerts.append({
                "alert": f"Repeat {ctype.replace('_', ' ').title()} Cluster",
                "severity": _severity(len(group), thresholds=(5, 8, 12)),
                "crime_type": ctype,
                "district": district,
                "occurrences": len(group),
                "window_days": window_days,
                "recommendation": f"{district} has recorded {len(group)} {ctype.replace('_', ' ')} case(s) in {window_days} days — consider a targeted response.",
            })
        alerts.sort(key=lambda a: a["occurrences"], reverse=True)
        return alerts

    def generate_alerts(self, window_days: int = DEFAULT_WINDOW_DAYS) -> dict:
        return {
            "repeat_locations": self.detect_repeat_locations(window_days=window_days),
            "repeat_accused": self.detect_repeat_accused(),
            "repeat_mo": self.detect_repeat_mo(),
            "repeat_victim_groups": self.detect_repeat_victim_groups(),
            "repeat_crime_types": self.detect_repeat_crime_types(),
        }
