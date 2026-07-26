"""
SHERLOCK — Conversation V2: LLM Orchestrator.

The single brain of the new conversation system. Replaces:
  - ``ConversationManager`` (backend/conversation/manager.py)
  - ``ConversationOrchestrator`` (backend/conversation/orchestrator.py)
  - ``ConversationPlanner`` (backend/conversation/planner.py)
  - ``ConversationAgent`` (backend/conversation/conversation_agent.py)
  - ``intent.py`` / ``router.py`` (regex-based routing)

Flow:
  1. Load conversation history (recent N messages from MessageV2)
  2. Load investigation context if scoped (selected entities, graph state)
  3. Build system prompt with personality, language, tools, context
  4. Call LLM with full message history + tool schemas
  5. If LLM returns tool calls → execute via ToolRegistry → feed results
     back → get final answer (multi-turn tool loop)
  6. Store all messages (user, tool calls/results, assistant reply)
  7. Return/stream the assistant response

Core principle:
    The LLM decides what to do. No regex routing, no hardcoded intent
    classification. The LLM sees the tools and picks the right ones.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator

from sqlalchemy.orm import Session

from backend.conversation_v2.llm import ConversationLLM, get_conversation_llm
from backend.conversation_v2.memory import (
    get_or_create_conversation,
    load_conversation_messages,
    store_message,
)
from backend.conversation_v2.prompts import build_system_prompt
from backend.tools.registry import ToolContext, ToolRegistry
from backend.tools.tool_definitions import build_default_registry

logger = logging.getLogger(__name__)

# Maximum tool-call rounds before forcing a text response
MAX_TOOL_ROUNDS = 5

# Some agents (e.g. SociologicalIntelligence, WitnessIntelligence,
# OrganizationIntelligence) attach every matching entity ID to a finding's
# source_entities / supporting_graph / related_documents with no cap — for a
# broad query this can mean hundreds of person IDs per finding, across up to
# 16 agents. That produces tool-result payloads of several hundred KB to
# multiple MB, which is fine over localhost but unreliable over a real
# network (proxy/timeout limits) — the likely cause of messages that appear
# to "vanish" with no reply once deployed. This caps list fields in-place
# before the result is stored or streamed, without touching agent logic.
_MAX_LIST_ITEMS = 8


def _slim_findings_payload(tool_result: dict) -> dict:
    def slim_finding(f: dict) -> dict:
        if not isinstance(f, dict):
            return f
        out = dict(f)
        for key in ("source_entities", "evidence", "related_documents"):
            val = out.get(key)
            if isinstance(val, list) and len(val) > _MAX_LIST_ITEMS:
                out[key] = val[:_MAX_LIST_ITEMS] + [f"... +{len(val) - _MAX_LIST_ITEMS} more"]
        sg = out.get("supporting_graph")
        if isinstance(sg, dict):
            out["supporting_graph"] = {
                k: (v[:_MAX_LIST_ITEMS] + [f"... +{len(v) - _MAX_LIST_ITEMS} more"]
                    if isinstance(v, list) and len(v) > _MAX_LIST_ITEMS else v)
                for k, v in sg.items()
            }
        meta = out.get("metadata")
        if isinstance(meta, dict):
            out["metadata"] = {
                k: (v[:_MAX_LIST_ITEMS] + [f"... +{len(v) - _MAX_LIST_ITEMS} more"]
                    if isinstance(v, list) and len(v) > _MAX_LIST_ITEMS else v)
                for k, v in meta.items()
            }
        return out

    if not isinstance(tool_result, dict):
        return tool_result
    result = dict(tool_result)
    for key in ("findings", "rejected_findings"):
        if isinstance(result.get(key), list):
            result[key] = [slim_finding(f) for f in result[key]]
    return result


@dataclass
class AssistantResponse:
    """Structured response from the orchestrator."""
    conversation_id: int
    reply: str
    tool_calls: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    suggested_questions: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass
class StreamEvent:
    """One event in the SSE stream."""
    event_type: str        # 'thinking' | 'tool_started' | 'tool_completed' |
                           # 'assistant_reply' | 'error'
    message: str = ""
    data: dict = field(default_factory=dict)
    agent: str = "SHERLOCK"


class LLMOrchestrator:
    """The single orchestration brain of Conversation V2.

    Usage::

        orchestrator = LLMOrchestrator(db)
        response = await orchestrator.handle_message(
            conversation_id=None,  # creates new conversation
            message="Show repeat offenders in Mysuru",
            language="en",
        )
    """

    def __init__(
        self,
        db: Session,
        llm: ConversationLLM | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.db = db
        self.llm = llm or get_conversation_llm()
        self.tools = tool_registry or build_default_registry()

    # ------------------------------------------------------------------
    # Public API: non-streaming
    # ------------------------------------------------------------------

    async def handle_message(
        self,
        conversation_id: int | None,
        message: str,
        language: str = "en",
        investigation_id: int | None = None,
    ) -> AssistantResponse:
        """Process one user message and return the assistant's response."""

        # 1. Ensure conversation exists
        conv = get_or_create_conversation(
            self.db, conversation_id, investigation_id, language
        )

        # 2. Store the user message
        store_message(self.db, conv.id, role="user", content=message)

        # 3. Build LLM context
        history = load_conversation_messages(self.db, conv.id)
        investigation_ctx = self._load_investigation_context(investigation_id)
        system_prompt = build_system_prompt(language, investigation_ctx)
        tool_schemas = self.tools.get_all_schemas()

        # 4. LLM tool-calling loop
        all_tool_calls: list[dict] = []
        rounds = 0

        while rounds < MAX_TOOL_ROUNDS:
            rounds += 1
            result = self.llm.run_conversation(
                message=message if rounds == 1 else "",
                history=history,
                context={"system_prompt": system_prompt},
                language=language,
            )

            # Direct reply — no tools needed
            if result.reply and not result.tool_call:
                reply_text = result.reply
                # Store assistant reply
                store_message(
                    self.db, conv.id, role="assistant", content=reply_text
                )
                return AssistantResponse(
                    conversation_id=conv.id,
                    reply=reply_text,
                    tool_calls=all_tool_calls,
                )

            # Tool call requested
            if result.tool_call:
                call_id = f"tc_{uuid.uuid4().hex[:8]}"
                tool_name = result.tool_call["name"]
                tool_args = result.tool_call.get("arguments", {})
                all_tool_calls.append({
                    "call_id": call_id,
                    "name": tool_name,
                    "arguments": tool_args,
                })

                # Store the assistant's tool-call decision
                store_message(
                    self.db, conv.id, role="assistant",
                    content=None,
                    tool_calls_json=json.dumps([{
                        "call_id": call_id,
                        "name": tool_name,
                        "arguments": tool_args,
                    }]),
                )

                # Execute the tool
                ctx = ToolContext(
                    db=self.db,
                    conversation_id=conv.id,
                    investigation_id=investigation_id,
                    language=language,
                )
                try:
                    tool_result = await self.tools.execute(
                        tool_name, tool_args, ctx
                    )
                except Exception as e:
                    logger.exception("Tool %s failed", tool_name)
                    tool_result = {"status": "error", "message": str(e)}

                tool_result = _slim_findings_payload(tool_result)

                # Store the tool result
                store_message(
                    self.db, conv.id, role="tool",
                    tool_name=tool_name,
                    tool_result_json=json.dumps(tool_result),
                    tool_call_id=call_id,
                )

                # Reload history with the new tool result for next LLM round
                history = load_conversation_messages(self.db, conv.id)

                # Format the tool results into a natural response
                formatted = self.llm.format_findings(
                    message,
                    tool_result.get("findings", [tool_result]),
                    {"system_prompt": system_prompt},
                    language=language,
                )

                # Store final assistant reply
                metadata = {}
                if tool_result.get("findings"):
                    metadata["citations"] = [
                        {"source": f.get("source", ""), "text": f.get("title", "")}
                        for f in tool_result["findings"][:5]
                    ]

                store_message(
                    self.db, conv.id, role="assistant",
                    content=formatted,
                    metadata_json=json.dumps(metadata) if metadata else None,
                )

                return AssistantResponse(
                    conversation_id=conv.id,
                    reply=formatted,
                    tool_calls=all_tool_calls,
                    citations=metadata.get("citations", []),
                )

            # Neither reply nor tool call — shouldn't happen, but break
            break

        # Fallback if we exceed MAX_TOOL_ROUNDS
        fallback_reply = "I've completed my analysis. Let me know if you'd like to explore further."
        store_message(self.db, conv.id, role="assistant", content=fallback_reply)
        return AssistantResponse(
            conversation_id=conv.id,
            reply=fallback_reply,
            tool_calls=all_tool_calls,
        )

    # ------------------------------------------------------------------
    # Public API: streaming (SSE)
    # ------------------------------------------------------------------

    async def stream_message(
        self,
        conversation_id: int | None,
        message: str,
        language: str = "en",
        investigation_id: int | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Process one user message and yield streaming events."""

        # 1. Ensure conversation exists
        conv = get_or_create_conversation(
            self.db, conversation_id, investigation_id, language
        )
        store_message(self.db, conv.id, role="user", content=message)

        yield StreamEvent(
            event_type="thinking",
            message="Let me look into that...",
            data={"conversation_id": conv.id},
        )

        # 2. Build context
        history = load_conversation_messages(self.db, conv.id)
        investigation_ctx = self._load_investigation_context(investigation_id)
        system_prompt = build_system_prompt(language, investigation_ctx)

        # 3. LLM call
        result = self.llm.run_conversation(
            message=message,
            history=history,
            context={"system_prompt": system_prompt},
            language=language,
        )

        if result.reply and not result.tool_call:
            store_message(self.db, conv.id, role="assistant", content=result.reply)
            yield StreamEvent(
                event_type="assistant_reply",
                message=result.reply,
                data={
                    "conversation_id": conv.id,
                    "reply": result.reply,
                },
            )
            return

        if result.tool_call:
            call_id = f"tc_{uuid.uuid4().hex[:8]}"
            tool_name = result.tool_call["name"]
            tool_args = result.tool_call.get("arguments", {})

            store_message(
                self.db, conv.id, role="assistant",
                content=None,
                tool_calls_json=json.dumps([{
                    "call_id": call_id,
                    "name": tool_name,
                    "arguments": tool_args,
                }]),
            )

            yield StreamEvent(
                event_type="tool_started",
                message=f"Running {tool_name}...",
                agent=tool_name,
                data={"tool_name": tool_name, "arguments": tool_args},
            )

            ctx = ToolContext(
                db=self.db,
                conversation_id=conv.id,
                investigation_id=investigation_id,
                language=language,
            )
            try:
                tool_result = await self.tools.execute(tool_name, tool_args, ctx)
            except Exception as e:
                logger.exception("Tool %s failed", tool_name)
                tool_result = {"status": "error", "message": str(e)}
                yield StreamEvent(
                    event_type="error",
                    message=str(e),
                    agent=tool_name,
                )

            store_message(
                self.db, conv.id, role="tool",
                tool_name=tool_name,
                tool_result_json=json.dumps(_slim_findings_payload(tool_result)),
                tool_call_id=call_id,
            )

            yield StreamEvent(
                event_type="tool_completed",
                message=f"{tool_name} completed.",
                agent=tool_name,
                data={"result_summary": tool_result.get("status", "done")},
            )

            # Format and return
            formatted = self.llm.format_findings(
                message,
                tool_result.get("findings", [tool_result]),
                {"system_prompt": system_prompt},
                language=language,
            )

            store_message(self.db, conv.id, role="assistant", content=formatted)

            yield StreamEvent(
                event_type="assistant_reply",
                message=formatted,
                data={
                    "conversation_id": conv.id,
                    "reply": formatted,
                    "tool_calls": [{"name": tool_name, "arguments": tool_args}],
                },
            )
            return

        # Fallback
        fallback = "I'm not sure how to help with that. Could you rephrase?"
        store_message(self.db, conv.id, role="assistant", content=fallback)
        yield StreamEvent(
            event_type="assistant_reply",
            message=fallback,
            data={"conversation_id": conv.id, "reply": fallback},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_investigation_context(
        self, investigation_id: int | None
    ) -> dict[str, Any] | None:
        """Load investigation entity selections for prompt injection."""
        if investigation_id is None:
            return None

        from backend.database.models.investigation_v2 import InvestigationV2

        inv = self.db.get(InvestigationV2, investigation_id)
        if inv is None:
            return None

        ctx: dict[str, Any] = {
            "investigation_id": inv.id,
            "title": inv.title,
            "description": inv.description,
            "status": inv.status.value,
        }

        for attr, key in [
            ("selected_fir_ids_json", "selected_firs"),
            ("selected_person_ids_json", "selected_persons"),
            ("selected_account_ids_json", "selected_accounts"),
            ("selected_location_ids_json", "selected_locations"),
            ("selected_org_ids_json", "selected_organizations"),
        ]:
            raw = getattr(inv, attr)
            if raw:
                try:
                    ctx[key] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    pass

        return ctx
