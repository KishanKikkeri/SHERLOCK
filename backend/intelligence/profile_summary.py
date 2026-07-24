"""
SHERLOCK — Stage G1: recommendations.

Fixed rule -> recommendation mapping, evaluated in order; a rule fires
only when the specific signal it names is actually present, and every
recommendation carries the "because" reason that fired it — no
open-ended LLM brainstorming, per the brief's "no LLM-generated
profiling" requirement.
"""

from __future__ import annotations


def generate_recommendations(history: dict, behavior: dict, modus: dict, network: dict,
                              risk: dict, priority: dict) -> list[dict]:
    recs: list[dict] = []

    def add(action: str, because: str):
        recs.append({"action": action, "because": because})

    if priority["priority"] in ("Urgent", "Critical"):
        add("Priority arrest / custody review",
            f"Investigation priority is {priority['priority']} ({'; '.join(priority['because'])})")

    if risk["overall_score"] >= 61:
        add("Increase surveillance",
            f"Overall risk is {risk['band']} ({risk['overall_score']}/100).")

    if behavior["escalation"]["trend"] == "escalating":
        add("Increase surveillance — escalating offence pattern",
            behavior["escalation"]["because"])

    if behavior["aggression"]["weapon_incidents"] > 0:
        add("Weapon tracing",
            f"{behavior['aggression']['weapon_incidents']} weapon incident(s) on record "
            f"({', '.join(behavior['aggression']['weapon_types']) or 'type unspecified'}).")

    financial_links = network.get("financial_links", [])
    suspicious_total = sum(l["suspicious_transaction_count"] for l in financial_links)
    if suspicious_total > 0:
        add("Financial audit",
            f"{suspicious_total} suspicious transaction(s) across {len(financial_links)} financial "
            f"counterparty link(s).")
        add("Monitor transactions",
            "Suspicious transaction activity on record — ongoing monitoring recommended.")

    if network.get("repeat_collaborators"):
        top = network["repeat_collaborators"][0]
        top_label = top.get("name") or f"person_{top.get('associate_id')}"
        add(f"Interview associate: {top_label}",
            "Recorded co-accused tie — repeat collaborator on multiple offences.")

    if modus.get("vehicle_usage"):
        add("Vehicle tracking",
            f"Vehicle type(s) on record in connection with offences: {', '.join(modus['vehicle_usage'])}.")

    mobility = behavior["mobility"]
    if len(mobility["districts_operated"]) >= 3:
        add("Coordinate with multiple jurisdictions",
            f"Active across {len(mobility['districts_operated'])} districts: "
            f"{', '.join(mobility['districts_operated'])}.")

    if network.get("organizations"):
        org_names = ", ".join(o["name"] for o in network["organizations"] if o.get("name"))
        add("Community/organization intelligence",
            f"Organization membership on record ({org_names or 'unnamed'}) — possible organized involvement.")

    if history.get("on_bail_no_chargesheet"):
        add("Expedite chargesheet filing",
            "Accused is on bail with no chargesheet filed yet — flight/tampering risk window.")

    if not recs:
        add("Routine monitoring",
            "No elevated risk signals found across violence, network, financial, or escalation dimensions.")

    return recs
