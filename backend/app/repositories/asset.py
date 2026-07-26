"""
Asset repository.

Contains organization-scoped database operations for
operational assets.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.repositories.base import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    """
    Repository for organization asset operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            Asset,
        )

    def create_asset(
        self,
        asset: Asset,
    ) -> Asset:
        """
        Persist a new asset.
        """

        asset.asset_code = (
            asset.asset_code.strip().upper()
        )

        asset.name = asset.name.strip()

        if asset.serial_number:
            asset.serial_number = (
                asset.serial_number.strip().upper()
            )

        if asset.registration_number:
            asset.registration_number = (
                asset.registration_number.strip().upper()
            )

        return self.create(
            asset
        )

    def get_by_id_for_organization(
        self,
        organization_id: uuid.UUID,
        asset_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Asset | None:
        """
        Retrieve one organization asset.
        """

        query = self.db.query(Asset).filter(
            Asset.id == asset_id,
            Asset.organization_id == organization_id,
        )

        if not include_inactive:
            query = query.filter(
                Asset.is_active.is_(True)
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
        asset_type: str | None = None,
        available_only: bool = False,
        include_inactive: bool = False,
    ) -> list[Asset]:
        """
        Retrieve organization assets.
        """

        query = self.db.query(Asset).filter(
            Asset.organization_id == organization_id
        )

        if not include_inactive:
            query = query.filter(
                Asset.is_active.is_(True)
            )

        if status_filter:
            query = query.filter(
                Asset.status == status_filter
            )

        if asset_type:
            query = query.filter(
                Asset.asset_type == asset_type
            )

        if available_only:
            query = query.filter(
                Asset.status == "available",
                Asset.is_active.is_(True),
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
                    Asset.asset_code.ilike(pattern),
                    Asset.name.ilike(pattern),
                    Asset.category.ilike(pattern),
                    Asset.manufacturer.ilike(pattern),
                    Asset.model_number.ilike(pattern),
                    Asset.serial_number.ilike(pattern),
                    Asset.registration_number.ilike(
                        pattern
                    ),
                    Asset.location.ilike(pattern),
                )
            )

        return (
            query.order_by(
                Asset.name.asc(),
                Asset.created_at.asc(),
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
        asset_type: str | None = None,
        available_only: bool = False,
        include_inactive: bool = False,
    ) -> int:
        """
        Count organization assets.
        """

        query = (
            self.db.query(
                func.count(Asset.id)
            )
            .filter(
                Asset.organization_id
                == organization_id
            )
        )

        if not include_inactive:
            query = query.filter(
                Asset.is_active.is_(True)
            )

        if status_filter:
            query = query.filter(
                Asset.status == status_filter
            )

        if asset_type:
            query = query.filter(
                Asset.asset_type == asset_type
            )

        if available_only:
            query = query.filter(
                Asset.status == "available",
                Asset.is_active.is_(True),
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
                    Asset.asset_code.ilike(pattern),
                    Asset.name.ilike(pattern),
                    Asset.category.ilike(pattern),
                    Asset.manufacturer.ilike(pattern),
                    Asset.model_number.ilike(pattern),
                    Asset.serial_number.ilike(pattern),
                    Asset.registration_number.ilike(
                        pattern
                    ),
                    Asset.location.ilike(pattern),
                )
            )

        return query.scalar() or 0

    def asset_code_exists(
        self,
        organization_id: uuid.UUID,
        asset_code: str,
        *,
        exclude_asset_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check asset-code uniqueness within an organization.
        """

        normalized_code = (
            asset_code.strip().lower()
        )

        query = self.db.query(Asset.id).filter(
            Asset.organization_id == organization_id,
            func.lower(Asset.asset_code)
            == normalized_code,
        )

        if exclude_asset_id is not None:
            query = query.filter(
                Asset.id != exclude_asset_id
            )

        return query.first() is not None

    def serial_number_exists(
        self,
        organization_id: uuid.UUID,
        serial_number: str,
        *,
        exclude_asset_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check serial-number uniqueness within an organization.
        """

        normalized_serial = (
            serial_number.strip().lower()
        )

        query = self.db.query(Asset.id).filter(
            Asset.organization_id == organization_id,
            func.lower(Asset.serial_number)
            == normalized_serial,
        )

        if exclude_asset_id is not None:
            query = query.filter(
                Asset.id != exclude_asset_id
            )

        return query.first() is not None

    def update_asset(
        self,
        asset: Asset,
    ) -> Asset:
        """
        Persist asset changes.
        """

        asset.asset_code = (
            asset.asset_code.strip().upper()
        )

        asset.name = asset.name.strip()

        if asset.serial_number:
            asset.serial_number = (
                asset.serial_number.strip().upper()
            )

        if asset.registration_number:
            asset.registration_number = (
                asset.registration_number.strip().upper()
            )

        return self.update(
            asset
        )

    def deactivate_asset(
        self,
        asset: Asset,
    ) -> Asset:
        """
        Soft-delete an asset.
        """

        asset.is_active = False

        return self.update(
            asset
        )

    def reactivate_asset(
        self,
        asset: Asset,
    ) -> Asset:
        """
        Reactivate an asset.
        """

        asset.is_active = True

        return self.update(
            asset
        )