"""
SHERLOCK — Sprint D1: Language detection.

Per the handover: detection must not depend only on an explicit
`language` parameter — callers (voice, WebSocket, REST) may omit it, or
may pass a stale/incorrect value, so every text that flows through the
translation layer gets independently detected.

Approach: Unicode-script counting. Kannada text lives entirely in the
Kannada Unicode block (U+0C80-U+0CFF); English/Latin text is ASCII
letters. This needs no model, no network call, and no API key, which
matters because detection has to run on every single query/message —
unlike translation itself, it can't degrade to "unavailable" without
breaking the one thing (routing en vs kn) that everything else depends
on. Good enough for two languages; extending to a third script-distinct
language (e.g. Tamil, Telugu — Sprint D6) is a one-line addition to
SCRIPT_RANGES. Hindi (Devanagari) is also script-distinct and would slot
in the same way; script-sharing language pairs (e.g. Hindi/Marathi, both
Devanagari) would need a real language-ID model instead — noted as a
limitation, not solved here.
"""

from dataclasses import dataclass, field

# (start, end) inclusive Unicode codepoint ranges, keyed by our language code.
SCRIPT_RANGES = {
    "kn": [(0x0C80, 0x0CFF)],   # Kannada
    "en": [(0x0041, 0x005A), (0x0061, 0x007A)],  # A-Z, a-z
}


@dataclass
class LanguageDetectionResult:
    language: str                      # "en" | "kn" | "mixed" | "unknown"
    confidence: float                  # 0.0 - 1.0
    script_counts: dict = field(default_factory=dict)   # {"en": n, "kn": n, "other": n}


def _script_of(ch: str) -> str | None:
    cp = ord(ch)
    for lang, ranges in SCRIPT_RANGES.items():
        for lo, hi in ranges:
            if lo <= cp <= hi:
                return lang
    return None


def detect_language(text: str) -> LanguageDetectionResult:
    """
    Detects whether `text` is English, Kannada, a mix of both, or
    contains no script-identifiable characters at all (numbers-only
    queries, punctuation, empty string).

    "mixed" is a real, expected case for this domain — e.g. a Kannada
    query that names an English-script person name ("ರವಿ Kumar ಬಗ್ಗೆ
    ತಿಳಿಸಿ") — and callers should treat it as "kn" for routing purposes
    (translate the whole thing) rather than erroring. Kept as its own
    label rather than silently folded into "kn" so the confidence score
    stays honest about how mixed it actually was.
    """
    if not text or not text.strip():
        return LanguageDetectionResult(language="unknown", confidence=0.0, script_counts={})

    counts = {"en": 0, "kn": 0, "other": 0}
    for ch in text:
        if ch.isspace() or not ch.isalpha():
            continue
        script = _script_of(ch)
        if script is None:
            counts["other"] += 1
        else:
            counts[script] += 1

    total_alpha = counts["en"] + counts["kn"] + counts["other"]
    if total_alpha == 0:
        return LanguageDetectionResult(language="unknown", confidence=0.0, script_counts=counts)

    en_ratio = counts["en"] / total_alpha
    kn_ratio = counts["kn"] / total_alpha

    if kn_ratio >= 0.85:
        return LanguageDetectionResult(language="kn", confidence=round(kn_ratio, 3), script_counts=counts)
    if en_ratio >= 0.85:
        return LanguageDetectionResult(language="en", confidence=round(en_ratio, 3), script_counts=counts)
    if kn_ratio > 0 and en_ratio > 0:
        # Genuinely mixed script. Confidence reflects the dominant script's share.
        dominant_ratio = max(kn_ratio, en_ratio)
        return LanguageDetectionResult(language="mixed", confidence=round(dominant_ratio, 3), script_counts=counts)
    if kn_ratio > en_ratio:
        return LanguageDetectionResult(language="kn", confidence=round(kn_ratio, 3), script_counts=counts)
    return LanguageDetectionResult(language="en", confidence=round(en_ratio, 3), script_counts=counts)
