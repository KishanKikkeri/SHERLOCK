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

✅ **Entity Resolution Agent** — implemented. Exact → known-alias → fuzzy (`difflib`) resolution of `PersonCrimeLink.raw_name_used` against canonical `Person`/`PersonAlias`. See `docs/AGENT_DESIGN.md`.

✅ **Dedicated Forecasting Agent** — implemented. Replaces the heuristic placeholder that lived inline in Pattern Analysis with a real per-district monthly time series + OLS linear trend fit. Still not ML-backed time-series modelling with confidence intervals — that's a real step up from here, not done yet — but it's a genuine fit over real data, not a single heuristic ratio.

✅ **Timeline Reconstruction Agent** *(not originally listed here, added because it uses the same real `Crime`/`FIR` data and slots into the same "Advanced Intelligence Agents" tier)* — chronological event sequencing + shrinking-gap escalation detection.

✅ **Similar Case Agent** *(same rationale)* — MO similarity matching across cases via `difflib`. Known limitation: the synthetic dataset's small MO vocabulary makes near-100% matches common within a crime type — see `docs/AGENT_DESIGN.md` for detail; this would look very different against real free-text FIR narratives.

**Sociological Intelligence Agent** — not built. Needs demographic/economic indicator data this schema doesn't have (`Person` has no income/education/district-vulnerability fields, and there's no district-level socioeconomic dataset at all). Real work, not a wiring exercise.

**Behavioral Profiling Agent** — not built. MO clustering and cross-case behavioral signature matching need either richer free-text MO data (see Similar Case's limitation above) or a proper embedding-based similarity model; the current MO field is too coarse (a ~23-phrase fixed vocabulary) to cluster meaningfully beyond what Similar Case already surfaces.

---

## Phase 5 roadmap alignment (per the restructured 10-phase plan) — division-by-division status

The broader roadmap's "Phase 5 — Advanced Specialist Divisions" names ~30 agents across 7 divisions. Here's what's actually buildable against *this* data model versus what needs new data first:

**Built (real data, real logic):**
- Intelligence Division: Timeline Reconstruction ✅, Similar Case ✅ (Crime Records / Lead Generation already existed pre-Phase-5)
- Criminal Intelligence Division: Entity Resolution ✅, Forecasting ✅ (Network Analysis / Pattern Analysis already existed)

**Blocked on new data, not just new code:**
- **Financial Intelligence Division** (Crypto Intelligence, Corporate Intelligence) — the schema has `BankAccount`/`Transaction` but no crypto wallet or corporate-entity tables at all.
- **Behavioral Sciences Division** (Victimology, Threat Assessment, Serial Crime Detection, Recidivism Prediction) — `PersonRole` distinguishes victim/accused/witness, so some of this is closer than it looks, but there's no risk/threat scoring history or victim-specific data to build against yet.
- **Digital Forensics Division** (Mobile/Computer Forensics, Metadata, Email/File Intelligence) — zero device/file/email data in the schema.
- **Cyber Crime Division** (Malware, Dark Web, Cryptocurrency Analysis, Infrastructure Mapping) — same gap; `CrimeType.CYBERCRIME` exists as a category but carries no cyber-specific evidence fields.
- **OSINT Division** (News, Social Media, Image, Video, Geo Intelligence) — no external content ingestion at all; `Location` has lat/long so Geo Intelligence is the closest of these to feasible, but still needs a real data source to query against.

Building agents for the blocked divisions without real backing data would mean hardcoding plausible-sounding output with nothing behind it — that's a demo prop, not an agent, so it's left undone rather than faked.

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
