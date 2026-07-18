"""
SHERLOCK — Stage D, Sprint 3 validation: Voice Localization.

Covers:
  1. Provider factories: pluggability + graceful default (no env vars
     set -> NullSTTProvider / EspeakTTSProvider, never a crash).
  2. EspeakTTSProvider — the one provider that's genuinely, locally
     functional in this environment: real audio bytes, both languages,
     verified as valid WAV (not just "some bytes came back").
  3. Cloud providers (Google/Azure/Whisper/Deepgram STT, Google/Azure
     TTS) degrade gracefully with no API key — never raise, always
     return a result object with a `-error` provider tag and a warning
     naming the missing key. Their actual HTTP-call code path is
     exercised with a mocked `requests.post` (this environment can't
     reach their real domains — see the Sprint D3 report).
  4. VoiceService end-to-end: fake STT "speaking" Kannada -> the
     UNMODIFIED VoiceCommandRouter correctly resolves a Kannada voice
     command once translation is available (mocked Anthropic client,
     same honest-limitation pattern as validate_d1_d2.py) -> a Kannada
     spoken_response -> real synthesized audio.
  5. VoiceService end-to-end with translation genuinely unavailable (no
     API key) — proves the whole chain still completes without an
     exception; the router falls through to a free-text investigation
     of the untranslated text, which is documented, expected cascading
     degradation, not a Sprint D3 bug.
  6. `/voice/transcribe`, `/voice/speak`, `/voice/query` API endpoints.
  7. `/voice/command` (Stage C3, untouched) still works exactly as
     before — regression.

Run: python validate_stage_d3.py
"""

import asyncio
import json
import os
import wave
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.database.config import SessionLocal
from backend.language.translation_service import TranslationService
from backend.voice.speech_to_text import (
    get_stt_provider, NullSTTProvider, GoogleSTTProvider, AzureSTTProvider,
    WhisperSTTProvider, DeepgramSTTProvider, SpeechToTextProvider, TranscriptionResult,
)
from backend.voice.text_to_speech import (
    get_tts_provider, EspeakTTSProvider, GoogleTTSProvider, AzureTTSProvider, NullTTSProvider,
)
from backend.voice.voice_service import VoiceService

client = TestClient(app)


def divider(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


def assert_(cond, msg):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        raise AssertionError(msg)


class FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeBlock(text)]


def is_valid_wav(audio_bytes: bytes) -> bool:
    try:
        with wave.open(BytesIO(audio_bytes), "rb") as w:
            return w.getnframes() > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 1. Provider factories
# ---------------------------------------------------------------------------
divider("Provider factories — pluggability + graceful defaults")

os.environ.pop("SHERLOCK_STT_PROVIDER", None)
os.environ.pop("SHERLOCK_TTS_PROVIDER", None)

assert_(isinstance(get_stt_provider(), NullSTTProvider), "No SHERLOCK_STT_PROVIDER -> NullSTTProvider by default")
assert_(isinstance(get_tts_provider(), EspeakTTSProvider), "No SHERLOCK_TTS_PROVIDER -> EspeakTTSProvider by default")
assert_(isinstance(get_stt_provider("google"), GoogleSTTProvider), "Explicit name selects the right provider (google)")
assert_(isinstance(get_stt_provider("bogus-provider"), NullSTTProvider), "Unknown provider name falls back to Null, doesn't raise")

os.environ["SHERLOCK_STT_PROVIDER"] = "azure"
assert_(isinstance(get_stt_provider(), AzureSTTProvider), "Env var SHERLOCK_STT_PROVIDER=azure selects AzureSTTProvider")
os.environ.pop("SHERLOCK_STT_PROVIDER", None)


# ---------------------------------------------------------------------------
# 2. EspeakTTSProvider — real, working, offline
# ---------------------------------------------------------------------------
divider("EspeakTTSProvider — real offline synthesis (both languages)")

espeak = EspeakTTSProvider()
assert_(espeak._binary is not None, "espeak-ng binary found on PATH")

r_en = espeak.synthesize("Investigation started.", "en")
assert_(r_en.provider == "espeak" and len(r_en.audio_bytes) > 1000, "English synthesis produces real audio bytes")
assert_(is_valid_wav(r_en.audio_bytes), "English output is a valid, playable WAV file")

r_kn = espeak.synthesize("ತನಿಖೆ ಪ್ರಾರಂಭವಾಗಿದೆ", "kn")
assert_(r_kn.provider == "espeak" and len(r_kn.audio_bytes) > 1000, "Kannada synthesis produces real audio bytes")
assert_(is_valid_wav(r_kn.audio_bytes), "Kannada output is a valid, playable WAV file")

r_empty = espeak.synthesize("", "en")
assert_(r_empty.audio_bytes == b"" and r_empty.warnings, "Empty text is handled without crashing")


# ---------------------------------------------------------------------------
# 3. Cloud providers — spec-correct, but graceful without keys/network
# ---------------------------------------------------------------------------
divider("Cloud STT/TTS providers — graceful degradation (no key)")

for env_key in ("GOOGLE_STT_API_KEY", "AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION",
                 "OPENAI_API_KEY", "DEEPGRAM_API_KEY", "GOOGLE_TTS_API_KEY"):
    os.environ.pop(env_key, None)

for cls in (GoogleSTTProvider, AzureSTTProvider, WhisperSTTProvider, DeepgramSTTProvider):
    result = cls().transcribe(b"fake-audio", "audio/wav", language_hint="en")
    assert_(result.provider.endswith("-error") and result.text == "" and result.warnings,
            f"{cls.__name__} degrades gracefully with no key configured (never raises)")

for cls in (GoogleTTSProvider, AzureTTSProvider):
    result = cls().synthesize("hello", "en")
    assert_(result.provider.endswith("-error") and result.audio_bytes == b"" and result.warnings,
            f"{cls.__name__} degrades gracefully with no key configured (never raises)")

divider("Cloud providers — spec-correctness via mocked HTTP (network unreachable in this sandbox)")

os.environ["GOOGLE_STT_API_KEY"] = "test-fake-key"
with patch("backend.voice.speech_to_text.requests.post") as mock_post:
    mock_post.return_value.raise_for_status = lambda: None
    mock_post.return_value.json = lambda: {
        "results": [{"alternatives": [{"transcript": "who are the accused", "confidence": 0.93}],
                     "languageCode": "en-IN"}]
    }
    result = GoogleSTTProvider().transcribe(b"fake-wav-bytes", "audio/wav", language_hint="en")
assert_(result.provider == "google" and result.text == "who are the accused" and result.confidence == 0.93,
        "GoogleSTTProvider correctly parses a well-formed API response (mocked)")
os.environ.pop("GOOGLE_STT_API_KEY", None)


# ---------------------------------------------------------------------------
# 4. VoiceService — full workflow with mocked translation
# ---------------------------------------------------------------------------
divider("VoiceService — Kannada voice command, full workflow (mocked translation)")

os.environ["ANTHROPIC_API_KEY"] = "test-fake-key-for-validation-only"


class FakeKannadaSTT(SpeechToTextProvider):
    name = "fake"

    def transcribe(self, audio_bytes, content_type, language_hint=None):
        return TranscriptionResult(text="ತನಿಖೆ ತೆರೆಯಿರಿ", language="kn", confidence=0.9, provider="fake")


def fake_translate_create(*args, **kwargs):
    prompt = kwargs["messages"][0]["content"]
    if "from Kannada to English" in prompt:
        return FakeResponse(json.dumps({"translation": "Open investigation", "confidence": 0.9, "notes": []}))
    return FakeResponse(json.dumps({"translation": "ಹೊಸ ತನಿಖೆ ತೆರೆಯಲಾಗಿದೆ.", "confidence": 0.9, "notes": []}))


session = SessionLocal()
service = VoiceService(session, stt_provider=FakeKannadaSTT())

with patch.object(TranslationService, "_client") as mock_client:
    mock_client.return_value.messages.create.side_effect = fake_translate_create
    result = asyncio.run(service.process_voice_command(b"fake-audio-bytes", "audio/wav"))

assert_(result.transcript == "ತನಿಖೆ ತೆರೆಯಿರಿ", "Raw transcript preserved as spoken")
assert_(result.detected_language == "kn", "Language correctly detected as Kannada")
assert_(result.working_transcript == "Open investigation",
        "Kannada transcript translated to English before reaching VoiceCommandRouter")
assert_(result.intent == "open_case",
        "The UNMODIFIED VoiceCommandRouter correctly resolved the intent from the translated text")
assert_(result.spoken_response != result.spoken_response_en or result.spoken_response_en == "",
        "Spoken response was translated back toward Kannada (mocked)")
assert_(result.audio is not None and len(result.audio.audio_bytes) > 0, "Real spoken-response audio was synthesized")
assert_(is_valid_wav(result.audio.audio_bytes), "Synthesized response audio is a valid WAV")
session.close()


# ---------------------------------------------------------------------------
# 5. VoiceService — full workflow with NO translation available (honest degradation)
# ---------------------------------------------------------------------------
divider("VoiceService — graceful cascade with no ANTHROPIC_API_KEY at all")

os.environ.pop("ANTHROPIC_API_KEY", None)
session = SessionLocal()
service = VoiceService(session, stt_provider=FakeKannadaSTT())
result = asyncio.run(service.process_voice_command(b"fake-audio-bytes", "audio/wav"))
session.close()

assert_(result.transcript == "ತನಿಖೆ ತೆರೆಯಿರಿ", "Transcript still captured even with no translation available")
assert_(any("ANTHROPIC_API_KEY" in w for w in result.warnings),
        "Warnings clearly explain translation was unavailable")
assert_(result.audio is not None, "Pipeline still completes end-to-end (no exception) without translation")
assert_(result.intent,
        "Router still produced *some* result from the untranslated text rather than crashing "
        "(expected fallthrough to free-text investigation — documented, not a Sprint D3 bug)")


# ---------------------------------------------------------------------------
# 6. API endpoints
# ---------------------------------------------------------------------------
divider("Voice API endpoints")

r = client.post("/voice/speak", json={"text": "Investigation started", "language": "en"})
assert_(r.status_code == 200 and len(r.content) > 1000, "POST /voice/speak (en) returns real audio")
assert_(r.headers.get("x-tts-provider") == "espeak", "X-TTS-Provider header names the actual provider used")

r_kn = client.post("/voice/speak", json={"text": "ತನಿಖೆ ಪ್ರಾರಂಭವಾಗಿದೆ", "language": "kn"})
assert_(r_kn.status_code == 200 and len(r_kn.content) > 1000, "POST /voice/speak (kn) returns real audio")

r_bad = client.post("/voice/speak", json={"text": "hi", "language": "fr"})
assert_(r_bad.status_code == 422, "POST /voice/speak rejects unsupported language")

files = {"audio": ("test.wav", r.content, "audio/wav")}
r2 = client.post("/voice/transcribe", files=files, data={"language_hint": "en"})
assert_(r2.status_code == 200, "POST /voice/transcribe accepts a real uploaded audio file")
body2 = r2.json()
assert_(body2["provider"] == "none" and body2["text"] == "",
        "No STT provider configured in this environment -> graceful empty result, not an error")

files3 = {"audio": ("test.wav", r.content, "audio/wav")}
r3 = client.post("/voice/query", files=files3, data={"language_hint": "en"})
assert_(r3.status_code == 200, "POST /voice/query completes even with STT unavailable")
body3 = r3.json()
assert_(body3["intent"] == "empty", "Empty transcript (no STT) correctly falls through to the 'empty' intent, not a 500")
assert_("warnings" in body3 and len(body3["warnings"]) > 0, "Warnings surfaced in the JSON response")


# ---------------------------------------------------------------------------
# 7. /voice/command regression (Stage C3, untouched)
# ---------------------------------------------------------------------------
divider("Regression — /voice/command (Stage C3) unaffected")

r4 = client.post("/voice/command", json={"transcript": "Open investigation"})
assert_(r4.status_code == 200 and r4.json().get("intent") == "open_case",
        "/voice/command still works exactly as before Sprint D3")


print("\nALL VALIDATIONS PASSED")
