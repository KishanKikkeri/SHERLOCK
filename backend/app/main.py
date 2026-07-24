"""
SHERLOCK — FastAPI application (Phase 6, stabilized).

Endpoints:
    WS  /ws/investigate      Live investigation stream (primary)
    GET /metrics             Dataset + graph stats for the header strip
    GET /graph/{person_id}   Subgraph around a person (for the vis panel)
    GET /health              Liveness probe
    POST /export/pdf         PDF investigation report export
    GET /analytics/dashboard Crime Pattern & Trend Analytics dashboard payload
    GET /analytics/sociological         Sociological insights dashboard (backend/api/sociological.py)
    GET /analytics/sociological/report  Structured sociological report
    GET /forecast/dashboard   /forecast/hotspots   /forecast/trends
    GET /forecast/repeat-alerts  /forecast/gang-alerts  /forecast/risk  /forecast/summary
                             Forecasting & Early Warning Engine (backend/api/forecast.py)
"""

import json
import logging
import os

from fastapi import Body, Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import Response as FastAPIResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from backend.api.investigation_stream import stream_investigation, run_investigation_once
from backend.api.sessions import router as sessions_router
from backend.api.conversation import router as conversation_router
from backend.api.conversation_chat import router as conversation_chat_router
from backend.api.board import router as board_router
from backend.api.voice import router as voice_router
from backend.api.discussion import router as discussion_router
from backend.api.collaboration import router as collaboration_router
from backend.api.language import router as language_router
from backend.api.auth import router as auth_router
from backend.api.admin import router as admin_router
from backend.api.audit import router as audit_router
from backend.api.governance import router as governance_router
from backend.api.offender_profile import router as offender_profile_router
from backend.api.analytics import router as analytics_router
from backend.api.forecast import router as forecast_router
from backend.api.sociological import router as sociological_router
from backend.security.config import AUTH_ENABLED
from backend.security.seed import run_all_seeds
from backend.security.permissions import RequirePermission, VIEW_CASE, RUN_INVESTIGATION, EXPORT_PDF
from backend.security import audit as security_audit
from backend.security.dependencies import AuthContext
from backend.security import masking
from backend.security.rate_limit import limiter
from backend.security.request_context import (
    RequestContextMiddleware, SecurityHeadersMiddleware, configure_structured_logging,
)
from backend.security.health import get_component_health
from backend.database.models import AuditAction
from backend.database.config import SessionLocal
from backend.database.models import Person, Crime, FIR, BankAccount, Transaction
from backend.graph.service import get_graph_service
from backend.graph.schema import node_key
from backend.logging_config import configure_logging
from backend.reporting.pdf_export import generate_investigation_pdf, pdf_export_warnings

configure_logging()
configure_structured_logging()
logger = logging.getLogger(__name__)

MAX_GRAPH_HOPS = 5  # BFS cost grows quickly; no legitimate UI use case needs more than this

app = FastAPI(title="SHERLOCK Crime Intelligence API", version="1.0.0")

# Stage E6 — rate limiting (optional, off by default; see backend/security/rate_limit.py)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Stage E6 — request/correlation IDs + security headers. Order matters:
# Starlette applies middleware in reverse of add order, so this makes
# SecurityHeadersMiddleware the outermost (runs last on the way out,
# guaranteeing its headers survive) with RequestContextMiddleware just
# inside it (so its timing measurement wraps the actual route handler).
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)

# Stage E6 — trusted hosts. Comma-separated env var; "*" (default) skips
# the restriction entirely rather than adding a middleware that allows
# everything anyway — one less moving part when it isn't configured.
_trusted_hosts_env = os.getenv("SHERLOCK_TRUSTED_HOSTS", "*").strip()
if _trusted_hosts_env and _trusted_hosts_env != "*":
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=[h.strip() for h in _trusted_hosts_env.split(",") if h.strip()])

# Stage E6 — CORS. Comma-separated env var; "*" (default) preserves the
# pre-Stage-E6 wide-open dev behavior exactly.
_cors_origins_env = os.getenv("SHERLOCK_CORS_ORIGINS", "*").strip()
_cors_origins = ["*"] if _cors_origins_env == "*" else [o.strip() for o in _cors_origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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

# Stage F2 (Conversation Intelligence System) — new, additive. Unifies
# chat + voice + evidence + reporting behind one /conversation/* surface;
# does not change or replace any router above.
app.include_router(conversation_chat_router)

# Stage G1 (Criminology-Based Offender Profiling Engine) — new, additive.
# Deterministic per-person dossier (Requirement 5): read-only, computed
# from FIR/Accused/Arrest/ChargeSheet/Weapon/Vehicle/PersonAssociation/
# Organization records already in the database.
app.include_router(offender_profile_router)

# Crime Pattern & Trend Analytics Agent — new, additive. Deterministic
# (no LLM) hotspot/cluster/modus/seasonal/trend/summary engines over the
# existing FIR/Crime/Location schema.
app.include_router(analytics_router)

# Forecasting & Early Warning Engine (Requirement 8), platform-wide,
# deterministic (no LLM) — new, additive.
app.include_router(forecast_router)

# Sociological Crime Insights dashboard, platform-wide (not session-scoped)
# — new, additive.
app.include_router(sociological_router)

# Stage D (Language Intelligence) — new, additive
app.include_router(language_router)

# Stage E1 (Authentication) — new, additive
app.include_router(auth_router)

# Stage E2 (RBAC / Administration) — new, additive
app.include_router(admin_router)

# Stage E3 (Audit & Compliance) — new, additive
app.include_router(audit_router)

# Stage E5 (Governance) — new, additive
app.include_router(governance_router)


@app.on_event("startup")
def _seed_security_data():
    """Seeds the fixed Role vocabulary (and an optional bootstrap admin,
    see backend/security/config.py) only when SHERLOCK_AUTH_ENABLED=true.
    Left untouched when auth is disabled, so a zero-configuration dev run
    creates no new rows in the security tables at all (Golden Rule 4/5)."""
    if not AUTH_ENABLED:
        return
    session = SessionLocal()
    try:
        run_all_seeds(session)
    except Exception:
        logger.exception("Security seed step failed on startup")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """
    Liveness probe. `status` and `system` are unchanged from pre-Stage-E6
    behavior; `components` (Stage E6) is additive — a caller that only
    ever checked `status == "operational"` is unaffected.
    """
    return {
        "status": "operational",
        "system": "SHERLOCK",
        "components": get_component_health(),
    }


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
def get_person_subgraph(person_id: int, hops: int = 1, ctx=Depends(RequirePermission(VIEW_CASE))):
    """
    Returns a small ego-graph around `person_id` (up to `hops` steps) as
    a {nodes, edges} payload for Cytoscape / react-force-graph.

    Stage E4: sensitive fields on each node (`Phone.number`,
    `BankAccount.account_number`, `Location.latitude`/`longitude`) are
    masked according to the caller's role — see
    `backend/security/masking.py`. The database itself is never touched;
    this only affects what's serialized into the response. With
    SHERLOCK_AUTH_ENABLED=false (default), visibility is always FULL —
    identical to pre-Stage-E4 behavior.
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
        visibility = masking.visibility_for(ctx)
        for n in visited:
            data = G.nodes[n]
            node_type = data.get("label", "Unknown")
            node_data = {k: v for k, v in data.items() if k != "label"}
            node_data = masking.mask_graph_node_data(node_type, node_data, visibility)
            label_val = (
                node_data.get("name") or node_data.get("fir_number") or node_data.get("number")
                or node_data.get("account_number") or node_data.get("registration_number")
                or n
            )
            nodes.append({
                "id": n,
                "label": label_val,
                "type": node_type,
                "data": node_data,
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
    # WebSocket handshakes can't carry an Authorization header from a
    # browser client, so when auth is enabled the access token is passed
    # as a query param instead: /ws/investigate?token=...  This mirrors
    # RUN_INVESTIGATION's permission requirement on POST /investigate,
    # just via a transport WS actually supports. When AUTH_ENABLED=false
    # (default), no token is required at all — unchanged from Stage D.
    if AUTH_ENABLED:
        from backend.security.dependencies import get_db as _get_db
        from backend.security.auth import get_user_from_access_token, get_user_role_names, AuthError
        from backend.security.permissions import has_permission
        from backend.security.dependencies import AuthContext

        token = websocket.query_params.get("token")
        db = next(_get_db())
        try:
            if not token:
                await websocket.close(code=4401, reason="Not authenticated.")
                return
            try:
                user = get_user_from_access_token(db, token)
            except AuthError as e:
                await websocket.close(code=4401, reason=str(e))
                return
            ctx = AuthContext(
                user_id=user.id, username=user.username,
                roles=get_user_role_names(db, user), officer_id=user.officer_id,
            )
            if not has_permission(ctx, RUN_INVESTIGATION):
                await websocket.close(code=4403, reason="Missing required permission: run_investigation")
                return
        finally:
            db.close()

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
async def investigate(payload: dict = Body(...), _ctx=Depends(RequirePermission(RUN_INVESTIGATION))):
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
async def export_pdf(payload: dict = Body(...), request: Request = None,
                      ctx: AuthContext = Depends(RequirePermission(EXPORT_PDF))):
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

    _audit_db = SessionLocal()
    try:
        security_audit.record(
            _audit_db, AuditAction.REPORT_GENERATED,
            user_id=ctx.user_id, username=ctx.username, target=f"case:{case_id or 'unknown'}",
            success=True, ip_address=(request.client.host if request and request.client else None),
            user_agent=(request.headers.get("user-agent") if request else None),
            metadata={"language": language},
        )
    finally:
        _audit_db.close()

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
