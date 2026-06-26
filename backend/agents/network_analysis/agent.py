"""
SHERLOCK — Network Analysis Agent (Phase 5).

Uses ONLY `graph_service.*` (find_repeat_offenders, find_associates,
find_connection) — never touches SQL or Cypher directly. Scopes its
analysis to the accused persons identified by the Crime Records Agent
(via `graph_context["accused_person_ids"]`), if available.
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding


class NetworkAnalysisAgent(BaseAgent):
    name = "NetworkAnalysis"

    def __init__(self, graph_service):
        self.graph_service = graph_service

    def run(self, state: dict):
        gctx = state.get("graph_context", {})
        accused_person_ids = set(gctx.get("accused_person_ids", []))

        repeat_offenders = self.graph_service.find_repeat_offenders(min_crimes=2, limit=50)

        findings = []

        if accused_person_ids:
            relevant = [r for r in repeat_offenders if r["person_id"] in accused_person_ids]
            scope_note = "within this investigation's case set"
            confidence = 0.92
        else:
            relevant = repeat_offenders
            scope_note = "across all cases (no case scope from Crime Records)"
            confidence = 0.75

        relevant.sort(key=lambda r: r["crime_count"], reverse=True)
        top = relevant[:5]

        if top:
            names = ", ".join(f"{r['name']} ({r['crime_count']} crimes)" for r in top)
            findings.append(AgentFinding(
                agent_name=self.name,
                finding_type="repeat_offender_network",
                summary=f"Identified {len(relevant)} repeat offender(s) {scope_note}: {names}",
                evidence=[f"{r['name']}: {r['crime_count']} PERSON_COMMITTED_CRIME relationships" for r in top],
                confidence=confidence,
                source_entities=[f"person_{r['person_id']}" for r in top],
                metadata={"repeat_offenders": top},
            ))

            # Associate network for the top offender
            top_person = top[0]
            associates = self.graph_service.find_associates(top_person["person_id"], limit=5)
            if associates:
                assoc_desc = ", ".join(
                    f"{a['name']} ({a.get('relation_type') or a['edge_type']})" for a in associates
                )
                findings.append(AgentFinding(
                    agent_name=self.name,
                    finding_type="criminal_association",
                    summary=(
                        f"{top_person['name']} (the top repeat offender) is connected to "
                        f"{len(associates)} associate(s): {assoc_desc}"
                    ),
                    evidence=[f"PERSON_ASSOCIATED_WITH / PERSON_LINKED_TO_PERSON edges in the Crime Intelligence Graph"],
                    confidence=0.85,
                    source_entities=[f"person_{top_person['person_id']}"] + [f"person_{a['associate_id']}" for a in associates],
                    metadata={"associates": associates},
                ))
        else:
            findings.append(AgentFinding(
                agent_name=self.name,
                finding_type="repeat_offender_network",
                summary="No repeat offenders (>=2 crimes) found for this query's scope.",
                evidence=[],
                confidence=0.5,
                source_entities=[],
                metadata={},
            ))

        return findings
