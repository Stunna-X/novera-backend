"""
Workforce repository.

Contains organization-scoped database operations for
workforce profiles.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import (
    Session,
    joinedload,
)

from app.models.membership import Membership
from app.models.role import Role
from app.models.user import User
from app.models.workforce_profile import WorkforceProfile
from app.repositories.base import BaseRepository


class WorkforceRepository(
    BaseRepository[WorkforceProfile]
):
    """
    Repository for workforce profile operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            WorkforceProfile,
        )

    def _with_member_details(self):
        """
        Return eager-loading options for membership details.
        """

        return (
            joinedload(
                WorkforceProfile.membership
            ).joinedload(
                Membership.user
            ),
            joinedload(
                WorkforceProfile.membership
            ).joinedload(
                Membership.role
            ),
        )

    def create_profile(
        self,
        profile: WorkforceProfile,
    ) -> WorkforceProfile:
        """
        Persist a workforce profile.
        """

        if profile.employee_code:
            profile.employee_code = (
                profile.employee_code.strip().upper()
            )

        return self.create(
            profile
        )

    def get_by_id_for_organization(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkforceProfile | None:
        """
        Retrieve one workforce profile.
        """

        query = (
            self.db.query(WorkforceProfile)
            .options(
                *self._with_member_details()
            )
            .filter(
                WorkforceProfile.id == profile_id,
                WorkforceProfile.organization_id
                == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkforceProfile.is_active.is_(True)
            )

        return query.first()

    def get_by_membership(
        self,
        organization_id: uuid.UUID,
        membership_id: uuid.UUID,
    ) -> WorkforceProfile | None:
        """
        Retrieve a profile by membership.
        """

        return (
            self.db.query(WorkforceProfile)
            .options(
                *self._with_member_details()
            )
            .filter(
                WorkforceProfile.organization_id
                == organization_id,
                WorkforceProfile.membership_id
                == membership_id,
            )
            .first()
        )

    def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        available_only: bool = False,
        include_inactive: bool = False,
    ) -> list[WorkforceProfile]:
        """
        Retrieve organization workforce profiles.
        """

        query = (
            self.db.query(WorkforceProfile)
            .options(
                *self._with_member_details()
            )
            .join(
                Membership,
                WorkforceProfile.membership_id
                == Membership.id,
            )
            .join(
                User,
                Membership.user_id == User.id,
            )
            .filter(
                WorkforceProfile.organization_id
                == organization_id
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkforceProfile.is_active.is_(True)
            )

        if status_filter:
            query = query.filter(
                WorkforceProfile.status
                == status_filter
            )

        if available_only:
            query = query.filter(
                WorkforceProfile.is_available.is_(True),
                WorkforceProfile.is_active.is_(True),
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            pattern = f"%{normalized_search}%"

            query = query.filter(
                or_(
                    User.first_name.ilike(pattern),
                    User.last_name.ilike(pattern),
                    User.email.ilike(pattern),
                    WorkforceProfile.employee_code.ilike(
                        pattern
                    ),
                    WorkforceProfile.job_title.ilike(
                        pattern
                    ),
                )
            )

        return (
            query.order_by(
                User.first_name.asc(),
                User.last_name.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        status_filter: str | None = None,
        available_only: bool = False,
        include_inactive: bool = False,
    ) -> int:
        """
        Count organization workforce profiles.
        """

        query = (
            self.db.query(
                func.count(WorkforceProfile.id)
            )
            .join(
                Membership,
                WorkforceProfile.membership_id
                == Membership.id,
            )
            .join(
                User,
                Membership.user_id == User.id,
            )
            .filter(
                WorkforceProfile.organization_id
                == organization_id
            )
        )

        if not include_inactive:
            query = query.filter(
                WorkforceProfile.is_active.is_(True)
            )

        if status_filter:
            query = query.filter(
                WorkforceProfile.status
                == status_filter
            )

        if available_only:
            query = query.filter(
                WorkforceProfile.is_available.is_(True),
                WorkforceProfile.is_active.is_(True),
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            pattern = f"%{normalized_search}%"

            query = query.filter(
                or_(
                    User.first_name.ilike(pattern),
                    User.last_name.ilike(pattern),
                    User.email.ilike(pattern),
                    WorkforceProfile.employee_code.ilike(
                        pattern
                    ),
                    WorkforceProfile.job_title.ilike(
                        pattern
                    ),
                )
            )

        return query.scalar() or 0

    def employee_code_exists(
        self,
        organization_id: uuid.UUID,
        employee_code: str,
        *,
        exclude_profile_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check employee-code uniqueness.
        """

        normalized_code = (
            employee_code.strip().lower()
        )

        query = self.db.query(
            WorkforceProfile.id
        ).filter(
            WorkforceProfile.organization_id
            == organization_id,
            func.lower(
                WorkforceProfile.employee_code
            )
            == normalized_code,
        )

        if exclude_profile_id is not None:
            query = query.filter(
                WorkforceProfile.id
                != exclude_profile_id
            )

        return query.first() is not None

    def update_profile(
        self,
        profile: WorkforceProfile,
    ) -> WorkforceProfile:
        """
        Persist workforce-profile changes.
        """

        if profile.employee_code:
            profile.employee_code = (
                profile.employee_code.strip().upper()
            )

        return self.update(
            profile
        )

    def deactivate_profile(
        self,
        profile: WorkforceProfile,
    ) -> WorkforceProfile:
        """
        Deactivate a workforce profile.
        """

        profile.is_active = False
        profile.is_available = False
        profile.status = "inactive"

        return self.update(
            profile
        )

    def reactivate_profile(
        self,
        profile: WorkforceProfile,
    ) -> WorkforceProfile:
        """
        Reactivate a workforce profile.
        """

        profile.is_active = True
        profile.is_available = True
        profile.status = "active"

        return self.update(
            profile
        )