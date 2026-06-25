"""
SHERLOCK — AgentFinding contract (Phase 5, frozen).

Every specialist agent returns one or more `AgentFinding` objects. No agent
returns free-form text to another agent — this dataclass is the only
currency that flows through the orchestration graph. The Evidence
Validation Agent annotates these (`validated`, `validation_notes`); the
Chief Agent reads only validated findings when synthesizing the final
report.
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

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentFinding":
        return cls(**d)
