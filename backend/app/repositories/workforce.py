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

    @staticmethod
    def _with_member_details():
        """
        Eager-load optional linked account details.
        """

        return (
            joinedload(
                WorkforceProfile.membership
            ).joinedload(
                Membership.user
            ),
        )

    def _organization_query(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        status_filter: str | None = None,
        available_only: bool = False,
        include_inactive: bool = False,
    ):
        """
        Build a consistently filtered organization query.

        Standalone employees remain included because membership
        and user records are optional.
        """

        query = self.db.query(
            WorkforceProfile
        ).filter(
            WorkforceProfile.organization_id
            == organization_id
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

            query = (
                query.outerjoin(
                    Membership,
                    WorkforceProfile.membership_id
                    == Membership.id,
                )
                .outerjoin(
                    User,
                    Membership.user_id == User.id,
                )
                .filter(
                    or_(
                        WorkforceProfile.full_name.ilike(
                            pattern
                        ),
                        WorkforceProfile.job_title.ilike(
                            pattern
                        ),
                        User.email.ilike(pattern),
                    )
                )
            )

        return query

    def create_profile(
        self,
        profile: WorkforceProfile,
    ) -> WorkforceProfile:
        """
        Persist a workforce profile.
        """

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
        Retrieve a profile by its optional membership.
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

        Includes employees without linked user accounts.
        """

        query = self._organization_query(
            organization_id=organization_id,
            search=search,
            status_filter=status_filter,
            available_only=available_only,
            include_inactive=include_inactive,
        )

        return (
            query.options(
                *self._with_member_details()
            )
            .order_by(
                WorkforceProfile.full_name.asc(),
                WorkforceProfile.id.asc(),
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

        Uses the same filters as the listing query.
        """

        query = self._organization_query(
            organization_id=organization_id,
            search=search,
            status_filter=status_filter,
            available_only=available_only,
            include_inactive=include_inactive,
        )

        return (
            query.with_entities(
                func.count(WorkforceProfile.id)
            ).scalar()
            or 0
        )

    def update_profile(
        self,
        profile: WorkforceProfile,
    ) -> WorkforceProfile:
        """
        Persist workforce-profile changes.
        """

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