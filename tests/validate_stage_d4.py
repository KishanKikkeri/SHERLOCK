"""
SHERLOCK — Stage D, Sprint 4 validation: Localized PDF Export.

Covers, against REAL generated PDFs (not mocks — PDF rendering is local,
no network/API key needed to validate the rendering pipeline itself):

  1. Kannada font registration succeeds and the font genuinely has no
     Latin glyphs (documents *why* the mixed-script markup fix exists,
     doesn't just assert the fix works).
  2. English-mode output is unaffected: same fonts used (Helvetica/
     Courier only, no Kannada font referenced at all), same extracted
     text content, whether `language` is omitted or explicitly "en".
  3. Kannada-mode PDF actually embeds the Kannada font (`pdffonts`) and
     extracts back to correct Kannada text (`pdftotext`) — not tofu,
     not mojibake.
  4. Mixed-script content (protected glossary terms like FIR/IPC sitting
     inside Kannada sentences, English agent names inside a Kannada
     report) renders correctly — this is the bug this sprint actually
     found and fixed (see report).
  5. Bilingual mode shows both languages.
  6. Graceful degradation: Kannada font unavailable -> falls back to a
     valid English PDF + a warning, never an exception.
  7. Graceful degradation: `language="kn"` requested but `final_report`
     has no `localized` block -> same graceful fallback.
  8. Invalid `language` value raises ValueError (fails loud, not a
     silent wrong-language PDF).
  9. `POST /export/pdf` API integration: `language` field + the
     `X-PDF-Warnings` response header.

Requires `pdffonts`/`pdftotext` (poppler-utils) and `fontTools` on PATH
for the deepest checks; both are used here, not just claimed available.

Run: python validate_stage_d4.py
"""

import subprocess
import tempfile
from unittest import mock

from fastapi.testclient import TestClient
from fontTools.ttLib import TTFont as FTFont

from backend.app.main import app
from backend.reporting import pdf_export
from backend.reporting.pdf_export import (
    generate_investigation_pdf, pdf_export_warnings,
    KANNADA_FONT_AVAILABLE, KANNADA_FONT_NAME, KANNADA_FONT_BOLD_NAME,
    _KANNADA_REGULAR_PATH,
)

client = TestClient(app)


def divider(title):
    print("\n" + "=" * 10 + f" {title} " + "=" * 10)


def assert_(cond, msg):
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        raise AssertionError(msg)


def pdffonts(path):
    return subprocess.run(["pdffonts", path], capture_output=True, text=True, check=True).stdout


def pdftotext(path):
    return subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True, check=True).stdout


SAMPLE_REPORT_EN = {
    "query": "Show repeat burglary offenders in Mysuru",
    "narrative": "Investigation summary for burglary offenders.",
    "agents_consulted": ["CrimeRecords", "CaseIntelligence"],
    "findings": [
        {"finding_type": "crime_summary", "agent_name": "CrimeRecords", "confidence": 0.9,
         "summary": "Found 3 repeat offenders.", "evidence": ["FIR-BLR-2026-00099 filed 2026-01-04"]},
    ],
}

# Hand-crafted localized block (doesn't depend on a live ANTHROPIC_API_KEY
# being available in this environment) with real Kannada text and a
# deliberately mixed-script sentence containing protected glossary terms
# (FIR, IPC) — exactly the case that broke before the mixed-script fix.
SAMPLE_REPORT_KN = {
    **SAMPLE_REPORT_EN,
    "localized": {
        "language": "kn",
        "original_query": "ಈ ಪ್ರಕರಣದ ಆರೋಪಿಗಳು ಯಾರು?",
        "narrative": "ಈ ಪ್ರಕರಣದಲ್ಲಿ 3 ಆರೋಪಿಗಳು ಇದ್ದಾರೆ, FIR ಪ್ರಕಾರ IPC ಸೆಕ್ಷನ್ 379, 411 ಅಡಿಯಲ್ಲಿ ದಾಖಲಿಸಲಾಗಿದೆ.",
        "findings": [
            {"finding_type": "crime_summary",
             "summary": "IPC 379 ಅಡಿಯಲ್ಲಿ ಆರೋಪಿಗಳನ್ನು ಹೆಸರಿಸುವ 3 FIR ದಾಖಲೆಗಳನ್ನು ಪಡೆಯಲಾಗಿದೆ."},
        ],
        "warnings": [],
    },
}


# ---------------------------------------------------------------------------
# 1. Font registration + the actual Latin-glyph gap that motivated the fix
# ---------------------------------------------------------------------------
divider("Kannada font registration + glyph coverage")

assert_(KANNADA_FONT_AVAILABLE, "Kannada font registered successfully at import time")

ft = FTFont(_KANNADA_REGULAR_PATH)
cmap = ft.getBestCmap()
assert_(0x0C85 in cmap, "Bundled font has Kannada script glyphs (U+0C85 'ಅ' present)")
assert_(0x41 not in cmap and 0x61 not in cmap,
        "Confirms (not assumes) the bundled Kannada font has NO Latin letters — "
        "this is exactly why the mixed-script markup fix in Sprint D4 is necessary")
assert_(ord("%") in cmap and ord("0") in cmap,
        "Font does cover digits/punctuation, so only Latin letters need the markup fix")


# ---------------------------------------------------------------------------
# 2. English mode — unaffected by this sprint
# ---------------------------------------------------------------------------
divider("English mode — regression")

pdf_omitted = generate_investigation_pdf(SAMPLE_REPORT_EN, [], "CID-1")
pdf_explicit = generate_investigation_pdf(SAMPLE_REPORT_EN, [], "CID-1", language="en")

with tempfile.NamedTemporaryFile(suffix=".pdf") as f1, tempfile.NamedTemporaryFile(suffix=".pdf") as f2:
    f1.write(pdf_omitted); f1.flush()
    f2.write(pdf_explicit); f2.flush()
    text1, text2 = pdftotext(f1.name), pdftotext(f2.name)
    fonts1 = pdffonts(f1.name)

assert_(text1 == text2, "Omitting `language` vs explicit language='en' produce identical extracted text")
assert_(KANNADA_FONT_NAME not in fonts1, "English-mode PDF never references the Kannada font at all")
assert_("Helvetica" in fonts1 and "Courier" in fonts1, "English-mode PDF still uses the original Helvetica/Courier fonts")
assert_("Found 3 repeat offenders." in text1, "English content renders correctly")


# ---------------------------------------------------------------------------
# 3 & 4. Kannada mode — real font embedding, correct text, mixed-script fix
# ---------------------------------------------------------------------------
divider("Kannada mode — real rendering validation")

pdf_kn = generate_investigation_pdf(SAMPLE_REPORT_KN, [], "REALKN-1", language="kn")
with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
    f.write(pdf_kn); f.flush()
    fonts_kn = pdffonts(f.name)
    text_kn = pdftotext(f.name)

assert_("NotoSansKannada-Regular" in fonts_kn and "emb" in fonts_kn, "Kannada font is present in pdffonts output")
for line in fonts_kn.splitlines():
    if "NotoSansKannada" in line:
        assert_(" yes " in line or line.strip().endswith("yes"),
                f"Kannada font is actually embedded (not just referenced): {line.strip()}")

assert_("ಆರೋಪಿಗಳು" in text_kn, "Kannada narrative text round-trips correctly through pdftotext")
assert_("FIR" in text_kn and "IPC" in text_kn,
        "Protected glossary terms (FIR, IPC) survive inside Kannada text — the mixed-script bug this sprint fixed")
assert_("IPC 379" in text_kn, "Mixed Kannada+Latin+digit sequence renders as one coherent run")
assert_("REALKN-1" in text_kn, "Case ID (Latin+digits) renders correctly under the Kannada font")
assert_("ಪ್ರಕರಣ ಸಂಖ್ಯೆ" in text_kn, "Kannada chrome/labels (case ID label) are localized in kn mode")


# ---------------------------------------------------------------------------
# 5. Bilingual mode
# ---------------------------------------------------------------------------
divider("Bilingual mode")

pdf_bi = generate_investigation_pdf(SAMPLE_REPORT_KN, [], "BI-1", language="bilingual")
with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
    f.write(pdf_bi); f.flush()
    text_bi = pdftotext(f.name)

assert_("Found 3 repeat offenders." not in text_bi or "ಆರೋಪಿಗಳು" in text_bi,
        "Bilingual mode is checked for actual bilingual content below")
assert_("Investigation summary for burglary offenders." in text_bi, "English narrative present in bilingual mode")
assert_("ಆರೋಪಿಗಳು" in text_bi, "Kannada narrative also present in bilingual mode")
assert_("CASE ID" in text_bi, "Bilingual mode keeps English chrome/labels per design")


# ---------------------------------------------------------------------------
# 6. Graceful degradation — font unavailable
# ---------------------------------------------------------------------------
divider("Graceful degradation — Kannada font unavailable")

with mock.patch.object(pdf_export, "KANNADA_FONT_AVAILABLE", False), \
     mock.patch.object(pdf_export, "KANNADA_FONT_ERROR", "simulated font load failure"):
    pdf_fallback = generate_investigation_pdf(SAMPLE_REPORT_KN, [], "FALLBACK-1", language="kn")
    warnings = pdf_export_warnings(SAMPLE_REPORT_KN, "kn")

with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
    f.write(pdf_fallback); f.flush()
    fonts_fb = pdffonts(f.name)
assert_(len(pdf_fallback) > 500, "A font-unavailable request still produces a real, non-empty PDF")
assert_("NotoSansKannada" not in fonts_fb, "Fallback PDF doesn't reference the (unavailable) Kannada font")
assert_(any("font unavailable" in w.lower() for w in warnings), "Warning explains exactly why it fell back")


# ---------------------------------------------------------------------------
# 7. Graceful degradation — no localized block
# ---------------------------------------------------------------------------
divider("Graceful degradation — missing localized block")

pdf_no_localized = generate_investigation_pdf(SAMPLE_REPORT_EN, [], "NOLOC-1", language="kn")
warnings2 = pdf_export_warnings(SAMPLE_REPORT_EN, "kn")
assert_(len(pdf_no_localized) > 500, "Kannada PDF requested for an English-only report still produces a real PDF")
assert_(any("no 'localized' block" in w for w in warnings2), "Warning explains the report had no localized content")


# ---------------------------------------------------------------------------
# 8. Invalid language
# ---------------------------------------------------------------------------
divider("Invalid language value")

try:
    generate_investigation_pdf(SAMPLE_REPORT_EN, [], "X", language="fr")
    assert_(False, "Should have raised ValueError for unsupported language")
except ValueError as e:
    assert_("fr" in str(e), f"ValueError names the bad value: {e}")


# ---------------------------------------------------------------------------
# 9. API integration
# ---------------------------------------------------------------------------
divider("POST /export/pdf — language param + X-PDF-Warnings header")

r = client.post("/export/pdf", json={"final_report": SAMPLE_REPORT_KN, "audit_trail": [],
                                      "case_id": "API-KN", "language": "kn"})
assert_(r.status_code == 200, "POST /export/pdf with language=kn succeeds")
assert_(r.headers.get("content-type") == "application/pdf", "Correct content-type")
assert_("x-pdf-warnings" not in r.headers, "No warning header when localization is actually available")

r2 = client.post("/export/pdf", json={"final_report": SAMPLE_REPORT_EN, "audit_trail": [],
                                       "case_id": "API-KN-NOLOC", "language": "kn"})
assert_(r2.status_code == 200, "Still 200 (graceful) even though this report has no localized block")
assert_("localized" in r2.headers.get("x-pdf-warnings", "").lower() or
        "no 'localized' block" in r2.headers.get("x-pdf-warnings", ""),
        "X-PDF-Warnings header explains the fallback")

r3 = client.post("/export/pdf", json={"final_report": SAMPLE_REPORT_EN, "audit_trail": [], "language": "xx"})
assert_(r3.status_code == 422, "Invalid language rejected with 422 at the API layer too")

r4 = client.post("/export/pdf", json={"final_report": SAMPLE_REPORT_EN, "audit_trail": []})
assert_(r4.status_code == 200 and "x-pdf-warnings" not in r4.headers,
        "Omitting language entirely (pre-Sprint-4 callers) still works with no warnings")


print("\nALL VALIDATIONS PASSED")
