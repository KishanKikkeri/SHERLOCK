# SHERLOCK — System Design

Technical deep dive for engineering reviewers. For the high-level overview, see `ARCHITECTURE.md`.

---

## Backend

### FastAPI Application

**Entry point:** `backend/app/server.py` → `backend/app/main.py`

```
python -m backend.app.server
# Uvicorn on 0.0.0.0:8000
# Serves frontend/index.html at GET /
```

The server creates SQLAlchemy tables on startup (`Base.metadata.create_all(engine)`) so the database is always ready before the first request.

CORS is fully open (`allow_origins=["*"]`) for hackathon convenience. Production would scope this to the known frontend origin.

**Endpoints:**

```
WS  /ws/investigate          Live investigation stream
GET /metrics                 Dataset + graph statistics (JSON)
GET /graph/{person_id}       Ego-subgraph for D3 visualisation
POST /export/pdf             Generate PDF from final_report dict
GET /health                  {"status": "operational"}
GET /                        Serves frontend/index.html
```

### WebSocket Investigation Stream

`backend/api/investigation_stream.py`

The core streaming loop:

```python
graph = build_investigation_graph(session, graph_service)
for step in graph.stream(initial_state):
    node_name, node_state = next(iter(step.items()))
    # node_state contains the diff produced by this node
    await send(make_event(EventType.AGENT_COMPLETED, ...))
    await asyncio.sleep(0.05)  # flush opportunity for the event loop
```

LangGraph's `.stream()` yields `{node_name: state_diff}` after each node completes. The 50ms sleep ensures the WebSocket frame is flushed before the next node starts, giving the frontend smooth progressive updates rather than a batch dump at the end.

### Database Configuration

`backend/database/config.py`

```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///sherlock.db")
```

SQLite for development (zero setup), PostgreSQL for production. `check_same_thread=False` is only set for SQLite (required for FastAPI's threading model).

### Synthetic Data Generator

`backend/datasets/generate_synthetic_data.py`

Generates reproducible Karnataka crime data with seeded randomness. Four patterns are deliberately injected:

1. **Entity resolution variants** — 30% of persons get 2–3 name aliases (e.g. "R Kumar", "R. Kumar", "Ravi K") used as `raw_name_used` in crime links
2. **Repeat-offender pool** — 5% of persons are over-weighted as accused on theft/burglary crimes
3. **Festival-season burglary spike** — Mysuru burglaries biased to months 9, 10, 11 (~92% concentration)
4. **Money-mule fraud ring** — 8 persons with flagged accounts, fan-in transactions into a hub, connected by ASSOCIATE edges

Scale: `--persons 500 --crimes 1000` for dev iteration; `--persons 5000 --crimes 10000` for the final demo dataset.

---

## Agent Pipeline

### LangGraph State

`backend/orchestrator/state.py`

```python
class SherlockState(TypedDict, total=False):
    query: str
    investigation_plan: dict
    active_agents: list
    findings: Annotated[list, operator.add]      # reducer: append
    validated_findings: list                      # overwrite
    evidence_log: Annotated[list, operator.add]  # reducer: append
    graph_context: dict                           # overwrite
    final_report: dict                            # overwrite
    audit_trail: Annotated[list, operator.add]   # reducer: append
```

`operator.add` reducers are critical: they mean each node's `findings` and `audit_trail` contributions are appended rather than overwritten, so the final state contains the complete accumulated history.

### BaseAgent

`backend/agents/base/agent.py`

```python
class BaseAgent(ABC):
    name: str
    always_runs: bool = False  # Chief + EvidenceValidation override to True

    @abstractmethod
    def run(self, state) -> list[AgentFinding] | tuple[list[AgentFinding], dict]:
        ...

    def to_node(self) -> Callable:
        # Returns a LangGraph node function that:
        # 1. Checks active_agents — skips if not in plan (unless always_runs)
        # 2. Calls self.run(state)
        # 3. Returns {findings: [...], audit_trail: [...], **extra}
```

Agents that need to pass data to downstream agents (e.g. Crime Records → `graph_context`) return `(findings, extra_state_dict)` from `run()`. The `to_node()` wrapper merges `extra` into the state update.

### Evidence Validation Agent

`backend/agents/evidence_validation/agent.py`

The mandatory gate. `always_runs = True` — cannot be skipped by the investigation plan.

Validation rules (in order):
1. `evidence` list empty → `validated=False`, `validation_notes="rejected: no supporting evidence"`
2. `confidence < 0.60` → `validated=True`, `validation_notes="flagged: low confidence (XX%)"`
3. Otherwise → `validated=True`, `validation_notes="validated"`

Writes annotated findings to `validated_findings` (full overwrite, not append — this is the definitive validated set).

### Query Parser

`backend/agents/base/query_parser.py`

Rule-based NLU. Extracts from the query string:
- `crime_type`: matches against `CrimeType` enum values
- `district`: matches against Karnataka district list
- `festival_season`: True if query contains "festival", "dasara", "diwali", "seasonal"
- `wants_forecast`: True if query contains "hotspot", "future", "predict", "forecast"
- `wants_repeat_offenders`: True if query contains "repeat", "habitual", "serial"
- `is_financial`: True if query contains "money", "transaction", "account", "fraud", "mule"

`plan_agents()` converts these flags into an `active_agents` list. Financial queries always include NetworkAnalysis (for repeat-offender context) plus FinancialAgent.

---

## Graph Layer

### GraphIntelligenceService Interface

`backend/graph/service.py`

```python
class GraphIntelligenceService(ABC):
    def find_repeat_offenders(self, min_crimes, limit) -> list[dict]: ...
    def find_associates(self, person_id, limit) -> list[dict]: ...
    def find_financial_network(self, account_id, max_hops) -> list[dict]: ...
    def find_location_clusters(self, crime_type, top_n) -> list[dict]: ...
    def find_connection(self, person_a_id, person_b_id, max_hops) -> dict: ...
    def get_metrics(self) -> dict: ...
```

Factory: `get_graph_service(backend="networkx"|"neo4j", session=...)`.

### NetworkX Implementation

`backend/graph/service_networkx.py`

Uses `nx.MultiDiGraph`. `find_connection` calls `nx.shortest_path()` on the undirected projection. `find_location_clusters` walks all Crime nodes and groups by (district, crime_type, month). All queries complete in <50ms on the 500-person dataset.

### Neo4j Implementation

`backend/graph/service_neo4j.py`

Equivalent Cypher queries. `find_connection` uses `shortestPath((a:Person)-[*..N]-(b:Person))`. `find_location_clusters` uses `toInteger(substring(c.timestamp, 5, 2))` to extract month from ISO timestamp strings.

### Graph Builder

`backend/graph/builder_neo4j.py`

Batched UNWIND/MERGE pattern for idempotent writes:

```cypher
UNWIND $rows AS row
MERGE (n:Person {id: row.id})
SET n.name = row.name, n.age = row.age, ...
```

Batch size: 500 rows. Safe to re-run — MERGE on `id` (which has a uniqueness constraint) is idempotent. Constraints created via `CONSTRAINT_STATEMENTS` in `graph/schema.py`.

---

## Frontend

### Single-File Architecture

`frontend/index.html` — all HTML, CSS, and React in one file. CDN-loaded React 18, ReactDOM, Babel (for JSX transpilation in-browser), and D3 7. No build step — open in any browser.

### WebSocket Client

```javascript
const ws = new WebSocket(`${WS}/ws/investigate`);
ws.onopen = () => ws.send(JSON.stringify({ query: trimmed }));
ws.onmessage = (msg) => {
    const event = JSON.parse(msg.data);
    setFeedEntries(prev => [...prev, event]);
    // extract findings, graph data, etc. from event.data
};
```

The `WS` constant auto-detects `localhost` vs deployed hostname, so the frontend works on both local and any server deploy without code changes.

### D3 Force Graph

`ForceGraph` component in `frontend/index.html`.

Fetches `GET /graph/{person_id}?hops=1` (1-hop ego-subgraph). Renders with:
- `d3.forceSimulation` with link, charge, center, and collision forces
- Node colour by entity type (amber=Person, red=Crime, green=Location, cyan=BankAccount, etc.)
- Zoom/pan via `d3.zoom()`
- Drag via `d3.drag()`
- Arrow markers on edges

Node labels are truncated to 14 characters to avoid overlap.

### PDF Export Flow

```javascript
const res = await fetch(`${API}/export/pdf`, {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ final_report, audit_trail, case_id }),
});
const blob = await res.blob();
const url = URL.createObjectURL(blob);
// trigger download via anchor click
```

The case ID is generated client-side (`INV-YYYYMMDD-XXXX`) so the PDF filename is deterministic per session.

---

## PDF Generation

`backend/reporting/pdf_export.py`

ReportLab `SimpleDocTemplate` with A4 page size. Sections:
1. Dark header block (SHERLOCK branding + case metadata)
2. Investigation query
3. Investigation timeline (from `audit_trail`)
4. Reasoning path (agent sequence)
5. Key findings (colour-coded cards: amber header, confidence badge)
6. Confidence heatmap (tabular, colour-coded by confidence level)
7. Recommended Actions (Prevention Agent findings, if present)
8. Footer (case ID, timestamp, classification)

PDF is returned as `application/pdf` binary from the FastAPI endpoint. Average size: 9–10KB for a full investigation report.

---

## Performance Characteristics

| Operation | Typical Time | Notes |
|-----------|-------------|-------|
| Graph build (500 persons) | ~1.2s | NetworkX, one-time on server start |
| Crime Records SQL query | ~50–200ms | Depends on filter selectivity |
| Network Analysis (graph traversal) | ~200–400ms | BFS on NetworkX |
| Pattern Analysis (cluster aggregation) | ~100–200ms | Dict accumulation over all Crime nodes |
| Financial Network trace | ~80–150ms | Edge traversal |
| Prevention Agent | ~20–50ms | Pure Python, reads state only |
| Evidence Validation | ~20–50ms | Pure Python |
| PDF generation | ~100–200ms | ReportLab render |
| **End-to-end investigation** | **1.1–1.6s** | All agents sequential |

WebSocket frame latency between agent completions: ~50ms (configured sleep) + network RTT.

---

## Configuration Reference

| Environment Variable | Default | Purpose |
|---------------------|---------|---------|
| `DATABASE_URL` | `sqlite:///sherlock.db` | Database connection string |
| `GRAPH_BACKEND` | `networkx` | Graph backend (`networkx` or `neo4j`) |
| `NEO4J_URI` | `bolt://localhost:7687` | Neo4j connection URI |
| `NEO4J_USER` | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | `sherlock123` | Neo4j password |
| `ANTHROPIC_API_KEY` | *(not set)* | Enables LLM narrative synthesis in Chief Agent |
