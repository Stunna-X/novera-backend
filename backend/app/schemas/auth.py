"""
Authentication schemas.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterSchema(BaseModel):
    first_name: str = Field(
        min_length=2,
        max_length=100,
    )

    last_name: str = Field(
        min_length=2,
        max_length=100,
    )

    email: EmailStr

    password: str = Field(
        min_length=8,
    )


class LoginSchema(BaseModel):
    email: EmailStr

    password: str


class RefreshTokenSchema(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str

    refresh_token: str

    token_type: str = "Bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID

    first_name: str

    last_name: str

    email: EmailStr

    email_verified: bool

    status: str


class AuthResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    user: UserResponse

    access_token: str

    refresh_token: str

    token_type: str = "Bearer"