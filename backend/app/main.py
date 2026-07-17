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

from backend.api.investigation_stream import stream_investigation, run_investigation_once
from backend.api.sessions import router as sessions_router
from backend.api.conversation import router as conversation_router
from backend.api.board import router as board_router
from backend.api.voice import router as voice_router
from backend.api.discussion import router as discussion_router
from backend.api.collaboration import router as collaboration_router
from backend.api.language import router as language_router
from backend.database.config import SessionLocal
from backend.database.models import Person, Crime, FIR, BankAccount, Transaction
from backend.graph.service import get_graph_service
from backend.graph.schema import node_key
from backend.logging_config import configure_logging
from backend.reporting.pdf_export import generate_investigation_pdf, pdf_export_warnings

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

# Stage C1 (Investigation Lifecycle) / Stage C2 (Conversation Memory) / Stage C5 (Board) / Stage C3 (Voice) / Stage C4 (Discussion) / Stage C6 (Collaboration) — new, additive
app.include_router(sessions_router)
app.include_router(conversation_router)
app.include_router(board_router)
app.include_router(voice_router)
app.include_router(discussion_router)
app.include_router(collaboration_router)

# Stage D (Language Intelligence) — new, additive
app.include_router(language_router)


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
        session_id = payload.get("session_id")  # Stage C2, optional
        enable_discussion = bool(payload.get("enable_discussion", False))  # Stage C4, optional
        language = payload.get("language")  # Stage D, Sprint 2, optional — e.g. "kn". Auto-detected if omitted.
        if not query:
            await websocket.send_json({"event_type": "error", "message": "Empty query."})
            return

        async def send(event: dict):
            await websocket.send_json(event)

        await stream_investigation(query, send, session_id=session_id,
                                    enable_discussion=enable_discussion, language=language)

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
# Non-streaming investigation endpoint (Stage D, Sprint 2)
# ---------------------------------------------------------------------------

@app.post("/investigate")
async def investigate(payload: dict = Body(...)):
    """
    Non-streaming counterpart to `/ws/investigate`, added for Stage D so
    the multilingual pipeline has a plain request/response shape to test
    and integrate against (the handover's own example payload):

        POST /investigate
        { "query": "...", "language": "kn" }

    `language` is optional; omitted or "en" behaves exactly like the
    existing English-only pipeline. `/ws/investigate` remains the
    primary, live-streaming entry point — this endpoint just drains the
    same event stream server-side (via `run_investigation_once`) and
    returns the finished report, for callers that don't want a
    WebSocket (e.g. simple scripts, curl, future non-streaming clients).
    """
    query = (payload.get("query") or "").strip()
    session_id = payload.get("session_id")
    language = payload.get("language")

    if not query:
        raise HTTPException(status_code=422, detail="query is required.")
    if language is not None and language not in ("en", "kn"):
        raise HTTPException(status_code=422, detail="language must be 'en' or 'kn' if provided.")

    try:
        final_report = await run_investigation_once(query, session_id=session_id, language=language)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        logger.exception("POST /investigate failed for query: %r", query)
        raise HTTPException(status_code=500, detail="Investigation failed.")

    return {"query": query, "language": language or "en", "final_report": final_report}


# ---------------------------------------------------------------------------
# PDF Export
# ---------------------------------------------------------------------------

@app.post("/export/pdf")
async def export_pdf(payload: dict = Body(...)):
    """
    Generate a PDF investigation report from a completed final_report.

    Body: { "final_report": {...}, "audit_trail": [...], "case_id": "...", "language": "kn" }
    Returns: application/pdf binary

    `language` (Stage D, Sprint 4, optional): "en" (default, unchanged
    pre-Sprint-4 behavior), "kn", or "bilingual". If a Kannada PDF is
    requested but can't actually be produced (Kannada font missing on
    this server, or `final_report` has no `localized` block because the
    investigation didn't run with `language="kn"`), the endpoint still
    returns 200 with a valid English PDF — degrading gracefully rather
    than failing the whole export — and explains why via the
    `X-PDF-Warnings` response header.
    """
    final_report = payload.get("final_report") or {}
    audit_trail  = payload.get("audit_trail")  or []
    case_id      = payload.get("case_id")
    language     = payload.get("language") or "en"

    if not isinstance(final_report, dict):
        raise HTTPException(status_code=422, detail="final_report must be an object.")
    if not isinstance(audit_trail, list):
        raise HTTPException(status_code=422, detail="audit_trail must be an array.")
    if language not in ("en", "kn", "bilingual"):
        raise HTTPException(status_code=422, detail="language must be one of 'en', 'kn', 'bilingual'.")

    try:
        pdf_bytes = generate_investigation_pdf(final_report, audit_trail, case_id, language=language)
    except Exception:
        logger.exception("PDF export failed for case_id=%r", case_id)
        raise HTTPException(status_code=500, detail="PDF generation failed.")

    headers = {
        "Content-Disposition": f'attachment; filename="SHERLOCK-{case_id or "report"}.pdf"',
        "Content-Length": str(len(pdf_bytes)),
    }
    warnings = pdf_export_warnings(final_report, language)
    if warnings:
        headers["X-PDF-Warnings"] = " | ".join(warnings)

    return FastAPIResponse(
        content=pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )
