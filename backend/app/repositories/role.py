"""
Role repository.

Contains database operations for platform roles
and their assigned permissions.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models.role import Role
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    """
    Repository for role database operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            Role,
        )

    def create_role(
        self,
        role: Role,
    ) -> Role:
        """
        Persist a new role.
        """

        role.name = role.name.strip()

        return self.create(
            role
        )

    def get_by_id(
        self,
        role_id: uuid.UUID,
    ) -> Role | None:
        """
        Retrieve one role by its ID.
        """

        return (
            self.db.query(Role)
            .filter(
                Role.id == role_id
            )
            .first()
        )

    def get_by_id_with_permissions(
        self,
        role_id: uuid.UUID,
    ) -> Role | None:
        """
        Retrieve one role and eagerly load its permissions.
        """

        return (
            self.db.query(Role)
            .options(
                selectinload(
                    Role.permissions
                )
            )
            .filter(
                Role.id == role_id
            )
            .first()
        )

    def get_by_name(
        self,
        name: str,
    ) -> Role | None:
        """
        Retrieve a role by name using a case-insensitive lookup.
        """

        normalized_name = (
            name.strip().lower()
        )

        return (
            self.db.query(Role)
            .filter(
                func.lower(Role.name)
                == normalized_name
            )
            .first()
        )

    def get_by_name_with_permissions(
        self,
        name: str,
    ) -> Role | None:
        """
        Retrieve a role by name and eagerly load its permissions.
        """

        normalized_name = (
            name.strip().lower()
        )

        return (
            self.db.query(Role)
            .options(
                selectinload(
                    Role.permissions
                )
            )
            .filter(
                func.lower(Role.name)
                == normalized_name
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

        normalized_name = (
            name.strip().lower()
        )

        return (
            self.db.query(Role.id)
            .filter(
                func.lower(Role.name)
                == normalized_name
            )
            .first()
            is not None
        )

    def list_roles(
        self,
    ) -> list[Role]:
        """
        Retrieve every available role.
        """

        return (
            self.db.query(Role)
            .order_by(
                Role.name.asc()
            )
            .all()
        )

    def list_roles_with_permissions(
        self,
    ) -> list[Role]:
        """
        Retrieve every role and eagerly load permissions.
        """

        return (
            self.db.query(Role)
            .options(
                selectinload(
                    Role.permissions
                )
            )
            .order_by(
                Role.name.asc()
            )
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
            .filter(
                Role.is_system.is_(True)
            )
            .order_by(
                Role.name.asc()
            )
            .all()
        )

    def list_system_roles_with_permissions(
        self,
    ) -> list[Role]:
        """
        Retrieve platform-managed roles with permissions loaded.
        """

        return (
            self.db.query(Role)
            .options(
                selectinload(
                    Role.permissions
                )
            )
            .filter(
                Role.is_system.is_(True)
            )
            .order_by(
                Role.name.asc()
            )
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

        return self.update(
            role
        )

    def delete_role(
        self,
        role: Role,
    ) -> None:
        """
        Delete a non-system role.
        """

        self.delete(
            role
        )