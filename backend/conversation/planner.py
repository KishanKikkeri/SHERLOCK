"""
SHERLOCK — Stage F3: Conversational Intelligence — Planner.

Handles context-aware intent classification, pronoun/entity resolution,
ambiguity detection, and tool-budget planning before any execution.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from backend.conversation.intent import ClassifiedIntent, classify_intent
from backend.conversation.router import ConversationIntent, route
from backend.conversation.llm import get_conversation_llm
from backend.conversation.tools import TOOL_SCHEMAS

logger = logging.getLogger(__name__)


class PlannedPlan:
    def __init__(
        self,
        intent: ConversationIntent,
        resolved_query: str,
        tools_to_call: List[Dict[str, Any]],
        ambiguity_detected: bool = False,
        clarification_question: str | None = None
    ):
        self.intent = intent
        self.resolved_query = resolved_query
        self.tools_to_call = tools_to_call  # list of {"name": "...", "arguments": {...}}
        self.ambiguity_detected = ambiguity_detected
        self.clarification_question = clarification_question


class ConversationPlanner:
    def __init__(self, db):
        self.db = db
        self.llm = get_conversation_llm()

    def plan(self, message: str, context: dict, language: str = "en") -> PlannedPlan:
        """Analyze message in context, resolve references, detect ambiguity, and plan tools."""
        # 1. Check if LLM is a real LLM (not DeterministicAdapter)
        from backend.conversation.llm import DeterministicAdapter
        if isinstance(self.llm, DeterministicAdapter):
            return self._plan_deterministic(message, context, language)

        try:
            return self._plan_llm(message, context, language)
        except Exception:
            logger.warning("LLM planning failed, falling back to deterministic planning", exc_info=True)
            return self._plan_deterministic(message, context, language)

    def _plan_llm(self, message: str, context: dict, language: str = "en") -> PlannedPlan:
        # Prompt the LLM to return a JSON block mapping the plan
        system_prompt = (
            "You are the Conversation Planner for SHERLOCK, an AI crime intelligence system. "
            "Your task is to analyze the user's query in context of the conversation and memory, "
            "resolve references, classify intent, and output a structured tool-calling plan.\n\n"
            "Intent categories:\n"
            "- greeting: User says hello, hi, how are you.\n"
            "- chitchat: General chat, capability questions, thanks, bye.\n"
            "- investigate: Query requires case records, accomplice graph search, database lookups.\n"
            "- summarize: User requests a summary of the conversation.\n"
            "- clear_history: User requests to start over or clear history.\n"
            "- export_pdf: User wants to download a PDF report.\n\n"
            "Available tools:\n"
            + json.dumps(TOOL_SCHEMAS, indent=2) + "\n\n"
            "Rules:\n"
            "1. Resolve pronouns ('him', 'them', 'the second one', 'his brother') to real entities in the context.\n"
            "2. Decide if existing memory/history is sufficient to answer (if so, tools_to_call is empty).\n"
            "3. If new data is needed, select the MINIMUM required tools. Avoid duplicate investigations.\n"
            "4. If query is ambiguous (e.g. 'tell me about him' when multiple suspects are in context), set 'ambiguity_detected' to true and fill 'clarification_question'.\n"
            "5. Output ONLY valid JSON in the specified format, no other text."
        )

        user_prompt = (
            f"Active Context:\n{json.dumps(context, indent=2)}\n\n"
            f"User Query: {message}\n\n"
            "Output JSON format:\n"
            "{\n"
            "  \"resolved_query\": \"query with pronouns resolved\",\n"
            "  \"intent\": \"investigate\" | \"chitchat\" | \"greeting\" | \"summarize\" | \"clear_history\" | \"export_pdf\",\n"
            "  \"ambiguity_detected\": false,\n"
            "  \"clarification_question\": null,\n"
            "  \"tools_to_call\": [\n"
            "    {\"name\": \"tool_name\", \"arguments\": {\"arg\": \"val\"}}\n"
            "  ]\n"
            "}"
        )

        response_text = self.llm.completion(system_prompt, user_prompt)
        # Parse JSON output
        try:
            # Clean up potential markdown formatting block
            match = re.search(r"\{.*\}", response_text, re.DOTALL)
            json_str = match.group(0) if match else response_text
            res = json.loads(json_str)

            intent_str = res.get("intent", "investigate")
            intent = ConversationIntent(intent_str) if intent_str in [i.value for i in ConversationIntent] else ConversationIntent.INVESTIGATE

            return PlannedPlan(
                intent=intent,
                resolved_query=res.get("resolved_query", message),
                tools_to_call=res.get("tools_to_call") or [],
                ambiguity_detected=res.get("ambiguity_detected", False),
                clarification_question=res.get("clarification_question")
            )
        except Exception as e:
            logger.warning("Failed to parse LLM planning response: %s", response_text)
            raise e

    def _plan_deterministic(self, message: str, context: dict, language: str = "en") -> PlannedPlan:
        """Fallback logic using regex/intent engine when no LLM is configured."""
        from backend.memory.conversation_memory import ConversationMemoryService
        memory_svc = ConversationMemoryService(self.db)

        # Resolve turn (pronoun, topic reset, clarification)
        resolve_res = memory_svc.resolve_turn(context["session_id"], message)

        # Map to ConversationIntent
        classified = classify_intent(
            message,
            context_summary=context.get("conversation_summary"),
            has_pending_clarification=context.get("has_pending_clarification", False),
            has_context=len(context.get("previous_messages", [])) > 0
        )

        intent = classified.intent

        # Determine tools
        tools_to_call = []
        if intent == ConversationIntent.INVESTIGATE:
            # Decide if general investigate or specific tool
            # For simplicity in deterministic mode, run investigation pipeline
            tools_to_call.append({
                "name": "investigate",
                "arguments": {"query": resolve_res.resolved_query}
            })
        elif intent == ConversationIntent.FOLLOWUP:
            # If follow up, run graph search
            tools_to_call.append({
                "name": "search_graph",
                "arguments": {"query": resolve_res.resolved_query}
            })

        return PlannedPlan(
            intent=intent,
            resolved_query=resolve_res.resolved_query,
            tools_to_call=tools_to_call,
            ambiguity_detected=resolve_res.needs_clarification,
            clarification_question=resolve_res.clarification_question
        )
