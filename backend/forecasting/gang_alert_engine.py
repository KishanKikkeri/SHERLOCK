"""
SHERLOCK — Gang Activity Detection Engine (Forecasting & Early Warning
Engine, Requirement 8). No Neo4j — builds its own lightweight in-memory
`networkx.Graph` straight from SQL, separate from `backend/graph/service*`
(which is the investigation-scoped graph used by Network Analysis etc.).
This graph exists only to run community detection over, once, for the
forecast dashboard.

Edge sources, and what's real vs a named gap:
    - PersonAssociation           real — every relation_type, weighted by `strength`
    - OrganizationMembership       real — co-membership in the same Organization
    - co-accused on the same FIR   real — from the Accused table
    - phone calls                  real — CallRecord between two Phones, mapped
                                    to their owners via Phone.owner_id
    - financial transactions       real — Transaction between two BankAccounts,
                                    mapped to their owners via BankAccount.owner_id
    - vehicle used in a crime       real, but NOT "shared ownership" (Vehicle has
                                    exactly one owner_id, so two people can't own
                                    the same vehicle in this schema) — instead
                                    this links a vehicle's owner to whoever was
                                    accused in the FIR the vehicle was used in,
                                    when those are different people
    - weapon used in a crime        same shape as vehicles: links
                                    Weapon.recovered_from_person_id to the
                                    accused of Weapon.used_in_fir_id

"Shared vehicle" / "shared weapon" in the literal sense the brief names
(one item, multiple owners) is NOT representable in this schema — Vehicle
and Weapon each have a single owner/recovery-person FK. The edges above
are the closest honest equivalent: a real link the item creates between
two specific people, not an invented many-owner relationship.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta

import networkx as nx

from backend.database.models import (
    Accused, BankAccount, CallRecord, Crime, FIR, Organization, OrganizationMembership,
    OrganizationType, Person, PersonAssociation, Phone, Transaction, Vehicle, Weapon,
)
from backend.forecasting.trend_forecaster import reference_now

# Same weighting convention as backend/agents/behavioral_intelligence/agent.py —
# kept in sync manually rather than imported, to avoid coupling this
# standalone forecasting engine to the agents package.
VIOLENCE_WEIGHTS = {
    "assault": 100, "drug_trafficking": 70, "burglary": 40,
    "theft": 30, "fraud": 20, "cybercrime": 15,
}

RECENT_WINDOW_DAYS = 90


class GangAlertEngine:
    def __init__(self, session):
        self.session = session

    # -- graph construction -------------------------------------------------

    def build_graph(self) -> nx.Graph:
        g = nx.Graph()

        def merge_edge(a, b, kind: str, weight: float, **detail):
            """Two people can be linked by more than one signal (e.g. both
            org-mates AND phone contacts) — a plain add_edge() call would
            silently overwrite the earlier kind/weight. This accumulates:
            `kinds` is the set of every edge type found for this pair,
            `weight` sums across all of them, and `details` keeps each
            kind's own evidence (call_count, organization_id, etc.)."""
            if g.has_edge(a, b):
                g[a][b]["weight"] += weight
                g[a][b]["kinds"].add(kind)
                g[a][b]["details"][kind] = detail
            else:
                g.add_edge(a, b, weight=weight, kinds={kind}, details={kind: detail})

        for assoc in self.session.query(PersonAssociation).all():
            merge_edge(assoc.person_a_id, assoc.person_b_id, "association",
                       assoc.strength or 0.5, relation_type=assoc.relation_type.value)

        # Co-membership in the same Organization.
        org_members = defaultdict(list)
        for m in self.session.query(OrganizationMembership).all():
            org_members[m.organization_id].append(m.person_id)
        for org_id, members in org_members.items():
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    merge_edge(members[i], members[j], "org_membership", 1.0, organization_id=org_id)

        # Co-accused on the same FIR.
        accused_by_fir = defaultdict(list)
        for a in self.session.query(Accused).all():
            accused_by_fir[a.fir_id].append(a.person_id)
        for fir_id, members in accused_by_fir.items():
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    merge_edge(members[i], members[j], "co_accused_fir", 0.5, fir_id=fir_id)

        # Phone calls, mapped to owners.
        if CallRecord is not None:
            phone_owner = {p.id: p.owner_id for p in self.session.query(Phone).all()}
            call_counts = Counter()
            for call in self.session.query(CallRecord).all():
                a = phone_owner.get(call.caller_phone_id)
                b = phone_owner.get(call.receiver_phone_id)
                if a and b and a != b:
                    call_counts[frozenset((a, b))] += 1
            for pair, count in call_counts.items():
                a, b = tuple(pair)
                merge_edge(a, b, "phone_call", min(count * 0.2, 3.0), call_count=count)

        # Financial transactions, mapped to account owners.
        account_owner = {a.id: a.owner_id for a in self.session.query(BankAccount).all() if a.owner_id}
        txn_counts = Counter()
        for txn in self.session.query(Transaction).all():
            a = account_owner.get(txn.sender_account_id)
            b = account_owner.get(txn.receiver_account_id)
            if a and b and a != b:
                txn_counts[frozenset((a, b))] += 1
        for pair, count in txn_counts.items():
            a, b = tuple(pair)
            merge_edge(a, b, "transaction", min(count * 0.2, 3.0), transaction_count=count)

        # Vehicle used in a crime: owner <-> that FIR's accused (if different).
        for vehicle in self.session.query(Vehicle).filter(Vehicle.used_in_fir_id.isnot(None)).all():
            for accused_id in accused_by_fir.get(vehicle.used_in_fir_id, []):
                if vehicle.owner_id and vehicle.owner_id != accused_id:
                    merge_edge(vehicle.owner_id, accused_id, "vehicle_link", 0.75, fir_id=vehicle.used_in_fir_id)

        # Weapon used in a crime: recovered-from-person <-> that FIR's accused.
        for weapon in self.session.query(Weapon).filter(Weapon.used_in_fir_id.isnot(None), Weapon.recovered_from_person_id.isnot(None)).all():
            for accused_id in accused_by_fir.get(weapon.used_in_fir_id, []):
                if weapon.recovered_from_person_id != accused_id:
                    merge_edge(weapon.recovered_from_person_id, accused_id, "weapon_link", 0.75, fir_id=weapon.used_in_fir_id)

        return g

    # -- community detection -------------------------------------------------

    def detect_communities(self, graph: nx.Graph | None = None, min_size: int = 3) -> list[set[int]]:
        g = graph if graph is not None else self.build_graph()
        if g.number_of_nodes() == 0:
            return []
        try:
            from networkx.algorithms.community import greedy_modularity_communities
            communities = [set(c) for c in greedy_modularity_communities(g, weight="weight")]
        except Exception:
            # Fall back to connected components if modularity detection fails
            # (e.g. degenerate/very small graphs).
            communities = [set(c) for c in nx.connected_components(g)]
        return [c for c in communities if len(c) >= min_size]

    def compute_metrics(self, graph: nx.Graph | None = None) -> dict:
        g = graph if graph is not None else self.build_graph()
        if g.number_of_nodes() == 0:
            return {"nodes": 0, "edges": 0, "connected_components": 0, "degree_centrality": {}, "pagerank": {}}
        return {
            "nodes": g.number_of_nodes(),
            "edges": g.number_of_edges(),
            "connected_components": nx.number_connected_components(g),
            "degree_centrality": {k: round(v, 3) for k, v in nx.degree_centrality(g).items()},
            "pagerank": {k: round(v, 4) for k, v in nx.pagerank(g, weight="weight").items()},
        }

    # -- gang classification -------------------------------------------------

    def get_gang_alerts(self, min_size: int = 3) -> list[dict]:
        graph = self.build_graph()
        communities = self.detect_communities(graph, min_size=min_size)
        if not communities:
            return []

        pagerank = nx.pagerank(graph, weight="weight") if graph.number_of_edges() else {}
        alerts = []
        for i, members in enumerate(sorted(communities, key=len, reverse=True)):
            alert = self._classify(f"G-{i + 1}", members, graph, pagerank)
            alerts.append(alert)
        return alerts

    def _classify(self, gang_id: str, member_ids: set[int], graph: nx.Graph, pagerank: dict) -> dict:
        persons = self.session.query(Person).filter(Person.id.in_(member_ids)).all()
        accused_records = self.session.query(Accused).filter(Accused.person_id.in_(member_ids)).all()
        fir_ids = {a.fir_id for a in accused_records}
        crimes = [f.crime for f in self.session.query(FIR).filter(FIR.id.in_(fir_ids)).all() if f.crime]

        now = reference_now(self.session)
        recent_cutoff = now - timedelta(days=RECENT_WINDOW_DAYS)
        prior_cutoff = now - timedelta(days=RECENT_WINDOW_DAYS * 2)
        recent_count = sum(1 for c in crimes if c.timestamp >= recent_cutoff)
        prior_count = sum(1 for c in crimes if prior_cutoff <= c.timestamp < recent_cutoff)
        if prior_count:
            activity_growth = round((recent_count - prior_count) / prior_count * 100, 1)
        else:
            activity_growth = 100.0 if recent_count else 0.0

        is_gang_org = (
            self.session.query(OrganizationMembership)
            .join(Organization, Organization.id == OrganizationMembership.organization_id)
            .filter(OrganizationMembership.person_id.in_(member_ids), Organization.org_type == OrganizationType.GANG)
            .first() is not None
        )
        violence_scores = [VIOLENCE_WEIGHTS.get(c.type.value, 25) for c in crimes]
        avg_violence = sum(violence_scores) / len(violence_scores) if violence_scores else 0

        districts = Counter(c.location.district for c in crimes if c.location)
        top_district = districts.most_common(1)[0][0] if districts else None

        risk_score = (
            min(len(member_ids) * 8, 40)
            + max(0, min(activity_growth, 100)) * 0.3
            + (20 if is_gang_org else 0)
            + avg_violence * 0.1
        )
        risk_score = round(min(risk_score, 100), 1)
        if risk_score >= 70:
            risk_label = "Critical"
        elif risk_score >= 45:
            risk_label = "High"
        elif risk_score >= 20:
            risk_label = "Medium"
        else:
            risk_label = "Low"

        if recent_count == 0:
            category = "Dormant"
        elif activity_growth >= 50 and len(member_ids) <= 5:
            category = "Emerging"
        elif activity_growth > 20:
            category = "Growing"
        elif risk_label in ("Critical", "High"):
            category = "High-risk"
        else:
            category = "Stable"

        top_person_id = max(member_ids, key=lambda pid: pagerank.get(pid, 0)) if pagerank else None

        return {
            "gang_id": gang_id,
            "members": len(member_ids),
            "member_person_ids": sorted(member_ids)[:30],
            "activity_growth": activity_growth,
            "risk": risk_label,
            "category": category,
            "district": top_district,
            "confirmed_org_membership": is_gang_org,
            "most_central_person_id": top_person_id,
            "evidence": {
                "recent_crimes_last_90d": recent_count,
                "prior_crimes_90_to_180d": prior_count,
                "avg_violence_weight": round(avg_violence, 1),
                "distinct_firs": len(fir_ids),
            },
            "method": (
                "NetworkX greedy-modularity community over a graph of PersonAssociation, "
                "OrganizationMembership, co-accused-FIR, phone-call, transaction, "
                "vehicle-used-in-crime, and weapon-used-in-crime edges."
            ),
        }
