"""
SHERLOCK — Stage F3: Conversational Intelligence — intent classification.

Sits between the raw user message and the ConversationManager's dispatch
logic. Decides *what kind* of thing the message is — a greeting, a
follow-up answerable from memory, a new investigation request, a meta-
command — so the manager can branch on intent rather than routing
everything through the investigation pipeline.

Two paths, same output:
  1. ANTHROPIC_API_KEY set: Claude classifies with a tight, few-shot
     system prompt (max 150 tokens — this is classification, not
     generation). Slower but handles edge cases and multilingual input.
  2. No key: enhanced regex set covering greetings, chitchat, and
     follow-up patterns. Same philosophy as the existing router.py and
     conversation_memory.py — fixed, documented phrases, not a general-
     purpose NLU system. Falls through to INVESTIGATE for anything
     ambiguous (safer failure mode).

Both produce a `ClassifiedIntent` dataclass so downstream code is
path-agnostic.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field

from backend.conversation.router import ConversationIntent, route

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedIntent:
    """Result of intent classification for one user message."""
    intent: ConversationIntent
    confidence: float = 1.0
    # Extracted entities/references from the message (LLM path only)
    extracted_entities: list[str] = field(default_factory=list)
    # For FOLLOWUP: what the user is asking about (e.g. "his brother")
    followup_target: str | None = None
    # The matched phrase that triggered this classification (regex path)
    matched_phrase: str | None = None


# ---------------------------------------------------------------------------
# Regex patterns — the deterministic fallback
# ---------------------------------------------------------------------------

_GREETING_RE = re.compile(
    r"^\s*("
    r"h(i|ello|ey|owdy)"
    r"|good\s+(morning|afternoon|evening|day)"
    r"|what'?s\s+up"
    r"|how\s+are\s+you"
    r"|how\s+do\s+you\s+do"
    r"|yo\b"
    r"|namaste"
    r"|namaskar[a]?"
    r")\s*[!.?]*\s*$",
    re.IGNORECASE,
)

_CHITCHAT_RE = re.compile(
    r"\b("
    r"what can you do|what are you|who are you|help me"
    r"|explain\s+(what|how|why)\b"
    r"|explain\s+\w+"
    r"|what\s+is\s+(a\s+)?(?!fir\b|case\b|investigation\b)\w+"
    r"|tell\s+me\s+about\s+(yourself|sherlock)"
    r"|thank\s*(you|s)"
    r"|thanks"
    r"|ok(ay)?\b"
    r"|got\s+it"
    r"|I\s+(see|understand)"
    r"|no\s+(thanks|thank\s+you)"
    r"|never\s*mind"
    r"|cancel"
    r"|bye"
    r"|goodbye"
    r")\b",
    re.IGNORECASE,
)

# Follow-up patterns that reference prior context and can be answered
# from memory without re-running the investigation pipeline.
_FOLLOWUP_RE = re.compile(
    r"\b("
    r"what\s+about\s+(him|her|them|that|this|it|the\s+\w+)"
    r"|show\s+(me\s+)?(the\s+)?(second|third|first|fourth|fifth|next|other|another)\s+"
    r"|compare\s+them"
    r"|go\s+(deeper|further|on)"
    r"|tell\s+me\s+more"
    r"|more\s+(details?|info(rmation)?)"
    r"|elaborate"
    r"|expand\s+on\s+(that|this|it)"
    r"|can\s+you\s+(show|explain|describe|detail)\s+(that|this|it|the\s+\w+)"
    r"|what\s+(did|does)\s+(he|she|they|it|that)\b"
    r"|who\s+(is|was|are|were)\s+(he|she|they|that)\b"
    r"|and\s+(his|her|their)\s+\w+"
    r"|what\s+else"
    r"|anything\s+else"
    r"|continue"
    r")\b",
    re.IGNORECASE,
)

# Phrases that suggest this is an answer to a pending clarification
# (e.g. "the first one", "Ravi", a bare name or ordinal). Only checked
# when the session actually has a pending clarification.
_ORDINAL_ANSWER_RE = re.compile(
    r"^\s*(the\s+)?(first|second|third|fourth|fifth)(\s+one)?\s*$",
    re.IGNORECASE,
)

# Investigation intent keywords — if these appear, override any chitchat
# or followup match. These indicate the user wants actual investigative
# work, not a conversational shortcut.
_INVESTIGATION_KEYWORDS_RE = re.compile(
    r"\b("
    r"find\b|search\b|investigate\b|analyze\b|analyse\b"
    r"|show\s+(me\s+)?(all\s+)?(fir|case|crime|suspect|offender|transaction|account|financial|network)"
    r"|trace\b|track\b"
    r"|who\s+(stole|committed|did|robbed|murdered|killed|assaulted|attacked)"
    r"|generate\s+(timeline|report|graph|network|analysis)"
    r"|fir\s*#?\s*\d+"
    r"|case\s*#?\s*\d+"
    r"|ka\d{2}[a-z]{1,2}\d{4}"
    r"|compare\s+fir"
    r"|financial\s+(link|links|trail|fraud|analysis)"
    r"|money\s+(trail|laundering)"
    r"|crime\s+(pattern|hotspot|trend)"
    r"|repeat\s+offender"
    r"|who\s+owns"
    r"|show\s+(evidence|timeline|connections|links)"
    r")\b",
    re.IGNORECASE,
)


def _classify_regex(
    message: str,
    has_pending_clarification: bool = False,
    has_context: bool = False,
) -> ClassifiedIntent:
    """Deterministic intent classification using regex patterns.

    Order matters:
      1. Meta-commands checked first (via existing route()) — authoritative.
      2. Investigation keywords override everything else — a message like
         "find the second suspect" is an investigation, not a followup.
      3. Greeting (only if the full message IS a greeting, not a substring).
      4. Pending clarification answer check.
      5. Follow-up patterns (only if there's existing context).
      6. Chitchat patterns.
      7. Default: INVESTIGATE (safer failure mode).
    """
    text = (message or "").strip()

    # 1. Existing meta-command routing — unchanged behavior
    routed = route(text)
    if routed.intent != ConversationIntent.INVESTIGATE:
        return ClassifiedIntent(
            intent=routed.intent,
            matched_phrase=routed.matched_phrase,
        )

    # 2. Explicit investigation keywords — override chitchat/followup
    m = _INVESTIGATION_KEYWORDS_RE.search(text)
    if m:
        return ClassifiedIntent(
            intent=ConversationIntent.INVESTIGATE,
            matched_phrase=m.group(0),
        )

    # 3. Pure greeting (full message is just a greeting)
    m = _GREETING_RE.match(text)
    if m:
        return ClassifiedIntent(
            intent=ConversationIntent.GREETING,
            matched_phrase=m.group(0).strip(),
        )

    # 4. Pending clarification — short answers likely responding to a question
    if has_pending_clarification:
        m = _ORDINAL_ANSWER_RE.match(text)
        if m:
            return ClassifiedIntent(
                intent=ConversationIntent.CLARIFICATION_RESPONSE,
                matched_phrase=m.group(0).strip(),
            )
        # Very short messages (1-3 words) when there's a pending
        # clarification are almost certainly answers to it.
        if len(text.split()) <= 3:
            return ClassifiedIntent(
                intent=ConversationIntent.CLARIFICATION_RESPONSE,
                matched_phrase=text,
            )

    # 5. Follow-up patterns (only meaningful with existing context)
    if has_context:
        m = _FOLLOWUP_RE.search(text)
        if m:
            return ClassifiedIntent(
                intent=ConversationIntent.FOLLOWUP,
                followup_target=m.group(0).strip(),
                matched_phrase=m.group(0).strip(),
            )

    # 6. Chitchat
    m = _CHITCHAT_RE.search(text)
    if m:
        return ClassifiedIntent(
            intent=ConversationIntent.CHITCHAT,
            matched_phrase=m.group(0).strip(),
        )

    # 7. Default — INVESTIGATE (safe fallback)
    return ClassifiedIntent(intent=ConversationIntent.INVESTIGATE)


def _classify_llm(
    message: str,
    context_summary: str | None = None,
    has_pending_clarification: bool = False,
    has_context: bool = False,
) -> ClassifiedIntent:
    """LLM-backed intent classification using Claude.

    Uses a tight system prompt with few-shot examples. Max 150 tokens —
    this is classification, not generation. Falls back to regex on any
    failure (network error, malformed response, etc.)."""
    try:
        from anthropic import Anthropic

        client = Anthropic()

        context_block = ""
        if context_summary:
            context_block = f"\n\nCurrent conversation context:\n{context_summary[:500]}"
        if has_pending_clarification:
            context_block += "\n\nThere is a PENDING CLARIFICATION QUESTION the user may be answering."

        system_prompt = (
            "You are an intent classifier for SHERLOCK, a crime investigation AI.\n"
            "Classify the user's message into exactly ONE intent. Respond with valid JSON only.\n\n"
            "Intents:\n"
            '- "greeting": Greetings, hellos. Example: "Hi", "Good morning"\n'
            '- "chitchat": Off-topic, meta questions, thanks. Example: "What can you do?", "Thanks", "Explain cybercrime"\n'
            '- "followup": References prior context, answerable from memory. Example: "What about him?", "Show the second case", "Compare them", "Tell me more"\n'
            '- "clarification_response": Short answer to a pending clarification question. Example: "The first one", "Ravi"\n'
            '- "investigate": Needs the investigation pipeline. Example: "Find Ramesh", "Search FIR 231", "Show financial links", "Who stole the bike?"\n'
            '- "summarize": Asks for conversation summary. Example: "Summarize this conversation"\n'
            '- "export_pdf": Asks for PDF export. Example: "Export as PDF"\n'
            '- "clear_history": Asks to clear conversation. Example: "Clear this conversation"\n\n'
            "Rules:\n"
            "- If a message could be either chitchat or investigation, choose investigate (safer).\n"
            "- followup is ONLY valid when there is existing context. Otherwise use investigate.\n"
            "- clarification_response is ONLY valid when there is a PENDING CLARIFICATION.\n"
            f"- Conversation has prior context: {has_context}\n\n"
            'Respond with: {"intent": "<intent>", "confidence": <0.0-1.0>}\n'
            "Nothing else."
        )

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            system=system_prompt,
            messages=[{"role": "user", "content": message + context_block}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()

        parsed = json.loads(text)
        intent_str = parsed.get("intent", "investigate")
        confidence = float(parsed.get("confidence", 0.8))

        # Map string to enum
        intent_map = {
            "greeting": ConversationIntent.GREETING,
            "chitchat": ConversationIntent.CHITCHAT,
            "followup": ConversationIntent.FOLLOWUP,
            "clarification_response": ConversationIntent.CLARIFICATION_RESPONSE,
            "investigate": ConversationIntent.INVESTIGATE,
            "summarize": ConversationIntent.SUMMARIZE,
            "export_pdf": ConversationIntent.EXPORT_PDF,
            "clear_history": ConversationIntent.CLEAR_HISTORY,
        }
        intent = intent_map.get(intent_str, ConversationIntent.INVESTIGATE)

        # Safety: don't classify as followup/clarification_response without context
        if intent == ConversationIntent.FOLLOWUP and not has_context:
            intent = ConversationIntent.INVESTIGATE
        if intent == ConversationIntent.CLARIFICATION_RESPONSE and not has_pending_clarification:
            intent = ConversationIntent.INVESTIGATE

        return ClassifiedIntent(intent=intent, confidence=confidence)

    except Exception:
        logger.warning("LLM intent classification failed, falling back to regex", exc_info=True)
        return _classify_regex(message, has_pending_clarification, has_context)


def classify_intent(
    message: str,
    context_summary: str | None = None,
    has_pending_clarification: bool = False,
    has_context: bool = False,
) -> ClassifiedIntent:
    """Main entry point — routes to LLM or regex classifier.

    Arguments mirror what ConversationManager knows at dispatch time:
      - message: the raw user text
      - context_summary: rolling conversation summary (if any)
      - has_pending_clarification: whether the last turn asked a
        clarification question the user might be answering
      - has_context: whether the session has any prior turns at all
    """
    if os.getenv("ANTHROPIC_API_KEY"):
        return _classify_llm(message, context_summary, has_pending_clarification, has_context)
    return _classify_regex(message, has_pending_clarification, has_context)
