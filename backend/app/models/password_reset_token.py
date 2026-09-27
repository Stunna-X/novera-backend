"""
Password reset token model.

Stores only a cryptographic hash of a password-reset token.
The raw token is delivered to the user and is never persisted.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


class PasswordResetToken(BaseModel):
    """
    One single-use password-reset token.
    """

    __tablename__ = "password_reset_tokens"

    __table_args__ = (
        Index(
            "ix_password_reset_tokens_user_id_expires_at",
            "user_id",
            "expires_at",
        ),
        Index(
            "ix_password_reset_tokens_expires_at",
            "expires_at",
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    user = relationship(
        "User",
        back_populates="password_reset_tokens",
    )

    def __repr__(self) -> str:
        return (
            f"<PasswordResetToken "
            f"id={self.id} "
            f"user_id={self.user_id} "
            f"expires_at={self.expires_at!r} "
            f"used_at={self.used_at!r}>"
        )