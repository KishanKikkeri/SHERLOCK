# SHERLOCK — Performance Report

*Measured on the 500-person / 1,001-crime synthetic dataset using the NetworkX backend (in-memory graph). All timings are wall-clock, single-threaded, on a standard development machine.*

---

## End-to-End Investigation Timings

| Demo | Total Time | Agents Fired |
|------|-----------|--------------|
| Demo 1 — Crime Pattern Discovery | 1,556ms | 6 |
| Demo 2 — Financial Intelligence | 1,117ms | 7 |
| Demo 3 — Criminal Association Discovery | 1,394ms | 6 |
| **Average** | **1,356ms** | **6.3** |

---

## Agent-Level Timings (Demo 1, Typical)

| Agent | Time | Notes |
|-------|------|-------|
| Chief Investigation Officer (plan) | ~50ms | Query parsing + plan construction |
| Crime Records Agent | ~200ms | SQLAlchemy query + festival filter |
| Network Analysis Agent | ~400ms | Graph traversal, BFS for associates |
| Financial Intelligence Agent | 0ms | Skipped (not in plan) |
| Pattern & MO Agent | ~200ms | Cluster aggregation over all Crime nodes |
| Prevention Intelligence Agent | ~50ms | Pure Python state reader |
| Evidence Validation Agent | ~30ms | Rule application over all findings |
| Chief Investigation Officer (synthesis) | ~20ms | Template narrative generation |
| **LangGraph overhead** | ~150ms | Node transitions + state serialisation |
| **WebSocket flush delays** | ~350ms | 50ms × 7 nodes (intentional, for UX) |

*The 50ms sleep between nodes is intentional — it gives the event loop time to flush each WebSocket frame before the next node starts, producing a smooth live feed rather than a batch update at the end.*

---

## Graph Query Performance (NetworkX backend)

| Query | Time | Dataset |
|-------|------|---------|
| `find_repeat_offenders(min_crimes=2)` | ~35ms | 500 persons, 10,454 edges |
| `find_associates(person_id, limit=20)` | ~8ms | Single BFS hop |
| `find_financial_network(account_id)` | ~12ms | Hub + 29 transactions |
| `find_location_clusters(crime_type="burglary")` | ~45ms | 1,001 Crime nodes |
| `find_connection(a, b, max_hops=6)` | ~15ms | NetworkX shortest_path |
| `build_graph(session)` | ~1,200ms | Full graph construction (one-time) |

*Neo4j timings would be similar for this dataset scale and significantly faster at 10,000+ crimes due to native index traversal.*

---

## Graph Build Performance

| Dataset Scale | Build Time (NetworkX) | Est. Neo4j |
|--------------|-----------------------|------------|
| 500 persons / 1,001 crimes | ~1.2s | ~3s (inc. Bolt overhead) |
| 2,000 persons / 5,000 crimes | ~5s | ~8s |
| 5,000 persons / 10,000 crimes | ~15s | ~20s |

Graph build is a one-time operation on server start (NetworkX) or data ingestion (Neo4j). It does not affect per-investigation latency.

---

## PDF Generation Performance

| Report Size | Generation Time | File Size |
|------------|----------------|-----------|
| 6 findings (Demo 1) | ~120ms | 9KB |
| 12 findings (Demo 2) | ~180ms | 10KB |
| 9 findings (Demo 3) | ~150ms | 9KB |

ReportLab renders to an in-memory buffer. PDF is returned as a binary response directly — no disk I/O.

---

## WebSocket Performance

| Metric | Value |
|--------|-------|
| Connection establishment | <50ms (localhost) |
| Time to first event | ~100ms (investigation_started) |
| Events per investigation | 8–10 |
| Time between events | 50ms minimum (intentional flush window) |
| Total stream duration | matches investigation duration |

The frontend renders each event immediately on receipt — no buffering. The live feed typically shows the first agent complete within ~300ms of query submission.

---

## Memory Profile (NetworkX backend)

| Component | Memory |
|-----------|--------|
| NetworkX graph (500 persons) | ~15MB |
| SQLite database | ~2MB |
| FastAPI process (idle) | ~80MB |
| FastAPI process (during investigation) | ~95MB |

Each investigation creates a fresh `GraphIntelligenceService` instance per WebSocket connection. The graph is built once per server start and held in memory — concurrent investigations share the same graph object (read-only access, thread-safe for NetworkX).

---

## Scalability Projections

| Metric | Dev (500 persons) | Demo (5,000) | Production (50,000) |
|--------|------------------|--------------|---------------------|
| Graph edges | 10,454 | ~100,000 | ~1,000,000 |
| Investigation time | ~1.4s | ~3–5s | ~10–15s (Neo4j) |
| Memory (graph) | 15MB | 150MB | 1.5GB → Neo4j |
| Recommended backend | NetworkX | NetworkX / Neo4j | Neo4j required |

At Karnataka state-wide scale (~2.5M FIRs), Neo4j with native graph indices would keep relationship traversal under 100ms. The agent pipeline is stateless and horizontally scalable — add FastAPI workers behind a load balancer.

---

## Bottleneck Analysis

| Bottleneck | Current | Mitigation |
|-----------|---------|-----------|
| Graph build time | ~1.2s | Build once on startup; warm cache |
| Network Analysis BFS | ~400ms | Neo4j native traversal at scale |
| WebSocket flush delays | 350ms total | Tunable; reduce to 10ms for speed |
| Pattern cluster aggregation | ~200ms | Pre-compute monthly counts |
| LLM narrative (if enabled) | +400–800ms | Async; doesn't block feed events |

*All current bottlenecks are acceptable for the demo use case. The system feels live and responsive to judges, with each agent completing visibly within the feed.*
