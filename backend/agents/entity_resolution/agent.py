"""
SHERLOCK — Entity Resolution Agent (Phase 5, Criminal Intelligence Division).

Real data, real problem: FIRs reference persons by whatever name was
written down at the time ("R Kumar", "Ravi K.", ...), never guaranteed to
match the canonical `Person.name`. `PersonCrimeLink.raw_name_used` carries
that messy raw name; `PersonAlias` carries the ground-truth variants a
person is known to go by.

This agent resolves each raw name reference in the investigation's scope
to its canonical Person, three ways in order of confidence:
  1. exact match against Person.name
  2. exact match against a known PersonAlias
  3. fuzzy match (difflib.SequenceMatcher) against name + aliases, for
     variants not in the ground-truth alias table at all

Deliberately stdlib-only (`difflib`) — no new dependency for something
this small, consistent with the rest of the pipeline's dependency-light
design.
"""

from difflib import SequenceMatcher

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import PersonCrimeLink

FUZZY_ACCEPT_THRESHOLD = 0.72  # below this, flag for manual review rather than silently resolving


class EntityResolutionAgent(BaseAgent):
    name = "EntityResolution"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        crime_ids = gctx.get("crime_ids")

        query = self.session.query(PersonCrimeLink)
        if crime_ids:
            query = query.filter(PersonCrimeLink.crime_id.in_(crime_ids))
        links = query.all()

        if not links:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="entity_resolution",
                summary="No person-crime references in scope to resolve.",
                confidence=0.5,
            )]

        resolutions = []
        for link in links:
            person = link.person
            if not person:
                continue
            raw = (link.raw_name_used or "").strip()
            canonical = person.name

            if raw == canonical:
                match_kind, score = "exact", 1.0
            else:
                alias_names = [a.alias_name for a in person.aliases]
                if raw in alias_names:
                    match_kind, score = "known_alias", 0.95
                else:
                    candidates = [canonical] + alias_names
                    best = max(candidates, key=lambda c: SequenceMatcher(None, raw.lower(), c.lower()).ratio())
                    score = SequenceMatcher(None, raw.lower(), best.lower()).ratio()
                    match_kind = "fuzzy_match" if score >= FUZZY_ACCEPT_THRESHOLD else "low_confidence"

            resolutions.append({
                "person_id": person.id,
                "canonical_name": canonical,
                "raw_name_used": raw,
                "match_kind": match_kind,
                "score": round(score, 2),
            })

        non_exact = [r for r in resolutions if r["match_kind"] != "exact"]
        low_conf = [r for r in resolutions if r["match_kind"] == "low_confidence"]
        distinct_people = len({r["person_id"] for r in resolutions})

        findings = [AgentFinding(
            agent_name=self.name,
            finding_type="entity_resolution",
            summary=(
                f"Resolved {len(resolutions)} name reference(s) in this case set to "
                f"{distinct_people} canonical identit{'y' if distinct_people == 1 else 'ies'}; "
                f"{len(non_exact)} required alias or fuzzy resolution."
            ),
            evidence=(
                [f'"{r["raw_name_used"]}" -> {r["canonical_name"]} ({r["match_kind"]}, {r["score"]:.0%})'
                 for r in non_exact[:5]]
                or [f"All {len(resolutions)} name reference(s) matched a canonical name exactly."]
            ),
            confidence=0.9 if not low_conf else 0.7,
            source_entities=[f"person_{r['person_id']}" for r in resolutions],
            metadata={"resolutions": resolutions},
        )]

        if low_conf:
            findings.append(AgentFinding(
                agent_name=self.name,
                finding_type="entity_resolution_flag",
                summary=(
                    f"{len(low_conf)} name reference(s) had low-confidence resolution "
                    f"(below {FUZZY_ACCEPT_THRESHOLD:.0%} similarity) and should be reviewed manually."
                ),
                evidence=[f'"{r["raw_name_used"]}" best-matched {r["canonical_name"]} at only {r["score"]:.0%} similarity'
                          for r in low_conf[:5]],
                confidence=0.55,
                source_entities=[f"person_{r['person_id']}" for r in low_conf],
                metadata={"flagged": low_conf},
            ))

        return findings
