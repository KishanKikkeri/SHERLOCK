"""
SHERLOCK — Property Intelligence Agent (Sprint B3, Stage B Division 4).

Consolidation note (same rationale as Witness Intelligence in Sprint
B2): the brief lists Property Recovery and Asset Link as two agents, but
both start from the same `Property` rows for the cases in scope, so
they're two finding types from one agent rather than duplicated
data-gathering.

Property Recovery: reports where every property item in scope currently
sits on the seized -> in_custody -> released -> disposed funnel (see
PropertyStatus in models/enums.py) — a direct status roll-up, not an
inference.

Asset Link: for each person who has property recovered from them,
traces every OTHER asset (vehicle, bank account) that same person owns —
a real "what else does this person have" query that the AER migration
made possible (Stage A's legacy schema had no Property table at all to
link from). Organization-linked assets (Sprint B3's new
`organization_id` on BankAccount/Property) are included when present.
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Crime, Property, Vehicle, BankAccount

MAX_PROPERTY_ITEMS = 10


class PropertyIntelligenceAgent(BaseAgent):
    name = "PropertyIntelligence"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        crime_ids = gctx.get("crime_ids")

        query = self.session.query(Crime)
        if crime_ids:
            query = query.filter(Crime.id.in_(crime_ids))
        crimes = query.all()

        fir_ids = {c.fir.id for c in crimes if c.fir}
        if not fir_ids:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="property_recovery",
                summary="No FIRs in scope to check for property.",
                confidence=0.5,
            )]

        properties = (
            self.session.query(Property).filter(Property.fir_id.in_(fir_ids)).limit(MAX_PROPERTY_ITEMS).all()
        )
        if not properties:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="property_recovery",
                summary="No property/evidence recorded for the case(s) in scope.",
                confidence=0.6,
            )]

        findings = [self._recovery_funnel(properties)]

        asset_finding = self._asset_link(properties)
        if asset_finding:
            findings.append(asset_finding)

        return findings

    def _recovery_funnel(self, properties):
        by_status = {}
        for p in properties:
            by_status.setdefault(p.status.value, []).append(p)

        summary = (
            f"Property recovery: {len(properties)} item(s) in scope — "
            + ", ".join(f"{len(items)} {status}" for status, items in by_status.items()) + "."
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="property_recovery",
            summary=summary,
            evidence=[
                f"{p.description} ({p.category or 'uncategorized'}): {p.status.value}, FIR {p.fir.fir_number}"
                for p in properties
            ],
            confidence=0.95,  # direct status roll-up, not an inference
            source_entities=[f"property_{p.id}" for p in properties],
            metadata={"by_status": {k: len(v) for k, v in by_status.items()}, "total": len(properties)},
        )

    def _asset_link(self, properties):
        person_ids = {p.recovered_from_person_id for p in properties if p.recovered_from_person_id}
        if not person_ids:
            return None

        chains = {}
        for pid in person_ids:
            vehicles = self.session.query(Vehicle).filter_by(owner_id=pid).all()
            accounts = self.session.query(BankAccount).filter_by(owner_id=pid).all()
            if vehicles or accounts:
                chains[pid] = {
                    "vehicles": [v.registration_number for v in vehicles],
                    "bank_accounts": [a.account_number for a in accounts],
                    "flagged_mule_accounts": [a.account_number for a in accounts if a.is_flagged_mule],
                }

        if not chains:
            return None

        total_assets = sum(len(c["vehicles"]) + len(c["bank_accounts"]) for c in chains.values())
        flagged = sum(len(c["flagged_mule_accounts"]) for c in chains.values())
        summary = (
            f"Asset link: {len(chains)} person(s) with recovered property also have {total_assets} "
            f"other traceable asset(s) on record"
            + (f", including {flagged} flagged mule account(s)." if flagged else ".")
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="asset_link",
            summary=summary,
            evidence=[
                f"person_{pid}: vehicles={c['vehicles']}, bank_accounts={c['bank_accounts']}"
                for pid, c in chains.items()
            ],
            confidence=0.9,
            source_entities=[f"person_{pid}" for pid in chains],
            metadata={"chains": {str(k): v for k, v in chains.items()}},
        )
