"""
SHERLOCK — Stage F3: ConversationOrchestrator.

The core coordinator of the SHERLOCK V2 conversation-first, tool-driven architecture.
Replaces the old ConversationManager.

Orchestrates:
1. Session Context & Memory Retrieval
2. Tool Budget Planning (ConversationPlanner)
3. Parallel Tool Execution (ToolGateway)
4. Conversational Response Formatting (ConversationAgent)
5. Session Turn Recording
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List

from backend.api.events import EventType, make_event
from backend.api.investigation_stream import stream_investigation
from backend.conversation import citations as citations_mod
from backend.conversation import prompts as prompts_mod
from backend.conversation.planner import ConversationPlanner
from backend.conversation.conversation_agent import ConversationAgent
from backend.conversation.memory import ConversationStateMemory
from backend.conversation.tool_gateway import ToolGateway
from backend.conversation.tools import call_tool
from backend.conversation.router import ConversationIntent
from backend.conversation.session import get_or_create_session
from backend.conversation.summarizer import summarize_now
from backend.database.models import ConversationTurn
from backend.reporting.pdf_export import generate_investigation_pdf

logger = logging.getLogger(__name__)


# Friendly display status messages mapping internal agent names
THINKING_MESSAGES = {
    "chief_plan": "Planning investigation scope...",
    "crime_records": "Searching case records and FIRs...",
    "network_analysis": "Analyzing accomplice network...",
    "entity_resolution": "Resolving suspect identities...",
    "timeline_reconstruction": "Reconstructing offender timeline...",
    "financial_agent": "Tracing financial transactions...",
    "similar_case": "Searching for similar cases...",
    "pattern_analysis": "Detecting crime modus patterns...",
    "forecasting_agent": "Computing risk forecasts...",
    "prevention_agent": "Analyzing prevention intelligence...",
    "evidence_validation": "Validating evidence against database...",
    "chief_synthesis": "Synthesizing final findings...",
}


class ConversationOrchestrator:
    def __init__(self, db, roles: List[str] | None = None):
        from backend.memory.conversation_memory import ConversationMemoryService
        self.db = db
        self.planner = ConversationPlanner(db)
        self.agent = ConversationAgent(db)
        self.gateway = ToolGateway(db, roles=roles)
        self.memory = ConversationMemoryService(db)

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

        # 1. Retrieve history and memory state context
        memory = ConversationStateMemory(self.db, sid)
        context = memory.get_context_for_llm()

        # 2. Plan intent and tool budgeting
        plan = self.planner.plan(message, context, language=language or "en")
        intent = plan.intent

        # Handle Meta-commands directly
        if intent == ConversationIntent.SUMMARIZE:
            res = summarize_now(self.db, sid)
            return self._make_result(sid, intent, message, res["summary"] or "Nothing to summarize yet.")
        elif intent == ConversationIntent.CLEAR_HISTORY:
            self._clear_history(sid, message)
            return self._make_result(sid, intent, message, "Conversation context cleared. Starting fresh.")
        elif intent == ConversationIntent.EXPORT_PDF:
            pdf_bytes, warnings = self.export_last_report_as_pdf(sid, language=language or "en")
            res = self._make_result(sid, intent, message, "Report exported." if pdf_bytes else "No findings to export.")
            res["pdf_available"] = pdf_bytes is not None
            res["pdf_warnings"] = warnings
            return res

        # 3. Clarification responses
        if plan.ambiguity_detected:
            reply = plan.clarification_question or "Could you clarify who/what you mean?"
            self._record_lightweight_turn(sid, message, reply)
            return self._make_result(sid, intent, message, reply)

        # 4. Execute tool plan (parallel execution where possible)
        tool_results = {}
        findings = []
        rejected_findings = []
        if plan.tools_to_call:
            # Parallel execution
            tool_results = await self.gateway.execute_tools_parallel(
                plan.tools_to_call, session_id=sid, language=language or "en"
            )
            # Retrieve investigate tool findings if run
            for tc in plan.tools_to_call:
                if tc["name"] == "investigate":
                    key = f"investigate({json.dumps(tc.get('arguments'))})"
                    res = tool_results.get(key) or {}
                    findings = res.get("findings") or []
                    rejected_findings = res.get("rejected_findings") or []

        # 5. Format conversational response
        conversational_reply = self.agent.generate_response(
            message=message,
            history=context["previous_messages"],
            context=context,
            tool_results=tool_results,
            language=language or "en"
        )

        # 6. Record turn to database
        is_investigation = any(tc["name"] == "investigate" for tc in plan.tools_to_call)
        if is_investigation:
            # Investigate tool automatically records turn in stream_investigation, update its response summary
            last_turn = memory.memory_service.get_last_turn(sid)
            if last_turn:
                last_turn.response_summary = conversational_reply[:500]
                self.db.commit()
        else:
            self._record_lightweight_turn(sid, message, conversational_reply)

        last_turn = memory.memory_service.get_last_turn(sid)

        return {
            "session_id": sid,
            "intent": intent.value,
            "message": message,
            "reply": conversational_reply,
            "final_report": {
                "query": message,
                "findings": findings,
                "rejected_findings": rejected_findings,
            } if is_investigation else None,
            "citations": citations_mod.build_citations(self.db, findings) if is_investigation else [],
            "suggested_questions": prompts_mod.suggest_questions(last_turn),
        }

    async def stream_events(
        self,
        session_id: int | None,
        message: str,
        officer_id: int | None = None,
        language: str | None = None,
        enable_discussion: bool = False,
    ) -> AsyncGenerator[dict, None]:
        message = (message or "").strip()
        if not message:
            yield make_event(EventType.ERROR, message="Empty query.")
            return

        session_row = get_or_create_session(self.db, session_id, officer_id=officer_id)
        sid = session_row.id

        # 1. Retrieve context & memory snapshot
        memory = ConversationStateMemory(self.db, sid)
        context = memory.get_context_for_llm()

        # 2. Plan turn
        plan = self.planner.plan(message, context, language=language or "en")
        intent = plan.intent

        # Handle Meta-commands
        if intent in (ConversationIntent.SUMMARIZE, ConversationIntent.CLEAR_HISTORY, ConversationIntent.EXPORT_PDF):
            res = await self.handle_message(
                sid, message, officer_id=officer_id, language=language,
                enable_discussion=enable_discussion
            )
            yield make_event(
                EventType.REPORT_READY,
                agent="Conversation Orchestrator",
                message=res["reply"],
                data={"final_report": None, "conversation_result": res},
            )
            return

        # Handle ambiguity
        if plan.ambiguity_detected:
            reply = plan.clarification_question or "Could you clarify who/what you mean?"
            self._record_lightweight_turn(sid, message, reply)
            yield make_event(
                EventType.CONVERSATION_REPLY,
                agent="SHERLOCK",
                message=reply,
                data={"conversation_result": self._make_result(sid, intent, message, reply)},
            )
            return

        # 3. Execute tools
        if plan.tools_to_call:
            yield make_event(
                EventType.THINKING,
                agent="SHERLOCK",
                message=f"Executing tool(s): {', '.join(tc['name'] for tc in plan.tools_to_call)}..."
            )

            # Check if investigate tool is in the plan
            investigate_call = next((tc for tc in plan.tools_to_call if tc["name"] == "investigate"), None)
            if investigate_call:
                investigation_query = investigate_call.get("arguments", {}).get("query", message)
                events = []

                async def collect(event: dict):
                    events.append(event)

                await stream_investigation(
                    investigation_query, collect, session_id=sid,
                    enable_discussion=enable_discussion, language=language
                )

                findings = []
                final_report_data = {}
                for event in events:
                    event_type = event.get("event_type")
                    agent_name = event.get("agent")
                    
                    # Normalise to friendly status updates
                    if event_type in ("agent_started", "agent_completed") and agent_name in THINKING_MESSAGES:
                        event["message"] = THINKING_MESSAGES[agent_name]

                    if event_type == "report_ready":
                        final_report_data = (event.get("data") or {}).get("final_report") or {}
                        findings = final_report_data.get("findings") or []
                        
                        # Conversational summary from agent
                        conversational_reply = self.agent.generate_response(
                            message=message,
                            history=context["previous_messages"],
                            context=context,
                            tool_results={"investigate": {"findings": findings}},
                            language=language or "en"
                        )
                        
                        data = dict(event.get("data") or {})
                        data["citations"] = citations_mod.build_citations(self.db, findings)
                        data["session_id"] = sid
                        data["conversational_reply"] = conversational_reply
                        event["data"] = data
                        event["message"] = conversational_reply

                    yield event

                # Update the turn in database
                if final_report_data:
                    last_turn = memory.memory_service.get_last_turn(sid)
                    if last_turn:
                        last_turn.response_summary = final_report_data.get("conversational_reply", "")[:500]
                        self.db.commit()
                return

            else:
                # Other look-ups/traces
                tool_results = await self.gateway.execute_tools_parallel(
                    plan.tools_to_call, session_id=sid, language=language or "en"
                )

                # Format response
                conversational_reply = self.agent.generate_response(
                    message=message,
                    history=context["previous_messages"],
                    context=context,
                    tool_results=tool_results,
                    language=language or "en"
                )

                self._record_lightweight_turn(sid, message, conversational_reply)
                
                yield make_event(
                    EventType.CONVERSATION_REPLY,
                    agent="SHERLOCK",
                    message=conversational_reply,
                    data={"conversation_result": self._make_result(sid, intent, message, conversational_reply)},
                )
                return

        # 4. Direct Response (No tools needed)
        conversational_reply = self.agent.generate_response(
            message=message,
            history=context["previous_messages"],
            context=context,
            tool_results=None,
            language=language or "en"
        )
        self._record_lightweight_turn(sid, message, conversational_reply)
        yield make_event(
            EventType.CONVERSATION_REPLY,
            agent="SHERLOCK",
            message=conversational_reply,
            data={"conversation_result": self._make_result(sid, intent, message, conversational_reply)},
        )

    @staticmethod
    def _make_result(
        session_id: int,
        intent: ConversationIntent,
        message: str,
        reply: str,
        suggested_questions: list[str] | None = None,
    ) -> dict:
        return {
            "session_id": session_id,
            "intent": intent.value,
            "message": message,
            "reply": reply,
            "final_report": None,
            "citations": [],
            "suggested_questions": suggested_questions or [],
        }

    def _record_lightweight_turn(
        self, session_id: int, raw_query: str, reply: str,
    ) -> None:
        turns = self.db.query(ConversationTurn).filter_by(session_id=session_id).all()
        next_index = len(turns)

        turn = ConversationTurn(
            session_id=session_id,
            turn_index=next_index,
            raw_query=raw_query,
            resolved_query=None,
            response_summary=reply[:500] if reply else None,
            findings_json=None,
            entity_mentions_json=None,
            pending_clarification_json=None,
            topic_reset=None,
        )
        self.db.add(turn)
        self.db.commit()

    def _clear_history(self, session_id: int, matched_phrase: str) -> None:
        turns = self.db.query(ConversationTurn).filter_by(session_id=session_id).all()
        now = datetime.now(timezone.utc)
        for t in turns:
            if t.archived_at is None:
                t.archived_at = now
        if turns:
            self.db.commit()

        # Add a topic reset marker turn
        from backend.memory.conversation_memory import ConversationMemoryService
        memory_svc = ConversationMemoryService(self.db)
        memory_svc.record_turn(
            session_id,
            raw_query="[conversation cleared]",
            resolved_query="",
            final_state=None,
            topic_reset_phrase=matched_phrase[:255],
        )

    def export_last_report_as_pdf(self, session_id: int, language: str = "en") -> tuple[bytes | None, list[str]]:
        from backend.memory.conversation_memory import ConversationMemoryService
        memory_svc = ConversationMemoryService(self.db)
        last_turn = memory_svc.get_last_turn(session_id)
        if last_turn is None or not last_turn.findings_json:
            return None, ["No investigation findings recorded for this session yet."]

        final_report = {
            "narrative": last_turn.response_summary or "",
            "findings": json.loads(last_turn.findings_json),
        }

        if language in ("kn", "bilingual"):
            from backend.language.translation_service import TranslationService
            from backend.api.investigation_stream import _localize_report
            translator = TranslationService()
            final_report = _localize_report(final_report, "kn", translator)

        pdf_bytes = generate_investigation_pdf(
            final_report, audit_trail=[], case_id=f"session-{session_id}", language=language,
        )
        return pdf_bytes, []
