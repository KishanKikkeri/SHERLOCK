"""
SHERLOCK — Stage G1: risk engine.

Fixed weights, taken directly from the brief:

    Violence 25% | Repeat History 20% | Escalation 15% | Network 15%
    Financial 10% | Mobility 5% | Weapons 10%

Each component is normalized to 0-100 from signals `behavior_profiler.py`
/ `criminal_history.py` / `network_profile.py` already computed — this
module does not re-derive anything from raw records, only combines
already-explained sub-scores into one weighted total, and carries each
component's own "because" line forward so the overall score's
explanation is never a black box.
"""

from __future__ import annotations

WEIGHTS = {
    "violence": 0.25,
    "repeat_history": 0.20,
    "escalation": 0.15,
    "network": 0.15,
    "financial": 0.10,
    "mobility": 0.05,
    "weapons": 0.10,
}

BANDS = [
    (0, 20, "Very Low"),
    (21, 40, "Low"),
    (41, 60, "Medium"),
    (61, 80, "High"),
    (81, 100, "Critical"),
]


def _band(score: int) -> str:
    for low, high, label in BANDS:
        if low <= score <= high:
            return label
    return "Critical"  # score > 100 shouldn't happen, but never crash on it


def _repeat_history_score(history: dict) -> int:
    # 0 FIRs -> 0, 1 -> 20, habitual (>=5) -> 100, linear between.
    return min(history["fir_count"] * 20, 100)


def _financial_score(network: dict) -> int:
    links = network.get("financial_links", [])
    if not links:
        return 0
    suspicious = sum(l["suspicious_transaction_count"] for l in links)
    return min(suspicious * 25 + len(links) * 5, 100)


def _network_score(network: dict) -> int:
    graph_metrics = network.get("graph_metrics", {})
    base = min(network.get("associate_count", 0) * 8, 60)
    if graph_metrics.get("available"):
        base = min(base + round(graph_metrics.get("degree_centrality", 0) * 100), 100)
    return min(base, 100)


def _mobility_score(behavior: dict) -> int:
    districts = behavior["mobility"]["districts_operated"]
    return min(len(districts) * 20, 100)


def compute_risk_profile(history: dict, behavior: dict, network: dict) -> dict:
    components = {
        "violence": behavior["aggression"]["score"],
        "repeat_history": _repeat_history_score(history),
        "escalation": behavior["escalation"]["score"],
        "network": _network_score(network),
        "financial": _financial_score(network),
        "mobility": _mobility_score(behavior),
        "weapons": min(behavior["aggression"]["weapon_incidents"] * 30, 100),
    }

    overall = round(sum(components[k] * WEIGHTS[k] for k in WEIGHTS))
    band = _band(overall)

    reasons = []
    # Explain using the two or three highest-weighted-contribution
    # components, largest contribution first — not every component, so
    # the explanation reads like an investigator's summary rather than a
    # dump of every number.
    contributions = sorted(
        ((k, components[k] * WEIGHTS[k]) for k in WEIGHTS), key=lambda kv: kv[1], reverse=True
    )
    for key, _contribution in contributions[:4]:
        if components[key] == 0:
            continue
        if key == "violence":
            reasons.append(behavior["aggression"]["because"])
        elif key == "repeat_history":
            reasons.append(f"{history['fir_count']} FIR(s) on record as accused.")
        elif key == "escalation":
            reasons.append(behavior["escalation"]["because"])
        elif key == "network":
            reasons.append(network["because"])
        elif key == "financial":
            links = network.get("financial_links", [])
            suspicious = sum(l["suspicious_transaction_count"] for l in links)
            reasons.append(f"{suspicious} suspicious transaction(s) across {len(links)} financial link(s).")
        elif key == "mobility":
            reasons.append(behavior["mobility"]["because"])
        elif key == "weapons":
            reasons.append(f"{behavior['aggression']['weapon_incidents']} weapon incident(s) on record.")

    if not reasons:
        reasons.append("No significant risk signals found across violence, repeat history, escalation, "
                        "network, financial, mobility, or weapons — record is largely clean.")

    return {
        "overall_score": overall,
        "band": band,
        "components": components,
        "weights": WEIGHTS,
        "because": reasons,
    }
