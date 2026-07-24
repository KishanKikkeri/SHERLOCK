"""
SHERLOCK — Stage G1: criminal history.

Pure SQL roll-up, no scoring or interpretation here — see
behavior_profiler.py / risk_engine.py for anything judgment-based. This
module answers only "what does the record literally say."

Thresholds for `repeat_offender` (>=2 FIRs as accused) and
`habitual_offender` (>=5) are judgment calls, not a cited legal/CCTNS
standard — `repeat_offender`'s threshold matches
`DatabaseService.get_repeat_offenders`'s existing `min_crimes=2` default
for consistency across the codebase; `habitual_offender` is new and
flagged here as an assumption, same as this codebase's existing pattern
of flagging unstated schema/threshold decisions instead of hiding them.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from backend.database.models import Accused, ArrestStatus, ChargeSheetStatus, FIRStatus

REPEAT_OFFENDER_THRESHOLD = 2
HABITUAL_OFFENDER_THRESHOLD = 5


def compute_criminal_history(session, person_id: int) -> dict:
    accused_records = (
        session.query(Accused)
        .filter_by(person_id=person_id)
        .all()
    )

    # Only records with a real FIR/crime attached are usable for
    # dates/categories/frequency — an Accused row can't exist without an
    # fir_id (NOT NULL FK), but guard anyway in case the FIR's own crime
    # relationship is somehow missing.
    with_case = [a for a in accused_records if a.fir and a.fir.crime]
    firs = [a.fir for a in with_case]
    crimes = [a.fir.crime for a in with_case]

    arrests = [a for fir in firs for a in fir.arrests]
    chargesheets = [cs for fir in firs for cs in fir.chargesheets]
    convictions = [f for f in firs if f.status == FIRStatus.CONVICTED]
    pending = [f for f in firs if f.status in (FIRStatus.OPEN, FIRStatus.UNDER_INVESTIGATION)]

    crime_categories = Counter(c.type.value for c in crimes)
    timestamps = sorted(c.timestamp for c in crimes)
    first_offence = timestamps[0] if timestamps else None
    last_offence = timestamps[-1] if timestamps else None

    if first_offence and last_offence and first_offence != last_offence:
        span_years = max((last_offence - first_offence).days / 365.25, 1 / 365.25)
        crime_frequency_per_year = round(len(crimes) / span_years, 2)
    else:
        # A single offence (or same-day repeats) has no meaningful "per
        # year" rate — reported as null rather than a divide-by-near-zero
        # number that would look alarmingly high for no real reason.
        crime_frequency_per_year = None

    fir_count = len(firs)

    return {
        "fir_count": fir_count,
        "arrest_count": len(arrests),
        "chargesheet_count": len(chargesheets),
        "chargesheets_filed": len([cs for cs in chargesheets if cs.status == ChargeSheetStatus.FILED]),
        "conviction_count": len(convictions),
        "pending_investigation_count": len(pending),
        "crime_categories": dict(crime_categories),
        "first_offence_date": first_offence.isoformat() if first_offence else None,
        "latest_offence_date": last_offence.isoformat() if last_offence else None,
        "days_since_last_offence": (
            (datetime.now(timezone.utc).replace(tzinfo=None) - last_offence).days if last_offence else None
        ),
        "crime_frequency_per_year": crime_frequency_per_year,
        "repeat_offender": fir_count >= REPEAT_OFFENDER_THRESHOLD,
        "habitual_offender": fir_count >= HABITUAL_OFFENDER_THRESHOLD,
        "custody_status": next((a.custody_status for a in with_case if a.custody_status), None),
        "on_bail_no_chargesheet": any(
            a.status == ArrestStatus.RELEASED_ON_BAIL for a in arrests
        ) and not chargesheets,
        # Kept for downstream modules (behavior_profiler, modus_profiler)
        # so they don't re-run the same join.
        "_firs": firs,
        "_crimes": crimes,
        "_accused_records": with_case,
    }
