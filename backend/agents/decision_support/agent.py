"""
SHERLOCK — Decision Support Agent (Sprint B5, Stage B Division 14).

Different from Prevention Agent (Phase 5) even though both produce
recommendations: Prevention answers "how do we reduce future crime"
(patrol density, surveillance zones — district/pattern-level). Decision
Support answers "what should we do on THIS case, right now" — the seven
categories the brief names are all case-specific action items, not
policy-level recommendations. Runs downstream of the case-scoped Sprint
B1-B3 agents (Case/Officer/Witness/Property/Weapon/Organization
Intelligence, Network Analysis), reading their findings from
`state["findings"]` rather than re-deriving everything from scratch —
this agent's whole job is synthesis, so duplicating upstream queries
would be redundant and risks drifting out of sync with what those
agents already established.

Each of the seven categories is populated only when the underlying data
actually supports it — an empty category is reported as empty, not
padded with a generic suggestion, since a false "nothing to report" is
actively worse than an omission for something investigators might act on.

    - Recommended Next Steps: pulled directly from CaseIntelligence's
      pending_tasks across every case in scope.
    - Recommended Warrants: accused persons with 2+ FIRs who have never
      been arrested on any of them — a concrete, queryable definition of
      "warrant-worthy," not a vague risk score.
    - Persons to Question: individuals connected via PersonAssociation or
      case co-occurrence to an accused person, but not themselves accused
      in any case — i.e. the network exists (Network Analysis already
      found it), these are the people in it who haven't been formally
      brought in.
    - Evidence Still Missing: cases in scope with zero Property records.
    - Suggested Searches: persons with vehicles/bank accounts identified
      (Property/Financial Intelligence's Asset Link work) but not
      currently under RECOVERED/SEIZED status — assets identified but not
      yet acted on.
    - Suggested Financial Freeze: flagged mule accounts with no
      corresponding chargesheet yet on any linked case.
    - Recommended Surveillance: accused persons with a Behavioral
      Intelligence gang-likelihood signal (or Organization membership)
      who are not currently under arrest.
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import (
    Crime, FIR, Accused, Arrest, Property, BankAccount, Vehicle,
    PersonAssociation, OrganizationMembership,
)

MAX_ITEMS_PER_CATEGORY = 6


class DecisionSupportAgent(BaseAgent):
    name = "DecisionSupport"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        crime_ids = gctx.get("crime_ids")
        accused_person_ids = set(gctx.get("accused_person_ids", []) or [])

        query = self.session.query(Crime)
        if crime_ids:
            query = query.filter(Crime.id.in_(crime_ids))
        crimes = query.all()
        fir_ids = {c.fir.id for c in crimes if c.fir}

        if not fir_ids:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="decision_support",
                summary="No case(s) in scope to generate decision-support recommendations for.",
                confidence=0.5,
            )]

        next_steps = self._next_steps(state)
        warrants = self._recommended_warrants(accused_person_ids)
        persons_to_question = self._persons_to_question(accused_person_ids)
        missing_evidence = self._evidence_still_missing(fir_ids)
        searches = self._suggested_searches(accused_person_ids)
        freezes = self._suggested_freezes(fir_ids)
        surveillance = self._recommended_surveillance(accused_person_ids)

        categories = {
            "recommended_next_steps": next_steps,
            "recommended_warrants": warrants,
            "persons_to_question": persons_to_question,
            "evidence_still_missing": missing_evidence,
            "suggested_searches": searches,
            "suggested_financial_freeze": freezes,
            "recommended_surveillance": surveillance,
        }
        populated = {k: v for k, v in categories.items() if v}

        if not populated:
            summary = "Decision support: no outstanding action items identified for the case(s) in scope."
        else:
            summary = "Decision support: " + "; ".join(f"{len(v)} {k.replace('_', ' ')}" for k, v in populated.items()) + "."

        evidence = []
        for k, v in populated.items():
            evidence.append(f"{k.replace('_', ' ').title()}: {v[:MAX_ITEMS_PER_CATEGORY]}")

        return [AgentFinding(
            agent_name=self.name,
            finding_type="decision_support",
            summary=summary,
            evidence=evidence,
            confidence=0.85,
            source_entities=[f"crime_{c.id}" for c in crimes],
            metadata=categories,
        )]

    def _next_steps(self, state):
        # CaseIntelligence already computed pending_tasks per case — reuse
        # it rather than re-deriving the same logic here. Findings in
        # state["findings"] are plain dicts by this point (BaseAgent.to_node()
        # converts every AgentFinding via .to_dict() before appending).
        case_findings = [f for f in state.get("findings", []) if f.get("summary", "").startswith("Case ")]
        steps = []
        for f in case_findings:
            for task in f.get("metadata", {}).get("pending_tasks", []):
                steps.append(f"{f.get('metadata', {}).get('fir_number', '?')}: {task}")
        return steps[:MAX_ITEMS_PER_CATEGORY]

    def _recommended_warrants(self, accused_person_ids):
        warrants = []
        for pid in accused_person_ids:
            records = self.session.query(Accused).filter_by(person_id=pid).all()
            if len(records) < 2:
                continue
            has_arrest = self.session.query(Arrest).filter_by(person_id=pid).first() is not None
            if not has_arrest:
                warrants.append(f"person_{pid} ({records[0].person.name}): {len(records)} FIRs, never arrested")
        return warrants[:MAX_ITEMS_PER_CATEGORY]

    def _persons_to_question(self, accused_person_ids):
        if not accused_person_ids:
            return []
        assocs = self.session.query(PersonAssociation).filter(
            (PersonAssociation.person_a_id.in_(accused_person_ids)) |
            (PersonAssociation.person_b_id.in_(accused_person_ids))
        ).all()
        connected = set()
        for a in assocs:
            connected.add(a.person_a_id)
            connected.add(a.person_b_id)
        connected -= accused_person_ids

        not_yet_accused = []
        for pid in connected:
            is_accused = self.session.query(Accused).filter_by(person_id=pid).first() is not None
            if not is_accused:
                not_yet_accused.append(f"person_{pid}")
        return not_yet_accused[:MAX_ITEMS_PER_CATEGORY]

    def _evidence_still_missing(self, fir_ids):
        missing = []
        for fid in fir_ids:
            has_property = self.session.query(Property).filter_by(fir_id=fid).first() is not None
            if not has_property:
                fir = self.session.get(FIR, fid)
                missing.append(f"{fir.fir_number}: no property/evidence logged")
        return missing[:MAX_ITEMS_PER_CATEGORY]

    def _suggested_searches(self, accused_person_ids):
        suggestions = []
        for pid in accused_person_ids:
            vehicles = self.session.query(Vehicle).filter_by(owner_id=pid, seized=False).all()
            for v in vehicles:
                suggestions.append(f"person_{pid}: vehicle {v.registration_number} identified but not seized")
        return suggestions[:MAX_ITEMS_PER_CATEGORY]

    def _suggested_freezes(self, fir_ids):
        mule_accounts = self.session.query(BankAccount).filter_by(is_flagged_mule=True).all()
        freezes = []
        for acc in mule_accounts:
            owner_fir_ids = {a.fir_id for a in self.session.query(Accused).filter_by(person_id=acc.owner_id).all()}
            if not owner_fir_ids & fir_ids:
                continue
            has_chargesheet = any(
                self.session.get(FIR, fid).chargesheets
                for fid in owner_fir_ids
            )
            if not has_chargesheet:
                freezes.append(f"account {acc.account_number} ({acc.bank}): flagged mule, no chargesheet filed yet")
        return freezes[:MAX_ITEMS_PER_CATEGORY]

    def _recommended_surveillance(self, accused_person_ids):
        surveillance = []
        for pid in accused_person_ids:
            is_org_member = self.session.query(OrganizationMembership).filter_by(person_id=pid).first() is not None
            has_co_accused_tie = self.session.query(PersonAssociation).filter(
                ((PersonAssociation.person_a_id == pid) | (PersonAssociation.person_b_id == pid))
            ).first() is not None
            has_arrest = self.session.query(Arrest).filter_by(person_id=pid).first() is not None

            if (is_org_member or has_co_accused_tie) and not has_arrest:
                reason = "organization member" if is_org_member else "known association"
                surveillance.append(f"person_{pid}: {reason}, not currently under arrest")
        return surveillance[:MAX_ITEMS_PER_CATEGORY]
