"""
SHERLOCK — Sprint D3: Text-to-speech.

Same pluggability contract as `speech_to_text.py`: `get_tts_provider()`
reads `SHERLOCK_TTS_PROVIDER` ("google" / "azure" / "espeak" / "none"),
defaulting to "espeak".

Unlike every STT provider and the two cloud TTS providers below,
`EspeakTTSProvider` is genuinely, locally functional in this sandbox —
it shells out to the `espeak-ng` binary, which has real Kannada voice
support (`espeak-ng --voices | grep kn` lists it) and needs no network
call or API key. It's the reason "espeak" is the default rather than
"none": the handover's Definition of Done requires "voice output works
in both languages", and this is the one path that can actually be
validated end-to-end (real audio bytes, real Kannada synthesis) in an
environment with no reachable cloud STT/TTS endpoints. It is a robotic,
formant-synthesis voice, not a natural-sounding one — appropriate as a
guaranteed-available fallback/default, not necessarily what a deployed
system should ship as its primary voice. See the Sprint D3 report.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

ESPEAK_VOICES = {"en": "en", "kn": "kn"}


@dataclass
class SynthesisResult:
    audio_bytes: bytes
    content_type: str
    provider: str
    warnings: list = field(default_factory=list)


class TextToSpeechProvider:
    name = "base"

    def synthesize(self, text: str, language: str, voice: str | None = None) -> SynthesisResult:
        raise NotImplementedError


class NullTTSProvider(TextToSpeechProvider):
    name = "none"

    def synthesize(self, text, language, voice=None) -> SynthesisResult:
        return SynthesisResult(
            audio_bytes=b"", content_type="audio/wav", provider="none",
            warnings=["No TTS provider configured/available. Set SHERLOCK_TTS_PROVIDER "
                      "to 'espeak' (offline, no key needed), 'google', or 'azure'."],
        )


class EspeakTTSProvider(TextToSpeechProvider):
    """
    Offline TTS via the `espeak-ng` binary. Real and functional in any
    environment that has the binary installed — no network, no API key.
    Formant-synthesis voice quality (robotic), not comparable to a
    cloud neural TTS voice; documented as a real limitation, not hidden
    behind "TTS works".
    """

    name = "espeak"

    def __init__(self):
        self._binary = shutil.which("espeak-ng") or shutil.which("espeak")

    def synthesize(self, text, language, voice=None) -> SynthesisResult:
        if not self._binary:
            return SynthesisResult(
                audio_bytes=b"", content_type="audio/wav", provider="espeak-error",
                warnings=["espeak-ng binary not found on this host (apt install espeak-ng). "
                          "Falling back to no audio."],
            )
        if not text or not text.strip():
            return SynthesisResult(audio_bytes=b"", content_type="audio/wav", provider="espeak",
                                    warnings=["Empty text; nothing to synthesize."])

        espeak_voice = voice or ESPEAK_VOICES.get(language, "en")
        warnings = []
        if language not in ESPEAK_VOICES:
            warnings.append(f"Unrecognized language '{language}' for espeak; defaulting to English voice.")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                [self._binary, "-v", espeak_voice, "-w", tmp_path, text],
                capture_output=True, text=True, timeout=20,
            )
            if result.returncode != 0:
                return SynthesisResult(
                    audio_bytes=b"", content_type="audio/wav", provider="espeak-error",
                    warnings=[f"espeak-ng exited with code {result.returncode}: {result.stderr.strip()[:200]}"],
                )
            with open(tmp_path, "rb") as f:
                audio_bytes = f.read()
            return SynthesisResult(audio_bytes=audio_bytes, content_type="audio/wav",
                                    provider="espeak", warnings=warnings)
        except Exception as e:
            logger.warning("espeak-ng synthesis failed", exc_info=True)
            return SynthesisResult(audio_bytes=b"", content_type="audio/wav", provider="espeak-error",
                                    warnings=[f"espeak-ng invocation failed: {e}"])
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


class GoogleTTSProvider(TextToSpeechProvider):
    """Google Cloud Text-to-Speech `text:synthesize`. Not live-tested this
    sprint (unreachable domain in this sandbox + no key) — see module
    docstring and the Sprint D3 report."""

    name = "google"
    _VOICE_NAMES = {"en": "en-IN-Standard-A", "kn": "kn-IN-Standard-A"}
    _LANGUAGE_CODES = {"en": "en-IN", "kn": "kn-IN"}

    def synthesize(self, text, language, voice=None) -> SynthesisResult:
        api_key = os.getenv("GOOGLE_TTS_API_KEY")
        if not api_key:
            return SynthesisResult(audio_bytes=b"", content_type="audio/mp3", provider="google-error",
                                    warnings=["GOOGLE_TTS_API_KEY not set."])
        try:
            resp = requests.post(
                f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}",
                json={
                    "input": {"text": text},
                    "voice": {
                        "languageCode": self._LANGUAGE_CODES.get(language, "en-IN"),
                        "name": voice or self._VOICE_NAMES.get(language, "en-IN-Standard-A"),
                    },
                    "audioConfig": {"audioEncoding": "MP3"},
                },
                timeout=15,
            )
            resp.raise_for_status()
            import base64
            audio_b64 = resp.json().get("audioContent", "")
            return SynthesisResult(audio_bytes=base64.b64decode(audio_b64), content_type="audio/mp3",
                                    provider="google")
        except Exception as e:
            logger.warning("Google TTS call failed", exc_info=True)
            return SynthesisResult(audio_bytes=b"", content_type="audio/mp3", provider="google-error",
                                    warnings=[f"Google TTS request failed: {e}"])


class AzureTTSProvider(TextToSpeechProvider):
    """Azure Cognitive Services Speech synthesis REST (SSML). Not
    live-tested this sprint — see module docstring."""

    name = "azure"
    _VOICE_NAMES = {"en": "en-IN-NeerjaNeural", "kn": "kn-IN-SapnaNeural"}

    def synthesize(self, text, language, voice=None) -> SynthesisResult:
        api_key = os.getenv("AZURE_SPEECH_KEY")
        region = os.getenv("AZURE_SPEECH_REGION")
        if not api_key or not region:
            return SynthesisResult(audio_bytes=b"", content_type="audio/mp3", provider="azure-error",
                                    warnings=["AZURE_SPEECH_KEY / AZURE_SPEECH_REGION not set."])
        voice_name = voice or self._VOICE_NAMES.get(language, "en-IN-NeerjaNeural")
        lang_code = "kn-IN" if language == "kn" else "en-IN"
        ssml = (f"<speak version='1.0' xml:lang='{lang_code}'>"
                f"<voice xml:lang='{lang_code}' name='{voice_name}'>{text}</voice></speak>")
        try:
            resp = requests.post(
                f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                headers={
                    "Ocp-Apim-Subscription-Key": api_key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "audio-16khz-32kbitrate-mono-mp3",
                },
                data=ssml.encode("utf-8"), timeout=15,
            )
            resp.raise_for_status()
            return SynthesisResult(audio_bytes=resp.content, content_type="audio/mp3", provider="azure")
        except Exception as e:
            logger.warning("Azure TTS call failed", exc_info=True)
            return SynthesisResult(audio_bytes=b"", content_type="audio/mp3", provider="azure-error",
                                    warnings=[f"Azure TTS request failed: {e}"])


_PROVIDERS = {
    "google": GoogleTTSProvider,
    "azure": AzureTTSProvider,
    "espeak": EspeakTTSProvider,
    "none": NullTTSProvider,
}


def get_tts_provider(name: str | None = None) -> TextToSpeechProvider:
    """
    Factory. `name` overrides `SHERLOCK_TTS_PROVIDER`; both default to
    "espeak" — the one provider that actually works with zero
    configuration, matching the handover's graceful-degradation
    requirement while still giving real audio out of the box rather
    than defaulting straight to "none".
    """
    key = (name or os.getenv("SHERLOCK_TTS_PROVIDER") or "espeak").lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        logger.warning("Unknown SHERLOCK_TTS_PROVIDER=%r; falling back to EspeakTTSProvider.", key)
        cls = EspeakTTSProvider
    return cls()
