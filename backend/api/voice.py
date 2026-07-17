"""
SHERLOCK — Stage C3: Voice command API. Extended in Stage D, Sprint 3
with real audio in/out endpoints.

    POST /voice/command      { "transcript": "...", "session_id": 12 }

The browser does STT (via `useVoice.ts`'s existing wake-word/push-to-talk
Web Speech API wrapper) and posts the resulting text here; this endpoint
classifies and executes it (session lifecycle, board, report, or a
free-text investigation query) and returns a short spoken_response the
browser hands straight to `useVoice`'s existing `speak()` for TTS. No
audio ever crosses the wire in either direction — same "no server
round-trip for voice itself" design the existing frontend voice layer
already uses for board commands. UNCHANGED this sprint.

Stage D, Sprint 3 adds a second, optional path for callers that DO want
the server to handle real audio (needed for Kannada, since the
browser's Web Speech API's Kannada support is inconsistent across
browsers/OSes — not inspected in depth this sprint, but this endpoint
exists specifically so a Kannada-speaking officer isn't blocked on
browser support):

    POST /voice/transcribe    multipart audio -> {text, language, confidence, ...}
    POST /voice/speak         {text, language} -> audio bytes
    POST /voice/query         multipart audio -> {transcript, spoken_response, audio_base64, ...}
                               (full round trip: audio in, investigation/command run, audio out)

None of these three touch `/voice/command`, `VoiceCommandRouter`, or the
frontend's existing Web Speech-based voice flow — they're an additional,
optional path.
"""

import base64
import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from backend.database.config import SessionLocal
from backend.language import SUPPORTED_LANGUAGES
from backend.voice.command_router import VoiceCommandRouter
from backend.voice.voice_service import VoiceService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["voice"])


class VoiceCommandRequest(BaseModel):
    transcript: str
    session_id: int | None = None


@router.post("/command")
async def voice_command(body: VoiceCommandRequest):
    session = SessionLocal()
    try:
        cmd_router = VoiceCommandRouter(session)
        result = await cmd_router.route(body.transcript, session_id=body.session_id)
        return result.to_dict()
    except Exception:
        logger.exception("POST /voice/command failed for transcript: %r", body.transcript)
        raise HTTPException(status_code=500, detail="Voice command failed.")
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Stage D, Sprint 3 — real audio endpoints
# ---------------------------------------------------------------------------

class SpeakRequest(BaseModel):
    text: str
    language: str = "en"
    voice: str | None = None


@router.post("/transcribe")
async def voice_transcribe(audio: UploadFile = File(...), language_hint: str | None = Form(None)):
    """
    Body: multipart/form-data, field `audio` (the audio file), optional
    field `language_hint` ("en" or "kn"). Returns:
        {"text": "...", "language": "kn", "confidence": 0.0, "provider": "none", "warnings": [...]}

    `provider` tells you whether this is a real transcription or the
    graceful no-provider fallback — see `SHERLOCK_STT_PROVIDER` in the
    Sprint D3 report. `text` is empty (not an error) when no provider is
    configured; check `warnings` for why.
    """
    if language_hint is not None and language_hint not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"language_hint must be one of {SUPPORTED_LANGUAGES}.")
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="Uploaded audio file is empty.")

    session = SessionLocal()
    try:
        service = VoiceService(session)
        result = service.transcribe(audio_bytes, audio.content_type or "audio/wav", language_hint=language_hint)
    except Exception:
        logger.exception("POST /voice/transcribe failed")
        raise HTTPException(status_code=500, detail="Transcription failed.")
    finally:
        session.close()

    return {
        "text": result.text, "language": result.language, "confidence": result.confidence,
        "provider": result.provider, "warnings": result.warnings,
    }


@router.post("/speak")
async def voice_speak(body: SpeakRequest):
    """
    Body: {"text": "...", "language": "kn", "voice": null}
    Returns: audio bytes (Content-Type set per the active TTS provider —
    audio/wav for the default espeak provider, audio/mp3 for the Google/
    Azure providers). Metadata (which provider actually ran, and any
    warnings) is in the `X-TTS-Provider` / `X-TTS-Warnings` response
    headers rather than the body, so the body stays pure audio a client
    can play directly — same pattern as `/export/pdf`'s `X-PDF-Warnings`.
    """
    if body.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"language must be one of {SUPPORTED_LANGUAGES}.")
    if not body.text or not body.text.strip():
        raise HTTPException(status_code=422, detail="text is required.")

    session = SessionLocal()
    try:
        service = VoiceService(session)
        result = service.speak(body.text, body.language, voice=body.voice)
    except Exception:
        logger.exception("POST /voice/speak failed")
        raise HTTPException(status_code=500, detail="Speech synthesis failed.")
    finally:
        session.close()

    headers = {"X-TTS-Provider": result.provider}
    if result.warnings:
        headers["X-TTS-Warnings"] = " | ".join(result.warnings)
    return Response(content=result.audio_bytes, media_type=result.content_type, headers=headers)


@router.post("/query")
async def voice_query(audio: UploadFile = File(...), session_id: int | None = Form(None),
                       language_hint: str | None = Form(None)):
    """
    Full round trip, per the Stage D Sprint 3 workflow: Kannada (or
    English) speech in -> transcribe -> detect/translate -> run the same
    `VoiceCommandRouter` `/voice/command` already uses (free-text queries
    run a full investigation) -> translate the response back -> speak it.

    Returns JSON (not raw audio) because the response carries several
    text fields that may be in Kannada — audio is included as base64
    inside the JSON body (`audio_base64`) rather than as the whole
    response, so a Kannada transcript doesn't have to be squeezed into
    an HTTP header (which — unlike a JSON body — isn't reliably safe for
    non-ASCII text).
    """
    if language_hint is not None and language_hint not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"language_hint must be one of {SUPPORTED_LANGUAGES}.")
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=422, detail="Uploaded audio file is empty.")

    session = SessionLocal()
    try:
        service = VoiceService(session)
        result = await service.process_voice_command(
            audio_bytes, audio.content_type or "audio/wav",
            session_id=session_id, language_hint=language_hint,
        )
    except Exception:
        logger.exception("POST /voice/query failed")
        raise HTTPException(status_code=500, detail="Voice query failed.")
    finally:
        session.close()

    return {
        "transcript": result.transcript,
        "detected_language": result.detected_language,
        "working_transcript": result.working_transcript,
        "intent": result.intent,
        "spoken_response_en": result.spoken_response_en,
        "spoken_response": result.spoken_response,
        "session_id": result.session_id,
        "data": result.data,
        "audio_base64": base64.b64encode(result.audio.audio_bytes).decode("ascii") if result.audio else None,
        "audio_content_type": result.audio.content_type if result.audio else None,
        "audio_provider": result.audio.provider if result.audio else None,
        "warnings": result.warnings,
    }
