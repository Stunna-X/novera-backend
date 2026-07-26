"""
User repository.

Contains all database operations related to users.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """
    Repository for user database operations.
    """

    def __init__(self, db: Session):
        super().__init__(db, User)

    def get_by_email(
        self,
        email: str,
    ) -> User | None:
        """
        Retrieve a user by normalized email address.
        """

        normalized_email = email.strip().lower()

        return (
            self.db.query(User)
            .filter(User.email == normalized_email)
            .first()
        )

    def email_exists(
        self,
        email: str,
    ) -> bool:
        """
        Check whether an email address is already registered.
        """

        return self.get_by_email(email) is not None

    def create_user(
        self,
        user: User,
    ) -> User:
        """
        Persist a new user.
        """

        user.email = user.email.strip().lower()

        return self.create(user)

    def update_last_login(
        self,
        user: User,
    ) -> User:
        """
        Update the user's latest successful login time.
        """

        user.last_login_at = datetime.now(UTC)

        return self.update(user)

    def verify_email(
        self,
        user: User,
    ) -> User:
        """
        Mark the user's email address as verified.
        """

        user.email_verified = True

        return self.update(user)

    def list_active(
        self,
    ) -> list[User]:
        """
        Retrieve users whose email addresses are verified.

        This currently treats email verification as active status.
        """

        return (
            self.db.query(User)
            .filter(User.email_verified.is_(True))
            .all()
        )