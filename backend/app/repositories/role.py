"""
Role repository.

Contains database operations for platform roles.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.role import Role
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    """
    Repository for role database operations.
    """

    def __init__(self, db: Session):
        super().__init__(db, Role)

    def create_role(
        self,
        role: Role,
    ) -> Role:
        """
        Persist a new role.
        """

        role.name = role.name.strip()

        return self.create(role)

    def get_by_name(
        self,
        name: str,
    ) -> Role | None:
        """
        Retrieve a role by name using a case-insensitive lookup.
        """

        normalized_name = name.strip().lower()

        return (
            self.db.query(Role)
            .filter(
                func.lower(Role.name) == normalized_name
            )
            .first()
        )

    def name_exists(
        self,
        name: str,
    ) -> bool:
        """
        Check whether a role with the supplied name exists.
        """

        return self.get_by_name(name) is not None

    def list_roles(
        self,
    ) -> list[Role]:
        """
        Retrieve every available role.
        """

        return (
            self.db.query(Role)
            .order_by(Role.name.asc())
            .all()
        )

    def list_system_roles(
        self,
    ) -> list[Role]:
        """
        Retrieve roles managed by the Novera platform.
        """

        return (
            self.db.query(Role)
            .filter(Role.is_system.is_(True))
            .order_by(Role.name.asc())
            .all()
        )

    def update_role(
        self,
        role: Role,
    ) -> Role:
        """
        Persist changes to a role.
        """

        role.name = role.name.strip()

        return self.update(role)

    def delete_role(
        self,
        role: Role,
    ) -> None:
        """
        Delete a non-system role.
        """

        self.delete(role)