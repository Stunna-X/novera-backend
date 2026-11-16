"""
Workforce service.

Contains business logic for organization workforce profiles.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (
    Session,
    joinedload,
)

from app.enums.user import UserStatus
from app.models.membership import Membership
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

    def _get_membership_or_404(
        self,
        organization_id: uuid.UUID,
        membership_id: uuid.UUID,
    ) -> Membership:
        """
        Retrieve and validate an optional organization membership.
        """

        membership = (
            self.db.query(Membership)
            .options(
                joinedload(Membership.user),
            )
            .filter(
                Membership.id == membership_id,
                Membership.organization_id
                == organization_id,
            )
            .first()
        )

        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Organization membership not found.",
            )

        if membership.user.status != UserStatus.ACTIVE:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The selected user account "
                    "is not active."
                ),
            )

        return membership

    def _get_profile_or_404(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> WorkforceProfile:
        """
        Retrieve a workforce profile.
        """

        profile = (
            self.workforce.get_by_id_for_organization(
                organization_id=organization_id,
                profile_id=profile_id,
                include_inactive=include_inactive,
            )
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
        """
        Convert an ORM profile into an API response.

        Linked account information is optional.
        """

        membership = profile.membership
        user = (
            membership.user
            if membership is not None
            else None
        )

        return WorkforceProfileResponse(
            id=profile.id,
            organization_id=profile.organization_id,
            full_name=profile.full_name,
            membership_id=profile.membership_id,
            user_id=(
                membership.user_id
                if membership is not None
                else None
            ),
            email=(
                user.email
                if user is not None
                else None
            ),
            job_title=profile.job_title,
            employment_type=profile.employment_type,
            phone=profile.phone,
            emergency_contact_name=(
                profile.emergency_contact_name
            ),
            emergency_contact_phone=(
                profile.emergency_contact_phone
            ),
            skills=profile.skills or [],
            status=profile.status,
            is_available=profile.is_available,
            is_active=profile.is_active,
            notes=profile.notes,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )

    def create_profile(
        self,
        organization_id: uuid.UUID,
        payload: CreateWorkforceProfileSchema,
    ) -> WorkforceProfileResponse:
        """
        Create an organization employee.

        A linked organization membership is optional.
        """

        membership = None

        if payload.membership_id is not None:
            membership = self._get_membership_or_404(
                organization_id=organization_id,
                membership_id=payload.membership_id,
            )

            existing_profile = (
                self.workforce.get_by_membership(
                    organization_id=organization_id,
                    membership_id=membership.id,
                )
            )

            if existing_profile is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This organization member already has "
                        "a workforce profile."
                    ),
                )

        profile_data = payload.model_dump(
            exclude={"membership_id"}
        )

        if profile_data.get("status", "active") != "active":
            profile_data["is_available"] = False

        profile = WorkforceProfile(
            organization_id=organization_id,
            membership_id=(
                membership.id
                if membership is not None
                else None
            ),
            **profile_data,
        )

        try:
            created_profile = (
                self.workforce.create_profile(
                    profile
                )
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

            return self._build_response(
                loaded_profile
            )

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
        available_only: bool = False,
        include_inactive: bool = False,
    ) -> WorkforceProfileListResponse:
        """
        List organization workforce profiles.
        """

        profiles = (
            self.workforce.list_for_organization(
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                search=search,
                status_filter=status_filter,
                available_only=available_only,
                include_inactive=include_inactive,
            )
        )

        total = (
            self.workforce.count_for_organization(
                organization_id=organization_id,
                search=search,
                status_filter=status_filter,
                available_only=available_only,
                include_inactive=include_inactive,
            )
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
        """
        Return one workforce profile.
        """

        profile = self._get_profile_or_404(
            organization_id=organization_id,
            profile_id=profile_id,
            include_inactive=include_inactive,
        )

        return self._build_response(
            profile
        )

    def update_profile(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
        payload: UpdateWorkforceProfileSchema,
    ) -> WorkforceProfileResponse:
        """
        Update an active workforce profile.
        """

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
            "is_available": "Availability cannot be null.",
            "skills": "Skills cannot be null. Provide an empty list to clear skills.",
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

        if profile.status != "active":
            profile.is_available = False

        updated_profile = (
            self.workforce.update_profile(
                profile
            )
        )

        return self._build_response(
            updated_profile
        )

    def deactivate_profile(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> None:
        """
        Deactivate a workforce profile.
        """

        profile = self._get_profile_or_404(
            organization_id=organization_id,
            profile_id=profile_id,
        )

        self.workforce.deactivate_profile(
            profile
        )

    def reactivate_profile(
        self,
        organization_id: uuid.UUID,
        profile_id: uuid.UUID,
    ) -> WorkforceProfileResponse:
        """
        Reactivate a workforce profile.
        """

        profile = self._get_profile_or_404(
            organization_id=organization_id,
            profile_id=profile_id,
            include_inactive=True,
        )

        if not profile.is_active:
            profile = (
                self.workforce.reactivate_profile(
                    profile
                )
            )

        return self._build_response(
            profile
        )
