"""
Asset routes.

Provides organization-scoped endpoints for managing
equipment and operational assets.
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
from app.models.asset import Asset
from app.schemas.asset import (
    AssetListResponse,
    AssetResponse,
    AssetStatus,
    AssetType,
    CreateAssetSchema,
    UpdateAssetSchema,
)
from app.services.asset_service import AssetService


router = APIRouter(
    prefix="/organizations/{organization_id}/assets",
    tags=["Assets"],
)


@router.post(
    "",
    response_model=AssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create asset",
)
def create_asset(
    payload: CreateAssetSchema,
    context: OrganizationContext = Depends(
        require_permission("assets.create")
    ),
    db: Session = Depends(get_db),
) -> Asset:
    """
    Create an organization asset.

    Requires:
    - assets.create
    """

    service = AssetService(db)

    return service.create_asset(
        organization_id=context.organization.id,
        payload=payload,
    )


@router.get(
    "",
    response_model=AssetListResponse,
    summary="List assets",
)
def list_assets(
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
    asset_status: AssetStatus | None = Query(
        default=None,
        alias="status",
    ),
    asset_type: AssetType | None = Query(
        default=None,
    ),
    available_only: bool = Query(
        default=False,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("assets.read")
    ),
    db: Session = Depends(get_db),
) -> AssetListResponse:
    """
    List organization assets.

    Requires:
    - assets.read
    """

    service = AssetService(db)

    return service.list_assets(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        status_filter=asset_status,
        asset_type=asset_type,
        available_only=available_only,
        include_inactive=include_inactive,
    )


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Get asset",
)
def get_asset(
    asset_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("assets.read")
    ),
    db: Session = Depends(get_db),
) -> Asset:
    """
    Return one organization asset.

    Requires:
    - assets.read
    """

    service = AssetService(db)

    return service.get_asset(
        organization_id=context.organization.id,
        asset_id=asset_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="Update asset",
)
def update_asset(
    asset_id: uuid.UUID,
    payload: UpdateAssetSchema,
    context: OrganizationContext = Depends(
        require_permission("assets.update")
    ),
    db: Session = Depends(get_db),
) -> Asset:
    """
    Update an active organization asset.

    Requires:
    - assets.update
    """

    service = AssetService(db)

    return service.update_asset(
        organization_id=context.organization.id,
        asset_id=asset_id,
        payload=payload,
    )


@router.delete(
    "/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate asset",
)
def deactivate_asset(
    asset_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("assets.delete")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Soft-delete an organization asset.

    Requires:
    - assets.delete
    """

    service = AssetService(db)

    service.deactivate_asset(
        organization_id=context.organization.id,
        asset_id=asset_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/{asset_id}/reactivate",
    response_model=AssetResponse,
    summary="Reactivate asset",
)
def reactivate_asset(
    asset_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("assets.update")
    ),
    db: Session = Depends(get_db),
) -> Asset:
    """
    Reactivate an organization asset.

    Requires:
    - assets.update
    """

    service = AssetService(db)

    return service.reactivate_asset(
        organization_id=context.organization.id,
        asset_id=asset_id,
    )