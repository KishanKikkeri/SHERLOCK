"""
SHERLOCK — Stage F2: ConversationManager.

The single entry point the new `/conversation/*` routes (and, later, any
other chat-shaped client) call through. It does not reimplement anything
the pipeline already does — it sequences existing pieces:

    raw message
        -> router.route()                      (meta-command or investigate?)
        -> session.get_or_create_session()      (Stage C1)
        -> [investigate] run_investigation_once  (existing, session-aware —
                                                   resolves pronouns via
                                                   Stage C2 memory internally)
           or a meta-command handler below
        -> citations.build_citations()          (evidence, for the UI)
        -> prompts.suggest_questions()          (follow-ups, for the UI)

`handle_message` is the non-streaming path (POST /conversation/message).
`stream_events` is a thin async-generator wrapper for the streaming path
(POST /conversation/stream, SSE) — for INVESTIGATE it hands off directly
to `stream_investigation` so the live per-agent activity feed behaves
identically to the WebSocket path; meta-commands complete in one event
since there's no multi-agent pipeline to narrate.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from backend.api.events import EventType, make_event
from backend.api.investigation_stream import run_investigation_once, stream_investigation
from backend.conversation import citations as citations_mod
from backend.conversation import prompts as prompts_mod
from backend.conversation.router import ConversationIntent, route
from backend.conversation.session import get_or_create_session
from backend.conversation.summarizer import summarize_now
from backend.database.models import ConversationTurn
from backend.memory.conversation_memory import ConversationMemoryService
from backend.reporting.pdf_export import generate_investigation_pdf

logger = logging.getLogger(__name__)


class ConversationManager:
    def __init__(self, db):
        self.db = db
        self.memory = ConversationMemoryService(db)

    # -- non-streaming ----------------------------------------------------

    async def handle_message(
        self,
        session_id: int | None,
        message: str,
        officer_id: int | None = None,
        language: str | None = None,
        enable_discussion: bool = False,
    ) -> dict:
        message = (message or "").strip()
        if not message:
            raise ValueError("message is required.")

        session_row = get_or_create_session(self.db, session_id, officer_id=officer_id)
        sid = session_row.id
        intent = route(message)

        if intent.intent == ConversationIntent.SUMMARIZE:
            result = summarize_now(self.db, sid)
            return {
                "session_id": sid,
                "intent": intent.intent.value,
                "message": message,
                "reply": result["summary"] or "Nothing to summarize yet — ask an investigative question first.",
                "final_report": None,
                "citations": [],
                "suggested_questions": prompts_mod.suggest_questions(self.memory.get_last_turn(sid)),
            }

        if intent.intent == ConversationIntent.CLEAR_HISTORY:
            self._clear_history(sid, matched_phrase=intent.matched_phrase or message)
            return {
                "session_id": sid,
                "intent": intent.intent.value,
                "message": message,
                "reply": "Conversation context cleared. Prior turns stay on the record for audit "
                         "purposes (SHERLOCK never deletes investigative history), but the next "
                         "question starts fresh — no carried-over pronouns or entities.",
                "final_report": None,
                "citations": [],
                "suggested_questions": prompts_mod.suggest_questions(None),
            }

        if intent.intent == ConversationIntent.EXPORT_PDF:
            pdf_bytes, warnings = self.export_last_report_as_pdf(sid, language=language or "en")
            return {
                "session_id": sid,
                "intent": intent.intent.value,
                "message": message,
                "reply": "Report exported." if pdf_bytes else
                         "Nothing to export yet — ask an investigative question first.",
                "final_report": None,
                "citations": [],
                "suggested_questions": prompts_mod.suggest_questions(self.memory.get_last_turn(sid)),
                "pdf_available": pdf_bytes is not None,
                "pdf_warnings": warnings,
            }

        # Default: run the actual investigation. `run_investigation_once`
        # already resolves against session memory and records the turn —
        # see backend/api/investigation_stream.py.
        final_report = await run_investigation_once(message, session_id=sid, language=language)
        last_turn = self.memory.get_last_turn(sid)
        findings = final_report.get("findings") or []

        return {
            "session_id": sid,
            "intent": intent.intent.value,
            "message": message,
            "reply": final_report.get("narrative") or final_report.get("summary") or "",
            "final_report": final_report,
            "citations": citations_mod.build_citations(self.db, findings),
            "suggested_questions": prompts_mod.suggest_questions(last_turn),
        }

    # -- streaming ----------------------------------------------------------

    async def stream_events(
        self,
        session_id: int | None,
        message: str,
        officer_id: int | None = None,
        language: str | None = None,
        enable_discussion: bool = False,
    ):
        """Async generator of event dicts, same shape as the WebSocket
        path (`event_type`/`agent`/`message`/`data`) — see
        backend/api/events.py. The SSE route (backend/api/conversation_chat.py)
        just serializes whatever this yields."""
        message = (message or "").strip()
        if not message:
            yield make_event(EventType.ERROR, message="Empty query.")
            return

        session_row = get_or_create_session(self.db, session_id, officer_id=officer_id)
        sid = session_row.id
        intent = route(message)

        if intent.intent != ConversationIntent.INVESTIGATE:
            # Meta-commands aren't a multi-agent pipeline — reuse
            # handle_message so the logic isn't duplicated, then flatten
            # it into a single terminal event for the SSE stream.
            result = await self.handle_message(
                sid, message, officer_id=officer_id, language=language,
                enable_discussion=enable_discussion,
            )
            yield make_event(
                EventType.REPORT_READY,
                agent="Conversation Manager",
                message=result["reply"],
                data={"final_report": None, "conversation_result": result},
            )
            return

        events: list[dict] = []

        async def collect(event: dict):
            events.append(event)

        # Drain stream_investigation's own event queue into ours. It isn't
        # itself an async generator (it takes a `send` callback, for the
        # WebSocket's sake), so we buffer then re-yield — SSE responses
        # are generated after the coroutine completes either way, since
        # StreamingResponse pulls from an async generator, not a socket.
        await stream_investigation(
            message, collect, session_id=sid,
            enable_discussion=enable_discussion, language=language,
        )

        # Enrich the terminal report_ready event with the same
        # citations/suggested_questions handle_message returns, so a
        # streaming client gets evidence cards + follow-ups too, not just
        # the WebSocket's raw final_report shape.
        last_turn = self.memory.get_last_turn(sid)
        for event in events:
            if event.get("event_type") == "report_ready":
                final_report = (event.get("data") or {}).get("final_report") or {}
                findings = final_report.get("findings") or []
                data = dict(event.get("data") or {})
                data["citations"] = citations_mod.build_citations(self.db, findings)
                data["suggested_questions"] = prompts_mod.suggest_questions(last_turn)
                data["session_id"] = sid
                event = dict(event)
                event["data"] = data
            yield event
        return

    # -- meta-command helpers -------------------------------------------------

    def _clear_history(self, session_id: int, matched_phrase: str) -> None:
        """Soft-archives every existing turn (Stage E5 "no physical
        deletion" rule — see backend/security/retention.py) and records a
        topic-reset marker turn using the same, already-tested mechanism
        `resolve_turn` uses for "start over" / "forget the previous
        topic" phrases, so pronoun/entity carry-forward genuinely stops
        without inventing a second reset mechanism."""
        turns = self.memory.get_history(session_id)
        now = datetime.now(timezone.utc)
        for t in turns:
            if t.archived_at is None:
                t.archived_at = now
        if turns:
            self.db.commit()

        self.memory.record_turn(
            session_id,
            raw_query="[conversation cleared]",
            resolved_query="",
            final_state=None,
            topic_reset_phrase=matched_phrase[:255],
        )

    def export_last_report_as_pdf(self, session_id: int, language: str = "en") -> tuple[bytes | None, list[str]]:
        """Best-effort PDF export from what's actually persisted for this
        session. Known limitation, documented rather than hidden:
        `ConversationTurn` stores `findings_json` + `response_summary`,
        not a full `SherlockState["final_report"]` (narrative header,
        audit_trail) — see backend/database/models/conversation.py's own
        docstring on why. So this synthesizes a minimal report shape
        (`narrative` = last response_summary, `findings` = last turn's
        findings) good enough for a real PDF, rather than the richer
        report `POST /export/pdf` produces immediately after a live
        investigation (which has the full in-memory final_report)."""
        last_turn = self.memory.get_last_turn(session_id)
        if last_turn is None or not last_turn.findings_json:
            return None, ["No investigation findings recorded for this session yet."]

        final_report = {
            "narrative": last_turn.response_summary or "",
            "findings": json.loads(last_turn.findings_json),
        }
        pdf_bytes = generate_investigation_pdf(
            final_report, audit_trail=[], case_id=f"session-{session_id}", language=language,
        )
        return pdf_bytes, []
