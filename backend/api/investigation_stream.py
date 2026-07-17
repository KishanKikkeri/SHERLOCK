"""
SHERLOCK — Streaming investigation runner (Phase 6).

Wraps `run_investigation` to emit WebSocket events after each LangGraph
node completes, giving the frontend its live activity feed.

LangGraph's `.stream()` yields state diffs keyed by node name after each
node executes, which maps directly onto our AgentEvent protocol.
"""

import asyncio
import json
import logging

from backend.api.events import EventType, make_event
from backend.database.config import SessionLocal
from backend.database.service import DatabaseService
from backend.database.models import DiscussionRecord
from backend.discussion.engine import DiscussionEngine
from backend.graph.service import get_graph_service
from backend.memory.conversation_memory import ConversationMemoryService
from backend.orchestrator.graph import build_investigation_graph
from backend.language import TranslationService, detect_language, SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

# Node name -> display name for the activity feed.
#
# IMPORTANT: every value here must be unique. The frontend's investigation
# timeline (`useInvestigation.ts`) matches an incoming event's `agent` field
# against `AgentStep.name` to update the right row — if two node keys ever
# shared a display name again (as chief_plan/chief_synthesis once did, both
# as plain "Chief Investigation Officer"), the second node's completion
# event would silently overwrite the first node's row instead of updating
# its own, and that row would never receive its own update at all.
NODE_LABELS = {
    "chief_plan":              "Chief Investigation Officer — Planning",
    "crime_records":           "Crime Records Agent",
    "network_analysis":        "Network Analysis Agent",
    "entity_resolution":       "Entity Resolution Agent",
    "timeline_reconstruction": "Timeline Reconstruction Agent",
    "financial_agent":         "Financial Intelligence Agent",
    "similar_case":            "Similar Case Agent",
    "pattern_analysis":        "Pattern & MO Agent",
    "forecasting_agent":       "Forecasting Agent",
    "prevention_agent":        "Prevention Intelligence Agent",
    "evidence_validation":     "Evidence Validation Agent",
    "chief_synthesis":         "Chief Investigation Officer — Synthesis",
}


def _make_localizing_sender(send, target_language: str, translator: TranslationService):
    """
    Stage D, Sprint 2: wraps an event `send` callable so every event's
    `message` also gets a parallel Kannada (or other target-language)
    translation attached under `data.localized_message`, without ever
    touching `message` itself. `message` stays the canonical English
    string every existing frontend/consumer already reads — this is
    strictly additive, per Golden Rule 1 (never rename), applied to the
    WebSocket event shape as much as to APIs/tables.

    Not inserted into the orchestration graph — this wraps the *sender*
    the streaming runner already calls after each node completes, so no
    node, agent, or the graph topology itself is touched.
    """
    async def send_localized(event: dict):
        message = event.get("message")
        if not message:
            await send(event)
            return
        result = translator.translate(message, target_language=target_language, source_language="en")
        localized = dict(event)
        data = dict(event.get("data") or {})
        data["localized_message"] = result.text
        data["localized_language"] = target_language
        data["translation_confidence"] = result.confidence
        if result.warnings:
            data["translation_warnings"] = result.warnings
        localized["data"] = data
        await send(localized)
    return send_localized


def _localize_report(final_report: dict, target_language: str, translator: TranslationService,
                      original_query: str | None = None) -> dict:
    """
    Stage D, Sprint 2 (groundwork for Sprint D4's export modes): attaches
    a `localized` block to a copy of `final_report` — the narrative plus
    each accepted finding's summary, translated as one batch call. The
    original `narrative`/`findings` keys are left completely untouched,
    so any existing consumer (PDF export, frontend, demo scripts) that
    only knows about the English shape keeps working unmodified; a
    consumer that wants Kannada reads `final_report["localized"]`.

    `original_query` (Sprint D4): the un-translated query text as the
    person actually typed/spoke it, if translation happened. Stashed
    verbatim (not re-translated — it's already in the target language)
    so Sprint D4's PDF export can show "what the officer actually asked"
    instead of only the English text the pipeline worked from.
    """
    narrative = final_report.get("narrative") or ""
    findings = final_report.get("findings") or []
    summaries = [f.get("summary", "") for f in findings]

    texts = [narrative] + summaries
    results = translator.batch_translate(texts, target_language=target_language, source_language="en")

    localized_narrative = results[0].text if results else narrative
    localized_summaries = [r.text for r in results[1:]]
    warnings = [w for r in results for w in r.warnings]

    localized_findings = []
    for f, summary in zip(findings, localized_summaries):
        lf = dict(f)
        lf["summary"] = summary
        localized_findings.append(lf)

    report_copy = dict(final_report)
    report_copy["localized"] = {
        "language": target_language,
        "narrative": localized_narrative,
        "findings": localized_findings,
        "warnings": warnings,
        "original_query": original_query,
    }
    return report_copy


async def stream_investigation(query: str, send, session_id: int | None = None,
                                enable_discussion: bool = False, language: str | None = None):
    """
    Run the investigation pipeline and call `send(event_dict)` after each
    node. `send` is an async callable (WebSocket.send_json or an SSE helper).

    Builds a fresh DB session and graph service per investigation so
    concurrent requests don't share state.

    `session_id` (Stage C2, optional): if provided, this must be an
    existing InvestigationSession id. The raw query is resolved against
    that session's conversation memory ("expand his network" ->
    "expand Ravi Kumar's network") before being handed to the Chief, and
    the finished turn is persisted so the next turn on the same session
    can resolve against it too. Omitting session_id (existing callers,
    e.g. demo scripts) behaves exactly as before this sprint.

    Sprint 2: `resolve_turn` may also decide this turn needs a
    clarification question ("Show Ravi and Manoj" -> "Tell me about him")
    instead of a resolved query. When that happens the pipeline is never
    run — a `clarification_needed` event is sent and a lightweight turn
    is recorded so the *next* message on this session (e.g. "Ravi") is
    checked against the pending question first.

    `enable_discussion` (Stage C4, Sprint 3, optional, default False):
    when True, once the pipeline finishes, `DiscussionEngine` runs over
    this turn's validated findings and streams each specialist's opinion,
    any detected disagreements (with an explanation), and a consensus —
    then persists all three as one `DiscussionRecord` row. Defaults to
    False specifically so every existing caller (frontend, demo scripts,
    voice router) is completely unaffected unless it opts in — per
    Golden Rule 5, "everything new must degrade gracefully". Does not
    change the Chief's own final_report in any way; see
    backend/discussion/engine.py's docstring for why discussion is a
    parallel, additive step rather than inserted into the frozen graph.

    `language` (Stage D, Sprint 2, optional): the person's language for
    this turn — "en" or "kn". If omitted, it's auto-detected from `query`
    itself (per the Sprint D1 requirement to not depend solely on an
    explicit parameter), so Kannada queries are translated even when a
    caller forgets to pass it. If a non-English language is in effect
    (explicit or detected), the query is translated to English *before*
    conversation-memory resolution and the pipeline ever see it — nothing
    downstream of this point knows translation happened, per the Stage D
    architecture ("Translation Layer -> Chief -> ... -> Localization
    Layer"). Every event this call emits from here on is additionally
    localized (see `_make_localizing_sender`); `final_report` gets a
    parallel `localized` block. Omitting `language` and passing an
    English query behaves exactly as before this sprint — no translation
    call is made at all.
    """
    translator = TranslationService()
    detection = detect_language(query)
    effective_language = language or detection.language
    if effective_language not in SUPPORTED_LANGUAGES:
        effective_language = "en"

    original_query = query
    if effective_language != "en":
        query_translation = translator.translate(query, target_language="en", source_language=effective_language)
        query = query_translation.text
        await send(make_event(
            EventType.QUERY_TRANSLATED,
            agent="Language Service",
            message=f'Translated query from {effective_language} to English for processing.',
            data={
                "original_query": original_query,
                "translated_query": query,
                "source_language": effective_language,
                "confidence": query_translation.confidence,
                "engine": query_translation.engine,
                "warnings": query_translation.warnings,
            },
        ))
        send = _make_localizing_sender(send, effective_language, translator)

    await send(make_event(EventType.INVESTIGATION_STARTED, message=f"Investigation started: {query}"))

    session = SessionLocal()
    try:
        memory = ConversationMemoryService(session) if session_id is not None else None
        resolved_query = query
        if memory is not None:
            db = DatabaseService(session)
            if db.get_session(session_id) is None:
                await send(make_event(EventType.ERROR, message=f"Unknown session_id {session_id}."))
                return

            result = memory.resolve_turn(session_id, query)

            if result.needs_clarification:
                await send(make_event(
                    EventType.CLARIFICATION_NEEDED,
                    agent="Conversation Memory",
                    message=result.clarification_question,
                    data={
                        "reference": result.clarification_reference,
                        "options": [
                            {"id": o.id, "kind": o.kind, "label": o.label}
                            for o in result.clarification_options
                        ],
                    },
                ))
                memory.record_turn(session_id, raw_query=query, resolved_query=query,
                                    final_state=None, pending_clarification=result)
                return

            if result.topic_reset:
                await send(make_event(
                    EventType.TOPIC_RESET,
                    agent="Conversation Memory",
                    message=f'Context reset ("{result.reset_phrase}"). Prior entity references cleared.',
                ))
                if not result.resolved_query.strip():
                    # Reset phrase alone, nothing else to investigate this turn.
                    memory.record_turn(session_id, raw_query=query, resolved_query=query,
                                        final_state=None, topic_reset_phrase=result.reset_phrase)
                    return

            resolved_query = result.resolved_query
            if resolved_query != query and not result.topic_reset:
                await send(make_event(
                    EventType.AGENT_COMPLETED,
                    agent="Conversation Memory",
                    message=f'Resolved "{query}" -> "{resolved_query}" from session history.',
                ))
            if result.unsupported_reference:
                await send(make_event(
                    EventType.AGENT_COMPLETED,
                    agent="Conversation Memory",
                    message=(f'"{result.unsupported_reference}" isn\'t something I can resolve from '
                              f'context yet — please name it directly.'),
                ))

        graph_service = get_graph_service(backend="networkx", session=session)
        graph = build_investigation_graph(session, graph_service)

        initial_state = {
            "query": resolved_query,
            "raw_query": query,
            "resolved_query": resolved_query,
            "conversation_id": "live",
            "session_id": session_id,
            "investigation_plan": {},
            "active_agents": [],
            "findings": [],
            "validated_findings": [],
            "evidence_log": [],
            "graph_context": {},
            "final_report": {},
            "audit_trail": [],
        }

        final_state = None
        for step in graph.stream(initial_state):
            node_name, node_state = next(iter(step.items()))
            display_name = NODE_LABELS.get(node_name, node_name)

            # Pull the latest audit entry for this node's message
            trail = node_state.get("audit_trail", [])
            message = trail[-1]["message"] if trail else f"{display_name} completed."
            status = trail[-1]["status"] if trail else "done"

            etype = (
                EventType.AGENT_SKIPPED if status == "skipped"
                else EventType.AGENT_FAILED if status == "failed"
                else EventType.AGENT_COMPLETED
            )

            # Attach new findings as data payload for the frontend
            new_findings = node_state.get("findings", [])
            validated = node_state.get("validated_findings")
            report = node_state.get("final_report")

            await send(make_event(
                etype,
                agent=display_name,
                message=message,
                data={
                    "new_findings": new_findings,
                    "validated_findings": validated,
                    "final_report": report,
                },
            ))

            # Small yield so the event loop can flush the send
            await asyncio.sleep(0.05)
            final_state = node_state

        # Emit the complete final report
        if final_state:
            combined_report = final_state.get("final_report") or {}
            report_for_client = combined_report
            if effective_language != "en" and combined_report:
                report_for_client = _localize_report(combined_report, effective_language, translator,
                                                       original_query=original_query)

            await send(make_event(
                EventType.REPORT_READY,
                agent="Chief Investigation Officer",
                message="Investigation complete. Final report ready.",
                data={"final_report": report_for_client},
            ))

            recorded_turn = None
            if memory is not None:
                recorded_turn = memory.record_turn(
                    session_id, raw_query=query, resolved_query=resolved_query,
                    final_state=final_state,
                    topic_reset_phrase=result.reset_phrase if result.topic_reset else None)

            if enable_discussion:
                turn_index = recorded_turn.turn_index if recorded_turn is not None else None
                await run_discussion(send, session, session_id, turn_index, resolved_query, combined_report)

    except Exception as e:
        logger.exception("Investigation pipeline failed for query: %r", query)
        await send(make_event(EventType.ERROR, message=str(e)))
    finally:
        session.close()


async def run_discussion(send, session, session_id, turn_index, query: str, final_report: dict):
    """Stage C4, Sprint 3: run DiscussionEngine over this turn's validated
    findings, streaming each step and persisting the result as one
    DiscussionRecord row. Isolated in its own try/except so a discussion
    failure (e.g. the LLM call erroring) never takes down an otherwise-
    successful investigation — the report the person came for has
    already been sent by the time this runs."""
    try:
        await send(make_event(EventType.DISCUSSION_STARTED, agent="Discussion Engine",
                               message="Reviewing specialist findings for agreement/disagreement..."))

        findings = final_report.get("findings") or []
        engine = DiscussionEngine(session=session)
        opinions = engine.build_opinions(findings)
        disagreements = engine.detect_disagreements(opinions)
        consensus = engine.compute_consensus(opinions, disagreements)

        for op in opinions:
            await send(make_event(
                EventType.DISCUSSION_OPINION,
                agent=op.agent_name,
                message=op.claim,
                data={"confidence": op.confidence, "missing_evidence": op.missing_evidence,
                      "evidence": op.evidence, "finding_type": op.finding_type},
            ))

        for d in disagreements:
            await send(make_event(
                EventType.DISCUSSION_DISAGREEMENT,
                agent="Discussion Engine",
                message=d.explanation,
                data={"entity_kind": d.entity_kind, "entity_id": d.entity_id,
                      "entity_label": d.entity_label, "confidence_spread": d.confidence_spread,
                      "opinions": d.opinions},
            ))

        await send(make_event(
            EventType.DISCUSSION_CONSENSUS,
            agent="Discussion Engine",
            message=consensus.recommended_conclusion,
            data={"overall_confidence": consensus.overall_confidence,
                  "per_agent_confidence": consensus.per_agent_confidence,
                  "consensus_score": consensus.consensus_score,
                  "agreement_count": consensus.agreement_count,
                  "disagreement_count": consensus.disagreement_count,
                  "evidence_requests": consensus.evidence_requests},
        ))

        from dataclasses import asdict
        record = DiscussionRecord(
            session_id=session_id,
            turn_index=turn_index,
            query=query,
            opinions_json=json.dumps([asdict(o) for o in opinions]),
            disagreements_json=json.dumps([asdict(d) for d in disagreements]),
            consensus_json=json.dumps(asdict(consensus)),
        )
        session.add(record)
        session.commit()
    except Exception:
        logger.exception("Discussion Mode failed for query: %r (investigation itself already completed)", query)
        await send(make_event(EventType.ERROR, agent="Discussion Engine",
                               message="Discussion Mode failed, but the investigation result above is unaffected."))


async def run_investigation_once(query: str, session_id: int | None = None,
                                  language: str | None = None) -> dict:
    """Convenience wrapper for callers that just want the finished
    report, not a live event feed — e.g. Stage C3's voice command router,
    which needs one synchronous-feeling result to hand back to the
    browser's TTS. Internally just drains `stream_investigation`'s events
    and returns the `report_ready` payload (or raises on `error`).

    `language` (Stage D, Sprint 2, optional): forwarded to
    `stream_investigation` unchanged. Existing callers that omit it keep
    getting English-only behavior exactly as before this sprint."""
    events = []

    async def collect(event: dict):
        events.append(event)

    await stream_investigation(query, collect, session_id=session_id, language=language)

    error = next((e for e in events if e.get("event_type") == "error"), None)
    if error:
        raise RuntimeError(error.get("message", "Investigation failed."))

    report_event = next((e for e in events if e.get("event_type") == "report_ready"), None)
    if report_event is None:
        raise RuntimeError("Investigation did not produce a final report.")
    return report_event["data"]["final_report"]
