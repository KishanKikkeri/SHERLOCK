"""
SHERLOCK — Stage G1: investigation priority classification.

Routine -> Monitor -> Priority -> Urgent -> Critical, driven primarily
by the risk band (risk_engine.py) with two escalating overrides: recent
activity (an offence in the last 90 days moves a merely-"High" risk
person up a notch — recency matters for operational priority in a way
the risk *score* alone doesn't capture) and an open pending investigation
with no chargesheet yet (an active, unresolved case is inherently higher
priority than a closed one with the same historical risk).

Thresholds are judgment calls, stated as such — same pattern as every
other threshold in this module (criminal_history.py, risk_engine.py).
"""

from __future__ import annotations

_LADDER = ["Routine", "Monitor", "Priority", "Urgent", "Critical"]

_BAND_TO_INDEX = {
    "Very Low": 0,
    "Low": 0,
    "Medium": 1,
    "High": 2,
    "Critical": 4,
}

RECENT_ACTIVITY_DAYS = 90


def classify_priority(history: dict, risk: dict, network: dict) -> dict:
    index = _BAND_TO_INDEX.get(risk["band"], 1)
    reasons = [f"Risk band is {risk['band']} (score {risk['overall_score']}/100)."]

    days_since_last = history.get("days_since_last_offence")
    if days_since_last is not None and days_since_last <= RECENT_ACTIVITY_DAYS and index < 4:
        index += 1
        reasons.append(f"Most recent offence was {days_since_last} day(s) ago (within {RECENT_ACTIVITY_DAYS}-day recent-activity window).")

    if history.get("pending_investigation_count", 0) > 0 and index < 4:
        index += 1
        reasons.append(f"{history['pending_investigation_count']} investigation(s) still pending/open.")

    if history.get("habitual_offender") and index < 4:
        index += 1
        reasons.append("Classified as a habitual offender.")

    index = min(index, len(_LADDER) - 1)
    label = _LADDER[index]

    return {
        "priority": label,
        "ladder_index": index,
        "ladder": _LADDER,
        "because": reasons,
    }
