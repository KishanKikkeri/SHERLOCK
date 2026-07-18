"""
SHERLOCK — Stage E1: Seed data.

Two idempotent operations, safe to call on every startup:

  1. `seed_roles` — one Role row per SystemRole value. The role
     vocabulary is fixed (per the Sprint E2 brief), so this is not
     "initial data a user could later edit away" — it's closer to the
     Enum itself, just also queryable/joinable from SQL.

  2. `seed_bootstrap_admin` — only runs if both
     SHERLOCK_BOOTSTRAP_ADMIN_USERNAME/PASSWORD are set AND no
     Administrator user exists yet. Exists so a freshly deployed,
     auth-enabled instance always has a way in; harmless (a no-op) once
     any Administrator account exists.
"""

import logging

from sqlalchemy.orm import Session

from backend.database.models import Role, User, UserRole, SystemRole
from backend.security.config import BOOTSTRAP_ADMIN_USERNAME, BOOTSTRAP_ADMIN_PASSWORD
from backend.security.passwords import hash_password

logger = logging.getLogger(__name__)


def seed_roles(db: Session) -> None:
    existing = {r.name for r in db.query(Role).all()}
    created = 0
    for role in SystemRole:
        if role in existing:
            continue
        db.add(Role(name=role, description=f"{role.value.replace('_', ' ').title()} role"))
        created += 1
    if created:
        db.commit()
        logger.info("Seeded %d role(s).", created)


def seed_bootstrap_admin(db: Session) -> None:
    if not (BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD):
        return

    admin_role = db.query(Role).filter(Role.name == SystemRole.ADMINISTRATOR).first()
    if admin_role is None:
        # seed_roles hasn't run yet; caller should call it first.
        return

    has_admin = (
        db.query(UserRole)
        .filter(UserRole.role_id == admin_role.id)
        .first()
    )
    if has_admin is not None:
        return

    existing_user = db.query(User).filter(User.username == BOOTSTRAP_ADMIN_USERNAME).first()
    if existing_user is None:
        existing_user = User(
            username=BOOTSTRAP_ADMIN_USERNAME,
            password_hash=hash_password(BOOTSTRAP_ADMIN_PASSWORD),
            full_name="Bootstrap Administrator",
        )
        db.add(existing_user)
        db.flush()

    db.add(UserRole(user_id=existing_user.id, role_id=admin_role.id))
    db.commit()
    logger.warning(
        "Bootstrap Administrator account '%s' created/granted admin role. "
        "Log in and rotate this password immediately.",
        BOOTSTRAP_ADMIN_USERNAME,
    )


def run_all_seeds(db: Session) -> None:
    seed_roles(db)
    seed_bootstrap_admin(db)
