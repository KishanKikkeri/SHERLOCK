"""
SHERLOCK — Evidence Validation Agent.

Phase 5 baseline (unchanged): the mandatory checkpoint. Always runs,
regardless of the investigation plan. Applies three rules to every
finding accumulated in `state["findings"]`:

    no evidence       -> rejected  (validated=False)
    confidence < 0.6   -> flagged   (validated=True, but noted as low confidence)
    otherwise          -> validated (validated=True)

Writes the fully annotated list to `validated_findings` (overwrite field —
this is the version the Chief reads for synthesis), and also emits its own
`validation_summary` AgentFinding for the activity feed / audit trail.

Sprint B5 upgrade (Stage B Division 15, "Explainability"): this is also
where every finding gets its `reasoning` / `supporting_graph` /
`related_documents` populated (see base/explainability.py's docstring
for why here, not in each producing agent). Chosen specifically because
this node already iterates every finding regardless of source — adding
one function call here reaches all ~30 finding_types across every agent,
current and future, without editing 16 separate agent files.
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding
from backend.agents.base import explainability

MIN_CONFIDENCE = 0.6


class EvidenceValidationAgent(BaseAgent):
    name = "EvidenceValidation"
    always_runs = True

    def run(self, state: dict):
        findings = state.get("findings", [])
        annotated = []

        accepted, flagged, rejected = 0, 0, 0
        for f in findings:
            f = dict(f)  # don't mutate the original dict in state
            if not f.get("evidence"):
                f["validated"] = False
                f["validation_notes"] = "rejected: no supporting evidence"
                rejected += 1
            elif f.get("confidence", 0) < MIN_CONFIDENCE:
                f["validated"] = True
                f["validation_notes"] = f"flagged: low confidence ({f.get('confidence', 0):.0%})"
                flagged += 1
            else:
                f["validated"] = True
                f["validation_notes"] = "validated"
                accepted += 1

            # Sprint B5: enrich every finding with explainability fields,
            # rejected ones included — an investigator should still be able
            # to see *why* something was rejected, not just that it was.
            enriched = explainability.enrich(AgentFinding.from_dict(f))
            annotated.append(enriched.to_dict())

        summary_finding = AgentFinding(
            agent_name=self.name,
            finding_type="validation_summary",
            summary=(
                f"Validated {len(findings)} finding(s): {accepted} accepted, "
                f"{flagged} flagged (low confidence), {rejected} rejected (no evidence)."
            ),
            evidence=[f"Validation rules applied: evidence required, confidence >= {MIN_CONFIDENCE:.0%}"],
            confidence=1.0,
            source_entities=[],
            metadata={"accepted": accepted, "flagged": flagged, "rejected": rejected},
            validated=True,
            validation_notes="validated",
        )
        explainability.enrich(summary_finding)
        annotated.append(summary_finding.to_dict())

        return [summary_finding], {"validated_findings": annotated}
