"""
SHERLOCK — Crime Pattern & Trend Analytics API.

    GET /analytics/dashboard
    GET /analytics/hotspot/{location_name}

Read-only. `/dashboard` returns the full `summary_engine.generate_dashboard_summary()`
payload (KPI cards, executive summary, chart data, tables, insights,
MO enrichment, recommendations) — this is what replaces raw agent
findings on the Analytics page. `/hotspot/{location_name}` is the
drill-down for a single hotspot (crime-type breakdown + monthly
timeline) — see backend/analytics/summary_engine.py and
hotspot_engine.py for the payload shapes.

Scope note: this is deliberately global, not session-scoped. `Crime`
rows have no `session_id` / investigation-session linkage in the
schema — investigation "sessions" are a workspace grouping over FIRs,
not a partition of the crime dataset itself — so unlike
`/sessions/{id}/board`, there's no `session_id` filter to apply here.
`crime_type` / `district` / `granularity` / victim `gender` and
`age_min`/`age_max` are the filters available given the current
schema — there's no stored "risk band" field anywhere to filter by
(that's a Behavioral Intelligence agent output, not a persisted
column), so it isn't offered as a filter here.

Permission note: reuses VIEW_CASE (the broadest existing read
permission) since there's no dedicated analytics permission in
`backend/security/permissions.py` yet. `/metrics` (the other
dashboard-adjacent endpoint, in `backend/app/main.py`) has no
permission check at all, so this route is actually the stricter of
the two, not the looser one. Add an ANALYTICS-specific permission
constant if that's ever worth separating from VIEW_CASE.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database.config import SessionLocal
from backend.security.permissions import RequirePermission, VIEW_CASE
from backend.analytics.summary_engine import generate_dashboard_summary
from backend.analytics.hotspot_engine import location_breakdown

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics", tags=["analytics"])

VALID_GRANULARITIES = {"day", "week", "month", "quarter", "year"}
VALID_GENDERS = {"male", "female", "other"}


@router.get("/dashboard")
def get_analytics_dashboard(
    crime_type: str | None = Query(default=None),
    district: str | None = Query(default=None),
    granularity: str = Query(default="month"),
    victim_gender: str | None = Query(default=None),
    victim_age_min: int | None = Query(default=None, ge=0),
    victim_age_max: int | None = Query(default=None, ge=0),
    ctx=Depends(RequirePermission(VIEW_CASE)),
):
    if granularity not in VALID_GRANULARITIES:
        raise HTTPException(status_code=400, detail=f"granularity must be one of {sorted(VALID_GRANULARITIES)}")
    if victim_gender and victim_gender not in VALID_GENDERS:
        raise HTTPException(status_code=400, detail=f"victim_gender must be one of {sorted(VALID_GENDERS)}")

    session = SessionLocal()
    try:
        return generate_dashboard_summary(
            session, crime_type=crime_type, district=district, granularity=granularity,
            victim_gender=victim_gender, victim_age_min=victim_age_min, victim_age_max=victim_age_max,
        )
    except Exception:
        logger.exception("GET /analytics/dashboard failed")
        raise HTTPException(status_code=500, detail="Failed to build analytics dashboard.")
    finally:
        session.close()


@router.get("/hotspot/{location_name}")
def get_hotspot_breakdown(location_name: str, ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        result = location_breakdown(session, location_name)
        if result is None:
            raise HTTPException(status_code=404, detail=f"No location named '{location_name}'.")
        return result
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /analytics/hotspot/%s failed", location_name)
        raise HTTPException(status_code=500, detail="Failed to build hotspot breakdown.")
    finally:
        session.close()
