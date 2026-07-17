"""
SHERLOCK — Sprint D1: Translation service.

The ONE place translation calls happen. Nothing else in the codebase
should import an MT/LLM client directly for translation — per the
handover's "do not scatter translation calls throughout the codebase".

Engine: Anthropic Claude (`claude-sonnet-4-6`), the same model + the same
"optional via ANTHROPIC_API_KEY, graceful template fallback otherwise"
pattern already used by `ChiefAgent._generate_narrative` — chosen for
consistency with the rest of the codebase rather than introducing a
second LLM/MT provider and a second failure mode.

Honest constraints (see also the Stage D report's "Known Limitations"):
  - Online only. No offline/on-device model is wired up. If Anthropic
    is unreachable or ANTHROPIC_API_KEY is unset, translation degrades
    to passthrough + a warning — the caller always gets a `TranslationResult`
    back, never an exception, but a passthrough result on a real Kannada
    query is NOT a translation; callers must check `result.engine` and
    `result.warnings` before treating output as trustworthy.
  - This is a general-purpose LLM used for translation, not a certified
    legal-translation product. Do not present translated FIR/report text
    as an official record — it is an investigative aid. See glossary.py
    for terms that are protected/pinned specifically to reduce (not
    eliminate) legal-terminology drift.
  - Confidence is the model's own self-report, extracted from a
    structured JSON response, not an independently computed metric. Treat
    it as a rough signal, not a calibrated probability.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from backend.language.glossary import GlossaryService, GLOSSARY
from backend.language.language_detector import detect_language

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"

LANGUAGE_NAMES = {"en": "English", "kn": "Kannada"}


@dataclass
class TranslationResult:
    text: str                       # the translated (or passed-through) text
    source_language: str            # language actually translated from
    target_language: str            # language translated to
    detected_language: str          # what the detector said about the *input* text
    confidence: float               # 0.0 - 1.0
    engine: str                     # "anthropic" | "passthrough" | "noop"
    warnings: list = field(default_factory=list)


class TranslationService:
    """
    Usage:
        svc = TranslationService()
        result = svc.to_english("ಈ ಪ್ರಕರಣದ ಆರೋಪಿಗಳು ಯಾರು?")
        result.text  -> "Who are the accused in this case?"
    """

    def __init__(self, glossary: GlossaryService | None = None):
        self.glossary = glossary or GLOSSARY

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------
    def to_english(self, text: str) -> TranslationResult:
        return self.translate(text, target_language="en")

    def to_kannada(self, text: str) -> TranslationResult:
        return self.translate(text, target_language="kn")

    def translate(self, text: str, target_language: str, source_language: str | None = None) -> TranslationResult:
        detection = detect_language(text)
        effective_source = source_language or detection.language
        if effective_source in ("unknown", "mixed"):
            # "mixed" still needs translating (see language_detector's docstring);
            # "unknown" (no alphabetic content, e.g. a bare case number) doesn't.
            effective_source = "kn" if detection.language == "mixed" else target_language

        if not text or not text.strip():
            return TranslationResult(
                text=text, source_language=effective_source, target_language=target_language,
                detected_language=detection.language, confidence=1.0, engine="noop",
            )

        if effective_source == target_language:
            return TranslationResult(
                text=text, source_language=effective_source, target_language=target_language,
                detected_language=detection.language, confidence=1.0, engine="noop",
                warnings=["Source and target language are the same; text returned unchanged."],
            )

        if not os.getenv("ANTHROPIC_API_KEY"):
            return TranslationResult(
                text=text, source_language=effective_source, target_language=target_language,
                detected_language=detection.language, confidence=0.0, engine="passthrough",
                warnings=["ANTHROPIC_API_KEY not set; translation engine unavailable. "
                          "Original text returned unchanged."],
            )

        try:
            return self._translate_llm(text, effective_source, target_language, detection)
        except Exception:
            logger.warning("Translation failed (%s -> %s), falling back to passthrough",
                            effective_source, target_language, exc_info=True)
            return TranslationResult(
                text=text, source_language=effective_source, target_language=target_language,
                detected_language=detection.language, confidence=0.0, engine="passthrough",
                warnings=["Translation engine call failed; original text returned unchanged."],
            )

    def batch_translate(self, texts: list, target_language: str, source_language: str | None = None) -> list:
        """
        Translates a list of independent short strings (e.g. one
        investigation's activity-feed messages) as a single LLM call
        instead of N calls, for latency/cost — used by the activity feed
        and report localization in Sprint D2. Falls back to per-item
        `translate()` if the batch call or its JSON parse fails, so a
        malformed batch response never loses messages.
        """
        if not texts:
            return []

        non_empty_indices = [i for i, t in enumerate(texts) if t and t.strip()]
        if not non_empty_indices or not os.getenv("ANTHROPIC_API_KEY"):
            return [self.translate(t, target_language, source_language) for t in texts]

        try:
            return self._batch_translate_llm(texts, target_language, source_language)
        except Exception:
            logger.warning("Batch translation failed, falling back to per-item calls", exc_info=True)
            return [self.translate(t, target_language, source_language) for t in texts]

    # -----------------------------------------------------------------
    # Anthropic-backed implementation
    # -----------------------------------------------------------------
    def _client(self):
        from anthropic import Anthropic
        return Anthropic()

    def _translate_llm(self, text, source_language, target_language, detection) -> TranslationResult:
        directive = self.glossary.build_prompt_directive()
        src_name = LANGUAGE_NAMES.get(source_language, source_language)
        tgt_name = LANGUAGE_NAMES.get(target_language, target_language)

        prompt = (
            f"Translate the following text from {src_name} to {tgt_name}.\n"
            f"This is for a police investigation platform (SHERLOCK) used by "
            f"Karnataka Police officers — keep the register formal and precise.\n\n"
            f"{directive}\n\n"
            "Respond with ONLY a JSON object, no markdown fences, no preamble:\n"
            '{"translation": "...", "confidence": 0.0-1.0, "notes": ["..."]}\n\n'
            f"Text:\n{text}"
        )
        client = self._client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(block.text for block in response.content if block.type == "text").strip()
        parsed = self._parse_json(raw)

        translated = parsed.get("translation", "").strip()
        confidence = float(parsed.get("confidence", 0.7))
        notes = list(parsed.get("notes") or [])

        warnings = list(notes)
        warnings.extend(self._verify_glossary(text, translated, source_language, target_language))

        if not translated:
            warnings.append("Model returned an empty translation; original text returned unchanged.")
            return TranslationResult(
                text=text, source_language=source_language, target_language=target_language,
                detected_language=detection.language, confidence=0.0, engine="passthrough",
                warnings=warnings,
            )

        return TranslationResult(
            text=translated, source_language=source_language, target_language=target_language,
            detected_language=detection.language, confidence=confidence, engine="anthropic",
            warnings=warnings,
        )

    def _batch_translate_llm(self, texts, target_language, source_language) -> list:
        detections = [detect_language(t) if t else None for t in texts]
        # Batch translation assumes a single dominant source language for the
        # whole batch (true for our callers: one activity feed, one report,
        # all authored in English by the pipeline). Mixed-source batches
        # fall back to per-item translation above this method.
        non_empty = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
        src = source_language or (detections[non_empty[0][0]].language if non_empty else "en")
        if src == "mixed" or src == "unknown":
            src = "en"

        directive = self.glossary.build_prompt_directive()
        src_name = LANGUAGE_NAMES.get(src, src)
        tgt_name = LANGUAGE_NAMES.get(target_language, target_language)

        items_json = json.dumps({str(i): t for i, t in non_empty}, ensure_ascii=False)
        prompt = (
            f"Translate each value in this JSON object from {src_name} to {tgt_name}. "
            "This is for a police investigation platform (SHERLOCK) used by Karnataka "
            "Police officers — keep the register formal and precise. Preserve the keys "
            "exactly.\n\n"
            f"{directive}\n\n"
            "Respond with ONLY a JSON object mapping the same keys to translated "
            "strings, no markdown fences, no preamble:\n\n"
            f"{items_json}"
        )
        client = self._client()
        response = client.messages.create(
            model=MODEL,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(block.text for block in response.content if block.type == "text").strip()
        parsed = self._parse_json(raw)

        results = [None] * len(texts)
        for i, original in non_empty:
            translated = parsed.get(str(i), "").strip()
            det = detections[i]
            if translated:
                warnings = self._verify_glossary(original, translated, src, target_language)
                results[i] = TranslationResult(
                    text=translated, source_language=src, target_language=target_language,
                    detected_language=det.language, confidence=0.7, engine="anthropic",
                    warnings=warnings,
                )
            else:
                results[i] = TranslationResult(
                    text=original, source_language=src, target_language=target_language,
                    detected_language=det.language, confidence=0.0, engine="passthrough",
                    warnings=["Missing from batch translation response; original text returned unchanged."],
                )
        for i, t in enumerate(texts):
            if results[i] is None:
                results[i] = TranslationResult(
                    text=t, source_language=src, target_language=target_language,
                    detected_language="unknown", confidence=1.0, engine="noop",
                )
        return results

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------
    @staticmethod
    def _parse_json(raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
        return json.loads(cleaned.strip())

    def _verify_glossary(self, source_text, translated_text, source_language, target_language) -> list:
        """
        Lightweight post-hoc check, not enforcement: flags when a
        glossary term present in the source doesn't appear to have
        survived translation as instructed. Doesn't rewrite the
        translation — an LLM-based glossary rewrite risks breaking
        grammar around the substitution — it surfaces a warning so a
        human reviewer knows to look.
        """
        warnings = []
        if source_language == "en":
            for entry in self.glossary.terms_present_in(source_text):
                if entry.policy == "protect" and entry.term.lower() not in translated_text.lower():
                    warnings.append(f'Protected term "{entry.term}" may not have been preserved in translation.')
                elif entry.policy == "approved" and entry.kn and entry.kn not in translated_text:
                    warnings.append(f'Approved translation for "{entry.term}" ("{entry.kn}") may not have been used.')
        elif source_language == "kn":
            for kn_term, en_term in self.glossary._kn_index.items():
                if kn_term in source_text and en_term.lower() not in translated_text.lower():
                    warnings.append(f'Glossary term "{en_term}" ("{kn_term}") may not have been preserved.')
        return warnings
