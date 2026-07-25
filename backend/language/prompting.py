"""
SHERLOCK — Priority 27: Language-aware Prompting.

One shared helper every LLM-calling site in the backend uses to tell
Claude what language to write its output in, instead of each of
`chief/agent.py`, `sociological_insights.py`, `discussion/engine.py`,
and `conversation_memory.py` copy-pasting (and inevitably drifting on)
its own instruction wording.

The two building blocks:

    language_directive(language)   -> instruction text appended to an
                                       LLM prompt, telling the model to
                                       generate its answer directly in
                                       that language (Priority 27/29/31 —
                                       "no secondary translation step").

    localize_template_fallback()   -> for the deterministic, no-LLM-key
                                       template path every one of these
                                       call sites already has. Without
                                       this, the moment ANTHROPIC_API_KEY
                                       is unset, every narrative/summary
                                       silently reverts to English no
                                       matter what language is active —
                                       this passes the template's English
                                       output through the existing
                                       TranslationService so the
                                       fallback still honors the active
                                       language, rather than leaving
                                       template-mode as an unannounced
                                       English-only path.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_LANGUAGE_NAMES = {
    "en": "English",
    "kn": "Kannada",
}


def language_name(language: str) -> str:
    return _LANGUAGE_NAMES.get(language, "English")


def language_directive(language: str) -> str:
    """Instruction block to append to an LLM prompt so the model writes
    its answer directly in `language` — never as a separate translation
    pass. Empty string for English: every existing prompt in this
    codebase was already written and tuned assuming English output, so
    a redundant "respond in English" instruction is unnecessary and
    risks changing behavior for no benefit.
    """
    if language == "en" or language not in _LANGUAGE_NAMES:
        return ""
    name = language_name(language)
    return (
        f"\n\nRespond entirely in natural, conversational {name}. Do not mix "
        f"English unless the source material itself does. Keep proper nouns, "
        f"FIR/case numbers, and established police/legal terminology (e.g. "
        f"FIR, IPC, chargesheet) in their original form where translating "
        f"them would be unnatural or ambiguous. Output only the {name} "
        f"text — do not add a translation, transliteration, or English "
        f"version afterward."
    )


def localize_template_fallback(text: str, language: str) -> str:
    """Best-effort localization for deterministic template output when
    no LLM is available. Returns `text` unchanged for English or empty
    input, and on any translation failure — same degrade-to-original
    behavior every other `TranslationService` caller in this codebase
    already follows (see `_localize_report` in
    backend/api/investigation_stream.py).
    """
    if language == "en" or not text:
        return text
    try:
        from backend.language.translation_service import TranslationService

        result = TranslationService().translate(text, target_language=language, source_language="en")
        return result.text
    except Exception:
        logger.warning("Template-fallback localization to %s failed; returning English text", language, exc_info=True)
        return text
