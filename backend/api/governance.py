"""
SHERLOCK — Stage E5: Governance API.

    GET  /governance/retention-policy   View the current retention windows
    POST /governance/retention/run      Run the archival sweep now (idempotent)

Both require `administer_system` (Administrator only). This is the one
new permission from Sprint E2's vocabulary that had nothing using it
yet — it fits exactly here rather than overloading `manage_users`.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.security.dependencies import get_db
from backend.security.permissions import RequirePermission, ADMINISTER_SYSTEM
from backend.security.retention import get_retention_policy, apply_retention_policy

router = APIRouter(prefix="/governance", tags=["governance"])


@router.get("/retention-policy")
def retention_policy(_ctx=Depends(RequirePermission(ADMINISTER_SYSTEM))):
    return get_retention_policy()


@router.post("/retention/run")
def run_retention_sweep(_ctx=Depends(RequirePermission(ADMINISTER_SYSTEM)), db: Session = Depends(get_db)):
    return apply_retention_policy(db)
