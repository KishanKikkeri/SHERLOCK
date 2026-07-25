"""
SHERLOCK — Stage F3: Conversational Intelligence — response generator.

The "voice" of SHERLOCK. Takes structured findings, memory context, and
the user's message, and produces concise, natural-language responses.

This is NOT the investigation pipeline's narrative generator (that's
ChiefAgent._generate_narrative, which produces a formal briefing from
findings). This module sits *above* the pipeline: it decides how to
present investigation results conversationally, handles greetings and
chitchat, and enforces progressive disclosure.

Rules enforced here:
  - 3–6 sentence default response length
  - No agent names, no confidence scores, no internal reasoning
  - Progressive disclosure ("I found 3 suspects. Want to explore…?")
  - Evidence-on-demand ("I have strong evidence. Want me to show it?")
  - Natural, conversational tone — never reads like a report

Two paths:
  1. ANTHROPIC_API_KEY set: Claude reformats findings into a
     conversational response with a strict system prompt.
  2. No key: deterministic templates that still respect the rules.
"""

from __future__ import annotations

import logging
import os

from backend.language.context import resolve_language
from backend.language.prompting import language_directive, localize_template_fallback

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Greeting and chitchat — no LLM needed for these
# ---------------------------------------------------------------------------

_GREETING_RESPONSES = {
    "default": (
        "Hello! I'm SHERLOCK, your crime intelligence assistant. "
        "Ask me about cases, suspects, crime patterns, or anything "
        "investigative — I'm here to help."
    ),
    "how_are_you": (
        "I'm operational and ready to assist. "
        "What would you like to investigate?"
    ),
}

_CHITCHAT_RESPONSES = {
    "capabilities": (
        "I can help you with:\n"
        "• Searching cases, FIRs, and suspects\n"
        "• Analyzing crime patterns and financial links\n"
        "• Building timelines and network graphs\n"
        "• Identifying repeat offenders and hotspots\n"
        "• Comparing cases and generating forecasts\n\n"
        "Just ask naturally — \"Find Ramesh\", \"Show financial links for FIR 231\", "
        "or \"Who are the repeat offenders in Mysuru?\""
    ),
    "thanks": "You're welcome. Let me know if you need anything else.",
    "bye": "Goodbye! Feel free to come back whenever you need investigative help.",
    "ok": "Got it. What would you like to explore next?",
    "nevermind": "No problem. What else can I help with?",
    "off_topic": (
        "I'm specialized in crime investigation and intelligence analysis. "
        "Try asking about a case, suspect, or crime pattern — that's where I can really help."
    ),
}


def respond_to_greeting(message: str) -> str:
    """Direct response to a greeting — no LLM, no pipeline."""
    text = (message or "").strip().lower()
    language = resolve_language(None)

    if "how are you" in text or "how do you do" in text:
        reply = _GREETING_RESPONSES["how_are_you"]
    else:
        reply = _GREETING_RESPONSES["default"]

    return localize_template_fallback(reply, language)


def respond_to_chitchat(message: str) -> str:
    """Direct response to chitchat — no LLM, no pipeline."""
    text = (message or "").strip().lower()
    language = resolve_language(None)

    if any(w in text for w in ("what can you do", "what are you", "who are you", "help", "capabilities")):
        reply = _CHITCHAT_RESPONSES["capabilities"]
    elif any(w in text for w in ("thank", "thanks")):
        reply = _CHITCHAT_RESPONSES["thanks"]
    elif any(w in text for w in ("bye", "goodbye")):
        reply = _CHITCHAT_RESPONSES["bye"]
    elif any(w in text for w in ("ok", "okay", "got it", "i see", "i understand")):
        reply = _CHITCHAT_RESPONSES["ok"]
    elif any(w in text for w in ("never mind", "nevermind", "cancel")):
        reply = _CHITCHAT_RESPONSES["nevermind"]
    else:
        reply = _CHITCHAT_RESPONSES["off_topic"]

    return localize_template_fallback(reply, language)


# ---------------------------------------------------------------------------
# Investigation response formatting — the core of progressive disclosure
# ---------------------------------------------------------------------------

def format_investigation_response(
    query: str,
    final_report: dict,
    context_snapshot: dict | None = None,
    language: str | None = None,
) -> str:
    """Reformats the Chief's final_report into a concise, conversational
    response. This is the piece that replaces dumping the raw narrative.

    Returns 3–6 sentences with a progressive disclosure offer at the end.
    """
    language = language or resolve_language(None)
    narrative = final_report.get("narrative") or ""
    findings = final_report.get("findings") or []
    rejected = final_report.get("rejected_findings") or []

    if not findings and not narrative:
        msg = (
            "I wasn't able to find any validated information for that query. "
            "Could you try rephrasing, or give me more specific details like "
            "a name, FIR number, or location?"
        )
        return localize_template_fallback(msg, language)

    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return _format_response_llm(query, narrative, findings, language)
        except Exception:
            logger.warning("LLM response formatting failed, falling back to template", exc_info=True)

    return _format_response_template(query, narrative, findings, language)


def _format_response_template(
    query: str,
    narrative: str,
    findings: list[dict],
    language: str = "en",
) -> str:
    """Deterministic conversational formatting of investigation results."""
    lines = []

    # Summarize the key findings without agent names or confidence scores
    finding_summaries = []
    for f in findings[:5]:  # cap at 5 to keep it short
        summary = f.get("summary", "")
        if summary:
            # Strip agent name prefix if present (e.g. "[CrimeRecords] ...")
            if summary.startswith("["):
                summary = summary.split("]", 1)[-1].strip()
            finding_summaries.append(summary)

    if finding_summaries:
        if len(finding_summaries) == 1:
            lines.append(f"Here's what I found: {finding_summaries[0]}")
        else:
            lines.append(f"Here's what I found:")
            for s in finding_summaries[:3]:
                lines.append(f"• {s}")
            if len(finding_summaries) > 3:
                lines.append(f"...and {len(finding_summaries) - 3} more finding(s).")
    elif narrative:
        # Use the first 2-3 sentences of the narrative
        sentences = [s.strip() for s in narrative.split(".") if s.strip()]
        lines.append(". ".join(sentences[:3]) + ".")

    # Progressive disclosure offer
    disclosure_options = _build_disclosure_options(findings)
    if disclosure_options:
        lines.append("")
        lines.append("Would you like to explore:")
        for opt in disclosure_options[:4]:
            lines.append(f"• {opt}")

    result = "\n".join(lines)
    return localize_template_fallback(result, language)


def _format_response_llm(
    query: str,
    narrative: str,
    findings: list[dict],
    language: str = "en",
) -> str:
    """LLM-backed conversational reformatting of investigation results."""
    from anthropic import Anthropic

    client = Anthropic()

    findings_text = "\n".join(
        f"- {f.get('summary', 'No summary')}"
        for f in findings[:8]
    )

    system_prompt = (
        "You are SHERLOCK, a crime intelligence AI assistant. "
        "Rewrite the investigation findings below into a concise, natural "
        "conversational response.\n\n"
        "STRICT RULES:\n"
        "1. Maximum 3-6 sentences. Never longer.\n"
        "2. NEVER mention agent names (CrimeRecords, NetworkAnalysis, etc.)\n"
        "3. NEVER show confidence scores or percentages.\n"
        "4. NEVER say 'Investigation complete' or 'Report ready'.\n"
        "5. Write as if you're a knowledgeable colleague explaining what you found.\n"
        "6. End with a natural follow-up offer — suggest 2-3 specific things "
        "the user could explore next (timeline, suspects, evidence, financial "
        "links, etc.) based on what was found.\n"
        "7. Don't use bullet points for the main response — save them for the "
        "follow-up options only.\n"
        "8. If evidence was found, mention it exists but don't show it — say "
        "'I can show you the evidence if you'd like.'\n"
        + language_directive(language)
    )

    prompt = (
        f"User asked: {query}\n\n"
        f"Narrative summary:\n{narrative[:500]}\n\n"
        f"Key findings:\n{findings_text}\n\n"
        "Rewrite this as a brief, conversational response."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def _build_disclosure_options(findings: list[dict]) -> list[str]:
    """Builds progressive disclosure options based on what the findings
    actually contain, so suggestions are never dead ends."""
    options = []
    has_persons = False
    has_financial = False
    has_timeline = False
    has_network = False
    has_evidence = False

    for f in findings:
        agent = (f.get("agent_name") or "").lower()
        ftype = (f.get("finding_type") or "").lower()
        entities = f.get("source_entities") or []

        if any(e.startswith("person_") for e in entities):
            has_persons = True
        if "financial" in agent or "financial" in ftype or "transaction" in ftype:
            has_financial = True
        if "timeline" in agent or "timeline" in ftype:
            has_timeline = True
        if "network" in agent or "graph" in ftype:
            has_network = True
        if f.get("evidence"):
            has_evidence = True

    if has_persons:
        options.append("Suspects and their connections")
    if has_timeline:
        options.append("Timeline of events")
    if has_financial:
        options.append("Financial links and transactions")
    if has_network:
        options.append("Network graph")
    if has_evidence:
        options.append("Supporting evidence")

    # Fallback options if nothing specific
    if not options:
        options = ["More details", "Related cases"]

    return options


def format_followup_response(
    message: str,
    relevant_findings: list[dict],
    context_snapshot: dict | None = None,
    language: str | None = None,
) -> str:
    """Formats a response to a follow-up question using existing findings
    from memory — no new investigation was run."""
    language = language or resolve_language(None)

    if not relevant_findings:
        msg = (
            "I don't have enough context from our conversation to answer that. "
            "Could you be more specific, or shall I run a new investigation?"
        )
        return localize_template_fallback(msg, language)

    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return _format_followup_llm(message, relevant_findings, context_snapshot, language)
        except Exception:
            logger.warning("LLM followup formatting failed, falling back to template", exc_info=True)

    return _format_followup_template(message, relevant_findings, language)


def _format_followup_template(
    message: str,
    findings: list[dict],
    language: str = "en",
) -> str:
    """Deterministic follow-up formatting from memory findings."""
    lines = ["Based on what we've already found:"]
    for f in findings[:4]:
        summary = f.get("summary", "")
        if summary:
            if summary.startswith("["):
                summary = summary.split("]", 1)[-1].strip()
            lines.append(f"• {summary}")

    if len(findings) > 4:
        lines.append(f"\n...plus {len(findings) - 4} more related finding(s).")

    lines.append("\nWant me to dig deeper into any of these?")
    return localize_template_fallback("\n".join(lines), language)


def _format_followup_llm(
    message: str,
    findings: list[dict],
    context_snapshot: dict | None,
    language: str = "en",
) -> str:
    """LLM-backed follow-up formatting."""
    from anthropic import Anthropic

    client = Anthropic()

    findings_text = "\n".join(
        f"- {f.get('summary', 'No summary')}"
        for f in findings[:6]
    )

    context_text = ""
    if context_snapshot:
        active_suspects = context_snapshot.get("active_suspects", [])
        if active_suspects:
            context_text = f"\nActive suspects in conversation: {', '.join(str(s) for s in active_suspects)}"
        selected_case = context_snapshot.get("selected_case")
        if selected_case:
            context_text += f"\nCurrently discussing case: {selected_case}"

    system_prompt = (
        "You are SHERLOCK, a crime intelligence AI assistant. "
        "The user asked a follow-up question about something already discussed. "
        "Answer using ONLY the existing findings provided — do NOT invent new facts.\n\n"
        "STRICT RULES:\n"
        "1. Maximum 3-5 sentences.\n"
        "2. NEVER mention agent names or confidence scores.\n"
        "3. Write naturally, as a knowledgeable colleague.\n"
        "4. If the findings don't fully answer the question, say so honestly "
        "and offer to investigate further.\n"
        + language_directive(language)
    )

    prompt = (
        f"User's follow-up: {message}\n"
        f"{context_text}\n\n"
        f"Existing findings:\n{findings_text}\n\n"
        "Answer the follow-up using only these findings."
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=250,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
