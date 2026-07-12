"""
SHERLOCK — Stage A, Phase A3: Officer loader.

Expected CSV columns: name, badge_number, rank, posting_station, contact_number
`rank` must match one of the OfficerRank enum values (see models/enums.py).

Per Phase A3: "The loader must not depend on agents." This one only
depends on the DatabaseService/models layer, confirmed by the absence of
any `backend.agents` import above.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.database.models import Officer, OfficerRank
from backend.database.loaders.csv_loader import read_csv_rows, LoadResult


def load_officers(session: Session, csv_path: str, commit: bool = True) -> LoadResult:
    result = LoadResult()
    rows = read_csv_rows(csv_path)

    for i, row in enumerate(rows, start=2):  # start=2: row 1 is the header
        try:
            existing = session.query(Officer).filter_by(badge_number=row["badge_number"]).first()
            if existing:
                result.skipped += 1
                continue

            officer = Officer(
                name=row["name"],
                badge_number=row["badge_number"],
                rank=OfficerRank(row["rank"]),
                posting_station=row.get("posting_station") or None,
                contact_number=row.get("contact_number") or None,
            )
            session.add(officer)
            result.inserted += 1
        except (KeyError, ValueError) as e:
            result.errors.append(f"row {i}: {e}")

    if commit:
        session.commit()
    return result
