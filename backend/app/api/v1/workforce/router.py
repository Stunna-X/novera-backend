"""
Workforce routes.

Provides organization-scoped endpoints for managing
operational workforce profiles.
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    Query,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.database.session import get_db
from app.schemas.workforce import (
    CreateWorkforceProfileSchema,
    UpdateWorkforceProfileSchema,
    WorkforceProfileListResponse,
    WorkforceProfileResponse,
    WorkforceStatus,
)
from app.services.workforce_service import WorkforceService


router = APIRouter(
    prefix="/organizations/{organization_id}/workforce",
    tags=["Workforce"],
)


@router.post(
    "",
    response_model=WorkforceProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workforce profile",
)
def create_workforce_profile(
    payload: CreateWorkforceProfileSchema,
    context: OrganizationContext = Depends(
        require_permission("workforce.create")
    ),
    db: Session = Depends(get_db),
) -> WorkforceProfileResponse:
    """
    Create a workforce profile for an organization member.

    Requires:
    - workforce.create
    """

    service = WorkforceService(db)

    return service.create_profile(
        organization_id=context.organization.id,
        payload=payload,
    )


@router.get(
    "",
    response_model=WorkforceProfileListResponse,
    summary="List workforce",
)
def list_workforce_profiles(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    search: str | None = Query(
        default=None,
        min_length=1,
        max_length=160,
    ),
    workforce_status: WorkforceStatus | None = Query(
        default=None,
        alias="status",
    ),
    available_only: bool = Query(
        default=False,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("workforce.read")
    ),
    db: Session = Depends(get_db),
) -> WorkforceProfileListResponse:
    """
    List organization workforce profiles.

    Requires:
    - workforce.read
    """

    service = WorkforceService(db)

    return service.list_profiles(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        status_filter=workforce_status,
        available_only=available_only,
        include_inactive=include_inactive,
    )


@router.get(
    "/{profile_id}",
    response_model=WorkforceProfileResponse,
    summary="Get workforce profile",
)
def get_workforce_profile(
    profile_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("workforce.read")
    ),
    db: Session = Depends(get_db),
) -> WorkforceProfileResponse:
    """
    Return one workforce profile.

    Requires:
    - workforce.read
    """

    service = WorkforceService(db)

    return service.get_profile(
        organization_id=context.organization.id,
        profile_id=profile_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{profile_id}",
    response_model=WorkforceProfileResponse,
    summary="Update workforce profile",
)
def update_workforce_profile(
    profile_id: uuid.UUID,
    payload: UpdateWorkforceProfileSchema,
    context: OrganizationContext = Depends(
        require_permission("workforce.update")
    ),
    db: Session = Depends(get_db),
) -> WorkforceProfileResponse:
    """
    Update an active workforce profile.

    Requires:
    - workforce.update
    """

    service = WorkforceService(db)

    return service.update_profile(
        organization_id=context.organization.id,
        profile_id=profile_id,
        payload=payload,
    )


@router.delete(
    "/{profile_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate workforce profile",
)
def deactivate_workforce_profile(
    profile_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("workforce.delete")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Soft-delete a workforce profile.

    Requires:
    - workforce.delete
    """

    service = WorkforceService(db)

    service.deactivate_profile(
        organization_id=context.organization.id,
        profile_id=profile_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/{profile_id}/reactivate",
    response_model=WorkforceProfileResponse,
    summary="Reactivate workforce profile",
)
def reactivate_workforce_profile(
    profile_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("workforce.update")
    ),
    db: Session = Depends(get_db),
) -> WorkforceProfileResponse:
    """
    Reactivate a workforce profile.

    Requires:
    - workforce.update
    """

    service = WorkforceService(db)

    return service.reactivate_profile(
        organization_id=context.organization.id,
        profile_id=profile_id,
    )