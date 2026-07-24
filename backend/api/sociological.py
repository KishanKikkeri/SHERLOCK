"""
SHERLOCK — Sociological Crime Insights API (Agent 2 workstream).

    GET /analytics/sociological           Platform-wide dashboard payload
    GET /analytics/sociological/report    Structured report (Executive
                                           Summary -> Key Findings -> Risk
                                           Factors -> Evidence ->
                                           Recommendations -> Confidence ->
                                           Supporting Data)

Read-only, and deliberately NOT session-scoped (unlike
backend/api/board.py) — this is a department-wide statistical view
across every accused/victim person currently on record, not one
investigation's own findings. See
backend/intelligence/sociological_insights.py for what each field is
(and, honestly, isn't yet) backed by.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.database.config import SessionLocal
from backend.database.models import AuditAction
from backend.intelligence.sociological_insights import SociologicalInsightsService
from backend.security import audit as security_audit
from backend.security.permissions import VIEW_CASE, RequirePermission

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analytics/sociological", tags=["sociological-insights"])


@router.get("")
def get_sociological_dashboard(ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        result = SociologicalInsightsService(session).build_dashboard()
        security_audit.record(
            session, AuditAction.EVIDENCE_VIEWED,
            user_id=ctx.user_id, username=ctx.username, target="analytics:sociological", success=True,
        )
        return result
    except Exception:
        logger.exception("GET /analytics/sociological failed")
        raise HTTPException(status_code=500, detail="Failed to build sociological insights dashboard.")
    finally:
        session.close()


@router.get("/report")
def get_sociological_report(ctx=Depends(RequirePermission(VIEW_CASE))):
    session = SessionLocal()
    try:
        result = SociologicalInsightsService(session).build_report()
        security_audit.record(
            session, AuditAction.REPORT_GENERATED,
            user_id=ctx.user_id, username=ctx.username, target="analytics:sociological:report", success=True,
        )
        return result
    except Exception:
        logger.exception("GET /analytics/sociological/report failed")
        raise HTTPException(status_code=500, detail="Failed to build sociological report.")
    finally:
        session.close()
