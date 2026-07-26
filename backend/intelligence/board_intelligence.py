"""
SHERLOCK — Stage C5: Investigation Board Intelligence.

The frontend board (`frontend/src/components/board/InvestigationBoard.tsx`,
`hooks/useBoard.ts`) already exists and is entirely client-side today —
cards/links live in React state + localStorage, and `addFromFinding()`
already knows how to turn one `AgentFinding` into an evidence card. What
it doesn't have yet is anything that looks across *all* the findings in
an investigation and says "these two things are probably connected" —
that's what this module adds.

This is a read-only analysis layer: it never writes cards/links itself
(that stays a frontend/user action, per `useBoard`'s undo/redo model). It
returns suggestions in a shape the frontend can turn into
`BoardCard`/`BoardLink` objects with one `addCard`/`addLink` call per
item — see `backend/api/board.py` for the exact response contract.

Scope, honestly:
  - suggested_links       — real, from graph associate/connection queries
  - relationship_confidence — real, carried from the graph's own edge strength
  - hidden_connections     — real, multi-hop find_connection() paths
  - contradiction detection — real, but narrow: only the one contradiction
                              shape the system currently has data for
                              (Evidence Validation rejecting a finding that
                              shares an entity with an accepted one)
  - missing_evidence       — real, but heuristic: pattern-matches agent
                              summaries that already say "No X recorded"
  - ai_generated_hypotheses — real, but simple: promotes the
                              highest-confidence, not-yet-rejected findings,
                              not an LLM brainstorming novel theories
  - investigation_replay   — real: the session's own turn-by-turn history
  - evidence_clustering    — real, but simple: groups by agent + entity
                              type, not a learned similarity metric
"""

from __future__ import annotations

from collections import defaultdict

from backend.graph.service import GraphIntelligenceService
from backend.memory.conversation_memory import ConversationMemoryService


def _entity_refs(finding: dict, kind: str) -> list[int]:
    out = []
    for ref in finding.get("source_entities") or []:
        parts = ref.split("_")
        if len(parts) == 2 and parts[0] == kind and parts[1].isdigit():
            out.append(int(parts[1]))
    return out


class BoardIntelligenceService:
    def __init__(self, session, graph_service: GraphIntelligenceService):
        self.session = session
        self.graph = graph_service
        self.memory = ConversationMemoryService(session)

    # -- public entrypoint ---------------------------------------------

    def build(self, session_id: int) -> dict:
        findings = self.memory.get_all_findings(session_id)
        person_ids = sorted({pid for f in findings for pid in _entity_refs(f, "person")})

        return {
            "evidence_summary": {
                "finding_count": len(findings),
                "persons_referenced": len(person_ids),
            },
            "suggested_links": self._suggested_links(person_ids),
            "hidden_connections": self._hidden_connections(person_ids),
            "contradictions": self._contradictions(findings),
            "missing_evidence": self._missing_evidence(findings),
            "ai_generated_hypotheses": self._hypotheses(findings),
            "evidence_clusters": self._clusters(findings),
            "replay": self._replay(session_id),
        }

    # -- suggested links + relationship confidence ----------------------

    def _suggested_links(self, person_ids: list[int]) -> list[dict]:
        """Direct associate edges (co-accused, phone/account sharing,
        etc.) between people who've actually come up in this
        investigation — not a full graph dump, just the people already on
        (or headed for) the board."""
        links = []
        seen_pairs = set()
        for pid in person_ids:
            for assoc in self.graph.find_associates(pid, limit=5):
                other = assoc["associate_id"]
                if other not in person_ids:
                    continue  # only surface links between entities already in scope
                pair = tuple(sorted((pid, other)))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                links.append({
                    "from": f"person_{pair[0]}",
                    "to": f"person_{pair[1]}",
                    "label": assoc.get("relation_type") or assoc.get("edge_type"),
                    "confidence": assoc.get("strength"),
                    "reason": f"Graph association: {assoc.get('edge_type')}",
                })
        return links

    def _hidden_connections(self, person_ids: list[int]) -> list[dict]:
        """Multi-hop paths between pairs of people who each appear in
        this investigation but have no *direct* edge — the "hidden
        connection" a detective board is supposed to surface. Capped to
        avoid O(n^2) graph search on large boards; fine for the scale a
        single investigation session actually reaches."""
        hidden = []
        checked = set()
        capped = person_ids[:12]
        for i, a in enumerate(capped):
            for b in capped[i + 1:]:
                pair = (a, b)
                if pair in checked:
                    continue
                checked.add(pair)
                path = self.graph.find_connection(a, b, max_hops=3)
                if path and len(path) > 2:  # longer than a direct edge
                    hidden.append({
                        "from": f"person_{a}",
                        "to": f"person_{b}",
                        "path": path,
                        "hops": len(path) - 1,
                    })
        return hidden

    # -- contradiction detection -----------------------------------------

    def _contradictions(self, findings: list[dict]) -> list[dict]:
        """The one contradiction shape we actually have data for right
        now: Evidence Validation rejected a finding that shares an entity
        with a finding it accepted. Anything requiring semantic
        comparison of two witness statements' *content* is out of scope
        without an LLM call — flagged, not faked."""
        rejected = [f for f in findings if f.get("validated") is False]
        accepted = [f for f in findings if f.get("validated") is True]
        contradictions = []
        for r in rejected:
            r_entities = set(r.get("source_entities") or [])
            for a in accepted:
                shared = r_entities & set(a.get("source_entities") or [])
                if shared:
                    contradictions.append({
                        "rejected_finding": {"agent": r.get("agent_name"), "summary": r.get("summary")},
                        "conflicts_with": {"agent": a.get("agent_name"), "summary": a.get("summary")},
                        "shared_entities": sorted(shared),
                        "note": r.get("validation_notes"),
                    })
        return contradictions

    # -- missing evidence --------------------------------------------------

    _GAP_PHRASES = ("no property/evidence recorded", "no weapons recorded", "no organization linked")

    def _missing_evidence(self, findings: list[dict]) -> list[dict]:
        """Heuristic gap detection: agents like PropertyIntelligence/
        WeaponIntelligence/OrganizationIntelligence report a specific
        "nothing recorded for this case" sentence when scope is empty —
        that's a genuine investigative gap worth flagging on the board.
        Explicitly excludes `validation_summary` (EvidenceValidation's own
        aggregate finding, e.g. "...3 rejected (no evidence)") — that's a
        meta-statement about *other* findings, not a gap in the case
        itself, and matching it was a false positive caught in testing."""
        gaps = []
        for f in findings:
            if f.get("finding_type") == "validation_summary":
                continue
            summary = (f.get("summary") or "").lower()
            if any(phrase in summary for phrase in self._GAP_PHRASES):
                gaps.append({"agent": f.get("agent_name"), "gap": f.get("summary")})
        return gaps

    # -- hypotheses ----------------------------------------------------

    def _hypotheses(self, findings: list[dict], top_n: int = 5) -> list[dict]:
        candidates = [f for f in findings if f.get("validated") is not False and f.get("confidence")]
        candidates.sort(key=lambda f: f.get("confidence", 0), reverse=True)
        return [
            {
                "title": f.get("finding_type", "").replace("_", " ").title(),
                "body": f.get("summary"),
                "confidence": f.get("confidence"),
                "agent": f.get("agent_name"),
                "source_entities": f.get("source_entities"),
            }
            for f in candidates[:top_n]
        ]

    # -- clustering ------------------------------------------------------

    def _clusters(self, findings: list[dict]) -> list[dict]:
        by_agent = defaultdict(list)
        for f in findings:
            by_agent[f.get("agent_name", "unknown")].append(f.get("finding_type"))
        return [{"label": agent, "member_count": len(items), "finding_types": sorted(set(items))}
                for agent, items in by_agent.items()]

    # -- replay -----------------------------------------------------------

    def _replay(self, session_id: int) -> list[dict]:
        return [
            {
                "turn_index": t.turn_index,
                "query": t.raw_query,
                "resolved_query": t.resolved_query,
                "summary": t.response_summary,
                "timestamp": t.created_at.isoformat(),
            }
            for t in self.memory.get_history(session_id)
        ]
