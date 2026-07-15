"""
SHERLOCK — Similar Case Intelligence Agent (Stage A: Phase 5 baseline;
Sprint B1: upgraded per Stage B Division 1).

Baseline (Phase 5, unchanged): compares `Crime.modus_operandi` text across
cases (scoped to the query's crime type, if any) using stdlib
`difflib.SequenceMatcher` similarity. Surfaces case pairs whose MO
descriptions closely match.

Sprint B1 upgrade: MO-text similarity alone misses the strongest possible
signal a real investigator would check first — do two cases share an
actual accused, officer, or location? Those weren't queryable before the
AER migration (Accused/Officer are new tables). This agent now scores
each candidate pair on FOUR independent signals and reports whichever
fired, not just MO text:

    - MO text similarity (baseline, unchanged)
    - Accused overlap — same person charged in both cases
    - Officer overlap — same investigating officer on both cases
    - Location overlap — same crime location

Organization and weapon-based overlap (also named in the Stage B brief)
are NOT included here: no case currently links to an Organization at all
(no FK exists yet — see docs/AGENT_MAPPING.md's note on Organization
being scaffolding-only), and Weapon links to at most one FIR via
`used_in_fir_id`, which is a 1:1 relationship that can't itself produce
an "overlap between two cases" signal without weapon reuse data this
schema doesn't yet capture reliably. Both are real gaps, not oversights —
flagged for a future sprint rather than faked with an always-empty check.
"""

from difflib import SequenceMatcher

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.database.models import Crime, CrimeType

SIMILARITY_THRESHOLD = 0.6
MAX_POOL = 400  # guardrail so a huge unfiltered pool doesn't blow up the O(n^2) comparison


class SimilarCaseAgent(BaseAgent):
    name = "SimilarCase"

    def __init__(self, session):
        self.session = session

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        crime_ids = set(gctx.get("crime_ids", []) or [])
        filters = state.get("investigation_plan", {}).get("filters", {})
        crime_type = filters.get("crime_type")

        query = self.session.query(Crime)
        if crime_type:
            query = query.filter(Crime.type == CrimeType(crime_type))
        pool = query.limit(MAX_POOL).all()
        pool_with_mo = [c for c in pool if c.modus_operandi]

        if len(pool) < 2:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="similar_case",
                summary="Not enough cases in scope to compare.",
                confidence=0.5,
            )]

        anchors = [c for c in pool if c.id in crime_ids] or pool

        matches = []
        seen_pairs = set()
        for a in anchors:
            for b in pool:
                if a.id == b.id:
                    continue
                pair = tuple(sorted((a.id, b.id)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)

                signals = self._compare(a, b)
                if signals:
                    matches.append((a, b, signals))

        if not matches:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="similar_case",
                summary="No closely related cases found in this scope (MO, accused, officer, or location).",
                confidence=0.6,
            )]

        # Rank by number of independent signals first (a case sharing an
        # accused AND an officer is a stronger lead than MO-text alone),
        # then by MO similarity score as the tiebreaker.
        matches.sort(key=lambda m: (len(m[2]), m[2].get("mo_similarity", 0)), reverse=True)
        top = matches[:5]

        summary = (
            f"Found {len(matches)} related case pair(s); top match shares "
            f"{len(top[0][2])} signal(s): {', '.join(top[0][2].keys())}."
        )

        return [AgentFinding(
            agent_name=self.name,
            finding_type="similar_case",
            summary=summary,
            evidence=[
                f"Crime {a.id} ({a.type.value}, {a.timestamp:%Y-%m-%d}) vs "
                f"Crime {b.id} ({b.type.value}, {b.timestamp:%Y-%m-%d}): " +
                "; ".join(f"{k}={v}" for k, v in signals.items())
                for a, b, signals in top
            ],
            confidence=0.85 if any(len(s) > 1 for _, _, s in top) else 0.75,
            source_entities=sorted({f"crime_{a.id}" for a, _, _ in top} | {f"crime_{b.id}" for _, b, _ in top}),
            metadata={"matches": [
                {"crime_a": a.id, "crime_b": b.id, "signals": s} for a, b, s in top
            ]},
        )]

    @staticmethod
    def _compare(a: Crime, b: Crime) -> dict:
        """Returns a dict of every signal that fired for this pair — empty
        dict means no relationship detected at all."""
        signals = {}

        if a.modus_operandi and b.modus_operandi:
            score = SequenceMatcher(None, a.modus_operandi.lower(), b.modus_operandi.lower()).ratio()
            if score >= SIMILARITY_THRESHOLD:
                signals["mo_similarity"] = round(score, 2)

        if a.fir and b.fir:
            accused_a = {r.person_id for r in a.fir.accused_records}
            accused_b = {r.person_id for r in b.fir.accused_records}
            shared_accused = accused_a & accused_b
            if shared_accused:
                signals["shared_accused"] = sorted(shared_accused)

            officer_a = a.fir.investigating_officer_id
            officer_b = b.fir.investigating_officer_id
            if officer_a and officer_a == officer_b:
                signals["shared_officer"] = officer_a

        if a.location_id and a.location_id == b.location_id:
            signals["shared_location"] = a.location_id

        return signals
