"""
SHERLOCK — Stage F3: Conversational Intelligence — Pluggable LLM Interface.

Defines the single, pluggable `ConversationLLM` interface and concrete
adapters for Claude (Anthropic), GPT-4o (OpenAI), and Gemini (Google GenAI).

The rest of the system only interacts with this interface, making it
easy to change LLM models or keys without modifying the ConversationManager.
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any

from backend.conversation.intent import ClassifiedIntent
from backend.conversation.router import ConversationIntent, route
from backend.conversation.tools import TOOL_SCHEMAS
from backend.language.prompting import language_directive

logger = logging.getLogger(__name__)


class LLMResult:
    """The result of running the Conversation LLM."""
    def __init__(
        self,
        reply: str | None = None,
        tool_call: dict | None = None,
        intent: ConversationIntent = ConversationIntent.INVESTIGATE
    ):
        self.reply = reply
        self.tool_call = tool_call  # {"name": "...", "arguments": {...}}
        self.intent = intent


class ConversationLLM(ABC):
    @abstractmethod
    def run_conversation(
        self,
        message: str,
        history: list[dict],
        context: dict,
        language: str = "en"
    ) -> LLMResult:
        """Determines if a tool call is needed, or returns a direct reply."""
        pass

    @abstractmethod
    def format_findings(
        self,
        query: str,
        findings: list[dict],
        context: dict,
        language: str = "en"
    ) -> str:
        """Summarizes structured tool findings into a concise, natural response."""
        pass

    @abstractmethod
    def format_analytics(
        self,
        data: dict,
        language: str = "en"
    ) -> str:
        """Generates a natural-language executive summary from structured analytics dashboard data."""
        pass

    @abstractmethod
    def completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 400
    ) -> str:
        """Runs a raw text completion request."""
        pass


# ---------------------------------------------------------------------------
# Claude Adapter
# ---------------------------------------------------------------------------

class ClaudeAdapter(ConversationLLM):
    def __init__(self, api_key: str):
        from anthropic import Anthropic
        self.client = Anthropic(api_key=api_key)

    def run_conversation(
        self,
        message: str,
        history: list[dict],
        context: dict,
        language: str = "en"
    ) -> LLMResult:
        # Build prompt showing prior history and context
        system_prompt = (
            "You are SHERLOCK, a conversational crime detective assistant. "
            "Your personality should be clean, natural, and helpful, like ChatGPT.\n\n"
            "You have access to a set of specialized investigative tools. "
            "If the user asks a greeting, chitchat, or a question you can fully answer from the "
            "provided conversation history and context, answer immediately WITHOUT calling any tools.\n"
            "If you need new data, case searches, graph expansion, or detailed investigation, select "
            "the most specific tool to call.\n\n"
            "Rules for direct responses:\n"
            "1. Answer in 3-5 sentences. Keep it concise.\n"
            "2. Never mention agent names (e.g., CrimeRecords, NetworkAnalysis).\n"
            "3. Never show confidence scores or percentages.\n"
            "4. Never say 'Running tool...' or expose reasoning logs.\n"
            "5. Make natural progressive offers to explore further (e.g. suspects, timeline, financial links).\n"
            + language_directive(language)
        )

        formatted_history = []
        for h in history[-8:]:  # last 8 messages
            role = "user" if h["role"] == "user" else "assistant"
            formatted_history.append({"role": role, "content": h.get("text", "")})

        # Inject context summary
        context_str = f"Active Context:\n{json.dumps(context, indent=2)}"
        formatted_history.append({"role": "user", "content": f"Context:\n{context_str}\n\nUser Message: {message}"})

        # Convert schemas to Anthropic format
        claude_tools = []
        for t in TOOL_SCHEMAS:
            claude_tools.append({
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["parameters"]
            })

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=400,
            system=system_prompt,
            messages=formatted_history,
            tools=claude_tools
        )

        # Check for tool call
        tool_use = None
        reply = ""
        for block in response.content:
            if block.type == "tool_use":
                tool_use = {
                    "name": block.name,
                    "arguments": block.input
                }
            elif block.type == "text":
                reply += block.text

        if tool_use:
            return LLMResult(tool_call=tool_use, intent=ConversationIntent.INVESTIGATE)

        # Determine conversational intent based on reply/query
        routed = route(message)
        intent = routed.intent if routed.intent != ConversationIntent.INVESTIGATE else ConversationIntent.CHITCHAT
        return LLMResult(reply=reply.strip(), intent=intent)

    def format_findings(
        self,
        query: str,
        findings: list[dict],
        context: dict,
        language: str = "en"
    ) -> str:
        system_prompt = (
            "You are SHERLOCK, a crime intelligence assistant. "
            "Explain the structured tool findings conversationally to the user.\n\n"
            "STRICT RULES:\n"
            "1. Answer in 3-5 sentences. Never exceed this.\n"
            "2. NEVER mention agent names or expose internal confidence scores.\n"
            "3. Summarize the facts naturally and professionally.\n"
            "4. Suggest 2-3 follow-up actions (timeline, financial links, network) at the end.\n"
            + language_directive(language)
        )

        findings_text = json.dumps(findings[:10], indent=2)
        prompt = f"User query: {query}\n\nStructured findings:\n{findings_text}"

        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=400,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()

    def format_analytics(
        self,
        data: dict,
        language: str = "en"
    ) -> str:
        system_prompt = (
            "You are SHERLOCK, a crime pattern & trend analytics assistant. "
            "Write a concise, professional crime pattern executive summary based on the "
            "provided structured dashboard metrics. Keep it under 5 sentences, factual, "
            "and cite key numbers directly. Do not invent any statistics.\n"
            + language_directive(language)
        )
        prompt = f"Dashboard Data:\n{json.dumps(data, indent=2)}"
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()

    def completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 400
    ) -> str:
        response = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(block.text for block in response.content if block.type == "text").strip()




# ---------------------------------------------------------------------------
# OpenAI Adapter
# ---------------------------------------------------------------------------

class OpenAIAdapter(ConversationLLM):
    def __init__(self, api_key: str, base_url: str | None = None, model: str | None = None):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model or "gpt-4o"

    def run_conversation(
        self,
        message: str,
        history: list[dict],
        context: dict,
        language: str = "en"
    ) -> LLMResult:
        messages = [
            {"role": "system", "content": (
                "You are SHERLOCK, a conversational crime detective assistant. "
                "Your personality should be clean, natural, and helpful, like ChatGPT.\n\n"
                "If the user asks a greeting, chitchat, or a question you can fully answer from the "
                "provided history/context, reply directly. Otherwise, choose a tool.\n"
                "Rules: 3-5 sentences max, no agent names, no confidence scores.\n"
                + language_directive(language)
            )}
        ]

        for h in history[-8:]:
            messages.append({"role": "user" if h["role"] == "user" else "assistant", "content": h.get("text", "")})

        messages.append({"role": "user", "content": f"Context: {json.dumps(context)}\n\nQuery: {message}"})

        # OpenAI tools list
        openai_tools = [{"type": "function", "function": t} for t in TOOL_SCHEMAS]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=openai_tools,
            max_tokens=400
        )

        choice = response.choices[0].message
        if choice.tool_calls:
            tc = choice.tool_calls[0].function
            return LLMResult(
                tool_call={"name": tc.name, "arguments": json.loads(tc.arguments)},
                intent=ConversationIntent.INVESTIGATE
            )

        reply = choice.content or ""
        routed = route(message)
        intent = routed.intent if routed.intent != ConversationIntent.INVESTIGATE else ConversationIntent.CHITCHAT
        return LLMResult(reply=reply.strip(), intent=intent)

    def format_findings(
        self,
        query: str,
        findings: list[dict],
        context: dict,
        language: str = "en"
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": (
                    "You are SHERLOCK, a crime intelligence assistant. "
                    "Explain findings conversationally in 3-5 sentences. No agent names or scores.\n"
                    + language_directive(language)
                )},
                {"role": "user", "content": f"Query: {query}\nFindings: {json.dumps(findings[:10])}"}
            ],
            max_tokens=400
        )
        return response.choices[0].message.content.strip()

    def format_analytics(
        self,
        data: dict,
        language: str = "en"
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": (
                    "You are SHERLOCK, a crime pattern & trend analytics assistant. "
                    "Write a concise, professional crime pattern executive summary based on the "
                    "provided structured dashboard metrics. Keep it under 5 sentences, factual, "
                    "and cite key numbers directly. Do not invent any statistics.\n"
                    + language_directive(language)
                )},
                {"role": "user", "content": f"Dashboard Data: {json.dumps(data)}" }
            ],
            max_tokens=300
        )
        return response.choices[0].message.content.strip()

    def completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 400
    ) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=max_tokens
        )
        return response.choices[0].message.content or ""




# ---------------------------------------------------------------------------
# Google Gemini Adapter
# ---------------------------------------------------------------------------

class GeminiAdapter(ConversationLLM):
    def __init__(self, api_key: str):
        from google import genai
        # google-genai package uses GenAI client
        self.client = genai.Client(api_key=api_key)

    def run_conversation(
        self,
        message: str,
        history: list[dict],
        context: dict,
        language: str = "en"
    ) -> LLMResult:
        # Use gemini-2.5-pro or gemini-2.5-flash for tool calling
        system_prompt = (
            "You are SHERLOCK, a conversational crime detective assistant. "
            "Answer directly if you have context, or call tools if needed. "
            "Concise, 3-5 sentences, no agent names, no confidence scores.\n"
            + language_directive(language)
        )

        # Gemini SDK structures calls in Content objects
        from google.genai import types

        # Convert schemas to Gemini FunctionDeclarations
        gemini_tools = []
        for t in TOOL_SCHEMAS:
            gemini_tools.append(types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        k: types.Schema(
                            type=types.Type.STRING if v["type"] == "string" else types.Type.INTEGER,
                            description=v.get("description", "")
                        )
                        for k, v in t["parameters"]["properties"].items()
                    },
                    required=t["parameters"].get("required", [])
                )
            ))

        gemini_tool_config = types.Tool(function_declarations=gemini_tools)

        contents = []
        for h in history[-8:]:
            contents.append(types.Content(
                role="user" if h["role"] == "user" else "model",
                parts=[types.Part.from_text(text=h.get("text", ""))]
            ))

        contents.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"Context: {json.dumps(context)}\n\nQuery: {message}")]
        ))

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=[gemini_tool_config],
            max_output_tokens=400
        )

        response = self.client.models.generate_content(
            model="gemini-2.5-pro",
            contents=contents,
            config=config
        )

        # Parse calls
        function_calls = response.function_calls
        if function_calls:
            call = function_calls[0]
            # Convert args back to dict
            args = {k: v for k, v in call.args.items()}
            return LLMResult(
                tool_call={"name": call.name, "arguments": args},
                intent=ConversationIntent.INVESTIGATE
            )

        reply = response.text or ""
        routed = route(message)
        intent = routed.intent if routed.intent != ConversationIntent.INVESTIGATE else ConversationIntent.CHITCHAT
        return LLMResult(reply=reply.strip(), intent=intent)

    def format_findings(
        self,
        query: str,
        findings: list[dict],
        context: dict,
        language: str = "en"
    ) -> str:
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=(
                "You are SHERLOCK, a crime intelligence assistant. "
                "Explain findings conversationally in 3-5 sentences. No agent names or scores.\n"
                + language_directive(language)
            ),
            max_output_tokens=400
        )
        response = self.client.models.generate_content(
            model="gemini-2.5-pro",
            contents=f"Query: {query}\nFindings: {json.dumps(findings[:10])}",
            config=config
        )
        return response.text.strip()

    def format_analytics(
        self,
        data: dict,
        language: str = "en"
    ) -> str:
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=(
                "You are SHERLOCK, a crime pattern & trend analytics assistant. "
                "Write a concise, professional crime pattern executive summary based on the "
                "provided structured dashboard metrics. Keep it under 5 sentences, factual, "
                "and cite key numbers directly. Do not invent any statistics.\n"
                + language_directive(language)
            ),
            max_output_tokens=300
        )
        response = self.client.models.generate_content(
            model="gemini-2.5-pro",
            contents=f"Dashboard Data: {json.dumps(data)}",
            config=config
        )
        return response.text.strip()

    def completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 400
    ) -> str:
        from google.genai import types
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens
        )
        response = self.client.models.generate_content(
            model="gemini-2.5-pro",
            contents=user_prompt,
            config=config
        )
        return response.text or ""




# ---------------------------------------------------------------------------
# Deterministic Fallback Adapter (No API Keys)
# ---------------------------------------------------------------------------

class DeterministicAdapter(ConversationLLM):
    def run_conversation(
        self,
        message: str,
        history: list[dict],
        context: dict,
        language: str = "en"
    ) -> LLMResult:
        # Standard fallback rules (reuses regex classification logic)
        from backend.conversation.intent import classify_intent
        from backend.conversation.responder import respond_to_greeting, respond_to_chitchat

        classified = classify_intent(
            message,
            context_summary=context.get("context_summary"),
            has_pending_clarification=context.get("has_pending_clarification", False),
            has_context=len(history) > 0
        )

        if classified.intent == ConversationIntent.GREETING:
            return LLMResult(reply=respond_to_greeting(message), intent=classified.intent)
        elif classified.intent == ConversationIntent.CHITCHAT:
            return LLMResult(reply=respond_to_chitchat(message), intent=classified.intent)
        elif classified.intent == ConversationIntent.FOLLOWUP:
            # Let the tool registry handle follow-up by calling search_graph or investigate
            return LLMResult(
                tool_call={"name": "search_graph", "arguments": {"query": message}},
                intent=ConversationIntent.INVESTIGATE
            )
        elif classified.intent == ConversationIntent.CLARIFICATION_RESPONSE:
            # Reuses clarification resolution
            return LLMResult(
                tool_call={"name": "search_graph", "arguments": {"query": message}},
                intent=ConversationIntent.INVESTIGATE
            )
        elif classified.intent in (ConversationIntent.SUMMARIZE, ConversationIntent.EXPORT_PDF, ConversationIntent.CLEAR_HISTORY):
            return LLMResult(reply=None, tool_call=None, intent=classified.intent)

        # Default: call investigate tool
        return LLMResult(
            tool_call={"name": "investigate", "arguments": {"query": message}},
            intent=ConversationIntent.INVESTIGATE
        )

    def format_findings(
        self,
        query: str,
        findings: list[dict],
        context: dict,
        language: str = "en"
    ) -> str:
        # Reuses Stage F3 deterministic fallback formatter
        from backend.conversation.responder import _format_response_template
        # ChiefAgent.synthesis_node returns narrative="", so format_findings generates the layout
        return _format_response_template(query, "", findings, language=language)

    def format_analytics(
        self,
        data: dict,
        language: str = "en"
    ) -> str:
        # Reuses existing _executive_summary template helper
        from backend.analytics.summary_engine import _executive_summary
        # Extract individual inputs from aggregated data dict
        trend = data.get("charts", {}).get("trend", {})
        # Mock other fields if needed, but since data is already compiled we can pass it
        return _executive_summary(
            trend=trend,
            type_distribution=data.get("charts", {}).get("type_distribution", {}),
            top_hotspots=data.get("tables", {}).get("top_hotspots", []),
            outbreaks=data.get("insights", {}).get("outbreaks", []),
            spikes=data.get("insights", {}).get("spikes", []),
            repeat_sites=data.get("insights", {}).get("repeat_incident_clusters", []),
            festival=data.get("insights", {}).get("festival_concentration", [])
        )

    def completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 400
    ) -> str:
        # Reuses existing deterministic responders or returns a structured fallback JSON for planner
        if "Output JSON format" in user_prompt:
            # We can mock a planner JSON output matching the user's message
            # Clean user message out of user_prompt:
            msg_match = re.search(r"User Query:\s*(.*)", user_prompt)
            msg = msg_match.group(1).strip() if msg_match else ""
            
            # Simple fallback intent detection
            from backend.conversation.intent import classify_intent
            from backend.conversation.router import route
            
            # Use basic intent classifier
            classified = classify_intent(msg, has_context=True)
            
            tools_to_call = []
            if classified.intent == ConversationIntent.INVESTIGATE:
                tools_to_call.append({
                    "name": "investigate",
                    "arguments": {"query": msg}
                })
            elif classified.intent == ConversationIntent.FOLLOWUP:
                tools_to_call.append({
                    "name": "search_graph",
                    "arguments": {"query": msg}
                })

            res = {
                "resolved_query": msg,
                "intent": classified.intent.value,
                "ambiguity_detected": False,
                "clarification_question": None,
                "tools_to_call": tools_to_call
            }
            return json.dumps(res)
            
        return ""



# ---------------------------------------------------------------------------
# Pluggable Factory
# ---------------------------------------------------------------------------

def get_conversation_llm() -> ConversationLLM:
    """Resolves and loads the ConversationLLM provider based on env settings."""
    provider = os.getenv("SHERLOCK_LLM_PROVIDER", "").strip().lower()

    openai_key = os.getenv("OPENAI_API_KEY")
    openai_base = os.getenv("SHERLOCK_OPENAI_BASE_URL")
    openai_model = os.getenv("SHERLOCK_OPENAI_MODEL")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    # 1. OpenRouter support
    if provider == "openrouter" or openrouter_key or (openai_base and "openrouter" in openai_base.lower()):
        key = openrouter_key or openai_key
        base = openai_base or "https://openrouter.ai/api/v1"
        model = openai_model or "google/gemini-2.5-pro"
        if key:
            logger.info("Loading OpenAIAdapter configured for OpenRouter (model: %s)", model)
            return OpenAIAdapter(api_key=key, base_url=base, model=model)

    # 2. Explicitly configured provider
    if provider == "openai" and openai_key:
        logger.info("Loading pluggable OpenAIAdapter (model: %s)", openai_model or "gpt-4o")
        return OpenAIAdapter(api_key=openai_key, base_url=openai_base, model=openai_model)
    elif provider == "gemini" and (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        logger.info("Loading pluggable GeminiAdapter")
        return GeminiAdapter(key)
    elif provider == "claude" and os.getenv("ANTHROPIC_API_KEY"):
        logger.info("Loading pluggable ClaudeAdapter")
        return ClaudeAdapter(os.getenv("ANTHROPIC_API_KEY"))

    # 3. Key-based automatic fallback
    if os.getenv("ANTHROPIC_API_KEY"):
        logger.info("Auto-loading ClaudeAdapter (ANTHROPIC_API_KEY set)")
        return ClaudeAdapter(os.getenv("ANTHROPIC_API_KEY"))
    elif openai_key:
        logger.info("Auto-loading OpenAIAdapter (OPENAI_API_KEY set)")
        return OpenAIAdapter(api_key=openai_key, base_url=openai_base, model=openai_model)
    elif os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        logger.info("Auto-loading GeminiAdapter (GEMINI/GOOGLE key set)")
        return GeminiAdapter(key)

    # 4. Fallback to deterministic regex-driven dry-run
    logger.info("Auto-loading DeterministicAdapter (no LLM API keys set)")
    return DeterministicAdapter()
