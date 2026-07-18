"""
SHERLOCK — Stage E1: Request/response schemas for backend/api/auth.py.
"""

from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: datetime


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None
    full_name: str | None
    officer_id: int | None
    is_active: bool
    roles: list[str]

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    """Used by the (Sprint E2, Administrator-only) user-provisioning
    endpoint. Defined here now since it belongs next to the other auth
    schemas, even though the route itself lands in Sprint E2 alongside
    RequirePermission."""
    username: str
    password: str
    email: str | None = None
    full_name: str | None = None
    officer_id: int | None = None
    roles: list[str] = []
