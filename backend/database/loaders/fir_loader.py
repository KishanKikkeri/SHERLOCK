"""
SHERLOCK — Stage A, Phase A3: FIR loader.

Expected CSV columns: fir_number, crime_id, status, investigating_officer_badge, filed_date
`crime_id` must reference an already-loaded Crime row (load crimes first).
`investigating_officer_badge` is optional — resolved to an Officer via
badge_number lookup (so the source CSV doesn't need to know internal officer
IDs, only badge numbers, which is what real police paperwork would have).
"""

from __future__ import annotations
from datetime import datetime

from sqlalchemy.orm import Session

from backend.database.models import FIR, Officer, FIRStatus
from backend.database.loaders.csv_loader import read_csv_rows, coerce_int, LoadResult


def load_firs(session: Session, csv_path: str, commit: bool = True) -> LoadResult:
    result = LoadResult()
    rows = read_csv_rows(csv_path)

    for i, row in enumerate(rows, start=2):
        try:
            existing = session.query(FIR).filter_by(fir_number=row["fir_number"]).first()
            if existing:
                result.skipped += 1
                continue

            officer_id = None
            badge = row.get("investigating_officer_badge")
            if badge:
                officer = session.query(Officer).filter_by(badge_number=badge).first()
                if officer is None:
                    result.errors.append(f"row {i}: no officer with badge_number={badge!r}")
                    continue
                officer_id = officer.id

            fir = FIR(
                fir_number=row["fir_number"],
                crime_id=coerce_int(row["crime_id"]),
                status=FIRStatus(row.get("status") or "open"),
                investigating_officer_id=officer_id,
                filed_date=datetime.fromisoformat(row["filed_date"]) if row.get("filed_date") else datetime.utcnow(),
            )
            session.add(fir)
            result.inserted += 1
        except (KeyError, ValueError) as e:
            result.errors.append(f"row {i}: {e}")

    if commit:
        session.commit()
    return result
