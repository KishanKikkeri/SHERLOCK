"""
SHERLOCK — Forecasting & Early Warning API (Requirement 8).

    GET /forecast/dashboard       generate_forecast_dashboard() — everything composed
    GET /forecast/hotspots        HotspotForecaster.predict_hotspots()
    GET /forecast/trends          TrendForecaster (overall + by type + by district)
    GET /forecast/repeat-alerts   RepeatAlertEngine.generate_alerts()
    GET /forecast/gang-alerts     GangAlertEngine.get_gang_alerts()
    GET /forecast/risk            RiskForecaster.generate_all()
    GET /forecast/summary         alias of /forecast/dashboard (name from the brief)

Read-only, platform-wide (not session-scoped) — same shape as
GET /analytics/sociological. Deterministic: no LLM call anywhere in this
package, per Requirement 8's explicit "do not use LLMs" constraint.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.database.config import SessionLocal
from backend.database.models import AuditAction
from backend.forecasting.gang_alert_engine import GangAlertEngine
from backend.forecasting.hotspot_forecaster import HotspotForecaster
from backend.forecasting.repeat_alert_engine import RepeatAlertEngine
from backend.forecasting.risk_forecaster import RiskForecaster
from backend.forecasting.summary_engine import generate_forecast_dashboard
from backend.forecasting.trend_forecaster import TrendForecaster
from backend.security import audit as security_audit
from backend.security.permissions import VIEW_CASE, RequirePermission

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/forecast", tags=["forecasting"])


def _with_session(build):
    session = SessionLocal()
    try:
        return build(session)
    finally:
        session.close()


@router.get("/dashboard")
def get_forecast_dashboard(ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        result = generate_forecast_dashboard(session)
        security_audit.record(
            session, AuditAction.REPORT_GENERATED,
            user_id=ctx.user_id, username=ctx.username, target="forecast:dashboard", success=True,
        )
        return result
    except Exception:
        logger.exception("GET /forecast/dashboard failed")
        raise HTTPException(status_code=500, detail="Failed to build forecast dashboard.")
    finally:
        session.close()


@router.get("/summary")
def get_forecast_summary(ctx=Depends(RequirePermission(VIEW_CASE))):
    return get_forecast_dashboard(ctx)


@router.get("/hotspots")
def get_forecast_hotspots(top_n: int = 10, ctx=Depends(RequirePermission(VIEW_CASE))):
    try:
        return _with_session(lambda s: HotspotForecaster(s).predict_hotspots(top_n=top_n))
    except Exception:
        logger.exception("GET /forecast/hotspots failed")
        raise HTTPException(status_code=500, detail="Failed to build hotspot forecast.")


@router.get("/trends")
def get_forecast_trends(method: str = "weighted_moving_average", window: int = 6, ctx=Depends(RequirePermission(VIEW_CASE))):
    try:
        def build(session):
            t = TrendForecaster(session)
            return {
                "overall": t.forecast_crime_volume(method=method, window=window),
                "by_crime_type": t.forecast_by_type(method=method, window=window),
                "by_district": t.forecast_by_district(method=method, window=window),
            }
        return _with_session(build)
    except Exception:
        logger.exception("GET /forecast/trends failed")
        raise HTTPException(status_code=500, detail="Failed to build trend forecast.")


@router.get("/repeat-alerts")
def get_forecast_repeat_alerts(window_days: int = 28, ctx=Depends(RequirePermission(VIEW_CASE))):
    try:
        return _with_session(lambda s: RepeatAlertEngine(s).generate_alerts(window_days=window_days))
    except Exception:
        logger.exception("GET /forecast/repeat-alerts failed")
        raise HTTPException(status_code=500, detail="Failed to build repeat alerts.")


@router.get("/gang-alerts")
def get_forecast_gang_alerts(min_size: int = 3, ctx=Depends(RequirePermission(VIEW_CASE))):
    try:
        return _with_session(lambda s: GangAlertEngine(s).get_gang_alerts(min_size=min_size))
    except Exception:
        logger.exception("GET /forecast/gang-alerts failed")
        raise HTTPException(status_code=500, detail="Failed to build gang activity alerts.")


@router.get("/risk")
def get_forecast_risk(ctx=Depends(RequirePermission(VIEW_CASE))):
    try:
        return _with_session(lambda s: RiskForecaster(s).generate_all())
    except Exception:
        logger.exception("GET /forecast/risk failed")
        raise HTTPException(status_code=500, detail="Failed to build risk forecast.")
