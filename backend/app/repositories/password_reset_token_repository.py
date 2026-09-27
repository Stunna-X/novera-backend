"""
Password reset token repository.

Contains database operations for single-use password-reset tokens.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.password_reset_token import PasswordResetToken
from app.repositories.base import BaseRepository


class PasswordResetTokenRepository(BaseRepository[PasswordResetToken]):
    """
    Repository for password-reset token records.
    """

    def __init__(self, db: Session):
        super().__init__(db, PasswordResetToken)

    def get_by_token_hash(
        self,
        token_hash: str,
    ) -> PasswordResetToken | None:
        """
        Retrieve a password-reset token by its hash.
        """

        return (
            self.db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.token_hash == token_hash,
            )
            .first()
        )

    def create_token(
        self,
        token: PasswordResetToken,
    ) -> PasswordResetToken:
        """
        Persist a password-reset token.
        """

        return self.create(token)

    def mark_used(
        self,
        token: PasswordResetToken,
    ) -> PasswordResetToken:
        """
        Mark one password-reset token as consumed.
        """

        token.used_at = datetime.now(UTC)

        return self.update(token)

    def invalidate_all_for_user(
        self,
        user_id: uuid.UUID,
    ) -> None:
        """
        Invalidate every currently unused password-reset token
        belonging to a user.
        """

        now = datetime.now(UTC)

        (
            self.db.query(PasswordResetToken)
            .filter(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
            .update(
                {
                    PasswordResetToken.used_at: now,
                },
                synchronize_session=False,
            )
        )

        self.db.commit()