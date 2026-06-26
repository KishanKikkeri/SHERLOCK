"""
SHERLOCK — Evidence Validation Agent (Phase 5).

The mandatory checkpoint. Always runs, regardless of the investigation
plan. Applies three rules to every finding accumulated in `state["findings"]`:

    no evidence       -> rejected  (validated=False)
    confidence < 0.6   -> flagged   (validated=True, but noted as low confidence)
    otherwise          -> validated (validated=True)

Writes the fully annotated list to `validated_findings` (overwrite field —
this is the version the Chief reads for synthesis), and also emits its own
`validation_summary` AgentFinding for the activity feed / audit trail.
"""

from backend.agents.base.agent import BaseAgent
from backend.agents.base.finding import AgentFinding

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
            annotated.append(f)

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
        annotated.append(summary_finding.to_dict())

        return [summary_finding], {"validated_findings": annotated}
