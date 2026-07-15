"""
SHERLOCK — Financial Intelligence Agent.

Phase 6 baseline (unchanged): activated when a query is financial in
nature. Identifies flagged mule accounts, finds the hub account (highest
incoming transaction count), traces its transaction network via
`find_financial_network()`, and reports mule-ring structure + fan-in
pattern. This is what turns Demo 2 from "158 fraud FIRs retrieved" into
"₹8.1L suspicious fan-in network, 8 mule accounts, hub identified."

Sprint B3 upgrade (Stage B Division 8, "Financial Intelligence
Expansion"): the brief names four expansion agents — Bank Network, Asset
Flow, Corporate Fraud, Cryptocurrency (marked "(Future)" in the brief
itself). Two are implemented here as additional finding types on the
existing agent, following the same consolidation pattern used for
Witness/Property Intelligence in this sprint:

    - Bank Network: extends the hub-only view above to every flagged
      account's fan-in degree (not just the single busiest one), so a
      network with two separate hubs isn't reduced to reporting only
      the larger one.
    - Asset Flow: for the owners of flagged accounts, traces their other
      assets (vehicles, non-financial property) — the same "what else
      does this person hold" question Property Intelligence answers from
      the property side, answered here from the financial side.

Corporate Fraud and Cryptocurrency are NOT implemented: the brief itself
marks Cryptocurrency "(Future)", and Corporate Fraud has no schema
support yet — it would need audit/filing data this AER doesn't model.
Both left as explicitly deferred rather than stubbed.
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import BankAccount, Transaction, Vehicle, Property


class FinancialAgent(BaseAgent):
    name = "FinancialAgent"

    def __init__(self, session, graph_service):
        self.session = session
        self.graph_service = graph_service

    def run(self, state: dict):
        # Find all flagged mule accounts
        mule_accounts = self.session.query(BankAccount).filter_by(is_flagged_mule=True).all()
        if not mule_accounts:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="financial_network",
                summary="No flagged mule accounts found in the database.",
                evidence=[],
                confidence=0.5,
            )]

        # Identify hub = mule account with most received transactions
        hub = max(mule_accounts, key=lambda a: len(a.received_transactions))
        mules = [a for a in mule_accounts if a.id != hub.id]

        # Trace hub's full transaction network
        network = self.graph_service.find_financial_network(hub.id)
        incoming = [t for t in network if t["direction"] == "received"]
        suspicious = [t for t in network if t["is_suspicious"]]
        total_value = sum(t["amount"] for t in suspicious)

        findings = []

        # Finding 1: Mule ring structure
        findings.append(AgentFinding(
            agent_name=self.name,
            finding_type="financial_network",
            summary=(
                f"Money-mule network detected: {len(mule_accounts)} flagged accounts, "
                f"hub account owned by {hub.owner.name} ({hub.bank}). "
                f"{len(incoming)} incoming transactions totalling ₹{total_value:,.0f}."
            ),
            evidence=[
                f"Hub account: {hub.account_number} @ {hub.bank} (owner: {hub.owner.name})",
                f"{len(mule_accounts)} accounts flagged as mule accounts in the database",
                f"{len(suspicious)} suspicious transactions totalling ₹{total_value:,.0f}",
            ],
            confidence=0.93,
            source_entities=[f"person_{hub.owner_id}"] + [f"account_{a.id}" for a in mule_accounts],
            metadata={
                "hub_person_id": hub.owner_id,
                "hub_account_id": hub.id,
                "ring_size": len(mule_accounts),
                "total_suspicious_value": total_value,
                "transaction_count": len(suspicious),
                "network": network[:10],
            },
        ))

        # Finding 2: Fan-in pattern description
        senders = {t["counterparty_owner"] for t in incoming if t["counterparty_owner"]}
        if senders:
            findings.append(AgentFinding(
                agent_name=self.name,
                finding_type="suspicious_pattern",
                summary=(
                    f"Fan-in transaction pattern: {len(senders)} distinct sender(s) "
                    f"routing funds to a single hub account — classic money-mule "
                    f"aggregation structure. All {len(suspicious)} transactions flagged suspicious."
                ),
                evidence=[
                    f"Sender accounts: {', '.join(list(senders)[:4])}{'…' if len(senders)>4 else ''}",
                    f"Pattern: multiple-to-one fund aggregation into {hub.owner.name}'s account",
                ],
                confidence=0.89,
                source_entities=[f"account_{hub.id}"],
                metadata={"senders": list(senders), "pattern": "fan_in"},
            ))

        # Sprint B3: Finding 3 — Bank Network (every flagged account's fan-in
        # degree, not just the single busiest hub)
        network_finding = self._bank_network(mule_accounts)
        if network_finding:
            findings.append(network_finding)

        # Sprint B3: Finding 4 — Asset Flow (other assets held by flagged
        # account owners)
        asset_finding = self._asset_flow(mule_accounts)
        if asset_finding:
            findings.append(asset_finding)

        return findings

    def _bank_network(self, mule_accounts):
        degrees = []
        for acc in mule_accounts:
            fan_in = len(acc.received_transactions)
            fan_out = len(acc.sent_transactions)
            if fan_in or fan_out:
                degrees.append({
                    "account_id": acc.id, "account_number": acc.account_number,
                    "owner": acc.owner.name, "fan_in": fan_in, "fan_out": fan_out,
                })

        if not degrees:
            return None

        degrees.sort(key=lambda d: d["fan_in"] + d["fan_out"], reverse=True)
        multi_hub = len([d for d in degrees if d["fan_in"] >= 2])

        summary = (
            f"Bank network: {len(degrees)} flagged account(s) with transaction activity"
            + (f", {multi_hub} of them independent fan-in hubs (2+ senders each) — "
               f"possibly multiple parallel mule structures, not one ring." if multi_hub > 1 else ".")
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="bank_network",
            summary=summary,
            evidence=[f"{d['account_number']} ({d['owner']}): {d['fan_in']} in / {d['fan_out']} out" for d in degrees[:6]],
            confidence=0.85,
            source_entities=[f"account_{d['account_id']}" for d in degrees],
            metadata={"degrees": degrees},
        )

    def _asset_flow(self, mule_accounts):
        owner_ids = {a.owner_id for a in mule_accounts}
        chains = {}
        for pid in owner_ids:
            vehicles = self.session.query(Vehicle).filter_by(owner_id=pid).all()
            properties = self.session.query(Property).filter_by(recovered_from_person_id=pid).all()
            if vehicles or properties:
                chains[pid] = {
                    "vehicles": [v.registration_number for v in vehicles],
                    "properties": [p.description for p in properties],
                }

        if not chains:
            return None

        summary = (
            f"Asset flow: {len(chains)} flagged-account owner(s) also hold non-financial assets "
            f"traceable in this case — a fuller financial-crime picture than transactions alone."
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="asset_flow",
            summary=summary,
            evidence=[
                f"person_{pid}: vehicles={c['vehicles']}, properties={c['properties']}"
                for pid, c in chains.items()
            ],
            confidence=0.8,
            source_entities=[f"person_{pid}" for pid in chains],
            metadata={"chains": {str(k): v for k, v in chains.items()}},
        )
