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
"""

from backend.language.language_detector import detect_language, LanguageDetectionResult
from backend.language.glossary import GlossaryService, GLOSSARY
from backend.language.translation_service import TranslationService, TranslationResult
from backend.language.resources import get_resources, SUPPORTED_LANGUAGES

__all__ = [
    "detect_language",
    "LanguageDetectionResult",
    "GlossaryService",
    "GLOSSARY",
    "TranslationService",
    "TranslationResult",
    "get_resources",
    "SUPPORTED_LANGUAGES",
]
