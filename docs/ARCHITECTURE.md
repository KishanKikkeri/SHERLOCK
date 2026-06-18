# SHERLOCK — System Architecture

## Overview

SHERLOCK is a multi-layer crime intelligence platform built around a shared **Crime Intelligence Graph**. Unlike a chatbot that routes queries to a single LLM, SHERLOCK mirrors the organisational structure of a real Criminal Investigation Department: a Chief coordinates specialist investigators, each with restricted access, a single responsibility, and structured output requirements.

```
                        ┌────────────────────────────────────┐
                        │     User / Investigator            │
                        └────────────────┬───────────────────┘
                                         │  Natural language query
                        ┌────────────────▼───────────────────┐
                        │    SHERLOCK Command Center         │
                        │  React · WebSocket · D3 · PDF      │
                        └────────────────┬───────────────────┘
                                         │  WS /ws/investigate
                        ┌────────────────▼───────────────────┐
                        │         FastAPI Backend            │
                        │   Investigation Stream · Metrics   │
                        │   Graph API · PDF Export           │
                        └────────────────┬───────────────────┘
                                         │  LangGraph
                        ┌────────────────▼───────────────────┐
                        │   Chief Investigation Officer      │
                        │   Plans · Delegates · Synthesises  │
                        │   (never queries data directly)    │
                        └───┬──────┬──────┬──────┬──────────┘
                            │      │      │      │
               ┌────────────┘  ┌───┘  ┌──┘  ┌──┘
               │               │      │     │
    ┌──────────▼──┐  ┌─────────▼─┐  ┌─▼────▼──┐  ┌──────────────┐
    │Crime Records│  │  Network  │  │Pattern  │  │  Financial   │
    │   Agent     │  │ Analysis  │  │& MO     │  │Intelligence  │
    │             │  │  Agent    │  │Agent    │  │   Agent      │
    └──────────┬──┘  └─────────┬─┘  └─┬───┬──┘  └──────┬───────┘
               │               │      │   │             │
               └───────────────┴──────┘   └─────────────┘
                                      │
                        ┌─────────────▼──────────────────────┐
                        │    Prevention Intelligence Agent   │
                        │  Converts findings → actions       │
                        └─────────────┬──────────────────────┘
                                      │
                        ┌─────────────▼──────────────────────┐
                        │    Evidence Validation Agent       │
                        │  Mandatory gate · rejects          │
                        │  unsupported claims                │
                        └─────────────┬──────────────────────┘
                                      │
                        ┌─────────────▼──────────────────────┐
                        │    GraphIntelligenceService        │
                        │  Abstraction layer — agents never  │
                        │  write Cypher or touch NetworkX    │
                        └──────────┬──────────┬─────────────┘
                                   │          │
                    ┌──────────────▼──┐  ┌────▼────────────────┐
                    │  Neo4j (prod)   │  │  NetworkX (dev)     │
                    │  Cypher queries │  │  In-memory graph    │
                    └──────────────┬──┘  └────┬────────────────┘
                                   │          │
                    ┌──────────────▼──────────▼──────────────┐
                    │         PostgreSQL / SQLite             │
                    │      Source of truth for all records   │
                    └────────────────────────────────────────┘
```

---

## Layer Descriptions

### Layer 1: Command Center (Frontend)

Single-page React application. No build step required — CDN-loaded React + D3.

**Components:**
- **Metrics Strip** — 7 live stats from `GET /metrics`, loaded on page open
- **Investigation Feed** — WebSocket event stream, one entry per agent node
- **Crime Intelligence Graph** — D3 force-directed ego-subgraph around the top identified person, drag + zoom
- **Trend Chart** — Monthly bar chart from Pattern Agent's cluster data, festival months highlighted amber
- **Hotspot Panel** — District ranking bar chart
- **Evidence & Validation Panel** — All validated findings with confidence badges
- **Report Modal** — Full narrative + findings + prevention recommendations + PDF export button
- **Query Bar** — Free-form NL input + 3 quick-query presets

**Communication:** WebSocket for live investigation events; REST for metrics, graph subgraph, and PDF export.

---

### Layer 2: FastAPI Backend

Thin API layer. All business logic lives in the agent pipeline.

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ws/investigate` | WebSocket | Live investigation stream |
| `/metrics` | GET | Dataset + graph statistics |
| `/graph/{person_id}` | GET | Ego-subgraph for visualisation |
| `/export/pdf` | POST | Generate PDF investigation report |
| `/health` | GET | Liveness probe |

**Key design choice:** The WebSocket handler calls `graph.stream()` (LangGraph's streaming mode), which yields a state diff after each node completes. Each diff is translated into an `AgentEvent` and pushed to the frontend immediately — this is what produces the live activity feed.

---

### Layer 3: LangGraph Orchestration

```
chief_plan → crime_records → network_analysis → financial_agent
→ pattern_analysis → prevention_agent → evidence_validation → chief_synthesis → END
```

**SherlockState** flows through the graph, accumulating findings via `operator.add` reducers. Key fields:

| Field | Type | Description |
|-------|------|-------------|
| `query` | str | The original NL query |
| `investigation_plan` | dict | Agent list + extracted filters |
| `active_agents` | list[str] | Which specialists should run |
| `findings` | list[dict] | Accumulated AgentFinding dicts |
| `validated_findings` | list[dict] | Annotated by Evidence Validation |
| `graph_context` | dict | Shared intermediate data (crime_ids, etc.) |
| `audit_trail` | list[dict] | Per-agent status log (the activity feed) |
| `final_report` | dict | Chief's synthesised report |

**Dynamic routing** is implemented inside each node rather than as conditional edges. `BaseAgent.to_node()` checks whether the agent's name is in `active_agents` — if not, it logs a "skipped" entry and returns without doing work. This keeps the graph topology static and simple while still being plan-driven.

---

### Layer 4: Agent Pipeline

See `docs/AGENT_DESIGN.md` for detailed per-agent specifications.

**AgentFinding contract** — the frozen data structure every agent returns:

```python
@dataclass
class AgentFinding:
    agent_name: str       # which agent produced this
    finding_type: str     # e.g. "repeat_offender_network"
    summary: str          # human-readable one-sentence finding
    evidence: list[str]   # citations backing the claim
    confidence: float     # 0.0–1.0
    source_entities: list[str]  # e.g. ["person_123", "crime_456"]
    metadata: dict        # agent-specific structured data
    validated: bool       # set by Evidence Validation Agent
    validation_notes: str # "validated" / "flagged: low confidence" / "rejected: no evidence"
```

**No free-form text between agents.** All inter-agent communication is via `SherlockState` fields containing lists of `AgentFinding` dicts.

---

### Layer 5: GraphIntelligenceService

The abstraction boundary between agents and the graph backend. Agents call five methods:

```python
graph_service.find_repeat_offenders(min_crimes, limit)
graph_service.find_associates(person_id, limit)
graph_service.find_financial_network(account_id, max_hops)
graph_service.find_location_clusters(crime_type, top_n)
graph_service.find_connection(person_a_id, person_b_id, max_hops)
```

Set `GRAPH_BACKEND=networkx` (default, zero setup) or `GRAPH_BACKEND=neo4j` (production). The interface is identical — agents are unaware of which backend they're using.

---

### Layer 6: Crime Intelligence Graph

**Backends:** NetworkX (in-memory, dev/demo) and Neo4j (production, docker-compose).

**Nodes:** Person · Crime · FIR · Location · Vehicle · Phone · BankAccount · Transaction

**Relationships (11 types):**

| Relationship | From → To | Description |
|-------------|-----------|-------------|
| PERSON_COMMITTED_CRIME | Person → Crime | Accused role link |
| PERSON_INVOLVED_IN_FIR | Person → FIR | Victim / witness role link |
| PERSON_ASSOCIATED_WITH | Person ↔ Person | Social/criminal association |
| PERSON_LINKED_TO_PERSON | Person ↔ Person | Co-occurrence on same crime |
| PERSON_OWNS_PHONE | Person → Phone | Asset ownership |
| PERSON_OWNS_ACCOUNT | Person → BankAccount | Asset ownership |
| PERSON_OWNS_VEHICLE | Person → Vehicle | Asset ownership |
| CRIME_OCCURRED_AT | Crime → Location | Geographic link |
| CRIME_LINKED_TO_FIR | Crime → FIR | Official record link |
| ACCOUNT_SENT_TRANSACTION | BankAccount → Transaction | Financial flow |
| TRANSACTION_TO_ACCOUNT | Transaction → BankAccount | Financial flow |

The graph is built from PostgreSQL by a pipeline (`backend/graph/builder_networkx.py` or `builder_neo4j.py`) using batched UNWIND/MERGE writes — idempotent and re-runnable.

---

### Layer 7: PostgreSQL / SQLite

Source of truth for all raw records. The graph is a derived view — if rebuilt from scratch, it produces the same structure. SQLAlchemy ORM with the following tables:

`persons` · `person_aliases` · `locations` · `crimes` · `firs` · `person_crime_links` · `vehicles` · `phones` · `bank_accounts` · `transactions` · `person_associations`

`person_aliases` exists specifically for Entity Resolution — it holds ground-truth name variants (e.g. "Ravi Kumar" → ["R Kumar", "R. Kumar", "Ravi K"]) so the resolution agent's accuracy can be scored.

---

## Data Flow: Single Investigation

```
1. User submits: "Show repeat burglary offenders in Mysuru during festival season"

2. Chief Agent (plan_node):
   - query_parser extracts: crime_type=burglary, district=Mysuru, festival_season=True
   - plan_agents returns: ["CrimeRecords","NetworkAnalysis","PatternAnalysis","PreventionAgent"]
   - SherlockState.active_agents set

3. Crime Records Agent:
   - SQL query: Crime JOIN Location WHERE type=burglary AND district=Mysuru
   - Filter: timestamp.month IN {9,10,11}
   - Returns: 110 FIRs, stashes crime_ids + accused_person_ids in graph_context

4. Network Analysis Agent:
   - graph_service.find_repeat_offenders(min_crimes=2, limit=50)
   - Filters to accused persons from graph_context
   - graph_service.find_associates(top_offender.person_id)
   - Returns: 2 findings (repeat offenders + associate network)

5. Financial Agent: skipped (not in plan)

6. Pattern & MO Agent:
   - graph_service.find_location_clusters(crime_type="burglary", top_n=50)
   - Filters to Mysuru, computes festival_share = 110/117 = 94%
   - Emits: crime_pattern + seasonal_spike + hotspot_forecast findings

7. Prevention Agent:
   - Reads state["findings"] from steps 3–6
   - Emits: patrol_strategy + surveillance_action + prevention_recommendation (×2) findings

8. Evidence Validation Agent:
   - Checks all 10 findings: evidence present? confidence ≥ 60%?
   - Annotates: 10 validated, 0 rejected
   - Writes to validated_findings

9. Chief Agent (synthesis_node):
   - Reads validated_findings (10 accepted)
   - Generates narrative (template or Claude if API key set)
   - Writes final_report

10. WebSocket stream emits report_ready event → frontend opens report modal
```

---

## Key Design Decisions

### Why static graph topology with plan-driven skipping?

Conditional edges in LangGraph are more complex to debug and extend. With static topology, adding a new agent is: implement it, add a node, add it to the chain. The plan-driven skipping inside `BaseAgent.to_node()` provides the same flexibility without topology redesign.

### Why two graph backends?

Neo4j requires Docker and connection management — too much friction for the first `git clone`. NetworkX gives identical results for demo-scale data and zero setup. The `GraphIntelligenceService` abstraction means switching is one environment variable.

### Why PostgreSQL as source of truth instead of letting Neo4j be primary?

Neo4j is optimised for traversal, not for bulk record management, complex joins, or data integrity constraints. By keeping PostgreSQL as the canonical store and Neo4j as a derived intelligence layer, the system is more resilient and easier to migrate to real police data formats.

### Why is the narrative optionally LLM-generated?

The pipeline is fully functional without an LLM API key — the Chief Agent falls back to a deterministic template. This ensures the system works in offline/air-gapped environments (common in law enforcement). The LLM upgrade is one environment variable: `ANTHROPIC_API_KEY`.
