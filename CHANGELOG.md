# SHERLOCK — Changelog

All notable changes to this project are documented here, organised by build phase.

---

## v1.0.0 — Submission Release

*Phase 7: Documentation, demo polish, and final validation*

- Added Prevention Intelligence Agent (patrol, surveillance, CCTV, PMLA recommendations)
- Added Financial Intelligence Agent (money-mule ring detection, fan-in pattern analysis)
- Added PDF investigation report export (ReportLab, case ID, timeline, confidence heatmap)
- Added "All findings evidence-backed and validated" banner to Command Center header
- Updated quick-query presets to match the three official demo queries exactly
- Fixed financial query routing: NetworkAnalysis now runs for all query types
- Added `docs/pitch_deck.html` — 8-slide keyboard-navigable presentation
- Added `docs/JUDGE_QA.md` — word-for-word answers to 8 judge questions
- Added `docs/DEMO_SCRIPT.md` — timed, narrated demo flow
- Added `docs/ARCHITECTURE.md`, `SYSTEM_DESIGN.md`, `DATA_MODEL.md`, `GRAPH_SCHEMA.md`
- Added `docs/AGENT_DESIGN.md`, `API_REFERENCE.md`, `DEPLOYMENT_GUIDE.md`
- Added `docs/FEATURE_MAPPING.md`, `VALIDATION_REPORT.md`, `PERFORMANCE_REPORT.md`
- Added `docs/FUTURE_ROADMAP.md`, `CONTRIBUTING.md`, `CHANGELOG.md`
- **Validation:** 3/3 demos PASS, 0 rejected findings, avg 1.4s investigation time

---

## v0.6.0 — Command Center

*Phase 6: Frontend + WebSocket streaming*

- Built SHERLOCK Command Center (`frontend/index.html`) — single-file React application
- Dark intelligence aesthetic: IBM Plex Mono + IBM Plex Sans, amber/cyan on near-black
- Live Metrics Strip: 7 stats from `/metrics` endpoint
- Investigation Feed: WebSocket-streamed per-agent events with status icons
- Crime Intelligence Graph: D3 force-directed ego-subgraph, drag + zoom
- Crime Trends Chart: monthly bar chart, festival months highlighted amber
- District Hotspots Panel: ranked bar chart
- Evidence & Validation Panel: findings with confidence badges
- Report Modal: narrative + findings + prevention recommendations + PDF export button
- Query Bar: free-form NL input + quick-query presets + Enter-to-submit
- FastAPI WebSocket endpoint (`/ws/investigate`) with streaming LangGraph integration
- `GET /metrics`, `GET /graph/{person_id}`, `POST /export/pdf`, `GET /health`
- `backend/app/server.py`: single-command startup serving frontend at `/`

---

## v0.5.0 — Intelligence Layer (LangGraph)

*Phase 5: Multi-agent orchestration*

- Implemented `AgentFinding` dataclass — frozen inter-agent contract
- Implemented `SherlockState` TypedDict with `operator.add` reducers
- Implemented `BaseAgent` abstraction with plan-driven skip logic
- Implemented `query_parser.py` — rule-based NLU (crime type, district, intent flags)
- Implemented `ChiefAgent` — `plan_node` + `synthesis_node`, optional Claude narrative
- Implemented `CrimeRecordsAgent` — SQL retrieval, passes `graph_context` downstream
- Implemented `NetworkAnalysisAgent` — repeat offenders + associate networks via graph_service
- Implemented `PatternAnalysisAgent` — clusters, seasonal spikes, hotspot forecasts
- Implemented `EvidenceValidationAgent` — mandatory gate, three validation rules
- Built LangGraph 6-node graph: chief_plan → crime_records → network_analysis → pattern_analysis → evidence_validation → chief_synthesis
- Built `stream_investigation()` — wraps `graph.stream()`, emits WebSocket events per node
- **Milestone:** Demo 1 query answered end-to-end through the full agent pipeline

---

## v0.4.0 — Graph Intelligence Service

*Phase 2C: Query abstraction layer*

- Implemented `GraphIntelligenceService` abstract interface
- Implemented `NetworkXGraphService` with 5 core queries + `get_metrics()`
- Implemented `Neo4jGraphService` with equivalent Cypher queries
- `get_graph_service()` factory: selects backend from `GRAPH_BACKEND` env var
- `find_repeat_offenders()` — PERSON_COMMITTED_CRIME edge counting
- `find_associates()` — PERSON_ASSOCIATED_WITH / PERSON_LINKED_TO_PERSON traversal
- `find_financial_network()` — bidirectional transaction tracing
- `find_location_clusters()` — district/month crime aggregation
- `find_connection()` — shortest path between two persons
- Built `demo_graph_queries.py` — milestone demo validating all 5 queries
- **Milestone:** Crime Intelligence Graph operational, festival-season spike confirmed (94%)

---

## v0.3.0 — Graph Builders

*Phase 2B: SQL → Graph pipeline*

- Implemented `builder_networkx.py` — builds in-memory MultiDiGraph from SQLAlchemy session
- Implemented `builder_neo4j.py` — batched UNWIND/MERGE writes to Neo4j
- Implemented `neo4j_client.py` — driver wrapper with `run_query`, `run_write`, `run_write_batch`
- Implemented `graph/schema.py` — frozen node labels, relationship types, constraint statements
- Added Docker Compose: Postgres + Neo4j services
- All 11 relationship types implemented and verified

---

## v0.2.0 — Synthetic Dataset

*Phase 3: Reproducible test data with injected patterns*

- Implemented `generate_synthetic_data.py` with seeded Faker (Karnataka-specific)
- Injected 4 deliberate patterns: festival spike, repeat offenders, name aliases, money-mule ring
- Implemented `inspect_data.py` for dataset sanity checking
- **Validated:** 92% of Mysuru burglaries in Sep–Nov; top repeat offenders with 20–21 crimes

---

## v0.1.0 — Data Foundation

*Phase 1: Core entities and database layer*

- Defined all 10 SQLAlchemy models: `Person`, `PersonAlias`, `Location`, `Crime`, `FIR`, `PersonCrimeLink`, `Vehicle`, `Phone`, `BankAccount`, `Transaction`, `PersonAssociation`
- Implemented `database/config.py` with SQLite default + Postgres override
- Implemented `CrimeType`, `FIRStatus`, `PersonRole`, `RelationType`, `Gender` enumerations
- Established full repository structure per architecture freeze
- `PersonCrimeLink.raw_name_used` — the entity resolution challenge field
- `BankAccount.is_flagged_mule` and `Transaction.is_suspicious` — financial intelligence flags
