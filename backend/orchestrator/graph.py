"""
SHERLOCK — LangGraph orchestration graph (Phase 5, v1 topology).

```
chief_plan
   |
   v
crime_records
   |
   v
network_analysis
   |
   v
pattern_analysis
   |
   v
evidence_validation
   |
   v
chief_synthesis
   |
   v
  END
```

Topology is static and simple per the Phase 5 brief — "dynamic routing"
happens INSIDE each specialist node: `BaseAgent.to_node()` checks whether
the agent is in `state["active_agents"]` (set by the Chief's plan) and
skips its work (logging a "skipped" activity entry) if not. This means
adding a new specialist later (Financial, Sociological, Forecasting, ...)
is just: implement the agent, add a node, add it to the chain — no
topology redesign needed.
"""

from langgraph.graph import StateGraph, END

from backend.orchestrator.state import SherlockState
from backend.agents.chief.agent import ChiefAgent
from backend.agents.crime_records.agent import CrimeRecordsAgent
from backend.agents.network_analysis.agent import NetworkAnalysisAgent
from backend.agents.pattern_analysis.agent import PatternAnalysisAgent
from backend.agents.evidence_validation.agent import EvidenceValidationAgent
from backend.agents.financial.agent import FinancialAgent
from backend.agents.prevention.agent import PreventionAgent


def build_investigation_graph(session, graph_service):
    """Wire up all agents with their dependencies and compile the graph."""
    chief = ChiefAgent()
    crime_records = CrimeRecordsAgent(session)
    network_analysis = NetworkAnalysisAgent(graph_service)
    financial = FinancialAgent(session, graph_service)
    pattern_analysis = PatternAnalysisAgent(graph_service)
    prevention = PreventionAgent()
    evidence_validation = EvidenceValidationAgent()

    builder = StateGraph(SherlockState)
    builder.add_node("chief_plan",          chief.plan_node)
    builder.add_node("crime_records",       crime_records.to_node())
    builder.add_node("network_analysis",    network_analysis.to_node())
    builder.add_node("financial_agent",     financial.to_node())
    builder.add_node("pattern_analysis",    pattern_analysis.to_node())
    builder.add_node("prevention_agent",    prevention.to_node())
    builder.add_node("evidence_validation", evidence_validation.to_node())
    builder.add_node("chief_synthesis",     chief.synthesis_node)

    builder.set_entry_point("chief_plan")
    builder.add_edge("chief_plan",          "crime_records")
    builder.add_edge("crime_records",       "network_analysis")
    builder.add_edge("network_analysis",    "financial_agent")
    builder.add_edge("financial_agent",     "pattern_analysis")
    builder.add_edge("pattern_analysis",    "prevention_agent")
    builder.add_edge("prevention_agent",    "evidence_validation")
    builder.add_edge("evidence_validation", "chief_synthesis")
    builder.add_edge("chief_synthesis",     END)

    return builder.compile()


def run_investigation(query: str, session, graph_service, conversation_id: str = "demo"):
    """Convenience entry point: build the graph, run it for `query`, return final state."""
    graph = build_investigation_graph(session, graph_service)
    initial_state = {
        "query": query,
        "conversation_id": conversation_id,
        "investigation_plan": {},
        "active_agents": [],
        "findings": [],
        "validated_findings": [],
        "evidence_log": [],
        "graph_context": {},
        "final_report": {},
        "audit_trail": [],
    }
    return graph.invoke(initial_state)
