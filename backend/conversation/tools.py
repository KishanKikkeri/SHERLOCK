"""
SHERLOCK — Stage F3: Conversational Intelligence — Tool Registry.

Defines the 9 specialized investigative/look-up tools that the Conversation
LLM Brain can invoke. These tools wrap existing, highly optimized,
deterministic backend services.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.graph.search import search_entities
from backend.graph.service import get_graph_service
from backend.intelligence.offender_profiler import build_offender_profile
from backend.intelligence.network_profile import compute_network_profile
from backend.api.investigation_stream import run_investigation_once
from backend.database.models import Person, Accused, Victim, Witness, Arrest, ChargeSheet, BankAccount, FIR
from backend.conversation.summarizer import summarize_now

logger = logging.getLogger(__name__)

# List of tool schema definitions formatted in JSON Schema / OpenAI tool format.
# Pluggable adapters (Claude, OpenAI, Gemini) will translate these to their specific format if needed.
TOOL_SCHEMAS = [
    {
        "name": "investigate",
        "description": "Run the complete 20-agent LangGraph investigation pipeline to analyze a complex case, search for patterns, validate evidence, and produce structured findings. Use this for general investigative queries that cannot be solved by a simple entity lookup.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The natural language query describing the investigation target (e.g. 'Show repeat offenders in Mysuru', 'Analyze FIR 231 for fraud')."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_graph",
        "description": "Search the network database for any entity identifier (name, alias, vehicle number, phone, bank account, weapon serial, FIR number, organization, or location) and return matched candidate nodes with auto-detected types.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search term (name, vehicle number, phone, bank account, weapon, or FIR number)."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_cases",
        "description": "List and search case records or FIRs. Useful for listing active/closed cases or filtering by crime type or district.",
        "parameters": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Optional text to search case numbers, crime types, or districts."
                }
            }
        }
    },
    {
        "name": "search_person",
        "description": "Search for a suspect or offender by name to retrieve their general dossier, risk score, and basic metadata.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name or alias of the person to search."
                }
            },
            "required": ["name"]
        }
    },
    {
        "name": "financial_analysis",
        "description": "Perform money-mule tracing and financial transaction network analysis for a flagged account number or suspect.",
        "parameters": {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string",
                    "description": "The flagged bank account number to trace."
                }
            },
            "required": ["account_number"]
        }
    },
    {
        "name": "timeline",
        "description": "Reconstruct a chronological timeline of crimes, arrests, and chargesheets for a specific suspect/person by ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "person_id": {
                    "type": "integer",
                    "description": "The database ID of the person/suspect."
                }
            },
            "required": ["person_id"]
        }
    },
    {
        "name": "forecast",
        "description": "Fetch risk forecasting, repeats, gang alerts, or hot spots for a specific district.",
        "parameters": {
            "type": "object",
            "properties": {
                "district": {
                    "type": "string",
                    "description": "The name of the district (e.g. 'Mysuru', 'Bengaluru')."
                }
            },
            "required": ["district"]
        }
    },
    {
        "name": "network_graph",
        "description": "Generate an ego-network subgraph (nodes and edges) around a specific entity (Person, FIR, Vehicle, Phone, BankAccount, Location, etc.) for visual network expansion.",
        "parameters": {
            "type": "object",
            "properties": {
                "entity_id": {
                    "type": "integer",
                    "description": "The database ID of the entity."
                },
                "node_type": {
                    "type": "string",
                    "description": "The type of entity (e.g. 'Person', 'FIR', 'BankAccount', 'Vehicle')."
                },
                "hops": {
                    "type": "integer",
                    "description": "Number of hops to expand (default is 1).",
                    "default": 1
                }
            },
            "required": ["entity_id", "node_type"]
        }
    },
    {
        "name": "generate_pdf",
        "description": "Export the completed investigation report or conversation summary as a PDF document.",
        "parameters": {
            "type": "object",
            "properties": {
                "session_id": {
                    "type": "integer",
                    "description": "The session ID of the conversation to export."
                }
            },
            "required": ["session_id"]
        }
    }
]

# ---------------------------------------------------------------------------
# Tool Execution Wrappers
# ---------------------------------------------------------------------------

async def execute_investigate(session_id: int, query: str, language: str = "en") -> dict:
    """Wraps the 20-agent LangGraph pipeline."""
    try:
        # Run investigation, which returns state (ChiefAgent synthesis has narrative disabled)
        final_report = await run_investigation_once(query, session_id=session_id, language=language)
        return {
            "status": "success",
            "findings": final_report.get("findings") or [],
            "rejected_findings": final_report.get("rejected_findings") or [],
            "agents_consulted": final_report.get("agents_consulted") or [],
        }
    except Exception as e:
        logger.exception("investigate tool failed")
        return {"status": "error", "message": str(e)}


def execute_search_graph(query: str) -> dict:
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
                    "metadata": r.get("data", {})
                }
                for r in results
            ]
        }
    except Exception as e:
        logger.exception("search_graph tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def execute_search_cases(search: str | None = None) -> dict:
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
                    "district": f.crime.location.district if f.crime and f.crime.location else None,
                }
                for f in firs
            ]
        }
    except Exception as e:
        logger.exception("search_cases tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def execute_search_person(name: str) -> dict:
    db = SessionLocal()
    try:
        # Search suspect/person records
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
                    "age": p.age
                })
        return {"status": "success", "results": results}
    except Exception as e:
        logger.exception("search_person tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def execute_financial_analysis(account_number: str) -> dict:
    db = SessionLocal()
    try:
        # Find account
        acct = db.query(BankAccount).filter(BankAccount.account_number == account_number).first()
        if not acct:
            return {"status": "not_found", "message": f"Account {account_number} not found."}
        
        graph_service = get_graph_service(backend="networkx", session=db)
        profile = compute_network_profile(db, acct.owner_id, graph_service)
        network = graph_service.find_financial_network(acct.id)
        
        return {
            "status": "success",
            "owner": acct.owner.name,
            "bank": acct.bank,
            "network_profile": profile,
            "transactions": network[:15]  # limit payload size
        }
    except Exception as e:
        logger.exception("financial_analysis tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def execute_timeline(person_id: int) -> dict:
    db = SessionLocal()
    try:
        person = db.get(Person, person_id)
        if not person:
            return {"status": "not_found", "message": f"Person ID {person_id} not found."}
        
        events = []
        for a in db.query(Accused).filter_by(person_id=person_id).all():
            if a.fir and a.fir.crime:
                events.append({"date": a.fir.crime.timestamp.isoformat(), "type": "accused",
                                "label": f"Accused in {a.fir.crime.type.value} (FIR {a.fir.fir_number})"})
        for ar in db.query(Arrest).filter_by(person_id=person_id).all():
            events.append({"date": ar.arrest_date.isoformat(), "type": "arrest",
                            "label": f"Arrested ({ar.status.value})"})
        for a in db.query(Accused).filter_by(person_id=person_id).all():
            for cs in db.query(ChargeSheet).filter_by(fir_id=a.fir_id).all():
                events.append({"date": cs.filed_date.isoformat(), "type": "chargesheet",
                                "label": f"Chargesheet {cs.status.value}"})
        
        events.sort(key=lambda e: e["date"])
        return {"status": "success", "person": person.name, "timeline": events}
    except Exception as e:
        logger.exception("timeline tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def execute_forecast(district: str) -> dict:
    # Use forecast engine or basic query
    db = SessionLocal()
    try:
        from backend.forecasting.repeat_alert_engine import RepeatAlertEngine
        engine = RepeatAlertEngine(db)
        alerts = engine.compute_repeat_alerts(min_crimes=2)
        filtered = [a for a in alerts if a.get("district") == district]
        return {
            "status": "success",
            "district": district,
            "repeat_alerts": filtered[:10]
        }
    except Exception as e:
        logger.exception("forecast tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def execute_network_graph(entity_id: int, node_type: str, hops: int = 1) -> dict:
    db = SessionLocal()
    try:
        from backend.app.main import _build_ego_subgraph
        # Mock Context with admin permission so it returns full masked/unmasked data
        class MockCtx:
            roles = ["admin"]
        ctx = MockCtx()
        graph = _build_ego_subgraph(db, ctx, node_type, entity_id, hops)
        return {"status": "success", "graph": graph}
    except Exception as e:
        logger.exception("network_graph tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def execute_generate_pdf(session_id: int) -> dict:
    db = SessionLocal()
    try:
        from backend.conversation.orchestrator import ConversationOrchestrator
        orchestrator = ConversationOrchestrator(db)
        pdf_bytes, warnings = orchestrator.export_last_report_as_pdf(session_id)
        return {
            "status": "success",
            "pdf_length": len(pdf_bytes) if pdf_bytes else 0,
            "warnings": warnings
        }
    except Exception as e:
        logger.exception("generate_pdf tool failed")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tool Execution Router
# ---------------------------------------------------------------------------

async def call_tool(name: str, arguments: dict, session_id: int, language: str = "en") -> dict:
    """Executes a tool by name and returns its structured results."""
    logger.info("Executing tool: %s with arguments %s", name, arguments)
    if name == "investigate":
        query = arguments.get("query", "")
        return await execute_investigate(session_id, query, language)
    elif name == "search_graph":
        query = arguments.get("query", "")
        return execute_search_graph(query)
    elif name == "search_cases":
        search = arguments.get("search")
        return execute_search_cases(search)
    elif name == "search_person":
        name_val = arguments.get("name", "")
        return execute_search_person(name_val)
    elif name == "financial_analysis":
        account = arguments.get("account_number", "")
        return execute_financial_analysis(account)
    elif name == "timeline":
        p_id = int(arguments.get("person_id", 0))
        return execute_timeline(p_id)
    elif name == "forecast":
        district = arguments.get("district", "")
        return execute_forecast(district)
    elif name == "network_graph":
        ent_id = int(arguments.get("entity_id", 0))
        node_t = arguments.get("node_type", "")
        hops = int(arguments.get("hops", 1))
        return execute_network_graph(ent_id, node_t, hops)
    elif name == "generate_pdf":
        s_id = int(arguments.get("session_id", session_id))
        return execute_generate_pdf(s_id)
    else:
        raise ValueError(f"Unknown tool name: {name}")
