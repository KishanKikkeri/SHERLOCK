"""
SHERLOCK — Similar Case Agent (Phase 5, Intelligence Division).

Compares `Crime.modus_operandi` text across cases (scoped to the query's
crime type, if any) using stdlib `difflib.SequenceMatcher` similarity.
Surfaces case pairs whose MO descriptions closely match but which aren't
already the same FIR/investigation — a real (if simple) way to flag
possible serial activity or a shared MO worth cross-referencing.

O(n^2) comparisons — fine at hackathon/demo dataset scale (hundreds of
crimes). Would need an actual text-embedding index before this scales to
a real deployment's case volume; noted in the README, not hidden.
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
        pool = [c for c in query.limit(MAX_POOL).all() if c.modus_operandi]

        if len(pool) < 2:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="similar_case",
                summary="Not enough modus-operandi data in scope to compare cases.",
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
                score = SequenceMatcher(None, a.modus_operandi.lower(), b.modus_operandi.lower()).ratio()
                if score >= SIMILARITY_THRESHOLD:
                    matches.append((a, b, score))

        matches.sort(key=lambda m: m[2], reverse=True)
        top = matches[:5]

        if not top:
            return [AgentFinding(
                agent_name=self.name,
                finding_type="similar_case",
                summary="No cases with a closely matching modus operandi were found in this scope.",
                confidence=0.6,
            )]

        summary = (
            f"Found {len(matches)} case pair(s) with a closely matching modus operandi "
            f"(top similarity {top[0][2]:.0%})."
        )

        return [AgentFinding(
            agent_name=self.name,
            finding_type="similar_case",
            summary=summary,
            evidence=[
                f"Crime {a.id} ({a.type.value}, {a.timestamp:%Y-%m-%d}) vs "
                f"Crime {b.id} ({b.type.value}, {b.timestamp:%Y-%m-%d}): {score:.0%} MO similarity"
                for a, b, score in top
            ],
            confidence=0.75,
            source_entities=sorted({f"crime_{a.id}" for a, _, _ in top} | {f"crime_{b.id}" for _, b, _ in top}),
            metadata={"matches": [{"crime_a": a.id, "crime_b": b.id, "similarity": round(s, 2)} for a, b, s in top]},
        )]
