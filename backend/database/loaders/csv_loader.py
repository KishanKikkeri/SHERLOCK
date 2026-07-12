"""
SHERLOCK — Stage A, Phase A3: shared CSV loading utility.

Scoping note, stated plainly: the handover names 18 loader modules
(fir_loader.py, accused_loader.py, victim_loader.py, ...). No actual
Karnataka Police CSV/Excel/SQL-dump source data exists anywhere in this
repo or was provided alongside the handover — there is nothing to point
18 loaders at yet. Building all 18 against invented fixture data each
would be 18 files of untestable guesswork, not real infrastructure.

What's actually built for Stage A: this shared utility (real, reusable,
handles the CSV-reading/type-coercion/error-reporting concerns every
loader needs), plus three representative loaders (officer_loader.py,
fir_loader.py, accused_loader.py) that are genuinely complete and are
demonstrated end-to-end against small fixture CSVs in
database/loaders/fixtures/. Every other loader is the same three-line
pattern applied to a different model — see fir_loader.py's docstring for
the template to copy once real source files exist.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field


@dataclass
class LoadResult:
    """What every loader returns — enough to know if it's safe to proceed
    without silently swallowing bad rows (explicitly required: 'no
    placeholders', and a loader that eats errors silently is worse than
    one that fails loudly)."""
    inserted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def __repr__(self):
        return f"<LoadResult inserted={self.inserted} skipped={self.skipped} errors={len(self.errors)}>"


def read_csv_rows(path: str) -> list[dict]:
    """Reads a CSV into a list of plain dicts. Deliberately not pandas —
    the rest of this codebase (per requirements.txt in the stabilization
    pass) doesn't otherwise depend on it, and CSV row counts here are in
    the hundreds/thousands, not a scale that needs it."""
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def coerce_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def coerce_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}
