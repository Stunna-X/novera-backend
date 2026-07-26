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
        Retrieve an organization membership.
        """

        membership = (
            self.db.query(Membership)
            .options(
                joinedload(Membership.user),
                joinedload(Membership.role),
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

    def _ensure_employee_code_available(
        self,
        organization_id: uuid.UUID,
        employee_code: str | None,
        *,
        exclude_profile_id: uuid.UUID | None = None,
    ) -> None:
        """
        Ensure an employee code is unique.
        """

        if not employee_code:
            return

        if self.workforce.employee_code_exists(
            organization_id=organization_id,
            employee_code=employee_code,
            exclude_profile_id=exclude_profile_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another workforce member already "
                    "uses this employee code."
                ),
            )

    @staticmethod
    def _build_response(
        profile: WorkforceProfile,
    ) -> WorkforceProfileResponse:
        """
        Convert an ORM profile into an API response.
        """

        membership = profile.membership
        user = membership.user
        role = membership.role

        return WorkforceProfileResponse(
            id=profile.id,
            organization_id=profile.organization_id,
            membership_id=profile.membership_id,
            user_id=membership.user_id,
            first_name=user.first_name,
            last_name=user.last_name,
            email=user.email,
            role_name=role.name,
            employee_code=profile.employee_code,
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
            joined_on=profile.joined_on,
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
        Create an operational profile for a member.
        """

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

        profile_data = payload.model_dump()
        profile_data.pop("membership_id")

        self._ensure_employee_code_available(
            organization_id=organization_id,
            employee_code=profile_data.get(
                "employee_code"
            ),
        )

        if profile_data["status"] != "active":
            profile_data["is_available"] = False

        profile = WorkforceProfile(
            organization_id=organization_id,
            membership_id=membership.id,
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

        if (
            "status" in update_data
            and update_data["status"] is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Workforce status cannot be null.",
            )

        if (
            "is_available" in update_data
            and update_data["is_available"] is None
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Availability cannot be null.",
            )

        if "employee_code" in update_data:
            self._ensure_employee_code_available(
                organization_id=organization_id,
                employee_code=update_data[
                    "employee_code"
                ],
                exclude_profile_id=profile.id,
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