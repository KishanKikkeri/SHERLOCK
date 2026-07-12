"""
SHERLOCK — Stage A, Phase A3: Accused loader.

Expected CSV columns: person_id, fir_id, raw_name_used, repeat_offender

This loader is the one worth reading closely if you're writing
victim_loader.py / witness_loader.py next — they're the identical pattern
against Victim/Witness instead of Accused. It's also the loader that
exercises the Phase A7 compatibility sync (see models/compat.py):
inserting an Accused row here automatically creates the matching legacy
PersonCrimeLink row, with zero extra code required in this file.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.database.models import Accused
from backend.database.loaders.csv_loader import read_csv_rows, coerce_int, coerce_bool, LoadResult


def load_accused(session: Session, csv_path: str, commit: bool = True) -> LoadResult:
    result = LoadResult()
    rows = read_csv_rows(csv_path)

    for i, row in enumerate(rows, start=2):
        try:
            accused = Accused(
                person_id=coerce_int(row["person_id"]),
                fir_id=coerce_int(row["fir_id"]),
                raw_name_used=row["raw_name_used"],
                repeat_offender=coerce_bool(row.get("repeat_offender")),
            )
            session.add(accused)
            session.flush()  # triggers the after_insert compat sync immediately, so
                              # errors surface per-row instead of at the final commit
            result.inserted += 1
        except (KeyError, ValueError) as e:
            result.errors.append(f"row {i}: {e}")
            session.rollback()

    if commit:
        session.commit()
    return result
