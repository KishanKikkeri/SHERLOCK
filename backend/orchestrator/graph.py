"""
SHERLOCK — LangGraph orchestration graph (Phase 5, v2 topology).

```
chief_plan
   |
   v
crime_records
   |
   v
case_intelligence        <- Sprint B1
   |
   v
officer_intelligence     <- Sprint B2
   |
   v
witness_intelligence     <- Sprint B2
   |
   v
property_intelligence    <- Sprint B3
   |
   v
weapon_intelligence      <- Sprint B3
   |
   v
organization_intelligence <- Sprint B3
   |
   v
behavioral_intelligence  <- Sprint B4
   |
   v
sociological_intelligence <- Sprint B4
   |
   v
investigation_assignment <- Sprint B2 (gated — see below)
   |
   v
network_analysis
   |
   v
entity_resolution
   |
   v
timeline_reconstruction
   |
   v
financial_agent
   |
   v
similar_case
   |
   v
pattern_analysis
   |
   v
forecasting_agent        <- Sprint B4 upgrade (predictive)
   |
   v
decision_support         <- Sprint B5
   |
   v
prevention_agent
   |
   v
evidence_validation       <- Sprint B5 upgrade (explainability enrichment)
   |
   v
chief_synthesis
   |
   v
  END
```

Topology is still static and linear per the original Phase 5 brief —
"dynamic routing" happens INSIDE each specialist node: `BaseAgent.to_node()`
checks whether the agent is in `state["active_agents"]` (set by the
Chief's plan) and skips its work if not. EntityResolution,
TimelineReconstruction, CaseIntelligence, and every Sprint B2-B5
case-scoped agent (Officer/Witness/Property/Weapon/Organization/
Behavioral/Sociological Intelligence, DecisionSupport) plan-gate to
"always run" — every one of them degrades gracefully to a "nothing on
record" finding when its data isn't present, so unconditional execution
costs almost nothing. SimilarCase gates on a crime type being specified;
Forecasting gates on the query implying a forecast; InvestigationAssignment
(Sprint B2) gates on explicit assignment-intent keywords, since "who
should investigate this" is a different question from "what do we know
about this case" — see `plan_agents()` in query_parser.py.
"""

from langgraph.graph import StateGraph, END

from backend.orchestrator.state import SherlockState
from backend.agents.chief.agent import ChiefAgent
from backend.agents.crime_records.agent import CrimeRecordsAgent
from backend.agents.case_intelligence.agent import CaseIntelligenceAgent
from backend.agents.officer_intelligence.agent import OfficerIntelligenceAgent
from backend.agents.witness_intelligence.agent import WitnessIntelligenceAgent
from backend.agents.property_intelligence.agent import PropertyIntelligenceAgent
from backend.agents.weapon_intelligence.agent import WeaponIntelligenceAgent
from backend.agents.organization_intelligence.agent import OrganizationIntelligenceAgent
from backend.agents.behavioral_intelligence.agent import BehavioralIntelligenceAgent
from backend.agents.sociological_intelligence.agent import SociologicalIntelligenceAgent
from backend.agents.investigation_assignment.agent import InvestigationAssignmentAgent
from backend.agents.decision_support.agent import DecisionSupportAgent
from backend.agents.network_analysis.agent import NetworkAnalysisAgent
from backend.agents.entity_resolution.agent import EntityResolutionAgent
from backend.agents.timeline_reconstruction.agent import TimelineReconstructionAgent
from backend.agents.pattern_analysis.agent import PatternAnalysisAgent
from backend.agents.similar_case.agent import SimilarCaseAgent
from backend.agents.forecasting.agent import ForecastingAgent
from backend.agents.evidence_validation.agent import EvidenceValidationAgent
from backend.agents.financial.agent import FinancialAgent
from backend.agents.prevention.agent import PreventionAgent


def build_investigation_graph(session, graph_service):
    """Wire up all agents with their dependencies and compile the graph."""
    chief = ChiefAgent()
    crime_records = CrimeRecordsAgent(session)
    case_intelligence = CaseIntelligenceAgent(session)
    officer_intelligence = OfficerIntelligenceAgent(session)
    witness_intelligence = WitnessIntelligenceAgent(session)
    property_intelligence = PropertyIntelligenceAgent(session)
    weapon_intelligence = WeaponIntelligenceAgent(session)
    organization_intelligence = OrganizationIntelligenceAgent(session)
    behavioral_intelligence = BehavioralIntelligenceAgent(session)
    sociological_intelligence = SociologicalIntelligenceAgent(session)
    investigation_assignment = InvestigationAssignmentAgent(session)
    decision_support = DecisionSupportAgent(session)
    network_analysis = NetworkAnalysisAgent(graph_service)
    entity_resolution = EntityResolutionAgent(session)
    timeline_reconstruction = TimelineReconstructionAgent(session)
    financial = FinancialAgent(session, graph_service)
    similar_case = SimilarCaseAgent(session)
    pattern_analysis = PatternAnalysisAgent(graph_service)
    forecasting = ForecastingAgent(graph_service, session)
    prevention = PreventionAgent()
    evidence_validation = EvidenceValidationAgent()

    builder = StateGraph(SherlockState)
    builder.add_node("chief_plan",              chief.plan_node)
    builder.add_node("crime_records",           crime_records.to_node())
    builder.add_node("case_intelligence",       case_intelligence.to_node())
    builder.add_node("officer_intelligence",    officer_intelligence.to_node())
    builder.add_node("witness_intelligence",    witness_intelligence.to_node())
    builder.add_node("property_intelligence",   property_intelligence.to_node())
    builder.add_node("weapon_intelligence",     weapon_intelligence.to_node())
    builder.add_node("organization_intelligence", organization_intelligence.to_node())
    builder.add_node("behavioral_intelligence", behavioral_intelligence.to_node())
    builder.add_node("sociological_intelligence", sociological_intelligence.to_node())
    builder.add_node("investigation_assignment", investigation_assignment.to_node())
    builder.add_node("network_analysis",        network_analysis.to_node())
    builder.add_node("entity_resolution",       entity_resolution.to_node())
    builder.add_node("timeline_reconstruction", timeline_reconstruction.to_node())
    builder.add_node("financial_agent",         financial.to_node())
    builder.add_node("similar_case",            similar_case.to_node())
    builder.add_node("pattern_analysis",        pattern_analysis.to_node())
    builder.add_node("forecasting_agent",       forecasting.to_node())
    builder.add_node("decision_support",        decision_support.to_node())
    builder.add_node("prevention_agent",        prevention.to_node())
    builder.add_node("evidence_validation",     evidence_validation.to_node())
    builder.add_node("chief_synthesis",         chief.synthesis_node)

    builder.set_entry_point("chief_plan")
    builder.add_edge("chief_plan",              "crime_records")
    builder.add_edge("crime_records",           "case_intelligence")
    builder.add_edge("case_intelligence",       "officer_intelligence")
    builder.add_edge("officer_intelligence",    "witness_intelligence")
    builder.add_edge("witness_intelligence",    "property_intelligence")
    builder.add_edge("property_intelligence",   "weapon_intelligence")
    builder.add_edge("weapon_intelligence",     "organization_intelligence")
    builder.add_edge("organization_intelligence", "behavioral_intelligence")
    builder.add_edge("behavioral_intelligence",   "sociological_intelligence")
    builder.add_edge("sociological_intelligence", "investigation_assignment")
    builder.add_edge("investigation_assignment", "network_analysis")
    builder.add_edge("network_analysis",        "entity_resolution")
    builder.add_edge("entity_resolution",       "timeline_reconstruction")
    builder.add_edge("timeline_reconstruction", "financial_agent")
    builder.add_edge("financial_agent",         "similar_case")
    builder.add_edge("similar_case",            "pattern_analysis")
    builder.add_edge("pattern_analysis",        "forecasting_agent")
    builder.add_edge("forecasting_agent",       "decision_support")
    builder.add_edge("decision_support",        "prevention_agent")
    builder.add_edge("prevention_agent",        "evidence_validation")
    builder.add_edge("evidence_validation",     "chief_synthesis")
    builder.add_edge("chief_synthesis",         END)

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
