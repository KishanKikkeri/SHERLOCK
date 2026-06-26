"""
SHERLOCK — SherlockState (Phase 5, frozen).

The single state object that flows through the LangGraph orchestration
graph. `findings` and `audit_trail` use LangGraph's `operator.add` reducer
so every node's contributions accumulate rather than overwrite.

`validated_findings` is written ONCE by the Evidence Validation Agent (full
overwrite, no reducer) — it's the annotated version of `findings` that the
Chief Agent reads when synthesizing the final report.
"""

import operator
from typing import Annotated, Any, TypedDict


class SherlockState(TypedDict, total=False):
    query: str
    conversation_id: str

    investigation_plan: dict          # set once by Chief (plan step)
    active_agents: list                # list[str] — which specialists to run

    findings: Annotated[list, operator.add]          # list[dict] (AgentFinding.to_dict())
    validated_findings: list                          # list[dict], set once by Evidence Validation

    evidence_log: Annotated[list, operator.add]       # list[dict]
    graph_context: dict                # scratch space agents can stash intermediate data in

    final_report: dict                 # set once by Chief (synthesis step)
    audit_trail: Annotated[list, operator.add]        # list[dict] — the investigation activity feed
