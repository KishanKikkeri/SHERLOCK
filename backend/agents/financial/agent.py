"""
SHERLOCK — Financial Intelligence Agent (Phase 6, stress-test fix).

Activated when a query is financial in nature. Uses `graph_service` and
the SQL session to:

  1. Identify flagged mule accounts from the database.
  2. Find the hub account (highest incoming transaction count).
  3. Trace its full transaction network via `find_financial_network()`.
  4. Report the ring size, total suspicious value, and fan-in pattern.

This is what turns Demo 2 from "158 fraud FIRs retrieved" into
"₹8.1L suspicious fan-in network, 8 mule accounts, hub identified."
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import BankAccount, Transaction


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

        return findings
