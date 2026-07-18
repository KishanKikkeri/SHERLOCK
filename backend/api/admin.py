"""
SHERLOCK — Stage E2: User & role administration API.

Every route here requires MANAGE_USERS, which only the Administrator
role grants (see backend/security/permissions.py's ROLE_PERMISSIONS).
This is the "Administration" entry in the Sprint E2 brief's Secure
Routes list.

    POST   /admin/users                       Create a user (Administrator only)
    GET    /admin/users                        List users
    GET    /admin/users/{id}                   Get one user
    POST   /admin/users/{id}/roles             Grant a role
    DELETE /admin/users/{id}/roles/{role}      Revoke a role
    POST   /admin/users/{id}/deactivate        Soft-deactivate (no physical deletion)
    POST   /admin/users/{id}/reactivate        Reactivate
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.security.dependencies import get_db, AuthContext
from backend.security.permissions import RequirePermission, MANAGE_USERS
from backend.security.passwords import hash_password, WeakPasswordError
from backend.security.auth import get_user_role_names
from backend.security.schemas import CreateUserRequest, UserOut
from backend.database.models import User, Role, UserRole, SystemRole, AuditAction
from backend.security import audit as security_audit
from datetime import datetime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["administration"])


def _user_out(db: Session, user: User) -> UserOut:
    return UserOut(
        id=user.id, username=user.username, email=user.email, full_name=user.full_name,
        officer_id=user.officer_id, is_active=user.is_active,
        roles=get_user_role_names(db, user),
    )


@router.post("/users", response_model=UserOut)
def create_user(body: CreateUserRequest, ctx: AuthContext = Depends(RequirePermission(MANAGE_USERS)),
                 db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first() is not None:
        raise HTTPException(status_code=409, detail="Username already exists.")

    try:
        password_hash = hash_password(body.password)
    except WeakPasswordError as e:
        raise HTTPException(status_code=422, detail=str(e))

    user = User(
        username=body.username, email=body.email, full_name=body.full_name,
        officer_id=body.officer_id, password_hash=password_hash,
    )
    db.add(user)
    db.flush()

    for role_name in body.roles:
        try:
            role_enum = SystemRole(role_name)
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Unknown role: {role_name!r}")
        role = db.query(Role).filter(Role.name == role_enum).first()
        if role is None:
            raise HTTPException(status_code=422, detail=f"Role {role_name!r} isn't seeded yet.")
        granted_by_id = ctx.user_id if not ctx.is_system else None
        db.add(UserRole(user_id=user.id, role_id=role.id, granted_by_user_id=granted_by_id))

    db.commit()
    logger.info("User %r created by %r with roles %r", user.username, ctx.username, body.roles)
    return _user_out(db, user)


@router.get("/users", response_model=list[UserOut])
def list_users(_ctx: AuthContext = Depends(RequirePermission(MANAGE_USERS)), db: Session = Depends(get_db)):
    return [_user_out(db, u) for u in db.query(User).order_by(User.id).all()]


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int, _ctx: AuthContext = Depends(RequirePermission(MANAGE_USERS)),
             db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return _user_out(db, user)


@router.post("/users/{user_id}/roles", response_model=UserOut)
def grant_role(user_id: int, role: str, ctx: AuthContext = Depends(RequirePermission(MANAGE_USERS)),
               db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    try:
        role_enum = SystemRole(role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown role: {role!r}")

    role_row = db.query(Role).filter(Role.name == role_enum).first()
    if role_row is None:
        raise HTTPException(status_code=422, detail=f"Role {role!r} isn't seeded yet.")

    existing = db.query(UserRole).filter(UserRole.user_id == user_id, UserRole.role_id == role_row.id).first()
    if existing is None:
        granted_by_id = ctx.user_id if not ctx.is_system else None
        db.add(UserRole(user_id=user_id, role_id=role_row.id, granted_by_user_id=granted_by_id))
        db.commit()
        logger.info("Role %r granted to user %r by %r", role, user.username, ctx.username)
        security_audit.record(
            db, AuditAction.ROLE_CHANGED, user_id=ctx.user_id, username=ctx.username,
            target=f"user:{user_id}", success=True, metadata={"granted_role": role},
        )

    return _user_out(db, user)


@router.delete("/users/{user_id}/roles/{role}", response_model=UserOut)
def revoke_role(user_id: int, role: str, ctx: AuthContext = Depends(RequirePermission(MANAGE_USERS)),
                db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    try:
        role_enum = SystemRole(role)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown role: {role!r}")

    role_row = db.query(Role).filter(Role.name == role_enum).first()
    if role_row is not None:
        ur = db.query(UserRole).filter(UserRole.user_id == user_id, UserRole.role_id == role_row.id).first()
        if ur is not None:
            db.delete(ur)
            db.commit()
            logger.info("Role %r revoked from user %r by %r", role, user.username, ctx.username)
            security_audit.record(
                db, AuditAction.ROLE_CHANGED, user_id=ctx.user_id, username=ctx.username,
                target=f"user:{user_id}", success=True, metadata={"revoked_role": role},
            )

    return _user_out(db, user)


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, _ctx: AuthContext = Depends(RequirePermission(MANAGE_USERS)),
                     db: Session = Depends(get_db)):
    """Soft-deactivate only — no physical deletion, per Stage E5's
    governance requirement, implemented here already since deactivation
    is naturally the same operation as retention's 'archive, don't
    delete' rule applied to a User row."""
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = False
    user.deactivated_at = datetime.utcnow()
    db.add(user)
    db.commit()
    return _user_out(db, user)


@router.post("/users/{user_id}/reactivate", response_model=UserOut)
def reactivate_user(user_id: int, _ctx: AuthContext = Depends(RequirePermission(MANAGE_USERS)),
                     db: Session = Depends(get_db)):
    user = db.query(User).get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = True
    user.deactivated_at = None
    db.add(user)
    db.commit()
    return _user_out(db, user)
