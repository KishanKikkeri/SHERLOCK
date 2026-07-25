"""
SHERLOCK — Stage D: Language Intelligence.

Centralized multilingual layer. Per the Stage D handover's Golden Rules,
this package sits *outside* the investigation pipeline — it translates
before the Chief sees a query and localizes after the Chief produces a
report. No specialist agent, orchestrator node, or database table is
touched by anything in here.

Public surface:
    detect_language(text)              -> LanguageDetectionResult
    TranslationService                 -> .translate() / .to_english() / .to_kannada() / .batch_translate()
    TranslationResult                  -> dataclass returned by TranslationService
    GlossaryService / GLOSSARY         -> protected police-terminology glossary
    get_resources(language)            -> UI/localization string bundle (Sprint D5)
    SUPPORTED_LANGUAGES                -> ("en", "kn") for now; see glossary.py / resources.py
      for how a new language is added without rewriting this package (Sprint D6).

    resolve_language(explicit=None)    -> Priority 26: the one call every AI-generating
                                           service makes to find out what language to
                                           answer in (ambient request context, or an
                                           explicit override).
    get_current_language()             -> the raw ambient language, no override.
    LanguageContextMiddleware          -> ASGI middleware that populates the ambient
                                           context from the `X-App-Language` header.
    language_directive(language)       -> Priority 27: instruction text telling an LLM
                                           to generate its answer directly in `language`.
    localize_template_fallback(text, language) -> Priority 27/31: best-effort localization
                                           for the deterministic (no-LLM-key) template path.

Golden Rule update (Priority 25-33): the original Stage D rule that this
package sits "outside the investigation pipeline" — translating the query
before the Chief sees it and localizing the report afterward — covered
only the deterministic/graph part of the pipeline, and left every direct
LLM call (Chief's narrative, sociological executive summary, discussion
explanations, conversation summaries) generating in English regardless of
the active language. Those call sites now generate natively in the active
language via `language_directive()` instead of being translated after the
fact — see `backend/agents/chief/agent.py`, `backend/discussion/engine.py`,
`backend/intelligence/sociological_insights.py`, and
`backend/memory/conversation_memory.py`. The translate-before/localize-after
wrapping in `backend/api/investigation_stream.py` still applies to the
purely structural, non-LLM parts of a report (specialist-agent finding
summaries), which remain deterministic English f-strings.
"""

from backend.language.language_detector import detect_language, LanguageDetectionResult
from backend.language.glossary import GlossaryService, GLOSSARY
from backend.language.translation_service import TranslationService, TranslationResult
from backend.language.resources import get_resources, SUPPORTED_LANGUAGES
from backend.language.context import (
    resolve_language, get_current_language, set_current_language, LanguageContextMiddleware,
)
from backend.language.prompting import language_directive, localize_template_fallback, language_name

__all__ = [
    "detect_language",
    "LanguageDetectionResult",
    "GlossaryService",
    "GLOSSARY",
    "TranslationService",
    "TranslationResult",
    "get_resources",
    "SUPPORTED_LANGUAGES",
    "resolve_language",
    "get_current_language",
    "set_current_language",
    "LanguageContextMiddleware",
    "language_directive",
    "localize_template_fallback",
    "language_name",
]
