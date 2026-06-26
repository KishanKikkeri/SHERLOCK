# SHERLOCK — Future Roadmap

## Phase 1 (Current — Hackathon Submission)

✅ Crime Intelligence Graph (Neo4j + NetworkX)
✅ Multi-agent LangGraph pipeline (7 agents)
✅ Real-time WebSocket activity feed
✅ Criminal network analysis
✅ Crime pattern discovery (seasonal, geographic)
✅ Financial crime intelligence (money-mule detection)
✅ Prevention intelligence recommendations
✅ Explainable AI (evidence validation gate)
✅ PDF investigation report export
✅ React Command Center with D3 force graph

---

## Phase 2 — Language & Accessibility

**Kannada language support**
- Google Translate API or IndicBERT for Kannada ↔ English translation
- Query input accepted in Kannada
- Report narrative generated in Kannada
- Activity feed messages in Kannada

**Voice interface**
- Browser Web Speech API for query input
- Text-to-speech for report summary
- Hands-free operation for field investigators

*Priority: High — Karnataka Police investigators may prefer Kannada-first interfaces*

---

## Phase 3 — Advanced Intelligence Agents

**Dedicated Forecasting Agent**
- ML-backed hotspot prediction (replacing heuristic seasonal analysis)
- Time-series modelling on historical crime data
- Confidence intervals on predictions
- Early-warning alerts for predicted spikes

**Sociological Intelligence Agent**
- Demographic risk factor analysis
- Economic indicator correlation
- Social infrastructure mapping
- Vulnerability index per district

**Behavioral Profiling Agent**
- Modus operandi clustering (unsupervised)
- Recidivism risk scoring
- Cross-case behavioral signature matching

**Entity Resolution Agent**
- Automated name deduplication ("Ravi Kumar" / "R. Kumar" / "Ravi K")
- Fuzzy matching + graph-based resolution
- Confidence scoring on merged identities
- Ground-truth validation against known aliases

---

## Phase 4 — Integration & Scale

**Real data integration**
- CCTNS (Crime and Criminal Tracking Network System) API connector
- Live FIR ingestion pipeline
- Incremental graph updates (no full rebuild)
- Data validation and schema mapping

**Multi-district deployment**
- Role-based access control (RBAC)
- Constable / Inspector / Superintendent / Commissioner views
- District-level data isolation with cross-district intelligence sharing
- Audit logging for all data access

**Advanced graph algorithms**
- Community detection (Louvain, Label Propagation)
- Centrality scoring (betweenness, eigenvector)
- Gang/network cluster identification
- Temporal graph analysis (how networks evolve over time)

---

## Phase 5 — Operational Intelligence

**Live investigation mode**
- Real-time FIR ingestion → immediate graph update → agent re-analysis
- Alert triggers: "new FIR matches active investigation"
- Cross-case correlation as cases are filed

**Collaboration tools**
- Investigation assignments and handoffs
- Shared investigation workspaces
- Comment threads on findings
- Chain-of-custody tracking for digital evidence

**Mobile interface**
- React Native app for field investigators
- Offline-capable investigation history
- Push alerts for hotspot warnings

---

## Phase 6 — Advanced AI

**LLM-enhanced analysis**
- All agents upgraded to use Claude for reasoning (currently deterministic)
- Multi-turn investigation dialogue
- Clarification questions for ambiguous queries
- Counter-factual reasoning ("what if this person wasn't in the ring?")

**Confidence calibration**
- Bayesian confidence scoring based on evidence quality
- Cross-agent confidence reconciliation
- Uncertainty quantification in forecasts

**Explainability dashboard**
- Visual reasoning trace for each finding
- Evidence contribution weighting
- Sensitivity analysis ("what would change this conclusion?")

---

## Technical Debt & Hardening

| Item | Priority | Notes |
|------|----------|-------|
| Production Docker setup | High | Dockerfile.backend + compose.prod.yml |
| HTTPS / TLS | High | Required for production WebSocket |
| API authentication | High | JWT or API key for all endpoints |
| Rate limiting | Medium | Per-IP investigation limits |
| Graph caching | Medium | Pre-warm on startup, incremental updates |
| Test suite | Medium | pytest coverage for all agents |
| Observability | Low | OpenTelemetry traces, Prometheus metrics |

---

## Competitive Positioning

SHERLOCK is designed to be extensible without architectural changes. Adding a new specialist agent requires:
1. Create `backend/agents/{name}/agent.py` extending `BaseAgent`
2. Add the agent to `build_investigation_graph()` in `orchestrator/graph.py`
3. Add the agent name to `plan_agents()` in `query_parser.py`

No existing code changes required. This makes the system genuinely production-extensible, not just a hackathon prototype.
