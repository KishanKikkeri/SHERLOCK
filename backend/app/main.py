"""
SHERLOCK — FastAPI application (Phase 6, stabilized).

Endpoints:
    WS  /ws/investigate      Live investigation stream (primary)
    GET /metrics             Dataset + graph stats for the header strip
    GET /graph/{person_id}   Subgraph around a person (for the vis panel)
    GET /health              Liveness probe
    POST /export/pdf         PDF investigation report export
"""

import json
import logging

from fastapi import Body, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response as FastAPIResponse

from backend.api.investigation_stream import stream_investigation
from backend.database.config import SessionLocal
from backend.database.models import Person, Crime, FIR, BankAccount, Transaction
from backend.graph.service import get_graph_service
from backend.graph.schema import node_key
from backend.logging_config import configure_logging
from backend.reporting.pdf_export import generate_investigation_pdf

configure_logging()
logger = logging.getLogger(__name__)

MAX_GRAPH_HOPS = 5  # BFS cost grows quickly; no legitimate UI use case needs more than this

app = FastAPI(title="SHERLOCK Crime Intelligence API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production; open for hackathon dev
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "operational", "system": "SHERLOCK"}


# ---------------------------------------------------------------------------
# Metrics strip
# ---------------------------------------------------------------------------

@app.get("/metrics")
def metrics():
    session = SessionLocal()
    try:
        graph_service = get_graph_service(backend="networkx", session=session)
        graph_metrics = graph_service.get_metrics()
        repeat_offenders = graph_service.find_repeat_offenders(min_crimes=3, limit=200)
        mule_accounts = session.query(BankAccount).filter_by(is_flagged_mule=True).count()
        suspicious_tx = session.query(Transaction).filter_by(is_suspicious=True).count()

        return {
            "persons": session.query(Person).count(),
            "crimes": session.query(Crime).count(),
            "firs": session.query(FIR).count(),
            "relationships": sum(graph_metrics["relationships"].values()),
            "repeat_offenders": len(repeat_offenders),
            "fraud_network_size": mule_accounts,
            "suspicious_transactions": suspicious_tx,
        }
    except Exception:
        logger.exception("GET /metrics failed")
        raise HTTPException(status_code=500, detail="Failed to compute metrics.")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Subgraph for the investigation vis panel
# ---------------------------------------------------------------------------

@app.get("/graph/{person_id}")
def get_person_subgraph(person_id: int, hops: int = 1):
    """
    Returns a small ego-graph around `person_id` (up to `hops` steps) as
    a {nodes, edges} payload for Cytoscape / react-force-graph.
    """
    if not (1 <= hops <= MAX_GRAPH_HOPS):
        raise HTTPException(status_code=422, detail=f"hops must be between 1 and {MAX_GRAPH_HOPS}.")

    session = SessionLocal()
    try:
        graph_service = get_graph_service(backend="networkx", session=session)
        G = graph_service.G  # NetworkX graph directly

        center = node_key("Person", person_id)
        if center not in G:
            return {"nodes": [], "edges": []}

        # BFS up to `hops` hops (undirected)
        UG = G.to_undirected()
        visited = {center}
        frontier = {center}
        for _ in range(hops):
            next_frontier = set()
            for n in frontier:
                for nb in UG.neighbors(n):
                    if nb not in visited:
                        visited.add(nb)
                        next_frontier.add(nb)
            frontier = next_frontier

        nodes = []
        for n in visited:
            data = G.nodes[n]
            label_val = (
                data.get("name") or data.get("fir_number") or data.get("number")
                or data.get("account_number") or data.get("registration_number")
                or n
            )
            nodes.append({
                "id": n,
                "label": label_val,
                "type": data.get("label", "Unknown"),
                "data": {k: v for k, v in data.items() if k != "label"},
            })

        edges = []
        seen_edges = set()
        for u, v, data in G.edges(visited, data=True):
            if v not in visited:
                continue
            key = (min(u, v), max(u, v), data.get("type", ""))
            if key in seen_edges:
                continue
            seen_edges.add(key)
            edges.append({
                "source": u,
                "target": v,
                "type": data.get("type", "UNKNOWN"),
            })

        return {"nodes": nodes, "edges": edges, "center": center}
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /graph/%s failed", person_id)
        raise HTTPException(status_code=500, detail="Failed to build subgraph.")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# WebSocket: live investigation stream
# ---------------------------------------------------------------------------

@app.websocket("/ws/investigate")
async def ws_investigate(websocket: WebSocket):
    await websocket.accept()
    try:
        raw = await websocket.receive_text()
        payload = json.loads(raw)
        query = payload.get("query", "").strip()
        if not query:
            await websocket.send_json({"event_type": "error", "message": "Empty query."})
            return

        async def send(event: dict):
            await websocket.send_json(event)

        await stream_investigation(query, send)

    except WebSocketDisconnect:
        pass
    except json.JSONDecodeError:
        logger.warning("Received non-JSON payload on /ws/investigate")
        try:
            await websocket.send_json({"event_type": "error", "message": "Malformed request: expected JSON with a 'query' field."})
        except Exception:
            pass
    except Exception as e:
        logger.exception("Unhandled error in /ws/investigate")
        try:
            await websocket.send_json({"event_type": "error", "message": str(e)})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------

@app.post("/export/pdf")
async def export_pdf(payload: dict = Body(...)):
    """
    Generate a PDF investigation report from a completed final_report.

    Body: { "final_report": {...}, "audit_trail": [...], "case_id": "..." }
    Returns: application/pdf binary
    """
    final_report = payload.get("final_report") or {}
    audit_trail  = payload.get("audit_trail")  or []
    case_id      = payload.get("case_id")

    if not isinstance(final_report, dict):
        raise HTTPException(status_code=422, detail="final_report must be an object.")
    if not isinstance(audit_trail, list):
        raise HTTPException(status_code=422, detail="audit_trail must be an array.")

    try:
        pdf_bytes = generate_investigation_pdf(final_report, audit_trail, case_id)
    except Exception:
        logger.exception("PDF export failed for case_id=%r", case_id)
        raise HTTPException(status_code=500, detail="PDF generation failed.")

    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="SHERLOCK-{case_id or "report"}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
