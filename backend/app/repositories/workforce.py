"""
Workforce repository.

Contains organization-scoped database operations for
workforce profiles.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

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

    def _organization_query(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        status_filter: str | None = None,
        include_inactive: bool = False,
    ):
        """
        Build a consistently filtered organization query.
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

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            pattern = f"%{normalized_search}%"

            query = query.filter(
                or_(
                    WorkforceProfile.full_name.ilike(
                        pattern
                    ),
                    WorkforceProfile.job_title.ilike(
                        pattern
                    ),
                )
            )

        return query

    def create_profile(
        self,
        profile: WorkforceProfile,
    ) -> WorkforceProfile:
        """Persist a workforce profile."""

        return self.create(profile)

    def get_by_id_for_organization(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkforceProfile | None:
        """Retrieve one workforce profile."""

        query = self.db.query(
            WorkforceProfile
        ).filter(
            WorkforceProfile.id == profile_id,
            WorkforceProfile.organization_id
            == organization_id,
        )

        if not include_inactive:
            query = query.filter(
                WorkforceProfile.is_active.is_(True)
            )

        return query.first()

    def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        include_inactive: bool = False,
    ) -> list[WorkforceProfile]:
        """Retrieve organization workforce profiles."""

        query = self._organization_query(
            organization_id=organization_id,
            search=search,
            status_filter=status_filter,
            include_inactive=include_inactive,
        )

        return (
            query.order_by(
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
        include_inactive: bool = False,
    ) -> int:
        """Count organization workforce profiles."""

        query = self._organization_query(
            organization_id=organization_id,
            search=search,
            status_filter=status_filter,
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
        """Persist workforce-profile changes."""

        return self.update(profile)

    def deactivate_profile(
        self,
        profile: WorkforceProfile,
    ) -> WorkforceProfile:
        """Deactivate a workforce profile."""

        profile.is_active = False
        profile.status = "inactive"

        return self.update(profile)

    def reactivate_profile(
        self,
        profile: WorkforceProfile,
    ) -> WorkforceProfile:
        """Reactivate a workforce profile."""

        profile.is_active = True
        profile.status = "active"

        return self.update(profile)
