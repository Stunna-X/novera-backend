"""
Refresh token repository.

Contains database operations for refresh-token sessions.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    """
    Repository for refresh-token records.
    """

    def __init__(self, db: Session):
        super().__init__(db, RefreshToken)

    def get_by_token_hash(
        self,
        token_hash: str,
    ) -> RefreshToken | None:
        """
        Retrieve a refresh-token record by its hash.
        """

        return (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == token_hash,
            )
            .first()
        )

    def create_token(
        self,
        token: RefreshToken,
    ) -> RefreshToken:
        """
        Persist a refresh-token record.
        """

        return self.create(token)

    def revoke(
        self,
        token: RefreshToken,
    ) -> RefreshToken:
        """
        Revoke one refresh token.
        """

        token.revoked = True

        return self.update(token)

    def revoke_all_for_user(
        self,
        user_id: uuid.UUID,
    ) -> None:
        """
        Revoke every active refresh token belonging to a user.
        """

        (
            self.db.query(RefreshToken)
            .filter(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
            )
            .update(
                {
                    RefreshToken.revoked: True,
                },
                synchronize_session=False,
            )
        )

        self.db.commit()