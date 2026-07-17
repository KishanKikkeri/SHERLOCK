"""
SHERLOCK — Sprint D1: Domain glossary.

Police/legal terminology must not be translated literally — some terms
stay exactly as-is even inside Kannada output (e.g. "FIR" is used
verbatim in Kannada police speech and writing), others have a specific
approved Kannada equivalent that isn't necessarily what a generic MT
engine would produce on its own.

Two policies per glossary entry:

  "protect"  — never translate this term; it appears unchanged in
               output regardless of target language (e.g. FIR, IPC,
               Chargesheet-as-a-filing-name-in-some-contexts).
  "approved" — always use the exact Kannada string given here, not
               whatever the translation engine would otherwise choose.

The glossary is data, not code — `glossary_data.json` next to this file
is the configurable part the handover asks for. This module just loads
it and gives `TranslationService` a way to (a) tell the engine what to
protect and (b) verify afterward that protected/approved terms actually
survived translation.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

_DATA_PATH = os.path.join(os.path.dirname(__file__), "glossary_data.json")


@dataclass
class GlossaryEntry:
    term: str            # canonical English term
    policy: str           # "protect" | "approved"
    kn: str | None = None  # required when policy == "approved"; the exact Kannada string to use
    notes: str | None = None


def _load_default_glossary() -> dict:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class GlossaryService:
    """
    Loads and looks up the protected police-terminology glossary.

    Configurable per the handover: pass a custom `path` (or a raw
    `entries` dict) to override the shipped defaults — e.g. per-district
    terminology variants — without touching this code.
    """

    def __init__(self, path: str | None = None, entries: dict | None = None):
        if entries is not None:
            raw = entries
        else:
            raw = _load_default_glossary() if path is None else self._load(path)

        self._entries: dict[str, GlossaryEntry] = {}
        # Reverse index: approved Kannada string -> canonical English term,
        # so KN->EN translation can protect the same terms in the other direction.
        self._kn_index: dict[str, str] = {}

        for term, spec in raw.items():
            entry = GlossaryEntry(
                term=term,
                policy=spec.get("policy", "protect"),
                kn=spec.get("kn"),
                notes=spec.get("notes"),
            )
            self._entries[term.lower()] = entry
            if entry.policy == "approved" and entry.kn:
                self._kn_index[entry.kn] = term

    @staticmethod
    def _load(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def all_entries(self) -> list[GlossaryEntry]:
        return list(self._entries.values())

    def lookup_english(self, term: str) -> GlossaryEntry | None:
        return self._entries.get(term.lower())

    def lookup_kannada(self, kn_term: str) -> str | None:
        """Returns the canonical English term for an approved Kannada string, if any."""
        return self._kn_index.get(kn_term)

    def terms_present_in(self, text: str) -> list[GlossaryEntry]:
        """Which glossary entries appear (case-insensitive, whole-word-ish) in `text`."""
        lowered = text.lower()
        found = []
        for entry in self._entries.values():
            if entry.term.lower() in lowered:
                found.append(entry)
        return found

    def kn_terms_present_in(self, text: str) -> list[str]:
        return [term for kn, term in self._kn_index.items() if kn in text]

    def build_prompt_directive(self) -> str:
        """
        Renders the glossary as instructions for an LLM-based translation
        call. Kept as one directive block rather than one instruction per
        term so it reads naturally to the model instead of as a wall of
        rules — but every entry is still represented explicitly, nothing
        is summarized away.
        """
        protect = [e.term for e in self._entries.values() if e.policy == "protect"]
        approved = [(e.term, e.kn) for e in self._entries.values() if e.policy == "approved" and e.kn]

        lines = []
        if protect:
            lines.append(
                "Keep these terms EXACTLY as written, in their original English form, "
                "even when the surrounding sentence is translated: " + ", ".join(protect) + "."
            )
        if approved:
            pairs = "; ".join(f'"{en}" -> "{kn}"' for en, kn in approved)
            lines.append(
                "For these terms, always use the exact approved translation given, "
                "not a literal or alternate translation: " + pairs + "."
            )
        return "\n".join(lines)


# Module-level default instance + raw dict, for callers that just want
# "the glossary" without constructing their own GlossaryService.
GLOSSARY = GlossaryService()
