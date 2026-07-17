"""
SHERLOCK — Sprint D3: Speech-to-text.

Pluggable, per the handover ("Make providers pluggable... No provider
should be hardcoded"). `get_stt_provider()` reads `SHERLOCK_STT_PROVIDER`
(one of "google" / "azure" / "whisper" / "deepgram" / "none") and
returns the matching provider, defaulting to `NullSTTProvider` — which
never crashes, just reports "no provider configured" — when unset or
unrecognized.

Honest constraint, stated once here rather than repeated in every
provider class: none of the four cloud providers below could be
live-tested in the sandbox this sprint was built in — their domains
(speech.googleapis.com, *.cognitiveservices.azure.com, api.openai.com,
api.deepgram.com) aren't reachable from that environment, and no
provider API keys were available either. Each class is a real,
spec-correct integration (request shape, auth header, response
parsing) against that provider's actual REST API, not a stub — but
"correctly written" and "verified against the live service" are
different claims, and only the former is made here. See the Sprint D3
report's "Known Limitations" for what *was* validated: every provider's
error handling (bad/missing key, network failure, malformed response)
degrades to a `TranscriptionResult` with `provider="<name>-error"` and
a warning, never an unhandled exception — exercised in
`validate_stage_d3.py` via mocked HTTP responses.
"""

from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

LANGUAGE_CODES = {
    # BCP-47 codes each provider expects, keyed by our internal "en"/"kn".
    "google":   {"en": "en-IN", "kn": "kn-IN"},
    "azure":    {"en": "en-IN", "kn": "kn-IN"},
    "whisper":  {"en": "en", "kn": "kn"},
    "deepgram": {"en": "en-IN", "kn": "kn"},  # Deepgram's Kannada support is limited/model-dependent
}


@dataclass
class TranscriptionResult:
    text: str
    language: str | None          # "en" | "kn" | None if the provider couldn't tell
    confidence: float
    provider: str                 # e.g. "google", "none", "google-error"
    warnings: list = field(default_factory=list)


class SpeechToTextProvider:
    """Base interface every STT provider implements."""

    name = "base"

    def transcribe(self, audio_bytes: bytes, content_type: str,
                    language_hint: str | None = None) -> TranscriptionResult:
        raise NotImplementedError


class NullSTTProvider(SpeechToTextProvider):
    """Default when no provider is configured. Never raises."""

    name = "none"

    def transcribe(self, audio_bytes, content_type, language_hint=None) -> TranscriptionResult:
        return TranscriptionResult(
            text="", language=language_hint, confidence=0.0, provider="none",
            warnings=["No STT provider configured (SHERLOCK_STT_PROVIDER unset). "
                      "Set it to 'google', 'azure', 'whisper', or 'deepgram' and provide "
                      "that provider's API key to enable real transcription."],
        )


class GoogleSTTProvider(SpeechToTextProvider):
    """Google Cloud Speech-to-Text v1 `speech:recognize` (synchronous, short audio)."""

    name = "google"

    def transcribe(self, audio_bytes, content_type, language_hint=None) -> TranscriptionResult:
        api_key = os.getenv("GOOGLE_STT_API_KEY")
        if not api_key:
            return TranscriptionResult(text="", language=language_hint, confidence=0.0,
                                        provider="google-error",
                                        warnings=["GOOGLE_STT_API_KEY not set."])
        lang_code = LANGUAGE_CODES["google"].get(language_hint or "en", "en-IN")
        try:
            resp = requests.post(
                f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}",
                json={
                    "config": {
                        "encoding": "LINEAR16" if "wav" in content_type else "ENCODING_UNSPECIFIED",
                        "languageCode": lang_code,
                        "alternativeLanguageCodes": list(LANGUAGE_CODES["google"].values()),
                        "enableAutomaticPunctuation": True,
                    },
                    "audio": {"content": base64.b64encode(audio_bytes).decode("ascii")},
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results") or []
            if not results:
                return TranscriptionResult(text="", language=language_hint, confidence=0.0,
                                            provider="google", warnings=["No speech recognized."])
            alt = results[0]["alternatives"][0]
            detected_lang = results[0].get("languageCode", lang_code)
            internal_lang = "kn" if detected_lang.startswith("kn") else "en"
            return TranscriptionResult(
                text=alt.get("transcript", ""), language=internal_lang,
                confidence=float(alt.get("confidence", 0.0)), provider="google",
            )
        except Exception as e:
            logger.warning("Google STT call failed", exc_info=True)
            return TranscriptionResult(text="", language=language_hint, confidence=0.0,
                                        provider="google-error", warnings=[f"Google STT request failed: {e}"])


class AzureSTTProvider(SpeechToTextProvider):
    """Azure Cognitive Services Speech-to-Text REST (short audio, single recognition)."""

    name = "azure"

    def transcribe(self, audio_bytes, content_type, language_hint=None) -> TranscriptionResult:
        api_key = os.getenv("AZURE_SPEECH_KEY")
        region = os.getenv("AZURE_SPEECH_REGION")
        if not api_key or not region:
            return TranscriptionResult(text="", language=language_hint, confidence=0.0,
                                        provider="azure-error",
                                        warnings=["AZURE_SPEECH_KEY / AZURE_SPEECH_REGION not set."])
        lang_code = LANGUAGE_CODES["azure"].get(language_hint or "en", "en-IN")
        try:
            resp = requests.post(
                f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/"
                f"cognitiveservices/v1?language={lang_code}",
                headers={
                    "Ocp-Apim-Subscription-Key": api_key,
                    "Content-Type": content_type or "audio/wav; codecs=audio/pcm; samplerate=16000",
                    "Accept": "application/json",
                },
                data=audio_bytes,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("RecognitionStatus") != "Success":
                return TranscriptionResult(text="", language=language_hint, confidence=0.0,
                                            provider="azure",
                                            warnings=[f"Azure recognition status: {data.get('RecognitionStatus')}"])
            return TranscriptionResult(
                text=data.get("DisplayText", ""), language=language_hint or "en",
                confidence=float(data.get("Confidence", 0.0)) if "Confidence" in data else 0.7,
                provider="azure",
            )
        except Exception as e:
            logger.warning("Azure STT call failed", exc_info=True)
            return TranscriptionResult(text="", language=language_hint, confidence=0.0,
                                        provider="azure-error", warnings=[f"Azure STT request failed: {e}"])


class WhisperSTTProvider(SpeechToTextProvider):
    """OpenAI Whisper API (`/v1/audio/transcriptions`). Needs OPENAI_API_KEY —
    a separate provider/key from Anthropic; SHERLOCK's own LLM calls
    (translation, narrative generation) never touch this key or vice versa."""

    name = "whisper"

    def transcribe(self, audio_bytes, content_type, language_hint=None) -> TranscriptionResult:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return TranscriptionResult(text="", language=language_hint, confidence=0.0,
                                        provider="whisper-error",
                                        warnings=["OPENAI_API_KEY not set."])
        lang_code = LANGUAGE_CODES["whisper"].get(language_hint) if language_hint else None
        try:
            files = {"file": ("audio.wav", audio_bytes, content_type or "audio/wav")}
            data = {"model": "whisper-1"}
            if lang_code:
                data["language"] = lang_code
            resp = requests.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files=files, data=data, timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()
            return TranscriptionResult(
                text=result.get("text", ""), language=language_hint, confidence=0.7,
                provider="whisper",
                warnings=["Whisper API doesn't return a confidence score; 0.7 is a placeholder, not a measurement."],
            )
        except Exception as e:
            logger.warning("Whisper STT call failed", exc_info=True)
            return TranscriptionResult(text="", language=language_hint, confidence=0.0,
                                        provider="whisper-error", warnings=[f"Whisper request failed: {e}"])


class DeepgramSTTProvider(SpeechToTextProvider):
    """Deepgram `/v1/listen` prerecorded transcription."""

    name = "deepgram"

    def transcribe(self, audio_bytes, content_type, language_hint=None) -> TranscriptionResult:
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            return TranscriptionResult(text="", language=language_hint, confidence=0.0,
                                        provider="deepgram-error",
                                        warnings=["DEEPGRAM_API_KEY not set."])
        lang_code = LANGUAGE_CODES["deepgram"].get(language_hint or "en", "en-IN")
        try:
            resp = requests.post(
                f"https://api.deepgram.com/v1/listen?language={lang_code}&punctuate=true",
                headers={"Authorization": f"Token {api_key}", "Content-Type": content_type or "audio/wav"},
                data=audio_bytes, timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            channel = data["results"]["channels"][0]["alternatives"][0]
            return TranscriptionResult(
                text=channel.get("transcript", ""), language=language_hint or "en",
                confidence=float(channel.get("confidence", 0.0)), provider="deepgram",
            )
        except Exception as e:
            logger.warning("Deepgram STT call failed", exc_info=True)
            return TranscriptionResult(text="", language=language_hint, confidence=0.0,
                                        provider="deepgram-error", warnings=[f"Deepgram request failed: {e}"])


_PROVIDERS = {
    "google": GoogleSTTProvider,
    "azure": AzureSTTProvider,
    "whisper": WhisperSTTProvider,
    "deepgram": DeepgramSTTProvider,
    "none": NullSTTProvider,
}


def get_stt_provider(name: str | None = None) -> SpeechToTextProvider:
    """
    Factory. `name` overrides `SHERLOCK_STT_PROVIDER`; both default to
    "none" (`NullSTTProvider`) — the graceful, always-available default
    the handover requires ("no provider -> graceful fallback").
    """
    key = (name or os.getenv("SHERLOCK_STT_PROVIDER") or "none").lower()
    cls = _PROVIDERS.get(key)
    if cls is None:
        logger.warning("Unknown SHERLOCK_STT_PROVIDER=%r; falling back to NullSTTProvider.", key)
        cls = NullSTTProvider
    return cls()
