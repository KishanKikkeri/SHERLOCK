"""
SHERLOCK — Stage G1: behaviour profiling.

Reuses `backend.agents.behavioral_intelligence.agent.VIOLENCE_WEIGHTS`
rather than redefining a second severity table — that agent already
made the judgment call on relative crime severity for the investigation
pipeline's escalation/violence signals (Sprint B4), and a person's
severity ladder should read the same way whether it's surfaced through a
live investigation finding or this standalone profile. Everything below
that (aggression, planning, mobility, target selection, time-of-crime)
is new — Sprint B4's agent didn't compute these.

Every sub-score is a stated 0-100 heuristic, not a learned/calibrated
model — same discipline as behavioral_intelligence/agent.py.
"""

from __future__ import annotations

import math
from collections import Counter

from backend.agents.behavioral_intelligence.agent import VIOLENCE_WEIGHTS
from backend.database.models import BankAccount, PersonAlias, Vehicle, Weapon

# Derived directly from VIOLENCE_WEIGHTS (Sprint B4's own severity
# judgment call), sorted low -> high, rather than a second hand-picked
# ladder — so "did this person's crimes get worse over time" reads
# against the same severity ordering the investigation pipeline already
# uses for escalation/violence, not a competing definition.
SEVERITY_ORDER = sorted(VIOLENCE_WEIGHTS, key=lambda crime_type: VIOLENCE_WEIGHTS[crime_type])

VIOLENT_TYPES = {"assault", "drug_trafficking"}


def compute_behavior_profile(session, person_id: int, history: dict) -> dict:
    crimes = sorted(history["_crimes"], key=lambda c: c.timestamp)
    firs = history["_firs"]
    fir_ids = [f.id for f in firs]

    return {
        "escalation": _escalation(crimes),
        "aggression": _aggression(session, person_id, crimes, fir_ids),
        "planning": _planning(session, person_id, firs),
        "mobility": _mobility(crimes),
        "target_selection": _target_selection(firs),
        "time_profile": _time_profile(crimes),
    }


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------

def _escalation(crimes) -> dict:
    if len(crimes) < 2:
        return {
            "ladder": [c.type.value for c in crimes],
            "score": 0,
            "trend": "insufficient_history",
            "because": "Fewer than 2 offences on record — no trend can be computed.",
        }

    severities = [
        SEVERITY_ORDER.index(c.type.value) if c.type.value in SEVERITY_ORDER else 0
        for c in crimes
    ]
    # Trend = fraction of consecutive steps that increase in severity,
    # same "shrinking-gap" style ratio behavioral_intelligence/agent.py
    # uses for its own escalation score, applied to severity instead of
    # time-gap.
    increasing_steps = sum(1 for i in range(len(severities) - 1) if severities[i + 1] > severities[i])
    steps = len(severities) - 1
    score = round(increasing_steps / steps * 100) if steps else 0

    if score >= 60:
        trend = "escalating"
    elif score <= 20:
        trend = "stable_or_declining"
    else:
        trend = "mixed"

    return {
        "ladder": [c.type.value for c in crimes],
        "score": score,
        "trend": trend,
        "because": (
            f"{increasing_steps} of {steps} offence-to-offence transitions moved to a more "
            f"severe crime category (severity order: {' < '.join(SEVERITY_ORDER)})."
        ),
    }


# ---------------------------------------------------------------------------
# Aggression
# ---------------------------------------------------------------------------

def _aggression(session, person_id: int, crimes, fir_ids: list[int]) -> dict:
    violent_crimes = [c for c in crimes if c.type.value in VIOLENT_TYPES]
    weapons_used = (
        session.query(Weapon).filter(Weapon.used_in_fir_id.in_(fir_ids)).all() if fir_ids else []
    )
    weapons_recovered_from_person = (
        session.query(Weapon).filter_by(recovered_from_person_id=person_id).all()
    )

    if not crimes:
        score = 0
    else:
        violence_ratio = len(violent_crimes) / len(crimes)
        weapon_component = min(len(weapons_used) * 15, 40)
        score = min(round(violence_ratio * 60) + weapon_component, 100)

    return {
        "score": score,
        "violent_offence_count": len(violent_crimes),
        "weapon_incidents": len(weapons_used),
        "weapons_recovered_from_person": len(weapons_recovered_from_person),
        "weapon_types": sorted({w.weapon_type.value for w in weapons_used}),
        "because": (
            f"{len(violent_crimes)} of {len(crimes)} offence(s) were assault/drug-trafficking "
            f"type, with {len(weapons_used)} weapon(s) on record for those FIRs."
        ),
    }


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

def _planning(session, person_id: int, firs) -> dict:
    alias_count = session.query(PersonAlias).filter_by(person_id=person_id).count()
    vehicle_count = session.query(Vehicle).filter_by(owner_id=person_id).count()
    account_count = session.query(BankAccount).filter_by(owner_id=person_id).count()

    fir_ids = [f.id for f in firs]
    coordinated_firs = 0
    if fir_ids:
        # A FIR is "coordinated" for planning purposes if it has >=2
        # accused on record — one person acting with others implies some
        # amount of pre-arrangement, vs. a lone, unplanned offence.
        coordinated_firs = sum(1 for f in firs if len(f.accused_records) >= 2)

    financial_planning = account_count >= 2
    indicators = []
    if alias_count > 0:
        indicators.append(f"{alias_count} known alias(es)")
    if vehicle_count >= 2:
        indicators.append(f"{vehicle_count} registered vehicles")
    if financial_planning:
        indicators.append(f"{account_count} bank accounts")
    if coordinated_firs:
        indicators.append(f"{coordinated_firs} multi-accused (coordinated) FIR(s)")

    score = min(alias_count * 15 + (10 if vehicle_count >= 2 else 0) +
                (15 if financial_planning else 0) + coordinated_firs * 20, 100)

    return {
        "score": score,
        "alias_count": alias_count,
        "vehicle_count": vehicle_count,
        "bank_account_count": account_count,
        "coordinated_fir_count": coordinated_firs,
        "indicators": indicators,
        "because": (
            ", ".join(indicators) if indicators else "No aliases, multiple vehicles/accounts, "
            "or multi-accused FIRs on record — no planning indicators found."
        ),
    }


# ---------------------------------------------------------------------------
# Mobility
# ---------------------------------------------------------------------------

def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _mobility(crimes) -> dict:
    locations = [c.location for c in crimes if c.location]
    districts = sorted({loc.district for loc in locations})
    states = sorted({loc.state for loc in locations})

    avg_radius_km = None
    if len(locations) >= 2:
        pairs = [
            _haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)
            for i, a in enumerate(locations) for b in locations[i + 1:]
        ]
        if pairs:
            avg_radius_km = round(sum(pairs) / len(pairs), 1)

    return {
        "districts_operated": districts,
        "states_operated": states,
        "average_travel_radius_km": avg_radius_km,
        "because": (
            f"Offences recorded across {len(districts)} district(s) in {len(states)} state(s)"
            + (f"; average distance between offence locations is {avg_radius_km} km." if avg_radius_km else ".")
        ),
    }


# ---------------------------------------------------------------------------
# Target selection
# ---------------------------------------------------------------------------

def _target_selection(firs) -> dict:
    victims = [v for f in firs for v in f.victim_records]
    genders = Counter(v.person.gender.value for v in victims if v.person)
    total = sum(genders.values())

    return {
        "victim_count": len(victims),
        "victim_gender_distribution": dict(genders),
        # Schema limitation, stated rather than fabricated: Victim rows
        # are always Person-linked (accused.py/victim.py's design — see
        # those files' docstrings), so "organization/government/financial
        # institution victim" categories the brief lists aren't
        # distinguishable from this schema; only individual-victim
        # demographics are.
        "note": (
            "Victim records are person-linked only in this schema — business/government/"
            "financial-institution victim categories aren't separately modeled."
        ),
        "because": (
            f"{len(victims)} victim record(s) across this person's FIRs"
            + (f"; {genders.most_common(1)[0][0]} victims most common "
               f"({genders.most_common(1)[0][1]}/{total})." if genders else ".")
        ),
    }


# ---------------------------------------------------------------------------
# Time profile
# ---------------------------------------------------------------------------

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_MONTHS = ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"]


def _time_profile(crimes) -> dict:
    if not crimes:
        return {"most_common_weekday": None, "most_common_month": None,
                "most_common_hour": None, "because": "No offences on record."}

    weekdays = Counter(_WEEKDAYS[c.timestamp.weekday()] for c in crimes)
    months = Counter(_MONTHS[c.timestamp.month - 1] for c in crimes)
    hours = Counter(c.timestamp.hour for c in crimes)

    top_weekday = weekdays.most_common(1)[0]
    top_month = months.most_common(1)[0]
    top_hour = hours.most_common(1)[0]

    return {
        "most_common_weekday": top_weekday[0],
        "most_common_month": top_month[0],
        "most_common_hour": top_hour[0],
        "because": (
            f"{top_weekday[1]}/{len(crimes)} offence(s) on {top_weekday[0]}s, "
            f"{top_month[1]}/{len(crimes)} in {top_month[0]}, "
            f"{top_hour[1]}/{len(crimes)} around {top_hour[0]:02d}:00."
        ),
    }
