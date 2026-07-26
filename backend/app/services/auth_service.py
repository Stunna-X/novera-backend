"""
Authentication service.

Contains all business logic related to authentication.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.jwt import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from app.core.security import (
    hash_password,
    verify_password,
)
from app.enums.user import UserStatus
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import LoginSchema, RegisterSchema


class AuthService:
    """
    Handles authentication business logic.
    """

    def __init__(self, db: Session):
        self.users = UserRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        """
        Hash a raw refresh token before database storage.
        """

        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _unauthorized(
        detail: str = "Invalid refresh token.",
    ) -> HTTPException:
        """
        Build a consistent authentication exception.
        """

        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    @staticmethod
    def _validate_user_status(user: User) -> None:
        """
        Prevent locked or inactive accounts from authenticating.
        """

        if user.status == UserStatus.LOCKED:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is locked.",
            )

        if user.status == UserStatus.INACTIVE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account is inactive.",
            )

    def _create_tokens_for_user(
        self,
        user: User,
    ) -> dict[str, str]:
        """
        Create an access token and a database-backed refresh token.
        """

        access_token = create_access_token(
            {
                "sub": str(user.id),
                "email": user.email,
            }
        )

        refresh_token = create_refresh_token(
            {
                "sub": str(user.id),
            }
        )

        refresh_payload = verify_refresh_token(refresh_token)

        if refresh_payload is None:
            raise RuntimeError(
                "Generated refresh token could not be validated."
            )

        expiration = refresh_payload.get("exp")

        if expiration is None:
            raise RuntimeError(
                "Generated refresh token has no expiration."
            )

        expires_at = datetime.fromtimestamp(
            expiration,
            tz=UTC,
        )

        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=self._hash_refresh_token(refresh_token),
            expires_at=expires_at,
        )

        self.refresh_tokens.create_token(
            refresh_token_record
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
        }

    def register(
        self,
        payload: RegisterSchema,
    ) -> dict[str, Any]:
        """
        Register a new user and issue authentication tokens.
        """

        normalized_email = payload.email.strip().lower()

        if self.users.email_exists(normalized_email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists.",
            )

        user = User(
            first_name=payload.first_name.strip(),
            last_name=payload.last_name.strip(),
            email=normalized_email,
            password_hash=hash_password(payload.password),
        )

        user = self.users.create_user(user)

        tokens = self._create_tokens_for_user(user)

        return {
            "user": user,
            **tokens,
        }

    def login(
        self,
        payload: LoginSchema,
    ) -> dict[str, Any]:
        """
        Authenticate an existing user and issue tokens.
        """

        normalized_email = payload.email.strip().lower()

        user = self.users.get_by_email(normalized_email)

        if user is None or not verify_password(
            payload.password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )

        self._validate_user_status(user)

        self.users.update_last_login(user)

        tokens = self._create_tokens_for_user(user)

        return {
            "user": user,
            **tokens,
        }

    def refresh(
        self,
        refresh_token: str,
    ) -> dict[str, str]:
        """
        Validate and rotate a refresh token.
        """

        payload = verify_refresh_token(refresh_token)

        if payload is None:
            raise self._unauthorized()

        subject = payload.get("sub")

        if not subject:
            raise self._unauthorized()

        token_hash = self._hash_refresh_token(
            refresh_token
        )

        stored_token = (
            self.refresh_tokens.get_by_token_hash(
                token_hash
            )
        )

        if stored_token is None:
            raise self._unauthorized(
                "Refresh token was not found."
            )

        if str(stored_token.user_id) != str(subject):
            raise self._unauthorized()

        if stored_token.revoked:
            self.refresh_tokens.revoke_all_for_user(
                stored_token.user_id
            )

            raise self._unauthorized(
                "Refresh token has already been revoked."
            )

        if stored_token.expires_at <= datetime.now(UTC):
            raise self._unauthorized(
                "Refresh token has expired."
            )

        user = self.users.get(
            stored_token.user_id
        )

        if user is None:
            raise self._unauthorized(
                "User associated with this token was not found."
            )

        try:
            self._validate_user_status(user)
        except HTTPException:
            self.refresh_tokens.revoke_all_for_user(user.id)
            raise

        self.refresh_tokens.revoke(stored_token)

        return self._create_tokens_for_user(user)

    def logout(
        self,
        refresh_token: str,
    ) -> dict[str, str]:
        """
        Revoke the supplied refresh token.
        """

        token_hash = self._hash_refresh_token(
            refresh_token
        )

        stored_token = (
            self.refresh_tokens.get_by_token_hash(
                token_hash
            )
        )

        if stored_token is not None and not stored_token.revoked:
            self.refresh_tokens.revoke(stored_token)

        return {
            "message": "Logged out successfully.",
        }