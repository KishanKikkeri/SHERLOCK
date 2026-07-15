"""
SHERLOCK — Organization Intelligence Agent (Sprint B3, Stage B Division 7).

The Organization table existed since Stage A but had zero relationships
— pure scaffolding (see docs/AGENT_MAPPING.md Part 2). Sprint B3 added
`OrganizationMembership` plus optional `organization_id` on
BankAccount/Property specifically so this agent could be real instead of
a permanently-empty stub. See organization.py's docstring for the schema
change.

Traces the brief's diagram directly: Organization -> Members -> Bank
Accounts -> Properties -> Cases -> Funding. "Cases" here means: any FIR
where a member appears as Accused/Victim/Witness (derived — there's no
direct Organization-to-FIR link, which is realistic: an organization
isn't itself charged, its members are). "Funding" is approximated as
total transaction volume through the org's own flagged accounts, when
any exist — a real number, not invented, but a narrow proxy for what a
real funding-flow analysis would need (which would require the Sprint B3
"Bank Network" work below, applied specifically to org-linked accounts —
noted as a natural follow-up, not built here to keep this agent's scope
to what the brief's diagram actually asks for).
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Organization, OrganizationMembership, Transaction

MAX_ORGS = 5


class OrganizationIntelligenceAgent(BaseAgent):
    name = "OrganizationIntelligence"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        accused_person_ids = set(gctx.get("accused_person_ids", []) or [])

        if accused_person_ids:
            member_org_ids = {
                m.organization_id for m in
                self.session.query(OrganizationMembership)
                .filter(OrganizationMembership.person_id.in_(accused_person_ids)).all()
            }
            orgs = self.session.query(Organization).filter(Organization.id.in_(member_org_ids)).all() if member_org_ids else []
        else:
            orgs = self.session.query(Organization).limit(MAX_ORGS).all()

        if not orgs:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="organization_profile",
                summary="No organization linked to the person(s) in scope.",
                confidence=0.6,
            )]

        return [self._profile(o) for o in orgs[:MAX_ORGS]]

    def _profile(self, org: Organization):
        members = org.memberships
        accounts = org.bank_accounts
        properties = org.properties

        # Cases: any FIR where a member appears in any role
        case_fir_numbers = set()
        for m in members:
            p = m.person
            for a in p.accused_records:
                case_fir_numbers.add(a.fir.fir_number)
            for v in p.victim_records:
                case_fir_numbers.add(v.fir.fir_number)
            for w in p.witness_records:
                case_fir_numbers.add(w.fir.fir_number)

        funding_total = 0.0
        flagged_accounts = [a for a in accounts if a.is_flagged_mule]
        for acc in flagged_accounts:
            received = self.session.query(Transaction).filter_by(receiver_account_id=acc.id).all()
            funding_total += sum(t.amount for t in received)

        summary = (
            f"{org.name} ({org.org_type.value}): {len(members)} member(s), {len(accounts)} bank account(s) "
            f"({len(flagged_accounts)} flagged), {len(properties)} linked propert(y/ies), "
            f"appears in {len(case_fir_numbers)} case(s) via member involvement"
            + (f", \u20b9{funding_total:,.0f} routed through flagged accounts." if funding_total else ".")
        )

        return AgentFinding(
            agent_name=self.name,
            finding_type="organization_profile",
            summary=summary,
            evidence=(
                [f"Member: {m.person.name} ({m.role or 'role unspecified'})" for m in members]
                + [f"Case: {fn}" for fn in sorted(case_fir_numbers)]
            )[:8],
            confidence=0.85,
            source_entities=[f"organization_{org.id}"] + [f"person_{m.person_id}" for m in members],
            metadata={
                "organization_id": org.id,
                "name": org.name,
                "org_type": org.org_type.value,
                "member_count": len(members),
                "bank_account_count": len(accounts),
                "flagged_account_count": len(flagged_accounts),
                "property_count": len(properties),
                "linked_case_count": len(case_fir_numbers),
                "funding_via_flagged_accounts": funding_total,
            },
        )
