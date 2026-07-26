"""
SHERLOCK — Conversation V2: Tool handler definitions.

Each tool is defined as an async handler function that receives a
``ToolContext`` and keyword arguments matching its parameter schema.
Tools are registered into the global ``ToolRegistry`` at module import
via ``build_default_registry()``.

Tool handlers are migrated from ``backend/conversation/tools.py``
(which is now deprecated). The execution logic is identical — only the
registration/dispatch mechanism changed.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.tools.registry import ToolContext, ToolDefinition, ToolRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool Handlers
# ---------------------------------------------------------------------------

async def handle_investigate(ctx: ToolContext, *, query: str) -> dict:
    """Wraps the 20-agent LangGraph pipeline."""
    try:
        from backend.api.investigation_stream import run_investigation_once
        final_report = await run_investigation_once(
            query, session_id=ctx.conversation_id, language=ctx.language
        )
        return {
            "status": "success",
            "findings": final_report.get("findings") or [],
            "rejected_findings": final_report.get("rejected_findings") or [],
            "agents_consulted": final_report.get("agents_consulted") or [],
        }
    except Exception as e:
        logger.exception("investigate tool failed")
        return {"status": "error", "message": str(e)}


async def handle_search_graph(ctx: ToolContext, *, query: str) -> dict:
    """Search the entity graph for any identifier."""
    from backend.database.config import SessionLocal
    from backend.graph.search import search_entities
    db = SessionLocal()
    try:
        results = search_entities(db, query, limit=10)
        return {
            "status": "success",
            "results": [
                {
                    "id": r.get("id"),
                    "label": r.get("label"),
                    "kind": r.get("kind"),
                    "rank": r.get("rank"),
                    "metadata": r.get("data", {}),
                }
                for r in results
            ],
        }
    except Exception as e:
        logger.exception("search_graph tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


async def handle_search_cases(ctx: ToolContext, *, search: str | None = None) -> dict:
    """List and search FIR/case records."""
    from backend.database.config import SessionLocal
    from backend.database.service import DatabaseService
    db = SessionLocal()
    try:
        svc = DatabaseService(db)
        firs = svc.list_cases(search=search, limit=10)
        return {
            "status": "success",
            "results": [
                {
                    "id": f.id,
                    "fir_number": f.fir_number,
                    "status": f.status.value,
                    "crime_type": f.crime.type.value if f.crime else None,
                    "district": (
                        f.crime.location.district
                        if f.crime and f.crime.location
                        else None
                    ),
                }
                for f in firs
            ],
        }
    except Exception as e:
        logger.exception("search_cases tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


async def handle_search_person(ctx: ToolContext, *, name: str) -> dict:
    """Search for a suspect/person by name."""
    from backend.database.config import SessionLocal
    from backend.database.models import Person
    from backend.intelligence.offender_profiler import build_offender_profile
    db = SessionLocal()
    try:
        persons = db.query(Person).filter(Person.name.ilike(f"%{name}%")).limit(5).all()
        results = []
        for p in persons:
            try:
                profile = build_offender_profile(db, p.id)
                results.append(profile)
            except Exception:
                results.append({
                    "id": p.id,
                    "name": p.name,
                    "gender": p.gender.value if p.gender else None,
                    "age": p.age,
                })
        return {"status": "success", "results": results}
    except Exception as e:
        logger.exception("search_person tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


async def handle_financial_analysis(
    ctx: ToolContext, *, account_number: str
) -> dict:
    """Money-mule tracing and financial network analysis."""
    from backend.database.config import SessionLocal
    from backend.database.models import BankAccount
    from backend.graph.service import get_graph_service
    from backend.intelligence.network_profile import compute_network_profile
    db = SessionLocal()
    try:
        acct = (
            db.query(BankAccount)
            .filter(BankAccount.account_number == account_number)
            .first()
        )
        if not acct:
            return {
                "status": "not_found",
                "message": f"Account {account_number} not found.",
            }

        graph_service = get_graph_service(backend="networkx", session=db)
        profile = compute_network_profile(db, acct.owner_id, graph_service)
        network = graph_service.find_financial_network(acct.id)

        return {
            "status": "success",
            "owner": acct.owner.name,
            "bank": acct.bank,
            "network_profile": profile,
            "transactions": network[:15],
        }
    except Exception as e:
        logger.exception("financial_analysis tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


async def handle_timeline(ctx: ToolContext, *, person_id: int) -> dict:
    """Reconstruct chronological timeline for a person."""
    from backend.database.config import SessionLocal
    from backend.database.models import Person, Accused, Arrest, ChargeSheet
    db = SessionLocal()
    try:
        person = db.get(Person, int(person_id))
        if not person:
            return {
                "status": "not_found",
                "message": f"Person ID {person_id} not found.",
            }

        events = []
        for a in db.query(Accused).filter_by(person_id=person_id).all():
            if a.fir and a.fir.crime:
                events.append({
                    "date": a.fir.crime.timestamp.isoformat(),
                    "type": "accused",
                    "label": (
                        f"Accused in {a.fir.crime.type.value}"
                        f" (FIR {a.fir.fir_number})"
                    ),
                })
        for ar in db.query(Arrest).filter_by(person_id=person_id).all():
            events.append({
                "date": ar.arrest_date.isoformat(),
                "type": "arrest",
                "label": f"Arrested ({ar.status.value})",
            })
        for a in db.query(Accused).filter_by(person_id=person_id).all():
            for cs in db.query(ChargeSheet).filter_by(fir_id=a.fir_id).all():
                events.append({
                    "date": cs.filed_date.isoformat(),
                    "type": "chargesheet",
                    "label": f"Chargesheet {cs.status.value}",
                })

        events.sort(key=lambda e: e["date"])
        return {"status": "success", "person": person.name, "timeline": events}
    except Exception as e:
        logger.exception("timeline tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


async def handle_forecast(ctx: ToolContext, *, district: str) -> dict:
    """Fetch risk forecasting for a district."""
    from backend.database.config import SessionLocal
    db = SessionLocal()
    try:
        from backend.forecasting.repeat_alert_engine import RepeatAlertEngine
        engine = RepeatAlertEngine(db)
        alerts = engine.compute_repeat_alerts(min_crimes=2)
        filtered = [a for a in alerts if a.get("district") == district]
        return {
            "status": "success",
            "district": district,
            "repeat_alerts": filtered[:10],
        }
    except Exception as e:
        logger.exception("forecast tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


async def handle_network_graph(
    ctx: ToolContext, *, entity_id: int, node_type: str, hops: int = 1
) -> dict:
    """Generate ego-network subgraph for visual expansion."""
    from backend.database.config import SessionLocal
    db = SessionLocal()
    try:
        from backend.app.main import _build_ego_subgraph

        class MockCtx:
            roles = ["admin"]
        mock_ctx = MockCtx()
        graph = _build_ego_subgraph(db, mock_ctx, node_type, int(entity_id), int(hops))
        return {"status": "success", "graph": graph}
    except Exception as e:
        logger.exception("network_graph tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


async def handle_generate_pdf(ctx: ToolContext, *, session_id: int | None = None) -> dict:
    """Export investigation report as PDF."""
    from backend.database.config import SessionLocal
    db = SessionLocal()
    try:
        sid = session_id or ctx.conversation_id
        from backend.conversation.orchestrator import ConversationOrchestrator
        orchestrator = ConversationOrchestrator(db)
        pdf_bytes, warnings = orchestrator.export_last_report_as_pdf(
            sid, language=ctx.language
        )
        return {
            "status": "success",
            "pdf_length": len(pdf_bytes) if pdf_bytes else 0,
            "warnings": warnings,
        }
    except Exception as e:
        logger.exception("generate_pdf tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool Schema Definitions
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[ToolDefinition] = [
    ToolDefinition(
        name="investigate",
        description=(
            "Run the complete 20-agent LangGraph investigation pipeline to "
            "analyze a complex case, search for patterns, validate evidence, "
            "and produce structured findings. Use this for general investigative "
            "queries that cannot be solved by a simple entity lookup."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "The natural language query describing the investigation "
                        "target (e.g. 'Show repeat offenders in Mysuru')."
                    ),
                },
            },
            "required": ["query"],
        },
        handler=handle_investigate,
        streams_events=True,
    ),
    ToolDefinition(
        name="search_graph",
        description=(
            "Search the network database for any entity identifier (name, "
            "alias, vehicle number, phone, bank account, weapon serial, FIR "
            "number, organization, or location) and return matched candidate "
            "nodes with auto-detected types."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search term (name, vehicle number, phone, etc.).",
                },
            },
            "required": ["query"],
        },
        handler=handle_search_graph,
    ),
    ToolDefinition(
        name="search_cases",
        description=(
            "List and search case records or FIRs. Useful for listing "
            "active/closed cases or filtering by crime type or district."
        ),
        parameters={
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Optional text to search case numbers, crime types, or districts.",
                },
            },
        },
        handler=handle_search_cases,
    ),
    ToolDefinition(
        name="search_person",
        description=(
            "Search for a suspect or offender by name to retrieve their "
            "general dossier, risk score, and basic metadata."
        ),
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name or alias of the person to search.",
                },
            },
            "required": ["name"],
        },
        handler=handle_search_person,
    ),
    ToolDefinition(
        name="financial_analysis",
        description=(
            "Perform money-mule tracing and financial transaction network "
            "analysis for a flagged account number or suspect."
        ),
        parameters={
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string",
                    "description": "The flagged bank account number to trace.",
                },
            },
            "required": ["account_number"],
        },
        handler=handle_financial_analysis,
    ),
    ToolDefinition(
        name="timeline",
        description=(
            "Reconstruct a chronological timeline of crimes, arrests, and "
            "chargesheets for a specific suspect/person by ID."
        ),
        parameters={
            "type": "object",
            "properties": {
                "person_id": {
                    "type": "integer",
                    "description": "The database ID of the person/suspect.",
                },
            },
            "required": ["person_id"],
        },
        handler=handle_timeline,
    ),
    ToolDefinition(
        name="forecast",
        description=(
            "Fetch risk forecasting, repeat alerts, gang alerts, or hot "
            "spots for a specific district."
        ),
        parameters={
            "type": "object",
            "properties": {
                "district": {
                    "type": "string",
                    "description": "The name of the district (e.g. 'Mysuru').",
                },
            },
            "required": ["district"],
        },
        handler=handle_forecast,
    ),
    ToolDefinition(
        name="network_graph",
        description=(
            "Generate an ego-network subgraph (nodes and edges) around a "
            "specific entity (Person, FIR, Vehicle, Phone, BankAccount, "
            "Location, etc.) for visual network expansion."
        ),
        parameters={
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "integer",
                    "description": "The database ID of the entity.",
                },
                "node_type": {
                    "type": "string",
                    "description": (
                        "The type of entity (e.g. 'Person', 'FIR', 'BankAccount')."
                    ),
                },
                "hops": {
                    "type": "integer",
                    "description": "Number of hops to expand (default is 1).",
                    "default": 1,
                },
            },
            "required": ["entity_id", "node_type"],
        },
        handler=handle_network_graph,
    ),
    ToolDefinition(
        name="generate_pdf",
        description=(
            "Export the completed investigation report or conversation "
            "summary as a PDF document."
        ),
        parameters={
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "integer",
                    "description": "The session ID of the conversation to export.",
                },
            },
        },
        handler=handle_generate_pdf,
    ),
]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_default_registry() -> ToolRegistry:
    """Create a ToolRegistry pre-loaded with all SHERLOCK tools."""
    registry = ToolRegistry()
    for tool_def in TOOL_DEFINITIONS:
        registry.register(tool_def)
    logger.info(
        "ToolRegistry initialized with %d tools: %s",
        len(registry),
        ", ".join(registry.list_names()),
    )
    return registry
