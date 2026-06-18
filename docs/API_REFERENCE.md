# SHERLOCK — API Reference

Base URL: `http://localhost:8000`

Interactive docs: `http://localhost:8000/docs` (FastAPI Swagger UI)

---

## WebSocket: Live Investigation Stream

```
WS /ws/investigate
```

**Description:** Primary endpoint. Send a query, receive a stream of investigation events as the agent pipeline executes.

**Initiation message (client → server):**
```json
{ "query": "Show repeat burglary offenders in Mysuru during festival seasons" }
```

**Event stream (server → client):**

Each event is a JSON object:
```json
{
  "timestamp": "2026-06-16T08:15:00.123Z",
  "event_type": "agent_completed",
  "agent": "Network Analysis Agent",
  "message": "Network Analysis Agent reported: Identified 34 repeat offender(s)...",
  "data": {
    "new_findings": [...],
    "validated_findings": null,
    "final_report": null
  }
}
```

**Event types:**

| event_type | Trigger | data contents |
|-----------|---------|---------------|
| `investigation_started` | Query received | message only |
| `agent_completed` | Agent node finished | `new_findings` from this node |
| `agent_skipped` | Agent not in plan | message only |
| `validation_complete` | Evidence Validation done | `validated_findings` (annotated) |
| `report_ready` | Chief synthesis done | `final_report` (complete) |
| `error` | Exception in pipeline | `message` with error detail |

---

## POST /export/pdf

Generate a PDF investigation report.

**Request body:**
```json
{
  "final_report": {
    "query": "...",
    "narrative": "...",
    "findings": [...],
    "rejected_findings": [...],
    "agents_consulted": [...]
  },
  "audit_trail": [
    { "agent": "Chief Investigation Officer", "status": "done", "message": "..." }
  ],
  "case_id": "INV-20260616-4291"
}
```

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename="SHERLOCK-INV-20260616-4291.pdf"`
- Body: Binary PDF

**PDF sections:** SHERLOCK header · Case metadata · Investigation query · Timeline · Reasoning path · Key findings (colour-coded) · Confidence heatmap · Recommended Actions · Footer

---

## GET /metrics

Retrieve dataset and graph statistics for the Command Center header strip.

**Response:**
```json
{
  "persons": 500,
  "crimes": 1001,
  "firs": 1001,
  "relationships": 10454,
  "repeat_offenders": 34,
  "fraud_network_size": 8,
  "suspicious_transactions": 29
}
```

`repeat_offenders` counts persons with ≥3 PERSON_COMMITTED_CRIME edges (configurable in code).

---

## GET /graph/{person_id}

Retrieve a subgraph centred on a person for the D3 force visualisation.

**Path parameter:** `person_id` — integer person ID

**Query parameter:** `hops` — integer (default 1) — BFS depth from the centre node

**Response:**
```json
{
  "center": "Person:42",
  "nodes": [
    { "id": "Person:42", "label": "Ravi Kumar", "type": "Person", "data": {...} },
    { "id": "Crime:108", "label": "Crime:108", "type": "Crime", "data": {...} }
  ],
  "edges": [
    { "source": "Person:42", "target": "Crime:108", "type": "PERSON_COMMITTED_CRIME" }
  ]
}
```

---

## GET /health

Liveness probe.

**Response:**
```json
{ "status": "operational", "system": "SHERLOCK" }
```

---

## GET /

Serves `frontend/index.html` — the SHERLOCK Command Center.

---

## Error responses

All endpoints return standard HTTP status codes. WebSocket errors are sent as `event_type: "error"` events before the connection closes.

```json
{ "event_type": "error", "message": "Empty query." }
```
