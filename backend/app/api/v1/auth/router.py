"""
Authentication routes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    LoginSchema,
    RefreshTokenSchema,
    RegisterSchema,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post(
    "/register",
    response_model=AuthResponse,
)
def register(
    payload: RegisterSchema,
    db: Session = Depends(get_db),
) -> AuthResponse:
    service = AuthService(db)
    return service.register(payload)


@router.post(
    "/login",
    response_model=AuthResponse,
)
def login(
    payload: LoginSchema,
    db: Session = Depends(get_db),
) -> AuthResponse:
    service = AuthService(db)
    return service.login(payload)


@router.post(
    "/refresh",
    response_model=TokenResponse,
)
def refresh(
    payload: RefreshTokenSchema,
    db: Session = Depends(get_db),
) -> TokenResponse:
    service = AuthService(db)
    return service.refresh(payload.refresh_token)


@router.post("/logout")
def logout(
    payload: RefreshTokenSchema,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    service = AuthService(db)
    return service.logout(payload.refresh_token)


@router.get(
    "/me",
    response_model=UserResponse,
)
def me(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user