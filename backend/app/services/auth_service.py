"""
Authentication service.

Handles registration, login, token refresh, logout, and
password-reset flows.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.jwt import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from app.core.security import hash_password, verify_password
from app.email.providers.base import EmailProviderError
from app.enums.user import UserStatus
from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.password_reset_token_repository import (
    PasswordResetTokenRepository,
)
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import (
    ForgotPasswordSchema,
    LoginSchema,
    RegisterSchema,
    ResetPasswordSchema,
)
from app.services.auth_email_service import AuthEmailService


PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 60


class AuthService:
    """
    Service containing authentication business logic.
    """

    def __init__(self, db: Session):
        self.db = db
        self.users = UserRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)
        self.password_reset_tokens = PasswordResetTokenRepository(db)
        self.auth_email = AuthEmailService(
            application_settings=settings,
        )

    @staticmethod
    def _hash_refresh_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _hash_password_reset_token(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @staticmethod
    def _unauthorized(
        detail: str = "Invalid refresh token.",
    ) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )

    @staticmethod
    def _validate_user_status(user: User) -> None:
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
            refresh_token_record,
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
        normalized_email = payload.email.strip().lower()

        user = self.users.get_by_email(normalized_email)

        if user is None or not verify_password(
            payload.password,
            user.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
                headers={"WWW-Authenticate": "Bearer"},
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
        payload = verify_refresh_token(refresh_token)

        if payload is None:
            raise self._unauthorized()

        subject = payload.get("sub")

        if not subject:
            raise self._unauthorized()

        token_hash = self._hash_refresh_token(
            refresh_token,
        )

        stored_token = self.refresh_tokens.get_by_token_hash(
            token_hash,
        )

        if stored_token is None:
            raise self._unauthorized(
                "Refresh token was not found.",
            )

        if str(stored_token.user_id) != str(subject):
            raise self._unauthorized()

        if stored_token.revoked:
            self.refresh_tokens.revoke_all_for_user(
                stored_token.user_id,
            )

            raise self._unauthorized(
                "Refresh token has already been revoked.",
            )

        if stored_token.expires_at <= datetime.now(UTC):
            raise self._unauthorized(
                "Refresh token has expired.",
            )

        user = self.users.get(
            stored_token.user_id,
        )

        if user is None:
            raise self._unauthorized(
                "User associated with this token was not found.",
            )

        try:
            self._validate_user_status(user)
        except HTTPException:
            self.refresh_tokens.revoke_all_for_user(
                user.id,
            )
            raise

        self.refresh_tokens.revoke(
            stored_token,
        )

        return self._create_tokens_for_user(user)

    def logout(
        self,
        refresh_token: str,
    ) -> dict[str, str]:
        token_hash = self._hash_refresh_token(
            refresh_token,
        )

        stored_token = self.refresh_tokens.get_by_token_hash(
            token_hash,
        )

        if stored_token is not None and not stored_token.revoked:
            self.refresh_tokens.revoke(
                stored_token,
            )

        return {
            "message": "Logged out successfully.",
        }

    def request_password_reset(
        self,
        payload: ForgotPasswordSchema,
    ) -> dict[str, str]:
        """
        Request a password-reset email.

        Always returns the same response whether or not the
        email belongs to an account.
        """

        generic_response = {
            "message": (
                "If an account exists for that email, "
                "we've sent password reset instructions."
            )
        }

        normalized_email = payload.email.strip().lower()

        user = self.users.get_by_email(
            normalized_email,
        )

        if user is None:
            return generic_response


        # Do not reveal whether an existing account is locked or inactive.
        # These accounts cannot initiate a password reset, but the caller
        # must receive the same response as an unknown email address.
        if user.status in {UserStatus.LOCKED, UserStatus.INACTIVE}:
            return generic_response



        raw_token = secrets.token_urlsafe(48)

        token_hash = self._hash_password_reset_token(
            raw_token,
        )

        expires_at = datetime.now(UTC) + timedelta(
            minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
        )

        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        self.password_reset_tokens.create_token(
            reset_token,
        )

        try:
            self.auth_email.send_password_reset_email(
                email=user.email,
                first_name=user.first_name,
                token=raw_token,
            )
        except EmailProviderError:
            self.db.delete(reset_token)
            self.db.commit()

            return generic_response

        return generic_response

    def reset_password(
        self,
        payload: ResetPasswordSchema,
    ) -> dict[str, str]:
        """
        Reset a user's password using a valid single-use token.
        """

        token_hash = self._hash_password_reset_token(
            payload.token,
        )

        reset_token = self.password_reset_tokens.get_by_token_hash(
            token_hash,
        )

        invalid_token_error = HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

        if reset_token is None:
            raise invalid_token_error

        now = datetime.now(UTC)

        if reset_token.used_at is not None:
            raise invalid_token_error

        if reset_token.expires_at <= now:
            raise invalid_token_error

        user = self.users.get(
            reset_token.user_id,
        )

        if user is None:
            raise invalid_token_error

        self._validate_user_status(user)

        user.password_hash = hash_password(
            payload.password,
        )

        reset_token.used_at = now

        self.db.add(user)
        self.db.add(reset_token)

        # Invalidate all other outstanding password-reset tokens.
        self.db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.id != reset_token.id,
        ).update(
            {
                PasswordResetToken.used_at: now,
            },
            synchronize_session=False,
        )

        # Force every existing authenticated session to sign in again.
        self.db.query(RefreshToken).filter(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked.is_(False),
        ).update(
            {
                RefreshToken.revoked: True,
            },
            synchronize_session=False,
        )

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return {
            "message": (
                "Your password has been reset successfully. "
                "You can now sign in with your new password."
            )
        }
