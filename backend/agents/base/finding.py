"""
SHERLOCK — AgentFinding contract.

Phase 5 baseline (unchanged): every specialist agent returns one or more
`AgentFinding` objects. No agent returns free-form text to another agent
— this dataclass is the only currency that flows through the
orchestration graph. The Evidence Validation Agent annotates these
(`validated`, `validation_notes`); the Chief Agent reads only validated
findings when synthesizing the final report.

Sprint B5 upgrade (Stage B Division 15, "Explainability"): the brief
asks for every finding to carry Evidence -> Reasoning -> Confidence ->
Supporting Graph -> Related Documents. Evidence and Confidence already
existed. Three new fields added below — `reasoning`, `supporting_graph`,
`related_documents` — all with defaults, so every one of the ~16 existing
agent files (all of which construct `AgentFinding` via keyword arguments)
needed ZERO changes to keep working. Rather than editing every agent to
populate these individually, they're auto-derived centrally by
`backend/agents/base/explainability.py`, applied to every finding at the
Evidence Validation stage — the one point in the pipeline that already
touches every finding regardless of which agent produced it. See that
module's docstring for why this approach was chosen over touching each
agent file.
"""

from dataclasses import dataclass, field, asdict


@dataclass
class AgentFinding:
    agent_name: str
    finding_type: str
    summary: str
    evidence: list = field(default_factory=list)          # list[str]
    confidence: float = 0.0
    source_entities: list = field(default_factory=list)   # list[str], e.g. "person_123"
    metadata: dict = field(default_factory=dict)

    # Populated by the Evidence Validation Agent — never set by the
    # producing agent itself.
    validated: bool = False
    validation_notes: str = ""

    # Sprint B5 — populated by backend/agents/base/explainability.py at
    # validation time, not by the producing agent. Defaults keep every
    # existing agent construction call unchanged.
    reasoning: str = ""
    supporting_graph: dict = field(default_factory=dict)
    related_documents: list = field(default_factory=list)  # list[str], e.g. "FIR-2026-0099"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentFinding":
        return cls(**d)
