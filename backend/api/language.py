"""
SHERLOCK — Sprint D5: Language resources API.

Backend support for UI localization. The frontend rewrite is Stage G —
nothing here touches a frontend file; it exposes the data a future
frontend (or the current one, incrementally) can consume.

Endpoints:
    GET  /language/supported          List of supported language codes.
    GET  /language/resources/{lang}   Label/activity/workflow/discussion
                                       string bundle for that language.
    GET  /language/voice-commands     Centralized localized voice-command
                                       dictionary (Sprint D3 groundwork).
    POST /language/translate          Ad-hoc translate — mainly for
                                       manual testing/integration and for
                                       any future caller that needs a
                                       one-off translation outside the
                                       investigation pipeline (e.g. a
                                       chat-style free-text note).
    POST /language/detect             Ad-hoc language detection.
"""

from fastapi import APIRouter, Body, HTTPException

from backend.language import (
    TranslationService, detect_language, get_resources, SUPPORTED_LANGUAGES,
)
from backend.language.resources import VOICE_COMMANDS

router = APIRouter(prefix="/language", tags=["language"])

_translator = TranslationService()


@router.get("/supported")
def supported_languages():
    return {"languages": list(SUPPORTED_LANGUAGES)}


@router.get("/resources/{lang}")
def language_resources(lang: str):
    try:
        return get_resources(lang)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/voice-commands")
def voice_commands():
    return VOICE_COMMANDS


@router.post("/translate")
def translate_text(payload: dict = Body(...)):
    """
    Body: {"text": "...", "target_language": "kn", "source_language": "en"}
    `source_language` is optional; auto-detected if omitted.
    """
    text = payload.get("text")
    target_language = payload.get("target_language")
    source_language = payload.get("source_language")

    if not text or not isinstance(text, str):
        raise HTTPException(status_code=422, detail="text is required and must be a string.")
    if target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"target_language must be one of {SUPPORTED_LANGUAGES}.")

    result = _translator.translate(text, target_language=target_language, source_language=source_language)
    return {
        "text": result.text,
        "source_language": result.source_language,
        "target_language": result.target_language,
        "detected_language": result.detected_language,
        "confidence": result.confidence,
        "engine": result.engine,
        "warnings": result.warnings,
    }


@router.post("/detect")
def detect(payload: dict = Body(...)):
    text = payload.get("text")
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=422, detail="text is required and must be a string.")
    result = detect_language(text)
    return {
        "language": result.language,
        "confidence": result.confidence,
        "script_counts": result.script_counts,
    }
