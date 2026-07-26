"""
SHERLOCK — Conversation V2: Investigations V2 REST API.

Provides CRUD and workspace management for the new user-curated
InvestigationV2 workspaces. Includes:
  - Create/List/Get/Update/Soft-Delete investigations
  - Duplicate investigation workspace (copying selected entities)
  - Merge investigations (unioning selected entities)
  - Explicit entity selection (adding/removing FIRs, suspects, accounts, etc.)
"""

import json
import logging
from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.database.config import SessionLocal
from backend.database.models.investigation_v2 import InvestigationV2
from backend.database.models.enums import InvestigationV2Status
from backend.security.dependencies import AuthContext
from backend.security.permissions import RequirePermission, VIEW_CASE, MANAGE_CASE

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v2/investigations", tags=["investigations-v2"])


# ---------------------------------------------------------------------------
# Request/Response schemas
# ---------------------------------------------------------------------------

class CreateInvestigationRequest(BaseModel):
    title: str
    description: Optional[str] = None
    selected_firs: Optional[List[int]] = None
    selected_persons: Optional[List[int]] = None
    selected_accounts: Optional[List[int]] = None
    selected_locations: Optional[List[int]] = None
    selected_orgs: Optional[List[int]] = None


class UpdateInvestigationRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # "active" | "closed" | "archived"


class EntitySelectionRequest(BaseModel):
    kind: str  # "fir" | "person" | "account" | "location" | "org"
    ids: List[int]


def _serialize_investigation(row: InvestigationV2) -> dict:
    def safe_json_load(raw: str | None) -> list:
        if not raw:
            return []
        try:
            return json.loads(raw)
        except Exception:
            return []

    return {
        "id": row.id,
        "title": row.title,
        "description": row.description,
        "status": row.status.value,
        "created_by_officer_id": row.created_by_officer_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "selected_firs": safe_json_load(row.selected_fir_ids_json),
        "selected_persons": safe_json_load(row.selected_person_ids_json),
        "selected_accounts": safe_json_load(row.selected_account_ids_json),
        "selected_locations": safe_json_load(row.selected_location_ids_json),
        "selected_orgs": safe_json_load(row.selected_org_ids_json),
        "metadata": safe_json_load(row.metadata_json) if row.metadata_json else {},
    }


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@router.post("")
def create_investigation(
    payload: CreateInvestigationRequest,
    ctx: AuthContext = Depends(RequirePermission(MANAGE_CASE)),
):
    db = SessionLocal()
    try:
        inv = InvestigationV2(
            title=payload.title,
            description=payload.description,
            created_by_officer_id=ctx.officer_id,
            status=InvestigationV2Status.ACTIVE,
            selected_fir_ids_json=json.dumps(payload.selected_firs or []),
            selected_person_ids_json=json.dumps(payload.selected_persons or []),
            selected_account_ids_json=json.dumps(payload.selected_accounts or []),
            selected_location_ids_json=json.dumps(payload.selected_locations or []),
            selected_org_ids_json=json.dumps(payload.selected_orgs or []),
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return _serialize_investigation(inv)
    except Exception:
        db.rollback()
        logger.exception("Failed to create investigation")
        raise HTTPException(status_code=500, detail="Failed to create investigation.")
    finally:
        db.close()


@router.get("")
def list_investigations(
    status: Optional[str] = None,
    _ctx: AuthContext = Depends(RequirePermission(VIEW_CASE)),
):
    db = SessionLocal()
    try:
        query = db.query(InvestigationV2)
        if status and status.strip():
            clean_status = status.strip().lower()
            if clean_status != "all":
                try:
                    status_enum = InvestigationV2Status(clean_status)
                    query = query.filter(InvestigationV2.status == status_enum)
                except ValueError:
                    raise HTTPException(status_code=422, detail=f"Invalid status '{status}'.")
        else:
            # Exclude archived by default unless requested
            query = query.filter(InvestigationV2.status != InvestigationV2Status.ARCHIVED)

        rows = query.order_by(InvestigationV2.updated_at.desc()).all()
        return [_serialize_investigation(r) for r in rows]
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to list investigations")
        raise HTTPException(status_code=500, detail="Failed to list investigations.")
    finally:
        db.close()


@router.get("/{id}")
def get_investigation(
    id: int,
    _ctx: AuthContext = Depends(RequirePermission(VIEW_CASE)),
):
    db = SessionLocal()
    try:
        row = db.get(InvestigationV2, id)
        if not row:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        return _serialize_investigation(row)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to get investigation")
        raise HTTPException(status_code=500, detail="Failed to fetch investigation.")
    finally:
        db.close()


@router.patch("/{id}")
def update_investigation(
    id: int,
    payload: UpdateInvestigationRequest,
    _ctx: AuthContext = Depends(RequirePermission(MANAGE_CASE)),
):
    db = SessionLocal()
    try:
        row = db.get(InvestigationV2, id)
        if not row:
            raise HTTPException(status_code=404, detail="Investigation not found.")

        if payload.title is not None:
            row.title = payload.title
        if payload.description is not None:
            row.description = payload.description
        if payload.status is not None:
            try:
                status_enum = InvestigationV2Status(payload.status.lower())
                row.status = status_enum
                if status_enum == InvestigationV2Status.ARCHIVED:
                    row.archived_at = datetime.utcnow()
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Invalid status '{payload.status}'.")

        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _serialize_investigation(row)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to update investigation")
        raise HTTPException(status_code=500, detail="Failed to update investigation.")
    finally:
        db.close()


@router.delete("/{id}")
def delete_investigation(
    id: int,
    _ctx: AuthContext = Depends(RequirePermission(MANAGE_CASE)),
):
    """Soft-delete (archive) the investigation."""
    db = SessionLocal()
    try:
        row = db.get(InvestigationV2, id)
        if not row:
            raise HTTPException(status_code=404, detail="Investigation not found.")
        row.status = InvestigationV2Status.ARCHIVED
        row.archived_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        db.commit()
        return {"id": id, "status": "archived"}
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to delete investigation")
        raise HTTPException(status_code=500, detail="Failed to delete/archive investigation.")
    finally:
        db.close()


@router.post("/{id}/duplicate")
def duplicate_investigation(
    id: int,
    ctx: AuthContext = Depends(RequirePermission(MANAGE_CASE)),
):
    """Create a new copy of the investigation workspace with same entity selections."""
    db = SessionLocal()
    try:
        row = db.get(InvestigationV2, id)
        if not row:
            raise HTTPException(status_code=404, detail="Investigation not found.")

        copied = InvestigationV2(
            title=f"Copy of {row.title}",
            description=row.description,
            created_by_officer_id=ctx.officer_id,
            status=InvestigationV2Status.ACTIVE,
            selected_fir_ids_json=row.selected_fir_ids_json,
            selected_person_ids_json=row.selected_person_ids_json,
            selected_account_ids_json=row.selected_account_ids_json,
            selected_location_ids_json=row.selected_location_ids_json,
            selected_org_ids_json=row.selected_org_ids_json,
        )
        db.add(copied)
        db.commit()
        db.refresh(copied)
        return _serialize_investigation(copied)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to duplicate investigation")
        raise HTTPException(status_code=500, detail="Failed to duplicate investigation.")
    finally:
        db.close()


@router.post("/{id}/merge/{other_id}")
def merge_investigations(
    id: int,
    other_id: int,
    _ctx: AuthContext = Depends(RequirePermission(MANAGE_CASE)),
):
    """Merge another investigation's selected entities into this one (union of selections)."""
    db = SessionLocal()
    try:
        row = db.get(InvestigationV2, id)
        other = db.get(InvestigationV2, other_id)

        if not row or not other:
            raise HTTPException(status_code=404, detail="One or both investigations not found.")

        def merge_json_lists(raw1: str | None, raw2: str | None) -> str:
            list1 = json.loads(raw1) if raw1 else []
            list2 = json.loads(raw2) if raw2 else []
            union = sorted(list(set(list1 + list2)))
            return json.dumps(union)

        row.selected_fir_ids_json = merge_json_lists(row.selected_fir_ids_json, other.selected_fir_ids_json)
        row.selected_person_ids_json = merge_json_lists(row.selected_person_ids_json, other.selected_person_ids_json)
        row.selected_account_ids_json = merge_json_lists(row.selected_account_ids_json, other.selected_account_ids_json)
        row.selected_location_ids_json = merge_json_lists(row.selected_location_ids_json, other.selected_location_ids_json)
        row.selected_org_ids_json = merge_json_lists(row.selected_org_ids_json, other.selected_org_ids_json)

        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _serialize_investigation(row)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to merge investigations")
        raise HTTPException(status_code=500, detail="Failed to merge investigations.")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Entity Selection Endpoints
# ---------------------------------------------------------------------------

@router.post("/{id}/entities")
def add_entities(
    id: int,
    payload: EntitySelectionRequest,
    _ctx: AuthContext = Depends(RequirePermission(MANAGE_CASE)),
):
    """Add selected entities to the investigation workspace."""
    db = SessionLocal()
    try:
        row = db.get(InvestigationV2, id)
        if not row:
            raise HTTPException(status_code=404, detail="Investigation not found.")

        field_name = f"selected_{payload.kind}_ids_json"
        if payload.kind == "org":
            field_name = "selected_org_ids_json"

        if not hasattr(row, field_name):
            raise HTTPException(status_code=422, detail=f"Invalid entity kind '{payload.kind}'.")

        current_raw = getattr(row, field_name)
        current = json.loads(current_raw) if current_raw else []
        updated = sorted(list(set(current + payload.ids)))
        setattr(row, field_name, json.dumps(updated))

        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _serialize_investigation(row)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to add entities to investigation")
        raise HTTPException(status_code=500, detail="Failed to add entities.")
    finally:
        db.close()


@router.delete("/{id}/entities")
def remove_entities(
    id: int,
    payload: EntitySelectionRequest,
    _ctx: AuthContext = Depends(RequirePermission(MANAGE_CASE)),
):
    """Remove selected entities from the investigation workspace."""
    db = SessionLocal()
    try:
        row = db.get(InvestigationV2, id)
        if not row:
            raise HTTPException(status_code=404, detail="Investigation not found.")

        field_name = f"selected_{payload.kind}_ids_json"
        if payload.kind == "org":
            field_name = "selected_org_ids_json"

        if not hasattr(row, field_name):
            raise HTTPException(status_code=422, detail=f"Invalid entity kind '{payload.kind}'.")

        current_raw = getattr(row, field_name)
        current = json.loads(current_raw) if current_raw else []
        updated = [x for x in current if x not in payload.ids]
        setattr(row, field_name, json.dumps(updated))

        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return _serialize_investigation(row)
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        logger.exception("Failed to remove entities from investigation")
        raise HTTPException(status_code=500, detail="Failed to remove entities.")
    finally:
        db.close()
