# SHERLOCK — Agent Design Specifications

---

## Orchestrator: Chief Investigation Officer

**File:** `backend/agents/chief/agent.py`
**always_runs:** True (cannot be skipped)

### Purpose
The only agent allowed to plan. Interprets the natural language query, selects which specialist agents to dispatch, and synthesises the final report from validated findings. Never queries the database or graph directly.

### Two Phases

**Phase 1 — plan_node (entry point)**
- Calls `query_parser.extract_filters(query)` to identify crime type, district, temporal modifiers, intent flags
- Calls `query_parser.plan_agents(filters)` to select active agents
- Writes `investigation_plan` and `active_agents` to state

**Phase 2 — synthesis_node (final node)**
- Reads `validated_findings` (already filtered by Evidence Validation Agent)
- Generates narrative via deterministic template (or Claude API if `ANTHROPIC_API_KEY` is set)
- Writes `final_report` to state

### Confidence strategy
Chief does not produce `AgentFinding` objects — it produces a final report. No confidence scoring at this level.

### Inputs
`state["query"]`

### Outputs
`state["investigation_plan"]`, `state["active_agents"]`, `state["final_report"]`, `state["audit_trail"]`

---

## Tier 1: Crime Records Agent

**File:** `backend/agents/crime_records/agent.py`
**Name in plan:** `CrimeRecords`

### Purpose
Pure fact retrieval. No analysis, no inference. Given filters from the investigation plan, returns matching crimes and FIRs from PostgreSQL. Stashes crime IDs and accused person IDs in `graph_context` for downstream agents.

### Tools
SQLAlchemy queries: `Crime JOIN Location`, filter by `type`, `district`, `timestamp.month`

### Inputs
`state["investigation_plan"]["filters"]` — crime_type, district, festival_season

### Outputs
One `AgentFinding` of type `case_records`:
- `summary`: "Retrieved N crime FIR(s) [in district] [during festival season]"
- `evidence`: Sample FIR numbers (up to 5)
- `confidence`: 1.0 (direct database facts — certainty is always 100%)
- `metadata`: full crime_ids, accused_person_ids lists

Also writes `graph_context.crime_ids` and `graph_context.accused_person_ids` for Network Analysis and Financial agents.

### Confidence strategy
Always 1.0 — this agent retrieves facts, not inferences.

---

## Tier 2: Network Analysis Agent

**File:** `backend/agents/network_analysis/agent.py`
**Name in plan:** `NetworkAnalysis`

### Purpose
Relationship intelligence. Uses only `graph_service.*` calls — never touches SQL. Identifies repeat offenders within the crime scope established by Crime Records, then finds the associate network of the top offender.

### Tools
```python
graph_service.find_repeat_offenders(min_crimes=2, limit=50)
graph_service.find_associates(top_person_id, limit=5)
```

### Inputs
`state["graph_context"]["accused_person_ids"]` (from Crime Records Agent)

### Outputs
Up to 2 `AgentFinding` objects:
1. `repeat_offender_network` — list of top repeat offenders with crime counts
2. `criminal_association` — top offender's named associates with edge types

### Confidence strategy
- 0.92 when scoped to `accused_person_ids` (known case context)
- 0.75 when no case scope is available (all-cases fallback)
- 0.85 for association findings (graph-derived, not documented)

---

## Tier 2: Pattern & MO Agent

**File:** `backend/agents/pattern_analysis/agent.py`
**Name in plan:** `PatternAnalysis`

### Purpose
Temporal and geographic pattern detection. Identifies seasonal concentrations, geographic hotspots, and modus operandi patterns. Generates hotspot forecasts when the query requests them.

### Tools
```python
graph_service.find_location_clusters(crime_type, top_n=50)
```

### Inputs
`state["investigation_plan"]["filters"]` — crime_type, district, wants_forecast

### Outputs
Up to 3 `AgentFinding` objects:
1. `crime_pattern` — top clusters by (district, crime_type, month)
2. `seasonal_spike` — when ≥50% concentration in festival months detected (≥5 cases)
3. `hotspot_forecast` — forward-looking prediction (only if `wants_forecast=True`)

### Confidence strategy
- `crime_pattern`: 0.88 (statistical aggregation)
- `seasonal_spike`: 0.90 (high concentration = strong signal)
- `hotspot_forecast`: 0.70 (heuristic projection, deliberately lower to reflect uncertainty)

---

## Tier 2: Financial Intelligence Agent

**File:** `backend/agents/financial/agent.py`
**Name in plan:** `FinancialAgent`

### Purpose
Money-trail analysis. Identifies flagged mule accounts, finds the hub (highest incoming transaction count), traces all transactions through the network, and characterises the fan-in aggregation pattern.

### Tools
```python
self.session.query(BankAccount).filter_by(is_flagged_mule=True)
graph_service.find_financial_network(hub.id)
```

### Inputs
`state["investigation_plan"]["filters"]["is_financial"]` must be True (else agent skipped)

### Outputs
Up to 2 `AgentFinding` objects:
1. `financial_network` — ring size, hub owner, total suspicious transaction value
2. `suspicious_pattern` — fan-in characterisation with sender list

### Confidence strategy
- `financial_network`: 0.93 (database-confirmed mule flags + transaction records)
- `suspicious_pattern`: 0.89 (pattern inference from confirmed data)

---

## Tier 2: Prevention Intelligence Agent

**File:** `backend/agents/prevention/agent.py`
**Name in plan:** `PreventionAgent`

### Purpose
Converts analytical findings into concrete, prioritised law-enforcement recommendations. Never touches the database or graph — reads only `state["findings"]`.

### Tools
None (pure state reader)

### Inputs
`state["findings"]` — reads seasonal_spike, repeat_offender_network, financial_network findings

### Outputs
Up to 5 `AgentFinding` objects (finding_types: `patrol_strategy`, `surveillance_action`, `prevention_recommendation`):
1. Patrol density increase (always generated if district available)
2. Repeat offender surveillance (if repeat offenders identified)
3. CCTV deployment (if seasonal spike detected)
4. Financial freeze / PMLA referral (if financial ring detected)
5. Inter-district coordination (always generated)

### Confidence strategy
- Patrol: 0.88 (direct implication of pattern data)
- Surveillance: 0.85 (based on confirmed repeat offender count)
- CCTV: 0.82 (heuristic deployment recommendation)
- Financial: 0.91 (directly supported by confirmed mule accounts)
- Coordination: 0.75 (general recommendation, lower certainty)

---

## Governance: Evidence Validation Agent

**File:** `backend/agents/evidence_validation/agent.py`
**always_runs:** True (cannot be skipped)

### Purpose
The mandatory gateway. Every finding produced by any agent must pass three rules before it can appear in the final report. This is the "anti-hallucination" layer — it ensures no claim reaches the Chief without evidence.

### Tools
None (pure state reader)

### Rules

| Rule | Condition | Effect |
|------|-----------|--------|
| No evidence | `finding.evidence == []` | `validated=False`, `validation_notes="rejected: no supporting evidence"` |
| Low confidence | `finding.confidence < 0.60` | `validated=True`, `validation_notes="flagged: low confidence (XX%)"` |
| Valid | evidence present AND confidence ≥ 0.60 | `validated=True`, `validation_notes="validated"` |

### Inputs
`state["findings"]` — all accumulated findings from all agents

### Outputs
- Annotated `validated_findings` list (full overwrite — this is the definitive set)
- One `validation_summary` finding summarising accepted/flagged/rejected counts

### Confidence strategy
Always 1.0 — this agent applies deterministic rules, not probabilistic inference.

---

## Agent Communication Protocol

No agent communicates directly with another. All inter-agent information flows through `SherlockState`:

```
Crime Records Agent writes → graph_context.crime_ids
Network Analysis Agent reads ← graph_context.accused_person_ids

Pattern Agent writes → findings (seasonal_spike, etc.)
Prevention Agent reads ← findings (to derive recommendations)

All agents write → findings (accumulated via operator.add)
Evidence Validation reads ← findings (all of them)
Evidence Validation writes → validated_findings (Chief reads this)
Chief reads ← validated_findings (only validated findings)
```

This architecture means: adding a new agent never requires modifying an existing agent. It only requires wiring a new node into the LangGraph topology and listing it in `query_parser.plan_agents()`.
