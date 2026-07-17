"""
SHERLOCK — Sprint D3: Voice service.

Wires together everything Stage D already built (language detection,
`TranslationService`) with the two new pluggable provider modules and
the existing, UNTOUCHED Stage C3 `VoiceCommandRouter`, to implement the
handover's workflow:

    Kannada speech
      -> speech-to-text
      -> detect language
      -> translate
      -> investigation (or a voice command)
      -> translate response
      -> speech synthesis

`VoiceCommandRouter` itself is never modified — Golden Rule 1 for this
sprint ("Never touch backend/agents/* ... unless there is an actual
bug"; `command_router.py` isn't an agent, but the same "extend, don't
rewrite" spirit applies, and it's explicitly listed as "already
contains ... voice command dictionary" groundwork this sprint builds
on). `VoiceService` translates a Kannada transcript to English *before*
handing it to the router, and translates the router's English
`spoken_response` back to the requested language afterward — the router
itself only ever sees/produces English, exactly as it did before this
sprint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from backend.language import TranslationService, detect_language, SUPPORTED_LANGUAGES
from backend.voice.speech_to_text import get_stt_provider, TranscriptionResult
from backend.voice.text_to_speech import get_tts_provider, SynthesisResult
from backend.voice.command_router import VoiceCommandRouter

logger = logging.getLogger(__name__)


@dataclass
class VoiceQueryResult:
    transcript: str                    # raw STT output, in whatever language was spoken
    detected_language: str             # "en" | "kn" | "mixed" | "unknown"
    working_transcript: str            # transcript translated to English (== transcript if already English)
    intent: str                        # from VoiceCommandRouter
    spoken_response_en: str            # router's canonical English response
    spoken_response: str               # localized response, in detected_language
    session_id: int | None
    data: dict = field(default_factory=dict)
    audio: SynthesisResult | None = None
    warnings: list = field(default_factory=list)


class VoiceService:
    """
    Usage:
        service = VoiceService(db_session)
        result = await service.process_voice_command(audio_bytes, "audio/wav", session_id=12)
        # result.audio.audio_bytes is the spoken (localized) response, ready to send back
    """

    def __init__(self, db_session, stt_provider=None, tts_provider=None):
        self.db_session = db_session
        self.stt = stt_provider or get_stt_provider()
        self.tts = tts_provider or get_tts_provider()
        self.translator = TranslationService()
        self.command_router = VoiceCommandRouter(db_session)

    # -----------------------------------------------------------------
    def transcribe(self, audio_bytes: bytes, content_type: str,
                    language_hint: str | None = None) -> TranscriptionResult:
        """Standalone transcription — backs `POST /voice/transcribe`."""
        return self.stt.transcribe(audio_bytes, content_type, language_hint=language_hint)

    def speak(self, text: str, language: str, voice: str | None = None) -> SynthesisResult:
        """Standalone synthesis — backs `POST /voice/speak`."""
        if language not in SUPPORTED_LANGUAGES:
            language = "en"
        return self.tts.synthesize(text, language, voice=voice)

    # -----------------------------------------------------------------
    async def process_voice_command(self, audio_bytes: bytes, content_type: str,
                                     session_id: int | None = None,
                                     language_hint: str | None = None) -> VoiceQueryResult:
        """
        Full round trip: audio in -> (STT) -> (detect/translate) ->
        VoiceCommandRouter (which itself may run a full investigation for
        a free-text query, exactly as it does for an English Web-Speech
        transcript today) -> (translate response) -> (TTS) -> audio out.

        Never raises for a provider/translation failure — every stage
        degrades to "best effort" (empty transcript, English-only
        response, no audio) with the reason recorded in `.warnings`,
        per this sprint's Golden Rule 3.
        """
        warnings = []

        stt_result = self.stt.transcribe(audio_bytes, content_type, language_hint=language_hint)
        warnings.extend(stt_result.warnings)
        transcript = stt_result.text

        if not transcript.strip():
            return VoiceQueryResult(
                transcript="", detected_language=language_hint or "unknown", working_transcript="",
                intent="empty", spoken_response_en="I didn't catch that — try again.",
                spoken_response="I didn't catch that — try again.", session_id=session_id,
                warnings=warnings or ["No transcript to process (STT unavailable or silence)."],
            )

        detection = detect_language(transcript)
        effective_language = language_hint or stt_result.language or detection.language
        if effective_language not in SUPPORTED_LANGUAGES:
            effective_language = "en"

        working_transcript = transcript
        if effective_language != "en":
            translation = self.translator.translate(transcript, target_language="en",
                                                      source_language=effective_language)
            working_transcript = translation.text
            warnings.extend(translation.warnings)

        cmd_result = await self.command_router.route(working_transcript, session_id=session_id)

        spoken_response_en = cmd_result.spoken_response
        spoken_response = spoken_response_en
        if effective_language != "en":
            response_translation = self.translator.translate(
                spoken_response_en, target_language=effective_language, source_language="en")
            spoken_response = response_translation.text
            warnings.extend(response_translation.warnings)

        audio = self.tts.synthesize(spoken_response, effective_language)
        warnings.extend(audio.warnings)

        return VoiceQueryResult(
            transcript=transcript,
            detected_language=effective_language,
            working_transcript=working_transcript,
            intent=cmd_result.intent,
            spoken_response_en=spoken_response_en,
            spoken_response=spoken_response,
            session_id=cmd_result.session_id,
            data=cmd_result.data,
            audio=audio,
            warnings=warnings,
        )
