"""
Asset service.

Contains business logic for organization equipment
and operational assets.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.repositories.asset import AssetRepository
from app.schemas.asset import (
    AssetListResponse,
    CreateAssetSchema,
    UpdateAssetSchema,
)


class AssetService:
    """
    Handles organization-scoped asset business logic.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.assets = AssetRepository(db)

    def _get_asset_or_404(
        self,
        organization_id: uuid.UUID,
        asset_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Asset:
        """
        Retrieve an organization asset or raise 404.
        """

        asset = (
            self.assets.get_by_id_for_organization(
                organization_id=organization_id,
                asset_id=asset_id,
                include_inactive=include_inactive,
            )
        )

        if asset is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Asset not found.",
            )

        return asset

    def _ensure_asset_code_available(
        self,
        organization_id: uuid.UUID,
        asset_code: str,
        *,
        exclude_asset_id: uuid.UUID | None = None,
    ) -> None:
        """
        Ensure an asset code is unique.
        """

        if self.assets.asset_code_exists(
            organization_id=organization_id,
            asset_code=asset_code,
            exclude_asset_id=exclude_asset_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another asset in this organization "
                    "already uses this asset code."
                ),
            )

    def _ensure_serial_number_available(
        self,
        organization_id: uuid.UUID,
        serial_number: str | None,
        *,
        exclude_asset_id: uuid.UUID | None = None,
    ) -> None:
        """
        Ensure a serial number is unique when supplied.
        """

        if not serial_number:
            return

        if self.assets.serial_number_exists(
            organization_id=organization_id,
            serial_number=serial_number,
            exclude_asset_id=exclude_asset_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another asset in this organization "
                    "already uses this serial number."
                ),
            )

    def create_asset(
        self,
        organization_id: uuid.UUID,
        payload: CreateAssetSchema,
    ) -> Asset:
        """
        Create an organization asset.
        """

        asset_data = payload.model_dump()

        self._ensure_asset_code_available(
            organization_id=organization_id,
            asset_code=asset_data["asset_code"],
        )

        self._ensure_serial_number_available(
            organization_id=organization_id,
            serial_number=asset_data.get(
                "serial_number"
            ),
        )

        asset = Asset(
            organization_id=organization_id,
            **asset_data,
        )

        try:
            return self.assets.create_asset(
                asset
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The asset conflicts with an "
                    "existing organization asset."
                ),
            ) from exc

    def list_assets(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        asset_type: str | None = None,
        available_only: bool = False,
        include_inactive: bool = False,
    ) -> AssetListResponse:
        """
        Return a paginated organization asset collection.
        """

        assets = self.assets.list_for_organization(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            search=search,
            status_filter=status_filter,
            asset_type=asset_type,
            available_only=available_only,
            include_inactive=include_inactive,
        )

        total = self.assets.count_for_organization(
            organization_id=organization_id,
            search=search,
            status_filter=status_filter,
            asset_type=asset_type,
            available_only=available_only,
            include_inactive=include_inactive,
        )

        return AssetListResponse(
            items=assets,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_asset(
        self,
        organization_id: uuid.UUID,
        asset_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Asset:
        """
        Return one organization asset.
        """

        return self._get_asset_or_404(
            organization_id=organization_id,
            asset_id=asset_id,
            include_inactive=include_inactive,
        )

    def update_asset(
        self,
        organization_id: uuid.UUID,
        asset_id: uuid.UUID,
        payload: UpdateAssetSchema,
    ) -> Asset:
        """
        Update an active organization asset.
        """

        asset = self._get_asset_or_404(
            organization_id=organization_id,
            asset_id=asset_id,
        )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        required_fields = {
            "asset_code",
            "name",
            "asset_type",
            "status",
            "condition",
        }

        for field_name in required_fields:
            if (
                field_name in update_data
                and update_data[field_name] is None
            ):
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        f"{field_name.replace('_', ' ').title()} "
                        "cannot be null."
                    ),
                )

        if "asset_code" in update_data:
            self._ensure_asset_code_available(
                organization_id=organization_id,
                asset_code=update_data["asset_code"],
                exclude_asset_id=asset.id,
            )

        if "serial_number" in update_data:
            self._ensure_serial_number_available(
                organization_id=organization_id,
                serial_number=update_data[
                    "serial_number"
                ],
                exclude_asset_id=asset.id,
            )

        for field_name, field_value in update_data.items():
            setattr(
                asset,
                field_name,
                field_value,
            )

        try:
            return self.assets.update_asset(
                asset
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The asset conflicts with an "
                    "existing organization asset."
                ),
            ) from exc

    def deactivate_asset(
        self,
        organization_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> None:
        """
        Soft-delete an organization asset.
        """

        asset = self._get_asset_or_404(
            organization_id=organization_id,
            asset_id=asset_id,
        )

        self.assets.deactivate_asset(
            asset
        )

    def reactivate_asset(
        self,
        organization_id: uuid.UUID,
        asset_id: uuid.UUID,
    ) -> Asset:
        """
        Reactivate an organization asset.
        """

        asset = self._get_asset_or_404(
            organization_id=organization_id,
            asset_id=asset_id,
            include_inactive=True,
        )

        if asset.is_active:
            return asset

        return self.assets.reactivate_asset(
            asset
        )