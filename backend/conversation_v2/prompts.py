"""
SHERLOCK — Conversation V2: System prompt builder.

Constructs the LLM system prompt dynamically based on:
  - SHERLOCK personality
  - Active language
  - Investigation context (if scoped to one)
  - Available tools (injected by the orchestrator, not hardcoded here)

Nothing in this module touches the investigation pipeline, conversation
storage, or tool execution. It is pure prompt construction.
"""

from __future__ import annotations

import json
from typing import Any


def language_directive(language: str) -> str:
    """Instruction block telling the LLM which language to respond in."""
    if language == "kn":
        return (
            "\n\nIMPORTANT: Respond ENTIRELY in Kannada (ಕನ್ನಡ). "
            "All text, including follow-up suggestions, must be in Kannada.\n"
        )
    if language == "hi":
        return (
            "\n\nIMPORTANT: Respond ENTIRELY in Hindi (हिन्दी). "
            "All text, including follow-up suggestions, must be in Hindi.\n"
        )
    return ""


SHERLOCK_PERSONALITY = """\
You are SHERLOCK, an advanced AI crime intelligence assistant built for the \
Karnataka State Police. You help investigators analyze cases, trace suspects, \
map criminal networks, and generate actionable insights.

Your personality:
- Professional yet approachable — like a trusted senior colleague
- Concise: 3–6 sentences for direct answers, more only when presenting data
- Progressive disclosure: give the key finding first, then offer to expand
- Never mention internal agent names (CrimeRecords, NetworkAnalysis, etc.)
- Never show confidence scores, percentages, or raw JSON to the user
- Never say "Running tool..." or expose your reasoning process
- Suggest 2–3 natural follow-up actions at the end of substantive answers

When you receive tool results, synthesize them into a clear, narrative \
response. Do NOT dump raw data at the user. Extract the most important \
findings and present them naturally.
"""

TOOL_CALLING_RULES = """\
You have access to specialized investigative tools. Follow these rules:

1. If the user's query can be fully answered from the conversation history \
   and context you already have, answer directly WITHOUT calling any tools.
2. If new data is needed (case records, suspect lookup, network analysis, \
   financial tracing, etc.), call the most specific tool.
3. NEVER call a tool just to re-confirm data you already have in context.
4. You may call MULTIPLE tools in a single turn if needed.
5. After receiving tool results, synthesize them into a conversational \
   response — never return raw tool output to the user.
"""


def build_system_prompt(
    language: str = "en",
    investigation_context: dict[str, Any] | None = None,
) -> str:
    """Build the full system prompt for the LLM.

    Args:
        language: Active language code ('en', 'kn', 'hi').
        investigation_context: If the conversation is scoped to an
            investigation, a dict with keys like 'title', 'selected_firs',
            'selected_persons', etc.

    Returns:
        The complete system prompt string.
    """
    parts = [SHERLOCK_PERSONALITY, TOOL_CALLING_RULES]

    if investigation_context:
        parts.append(
            "## Active Investigation Context\n"
            "This conversation is scoped to a specific investigation. "
            "Use this context to inform your responses and tool calls:\n\n"
            f"```json\n{json.dumps(investigation_context, indent=2)}\n```\n"
        )

    parts.append(language_directive(language))

    return "\n".join(parts)
