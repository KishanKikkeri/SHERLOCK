"""
SHERLOCK — Stage C4: AI Discussion Mode — DiscussionEngine.

Architecture note (read this before touching the frozen graph): the
handover's diagram shows discussion happening *between* the specialist
agents and Chief's response:

    Chief -> Financial -> Behavior -> ... -> Discussion Engine ->
    Consensus -> Chief Response

Golden Rule 4 freezes the existing pipeline exactly as-is
(`chief_plan -> ... -> evidence_validation -> chief_synthesis -> END`,
see orchestrator/graph.py) and Golden Rule 3 forbids modifying agent
reasoning. Inserting a real node between validation and Chief synthesis
would mean editing `chief.synthesis_node` to consume it, which is exactly
the kind of change those rules exist to prevent.

So this sprint makes a deliberate, documented choice: DiscussionEngine
runs on the SAME validated findings the (unmodified) Chief already
synthesized from, as a parallel additive step run right after the graph
completes, not literally intercepted before Chief speaks. The Chief's own
narrative is completely unaffected — Discussion Mode adds a *second,
separate* explanation of the same evidence, surfaced alongside the
existing final report, not folded into it. "New layers should sit beside
it," per the handover's own closing instruction. A future sprint could
revisit literally reordering the graph if that's judged worth breaking
Golden Rule 4 for — that's a product/architecture call above this
sprint's scope, not something to sneak in unilaterally.

What "debate" means here, honestly: specialist agents don't message each
other or see each other's output — that would mean either modifying
agent code (forbidden) or re-running agents with cross-agent context
(a much bigger, riskier change than one sprint should make unilaterally).
"Debate" is this engine (new code, not agent code) reading the *outputs*
different agents already independently produced about the same entity,
and using an LLM (same graceful-degrade pattern as ChiefAgent) to narrate
*why* they land differently — grounded only in each finding's own
`summary`/`evidence`/`confidence`, never inventing a position an agent
didn't actually take.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

DISAGREEMENT_SPREAD_THRESHOLD = 0.35   # confidence spread that counts as "agents disagree"
MAX_DISAGREEMENTS = 8                   # cap explanation generation cost per turn

_ENTITY_REF = re.compile(r"^(person|fir|account|organization|property|weapon|crime|location|officer)_(\d+)$")


@dataclass
class AgentOpinion:
    agent_name: str
    finding_type: str
    claim: str                  # AgentFinding.summary, verbatim — never paraphrased into a new claim
    confidence: float
    evidence: list = field(default_factory=list)
    validated: bool = True
    missing_evidence: bool = False   # True when EvidenceValidation rejected this finding for lack of evidence
    source_entities: list = field(default_factory=list)


@dataclass
class Disagreement:
    entity_kind: str
    entity_id: int
    entity_label: str
    opinions: list        # list[dict] (AgentOpinion.__dict__), the conflicting ones
    confidence_spread: float
    explanation: str


@dataclass
class ConsensusResult:
    overall_confidence: float
    per_agent_confidence: dict          # agent_name -> mean confidence this turn
    consensus_score: float              # 1.0 = full agreement, 0.0 = maximal disagreement, over entities considered
    agreement_count: int                # distinct entities with no disagreement
    disagreement_count: int
    recommended_conclusion: str
    evidence_requests: list             # list[str] — agents that rejected findings for lack of evidence


class DiscussionEngine:
    """Runs over one turn's validated findings. `session` is an optional
    SQLAlchemy session, used only to resolve entity id -> display label
    (same lookup conversation_memory.py uses); pass None to skip labeling
    (labels fall back to "kind #id")."""

    def __init__(self, session=None):
        self.session = session

    # -- step 1: agent opinions -------------------------------------------

    def build_opinions(self, findings: list[dict]) -> list[AgentOpinion]:
        opinions = []
        for f in findings:
            if f.get("finding_type") in ("validation_summary",):
                continue  # meta-finding about the validation pass itself, not an opinion on the case
            opinions.append(AgentOpinion(
                agent_name=f.get("agent_name", "Unknown"),
                finding_type=f.get("finding_type", ""),
                claim=f.get("summary", ""),
                confidence=f.get("confidence", 0.0),
                evidence=f.get("evidence") or [],
                validated=f.get("validated", True),
                missing_evidence=not f.get("evidence"),
                source_entities=f.get("source_entities") or [],
            ))
        return opinions

    # -- step 2: group by shared entity -------------------------------------

    def _group_by_entity(self, opinions: list[AgentOpinion]) -> dict:
        groups: dict[tuple, list[AgentOpinion]] = {}
        for op in opinions:
            for ref in op.source_entities:
                m = _ENTITY_REF.match(ref)
                if not m:
                    continue
                key = (m.group(1), int(m.group(2)))
                groups.setdefault(key, []).append(op)
        return groups

    # -- step 3: debate / disagreement detection ----------------------------

    def detect_disagreements(self, opinions: list[AgentOpinion]) -> list[Disagreement]:
        """An entity counts as "disputed" when 2+ *different* agents have
        an opinion referencing it and their confidence spread exceeds
        DISAGREEMENT_SPREAD_THRESHOLD — the same honest heuristic
        documented in the module docstring: agents never actually see
        each other's claims, so "disagreement" here means "independently
        landed in different places on the same entity", not a literal
        back-and-forth."""
        groups = self._group_by_entity(opinions)
        disagreements = []
        for (kind, entity_id), group_opinions in groups.items():
            by_agent = {}
            for op in group_opinions:
                if op.missing_evidence:
                    continue  # abstaining ("no data") isn't a position to disagree with — see evidence_requests instead
                by_agent.setdefault(op.agent_name, []).append(op)
            if len(by_agent) < 2:
                continue  # only one agent has a substantive opinion here — nothing to disagree with

            agent_confidences = [max(o.confidence for o in ops) for ops in by_agent.values()]
            spread = max(agent_confidences) - min(agent_confidences)
            if spread <= DISAGREEMENT_SPREAD_THRESHOLD:
                continue

            # Take each agent's single highest-confidence opinion on this entity for the explanation.
            representative = [max(ops, key=lambda o: o.confidence) for ops in by_agent.values()]
            label = self._label_for(kind, entity_id)
            explanation = self._explain_disagreement(label, representative)
            disagreements.append(Disagreement(
                entity_kind=kind, entity_id=entity_id, entity_label=label,
                opinions=[asdict(o) for o in representative],
                confidence_spread=round(spread, 3),
                explanation=explanation,
            ))
            if len(disagreements) >= MAX_DISAGREEMENTS:
                break
        return disagreements

    # -- step 4: consensus ---------------------------------------------------

    def compute_consensus(self, opinions: list[AgentOpinion], disagreements: list[Disagreement]) -> ConsensusResult:
        validated_ops = [o for o in opinions if o.validated and not o.missing_evidence]
        overall_confidence = round(sum(o.confidence for o in validated_ops) / len(validated_ops), 3) if validated_ops else 0.0

        per_agent: dict[str, list[float]] = {}
        for o in opinions:
            per_agent.setdefault(o.agent_name, []).append(o.confidence)
        per_agent_confidence = {a: round(sum(c) / len(c), 3) for a, c in per_agent.items()}

        entities_considered = len(self._group_by_entity(opinions))
        disagreement_count = len(disagreements)
        agreement_count = max(entities_considered - disagreement_count, 0)
        consensus_score = round(agreement_count / entities_considered, 3) if entities_considered else 1.0

        evidence_requests = sorted({o.agent_name for o in opinions if o.missing_evidence})

        recommended_conclusion = self._recommend_conclusion(validated_ops, disagreements, overall_confidence)

        return ConsensusResult(
            overall_confidence=overall_confidence,
            per_agent_confidence=per_agent_confidence,
            consensus_score=consensus_score,
            agreement_count=agreement_count,
            disagreement_count=disagreement_count,
            recommended_conclusion=recommended_conclusion,
            evidence_requests=evidence_requests,
        )

    def _recommend_conclusion(self, validated_ops: list[AgentOpinion], disagreements: list[Disagreement],
                               overall_confidence: float) -> str:
        if not validated_ops:
            return "No validated findings support a conclusion this turn."
        top = max(validated_ops, key=lambda o: o.confidence)
        base = f'Highest-confidence finding ({top.confidence:.0%}, {top.agent_name}): {top.claim}'
        if disagreements:
            base += (f" Note: {len(disagreements)} entit{'y has' if len(disagreements) == 1 else 'ies have'} "
                     f"conflicting agent assessments — see disagreements before treating this as settled.")
        return base

    # -- explanations (LLM if available, deterministic template otherwise) --

    def _explain_disagreement(self, entity_label: str, representative: list[AgentOpinion]) -> str:
        if os.getenv("ANTHROPIC_API_KEY"):
            try:
                return self._explain_disagreement_llm(entity_label, representative)
            except Exception:
                logger.warning("LLM disagreement explanation failed, falling back to template", exc_info=True)
        return self._explain_disagreement_template(entity_label, representative)

    def _explain_disagreement_template(self, entity_label: str, representative: list[AgentOpinion]) -> str:
        ordered = sorted(representative, key=lambda o: -o.confidence)
        parts = [f'{o.agent_name} ({o.confidence:.0%} confidence) says: {o.claim}' for o in ordered]
        return f"Regarding {entity_label} — " + " However, ".join(parts) + \
            " Therefore this entity needs review before being treated as settled."

    def _explain_disagreement_llm(self, entity_label: str, representative: list[AgentOpinion]) -> str:
        from anthropic import Anthropic

        client = Anthropic()
        positions = "\n".join(
            f"- {o.agent_name} (confidence {o.confidence:.0%}): \"{o.claim}\" "
            f"[evidence: {', '.join(o.evidence) if o.evidence else 'none recorded'}]"
            for o in sorted(representative, key=lambda o: -o.confidence)
        )
        prompt = (
            f"Two or more SHERLOCK specialist agents produced different-confidence "
            f"findings about the same entity ({entity_label}) in a crime intelligence "
            f"investigation. State plainly what each agent concluded and why the "
            f"confidence differs, in 2-3 sentences, in the style: '<Agent> suggests X. "
            f"<Agent> disagrees because Y. Therefore...'. Only use the facts given below "
            f"— do not invent evidence, names, or numbers not present here.\n\n{positions}"
        )
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text")

    # -- label resolution -----------------------------------------------------

    def _label_for(self, kind: str, entity_id: int) -> str:
        if self.session is None:
            return f"{kind} #{entity_id}"
        try:
            from backend.memory.conversation_memory import _label_for
            return _label_for(self.session, kind, entity_id)
        except Exception:
            return f"{kind} #{entity_id}"

    # -- top-level entry point -------------------------------------------------

    def run(self, query: str, findings: list[dict]) -> dict:
        """Convenience wrapper: opinions -> disagreements -> consensus,
        as a single JSON-able dict ready for streaming/persistence."""
        opinions = self.build_opinions(findings)
        disagreements = self.detect_disagreements(opinions)
        consensus = self.compute_consensus(opinions, disagreements)
        return {
            "query": query,
            "opinions": [asdict(o) for o in opinions],
            "disagreements": [asdict(d) for d in disagreements],
            "consensus": asdict(consensus),
        }
