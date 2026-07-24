"""
SHERLOCK — Stage G1: Offender Profiling API.

New router, mounted additively in app/main.py. Reads only — nothing here
writes to the database. All scoring happens in `backend/intelligence/`;
this file is request handling + pagination/filtering only.

Endpoints:
    GET  /persons/{id}/profile        Full offender dossier (Requirement 5)
    GET  /persons/high-risk           Persons at or above a risk threshold
    POST /persons/profile/search      Filtered profile summaries
    GET  /persons/{id}/timeline       Chronological case-role history
    GET  /persons/{id}/network        Network profile + link to the graph view
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.database.config import SessionLocal
from backend.database.models import Accused, Person, Victim, Witness, Arrest, ChargeSheet
from backend.graph.service import get_graph_service
from backend.intelligence.offender_profiler import PersonNotFoundError, build_offender_profile
from backend.security.permissions import RequirePermission, VIEW_CASE

logger = logging.getLogger(__name__)
router = APIRouter(tags=["offender-profiling"])

MAX_BULK_PROFILES = 60  # bounds /persons/high-risk and /persons/profile/search — demo-dataset scale


# ---------------------------------------------------------------------------
# GET /persons/{id}/profile
# ---------------------------------------------------------------------------

@router.get("/persons/{person_id}/profile")
def get_offender_profile(person_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    db = SessionLocal()
    try:
        return build_offender_profile(db, person_id)
    except PersonNotFoundError:
        raise HTTPException(status_code=404, detail=f"No person with id={person_id}")
    except Exception:
        logger.exception("GET /persons/%s/profile failed", person_id)
        raise HTTPException(status_code=500, detail="Failed to build offender profile.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /persons/high-risk
# ---------------------------------------------------------------------------

@router.get("/persons/high-risk")
def list_high_risk_persons(min_risk: int = 61, limit: int = 20, _ctx=Depends(RequirePermission(VIEW_CASE))):
    if not (0 <= min_risk <= 100):
        raise HTTPException(status_code=422, detail="min_risk must be between 0 and 100.")
    if not (1 <= limit <= MAX_BULK_PROFILES):
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_BULK_PROFILES}.")

    db = SessionLocal()
    try:
        results = _profile_summaries(db, limit_candidates=MAX_BULK_PROFILES)
        matching = [r for r in results if r["risk_score"] >= min_risk]
        matching.sort(key=lambda r: r["risk_score"], reverse=True)
        return {"min_risk": min_risk, "count": len(matching[:limit]), "persons": matching[:limit]}
    except Exception:
        logger.exception("GET /persons/high-risk failed")
        raise HTTPException(status_code=500, detail="Failed to compute high-risk persons.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /persons/profile/search
# ---------------------------------------------------------------------------

class ProfileSearchRequest(BaseModel):
    name_contains: str | None = None
    min_risk: int | None = None
    crime_type: str | None = None
    district: str | None = None
    limit: int = 20


@router.post("/persons/profile/search")
def search_profiles(payload: ProfileSearchRequest, _ctx=Depends(RequirePermission(VIEW_CASE))):
    if not (1 <= payload.limit <= MAX_BULK_PROFILES):
        raise HTTPException(status_code=422, detail=f"limit must be between 1 and {MAX_BULK_PROFILES}.")

    db = SessionLocal()
    try:
        candidates = _profile_summaries(db, limit_candidates=MAX_BULK_PROFILES)

        def matches(r: dict) -> bool:
            if payload.name_contains and payload.name_contains.lower() not in r["name"].lower():
                return False
            if payload.min_risk is not None and r["risk_score"] < payload.min_risk:
                return False
            if payload.crime_type and payload.crime_type not in r["crime_categories"]:
                return False
            if payload.district and payload.district not in r["districts_operated"]:
                return False
            return True

        matching = [r for r in candidates if matches(r)]
        matching.sort(key=lambda r: r["risk_score"], reverse=True)
        return {"count": len(matching[:payload.limit]), "persons": matching[:payload.limit]}
    except Exception:
        logger.exception("POST /persons/profile/search failed")
        raise HTTPException(status_code=500, detail="Profile search failed.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /persons/{id}/timeline
# ---------------------------------------------------------------------------

@router.get("/persons/{person_id}/timeline")
def get_person_timeline(person_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    db = SessionLocal()
    try:
        person = db.get(Person, person_id)
        if person is None:
            raise HTTPException(status_code=404, detail=f"No person with id={person_id}")

        events = []
        for a in db.query(Accused).filter_by(person_id=person_id).all():
            if a.fir and a.fir.crime:
                events.append({"date": a.fir.crime.timestamp.isoformat(), "type": "accused",
                                "label": f"Accused in {a.fir.crime.type.value} (FIR {a.fir.fir_number})",
                                "fir_id": a.fir_id})
        for v in db.query(Victim).filter_by(person_id=person_id).all():
            if v.fir and v.fir.crime:
                events.append({"date": v.fir.crime.timestamp.isoformat(), "type": "victim",
                                "label": f"Victim in {v.fir.crime.type.value} (FIR {v.fir.fir_number})",
                                "fir_id": v.fir_id})
        for w in db.query(Witness).filter_by(person_id=person_id).all():
            if w.fir and w.fir.crime:
                events.append({"date": w.fir.crime.timestamp.isoformat(), "type": "witness",
                                "label": f"Witness in {w.fir.crime.type.value} (FIR {w.fir.fir_number})",
                                "fir_id": w.fir_id})
        for ar in db.query(Arrest).filter_by(person_id=person_id).all():
            events.append({"date": ar.arrest_date.isoformat(), "type": "arrest",
                            "label": f"Arrested ({ar.status.value})", "fir_id": ar.fir_id})
        for a in db.query(Accused).filter_by(person_id=person_id).all():
            for cs in db.query(ChargeSheet).filter_by(fir_id=a.fir_id).all():
                events.append({"date": cs.filed_date.isoformat(), "type": "chargesheet",
                                "label": f"Chargesheet {cs.status.value}", "fir_id": cs.fir_id})

        events.sort(key=lambda e: e["date"])
        return {"person_id": person_id, "name": person.name, "event_count": len(events), "events": events}
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /persons/%s/timeline failed", person_id)
        raise HTTPException(status_code=500, detail="Failed to build timeline.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /persons/{id}/network
# ---------------------------------------------------------------------------

@router.get("/persons/{person_id}/network")
def get_person_network(person_id: int, _ctx=Depends(RequirePermission(VIEW_CASE))):
    """Analytical network summary (associates, orgs, financial links,
    centrality). For the visual force-directed graph itself, the
    frontend reuses the existing `GET /graph/{person_id}` endpoint and
    `GraphView` component (see frontend/src/offender/NetworkSummary.tsx)
    — this endpoint deliberately does not duplicate that."""
    db = SessionLocal()
    try:
        person = db.get(Person, person_id)
        if person is None:
            raise HTTPException(status_code=404, detail=f"No person with id={person_id}")
        graph_service = get_graph_service(backend="networkx", session=db)
        from backend.intelligence import network_profile
        return {
            "person_id": person_id,
            "name": person.name,
            **network_profile.compute_network_profile(db, person_id, graph_service),
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("GET /persons/%s/network failed", person_id)
        raise HTTPException(status_code=500, detail="Failed to build network profile.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Shared helper — lightweight profile summaries for bulk endpoints
# ---------------------------------------------------------------------------

def _profile_summaries(db, limit_candidates: int) -> list[dict]:
    """Builds full profiles (needed for an accurate risk score) for every
    person with at least one Accused record, capped at
    `limit_candidates` — bounded for this demo-scale dataset (see
    MAX_BULK_PROFILES). Builds ONE graph_service and reuses it across
    every profile in the loop rather than rebuilding the in-memory graph
    once per person."""
    from sqlalchemy import func

    person_ids = [
        r[0] for r in
        db.query(Accused.person_id).group_by(Accused.person_id).limit(limit_candidates).all()
    ]
    if not person_ids:
        return []

    graph_service = get_graph_service(backend="networkx", session=db)
    summaries = []
    for pid in person_ids:
        try:
            profile = build_offender_profile(db, pid, graph_service=graph_service)
        except PersonNotFoundError:
            continue
        summaries.append({
            "person_id": pid,
            "name": profile["identity"]["name"],
            "risk_score": profile["risk_profile"]["overall_score"],
            "risk_band": profile["risk_profile"]["band"],
            "priority": profile["investigation_priority"]["priority"],
            "fir_count": profile["criminal_history"]["fir_count"],
            "crime_categories": list(profile["criminal_history"]["crime_categories"].keys()),
            "districts_operated": profile["behavior_profile"]["mobility"]["districts_operated"],
        })
    return summaries
