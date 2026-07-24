"""
SHERLOCK — Stage F2 (Conversation Intelligence System): citations.

The investigation pipeline already produces well-structured
`AgentFinding` objects (agent_name, summary, evidence, confidence,
source_entities, reasoning, related_documents — see
backend/agents/base/finding.py). What a chat UI's "Evidence" card needs
that a findings list doesn't hand over directly is each finding's
source entities resolved to human-readable labels (a raw "person_812"
means nothing on screen), so this module does exactly that resolution
and nothing else — it does not touch or re-derive `evidence`,
`reasoning`, or `confidence`, which are already correct.

Same entity-kind vocabulary and DB lookup shape as
`backend/memory/conversation_memory.py`'s `_label_for` (person, fir,
account, organization, property, weapon) — duplicated rather than
imported from that module because that function is a private helper of
a different subsystem's internals, not a shared public API; keeping
this self-contained means Stage C2 can keep changing its own internals
without this module silently breaking.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.database.models import Person, FIR, BankAccount, Organization, Property, Weapon

_ENTITY_REF = re.compile(r"^(person|fir|account|organization|property|weapon)_(\d+)$")

_KIND_MODEL = {
    "person": Person, "fir": FIR, "account": BankAccount,
    "organization": Organization, "property": Property, "weapon": Weapon,
}


def _label_for(db, kind: str, entity_id: int) -> str:
    model = _KIND_MODEL.get(kind)
    if model is None:
        return f"{kind} #{entity_id}"
    row = db.get(model, entity_id)
    if row is None:
        return f"{kind} #{entity_id}"
    if kind == "person":
        return row.name
    if kind == "fir":
        return row.fir_number
    if kind == "account":
        return f"{row.bank} account {row.account_number}"
    if kind == "organization":
        return row.name
    if kind in ("property", "weapon"):
        return row.description or f"{kind} #{entity_id}"
    return f"{kind} #{entity_id}"


@dataclass
class Citation:
    finding_type: str
    agent_name: str
    summary: str
    confidence: float
    validated: bool
    evidence: list = field(default_factory=list)
    reasoning: str = ""
    related_documents: list = field(default_factory=list)
    entities: list = field(default_factory=list)  # [{"kind","id","label"}]

    def to_dict(self) -> dict:
        return {
            "finding_type": self.finding_type,
            "agent_name": self.agent_name,
            "summary": self.summary,
            "confidence": self.confidence,
            "validated": self.validated,
            "evidence": self.evidence,
            "reasoning": self.reasoning,
            "related_documents": self.related_documents,
            "entities": self.entities,
        }


def build_citations(db, findings: list[dict]) -> list[dict]:
    """One Citation per validated finding, in the order the agents
    produced them. Findings that failed the Evidence Validation gate
    (`validated: False`) are omitted entirely — an unvalidated claim has
    no business being presented to an investigator as evidence, even in
    a chat bubble."""
    citations = []
    for f in findings or []:
        if not f.get("validated"):
            continue
        entities = []
        for ref in f.get("source_entities") or []:
            m = _ENTITY_REF.match(ref)
            if not m:
                continue
            kind, entity_id = m.group(1), int(m.group(2))
            entities.append({"kind": kind, "id": entity_id, "label": _label_for(db, kind, entity_id)})

        citations.append(Citation(
            finding_type=f.get("finding_type", ""),
            agent_name=f.get("agent_name", ""),
            summary=f.get("summary", ""),
            confidence=f.get("confidence", 0.0),
            validated=True,
            evidence=f.get("evidence") or [],
            reasoning=f.get("reasoning") or "",
            related_documents=f.get("related_documents") or [],
            entities=entities,
        ).to_dict())
    return citations
