"""
Workforce service.

Contains business logic for organization workforce profiles.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.workforce_profile import WorkforceProfile
from app.repositories.workforce import WorkforceRepository
from app.schemas.workforce import (
    CreateWorkforceProfileSchema,
    UpdateWorkforceProfileSchema,
    WorkforceProfileListResponse,
    WorkforceProfileResponse,
)


class WorkforceService:
    """
    Handles organization workforce business logic.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.workforce = WorkforceRepository(db)

    def _get_profile_or_404(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkforceProfile:
        """Retrieve an organization workforce profile."""

        profile = self.workforce.get_by_id_for_organization(
            organization_id=organization_id,
            profile_id=profile_id,
            include_inactive=include_inactive,
        )

        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workforce profile not found.",
            )

        return profile

    @staticmethod
    def _build_response(
        profile: WorkforceProfile,
    ) -> WorkforceProfileResponse:
        """Convert an ORM profile into an API response."""

        return WorkforceProfileResponse(
            id=profile.id,
            organization_id=profile.organization_id,
            full_name=profile.full_name,
            job_title=profile.job_title,
            employment_type=profile.employment_type,
            phone=profile.phone,
            status=profile.status,
            is_active=profile.is_active,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    def create_profile(
        self,
        organization_id: uuid.UUID,
        payload: CreateWorkforceProfileSchema,
    ) -> WorkforceProfileResponse:
        """Create a standalone organization employee."""

        profile = WorkforceProfile(
            organization_id=organization_id,
            **payload.model_dump(),
        )

        try:
            created_profile = self.workforce.create_profile(
                profile
            )

            loaded_profile = (
                self.workforce.get_by_id_for_organization(
                    organization_id=organization_id,
                    profile_id=created_profile.id,
                    include_inactive=True,
                )
            )

            if loaded_profile is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_500_INTERNAL_SERVER_ERROR
                    ),
                    detail=(
                        "Unable to load the created "
                        "workforce profile."
                    ),
                )

            return self._build_response(loaded_profile)

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The workforce profile conflicts "
                    "with an existing record."
                ),
            ) from exc

    def list_profiles(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        include_inactive: bool = False,
    ) -> WorkforceProfileListResponse:
        """List organization workforce profiles."""

        profiles = self.workforce.list_for_organization(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            search=search,
            status_filter=status_filter,
            include_inactive=include_inactive,
        )

        total = self.workforce.count_for_organization(
            organization_id=organization_id,
            search=search,
            status_filter=status_filter,
            include_inactive=include_inactive,
        )

        return WorkforceProfileListResponse(
            items=[
                self._build_response(profile)
                for profile in profiles
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_profile(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkforceProfileResponse:
        """Return one workforce profile."""

        profile = self._get_profile_or_404(
            organization_id=organization_id,
            profile_id=profile_id,
            include_inactive=include_inactive,
        )

        return self._build_response(profile)

    def update_profile(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
        payload: UpdateWorkforceProfileSchema,
    ) -> WorkforceProfileResponse:
        """Update an active workforce profile."""

        profile = self._get_profile_or_404(
            organization_id=organization_id,
            profile_id=profile_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        non_nullable_fields = {
            "full_name": "Employee name cannot be null.",
            "status": "Workforce status cannot be null.",
        }

        for field_name, error_message in (
            non_nullable_fields.items()
        ):
            if (
                field_name in update_data
                and update_data[field_name] is None
            ):
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_CONTENT
                    ),
                    detail=error_message,
                )

        for field_name, field_value in update_data.items():
            setattr(
                profile,
                field_name,
                field_value,
            )

        updated_profile = self.workforce.update_profile(
            profile
        )

        return self._build_response(updated_profile)

    def deactivate_profile(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> None:
        """Deactivate a workforce profile."""

        profile = self._get_profile_or_404(
            organization_id=organization_id,
            profile_id=profile_id,
        )

        self.workforce.deactivate_profile(profile)

    def reactivate_profile(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> WorkforceProfileResponse:
        """Reactivate a workforce profile."""

        profile = self._get_profile_or_404(
            organization_id=organization_id,
            profile_id=profile_id,
            include_inactive=True,
        )

        if not profile.is_active:
            profile = self.workforce.reactivate_profile(
                profile
            )

        return self._build_response(profile)
