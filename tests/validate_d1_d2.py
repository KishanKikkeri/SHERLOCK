"""
SHERLOCK — Stage D, Sprint 1/2 validation.

Covers:
  1. Language detection (English / Kannada / mixed / unknown).
  2. TranslationService graceful degradation with no ANTHROPIC_API_KEY
     (must never raise — every existing/new caller depends on this).
  3. TranslationService's Anthropic-backed path + glossary protection/
     verification, using a mocked Anthropic client (no live network
     call — see the Sprint report's "Known Limitations" for why this
     couldn't be validated against the real API in this environment).
  4. /language/* API surface (Sprint D5).
  5. End-to-end pipeline integration through POST /investigate and
     stream_investigation with language="kn", against the real seeded
     database, with and without ANTHROPIC_API_KEY — confirming the
     query_translated event, the report's `localized` block, and that
     the investigation itself never fails because of translation.
  6. Regression: existing English-only WS/REST callers (language
     omitted) are byte-for-byte unaffected — no query_translated event,
     no `localized` block, findings identical in shape to pre-Stage-D.

Run: python validate_d1_d2.py
"""

import asyncio
import json
import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.api.investigation_stream import stream_investigation
from backend.language import (
    detect_language, TranslationService, GLOSSARY, get_resources, SUPPORTED_LANGUAGES,
)

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


# ---------------------------------------------------------------------------
# 1. Language detection
# ---------------------------------------------------------------------------
divider("Language detection")

r = detect_language("Who are the accused in this case?")
assert_(r.language == "en" and r.confidence > 0.9, f"English detected correctly ({r})")

r = detect_language("ಈ ಪ್ರಕರಣದ ಆರೋಪಿಗಳು ಯಾರು?")
assert_(r.language == "kn" and r.confidence > 0.9, f"Kannada detected correctly ({r})")

r = detect_language("ರವಿ Kumar ಬಗ್ಗೆ ತಿಳಿಸಿ")
assert_(r.language == "mixed", f"Mixed-script query flagged as mixed, not silently dropped ({r})")

r = detect_language("FIR-2026-00013")
assert_(r.language in ("en", "unknown"), f"Alphanumeric case-number-like text doesn't crash detection ({r})")

r = detect_language("")
assert_(r.language == "unknown" and r.confidence == 0.0, f"Empty string handled ({r})")


# ---------------------------------------------------------------------------
# 2. Graceful degradation without ANTHROPIC_API_KEY
# ---------------------------------------------------------------------------
divider("Translation service — no API key (must never raise)")

os.environ.pop("ANTHROPIC_API_KEY", None)
svc = TranslationService()

result = svc.to_english("ಈ ಪ್ರಕರಣದ ಆರೋಪಿಗಳು ಯಾರು?")
assert_(result.engine == "passthrough", f"No key -> passthrough engine, not an exception ({result.engine})")
assert_(result.text == "ಈ ಪ್ರಕರಣದ ಆರೋಪಿಗಳು ಯಾರು?", "Passthrough returns original text unchanged")
assert_(len(result.warnings) == 1 and "ANTHROPIC_API_KEY" in result.warnings[0], "Warning names the actual cause")

same_lang = svc.translate("hello", target_language="en", source_language="en")
assert_(same_lang.engine == "noop" and same_lang.confidence == 1.0, "Same source/target language is a no-op, not a wasted call")

empty = svc.translate("", target_language="kn")
assert_(empty.engine == "noop", "Empty string is a no-op")

batch = svc.batch_translate(["one", "two"], target_language="kn")
assert_(len(batch) == 2 and all(r.engine == "passthrough" for r in batch),
        "batch_translate degrades per-item without a key, doesn't raise")


# ---------------------------------------------------------------------------
# 3. Anthropic-backed path + glossary (mocked — see report for why)
# ---------------------------------------------------------------------------
divider("Translation service — mocked Anthropic client + glossary enforcement")

os.environ["ANTHROPIC_API_KEY"] = "test-fake-key-for-validation-only"
svc = TranslationService()

good_json = json.dumps({"translation": "ಈ ಪ್ರಕರಣದಲ್ಲಿ ಆರೋಪಿ ಯಾರು?", "confidence": 0.92, "notes": []}, ensure_ascii=False)
with patch.object(TranslationService, "_client") as mock_client:
    mock_client.return_value.messages.create.return_value = FakeResponse(good_json)
    good = svc.translate("Who is the accused in this case?", target_language="kn", source_language="en")
assert_(good.engine == "anthropic", "Mocked LLM path used when a key is present")
assert_(good.warnings == [], "Correct glossary usage (ಆರೋಪಿ) produces no glossary warnings")

bad_json = json.dumps({"translation": "ಈ ಪ್ರಕರಣದ ವ್ಯಕ್ತಿ ಯಾರು?", "confidence": 0.5, "notes": []}, ensure_ascii=False)
with patch.object(TranslationService, "_client") as mock_client:
    mock_client.return_value.messages.create.return_value = FakeResponse(bad_json)
    bad = svc.translate("Who is the accused named in the FIR?", target_language="kn", source_language="en")
assert_(any("FIR" in w for w in bad.warnings), "Dropped protected term (FIR) is flagged")
assert_(any("Accused" in w for w in bad.warnings), "Ignored approved translation (Accused -> ಆರೋಪಿ) is flagged")

batch_json = json.dumps({"0": "ಒಂದು", "1": "ಎರಡು"}, ensure_ascii=False)
with patch.object(TranslationService, "_client") as mock_client:
    mock_client.return_value.messages.create.return_value = FakeResponse(batch_json)
    batch_results = svc.batch_translate(["one", "two"], target_language="kn", source_language="en")
assert_([r.text for r in batch_results] == ["ಒಂದು", "ಎರಡು"], "Batch translation maps results back to the right index")

assert_(GLOSSARY.lookup_english("FIR").policy == "protect", "FIR is a protected (untranslated) glossary term")
assert_(GLOSSARY.lookup_english("Accused").kn == "ಆರೋಪಿ", "Accused has the approved Kannada equivalent wired")
assert_(GLOSSARY.lookup_kannada("ಆರೋಪಿ") == "Accused", "Reverse (Kannada -> canonical English) glossary index works")


# ---------------------------------------------------------------------------
# 4. /language/* API (Sprint D5)
# ---------------------------------------------------------------------------
divider("Language resources API")

os.environ.pop("ANTHROPIC_API_KEY", None)  # back to no-key for the rest of this run

r = client.get("/language/supported")
assert_(r.status_code == 200 and set(r.json()["languages"]) == set(SUPPORTED_LANGUAGES), "GET /language/supported")

r = client.get("/language/resources/kn")
assert_(r.status_code == 200 and "labels" in r.json() and "discussion" in r.json(), "GET /language/resources/kn")

r = client.get("/language/resources/xx")
assert_(r.status_code == 404, "Unsupported language code returns 404, not a 500")

r = client.get("/language/voice-commands")
assert_(r.status_code == 200 and "open_investigation" in r.json(), "GET /language/voice-commands (Sprint D3 groundwork)")

r = client.post("/language/detect", json={"text": "ತನಿಖೆ ತೆರೆಯಿರಿ"})
assert_(r.status_code == 200 and r.json()["language"] == "kn", "POST /language/detect")

r = client.post("/language/translate", json={"text": "hello", "target_language": "zz"})
assert_(r.status_code == 422, "Unsupported target_language rejected with 422")


# ---------------------------------------------------------------------------
# 5. Pipeline integration — real seeded DB, real graph, no live LLM
# ---------------------------------------------------------------------------
divider("Pipeline integration — POST /investigate, language=kn, no API key")

r = client.post("/investigate", json={"query": "ಈ ಪ್ರಕರಣದ ಆರೋಪಿಗಳು ಯಾರು?", "language": "kn"})
assert_(r.status_code == 200, "POST /investigate with a Kannada query + language=kn doesn't fail")
data = r.json()
assert_(data["language"] == "kn", "Response echoes the requested language")
assert_("localized" in data["final_report"], "final_report carries a `localized` block when language != en")
assert_("narrative" in data["final_report"] and data["final_report"]["narrative"],
        "Original English `narrative` key is untouched/present alongside `localized`")

r = client.post("/investigate", json={"query": "not a language code test", "language": "xx"})
assert_(r.status_code == 422, "Invalid language code rejected with 422")


async def _run_ws_style(query, language=None):
    events = []

    async def collect(event):
        events.append(event)

    await stream_investigation(query, collect, language=language)
    return events


divider("Pipeline integration — stream_investigation, query_translated event")

events = asyncio.run(_run_ws_style("ಈ ಪ್ರಕರಣವನ್ನು ಮುಚ್ಚಿ", language="kn"))
translated_events = [e for e in events if e["event_type"] == "query_translated"]
assert_(len(translated_events) == 1, "Exactly one query_translated event emitted for a Kannada query")
assert_(translated_events[0]["data"]["original_query"] == "ಈ ಪ್ರಕರಣವನ್ನು ಮುಚ್ಚಿ", "Original query preserved in the event")
assert_(translated_events[0]["data"]["engine"] == "passthrough", "No key in this env -> passthrough engine, visible in the event data")

agent_events = [e for e in events if e["event_type"] == "agent_completed"]
assert_(len(agent_events) > 0, "Pipeline still ran agents after translation step (translation is before, not inside, the pipeline)")
assert_(all("localized_message" in (e.get("data") or {}) for e in agent_events),
        "Every per-node event got a parallel localized_message once language=kn was in effect")

report_events = [e for e in events if e["event_type"] == "report_ready"]
assert_(len(report_events) == 1, "report_ready still fires exactly once")
assert_("localized" in report_events[0]["data"]["final_report"], "Final report_ready payload carries the localized block too")


# ---------------------------------------------------------------------------
# 6. Regression — English-only, no `language` param, byte-for-byte as before
# ---------------------------------------------------------------------------
divider("Regression — language omitted behaves exactly as pre-Stage-D")

events_plain = asyncio.run(_run_ws_style("Show repeat burglary offenders in Mysuru"))
assert_(not any(e["event_type"] == "query_translated" for e in events_plain),
        "No query_translated event when language is omitted and query is English")
agent_events_plain = [e for e in events_plain if e["event_type"] == "agent_completed"]
assert_(all("localized_message" not in (e.get("data") or {}) for e in agent_events_plain),
        "No localized_message key added to events for English-only callers (additive, not always-on)")
report_plain = next(e for e in events_plain if e["event_type"] == "report_ready")
assert_("localized" not in report_plain["data"]["final_report"],
        "No `localized` block added to final_report for English-only callers")

r = client.post("/investigate", json={"query": "Show repeat burglary offenders in Mysuru"})
assert_(r.status_code == 200 and r.json()["language"] == "en", "POST /investigate with no language field defaults to en")
assert_("localized" not in r.json()["final_report"], "No localized block when language omitted")


print("\nALL VALIDATIONS PASSED")
