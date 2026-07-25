"""
SHERLOCK — Stage F3: Conversational Intelligence — Conversation Agent.

Generates concise, natural-sounding, context-aware responses (3-6 sentences)
from conversation history, memory state, and structured tool outputs.

Excludes internal agent names, reasoning logs, and raw statistics
unless explicitly requested.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from backend.conversation.llm import get_conversation_llm, DeterministicAdapter
from backend.language.prompting import language_directive

logger = logging.getLogger(__name__)


class ConversationAgent:
    def __init__(self, db):
        self.db = db
        self.llm = get_conversation_llm()

    def generate_response(
        self,
        message: str,
        history: list[dict],
        context: dict,
        tool_results: dict | None = None,
        language: str = "en"
    ) -> str:
        """Formulates the final user-facing reply from history, context, and tool outputs."""
        if isinstance(self.llm, DeterministicAdapter):
            # Fallback to deterministic responders
            return self._generate_deterministic(message, context, tool_results, language)

        try:
            return self._generate_llm(message, history, context, tool_results, language)
        except Exception:
            logger.warning("LLM response generation failed, falling back to deterministic", exc_info=True)
            return self._generate_deterministic(message, context, tool_results, language)

    def _generate_llm(
        self,
        message: str,
        history: list[dict],
        context: dict,
        tool_results: dict | None = None,
        language: str = "en"
    ) -> str:
        system_prompt = (
            "You are SHERLOCK, a conversational crime detective assistant. "
            "Your personality should be clean, natural, and highly capable, like ChatGPT.\n\n"
            "STRICT RULES:\n"
            "1. Answer in 3-6 sentences. Keep it extremely concise (under 150 words) unless explicitly asked to expand.\n"
            "2. NEVER expose internal agent names (e.g. CrimeRecords, FinancialAgent, SimilarCase).\n"
            "3. NEVER expose confidence scores, percentages, or reasoning metrics.\n"
            "4. NEVER dump raw JSON or raw reports.\n"
            "5. Progressive Disclosure: Offer details, timelines, financial links, or PDF reports naturally as follow-up options, but do not show them by default.\n"
            + language_directive(language)
        )

        user_prompt = (
            f"Conversation History:\n{json.dumps(history[-8:], indent=2)}\n\n"
            f"Active Context:\n{json.dumps(context, indent=2)}\n\n"
            f"User Message: {message}\n\n"
        )

        if tool_results:
            user_prompt += f"Structured Tool Results:\n{json.dumps(tool_results, indent=2)}\n\n"

        user_prompt += "Generate the natural conversational response:"

        return self.llm.completion(system_prompt, user_prompt, max_tokens=450).strip()

    def _generate_deterministic(
        self,
        message: str,
        context: dict,
        tool_results: dict | None = None,
        language: str = "en"
    ) -> str:
        """Deterministic responder when LLM is unavailable."""
        from backend.conversation.responder import respond_to_greeting, respond_to_chitchat, _format_response_template
        
        # Simple intent check
        from backend.conversation.intent import classify_intent
        classified = classify_intent(message, has_context=True)

        if classified.intent == "greeting":
            return respond_to_greeting(message)
        elif classified.intent == "chitchat":
            return respond_to_chitchat(message)

        if tool_results:
            # Format using deterministic template
            findings = []
            for key, val in tool_results.items():
                if isinstance(val, dict):
                    findings.extend(val.get("findings") or val.get("results") or [])
            
            return _format_response_template(message, "", findings, language=language)

        return "I have updated the conversation context with your query."
