"""
Inventory service.

Contains organization-scoped business logic for inventory locations,
catalogue items, item-location balances, and low-stock reporting.

Repository mutations flush without committing. This service owns the
final transaction boundary so every catalogue write is committed or
rolled back as one unit.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.inventory import (
    InventoryBalance,
    InventoryItem,
    InventoryLocation,
)
from app.repositories.inventory import (
    InventoryRepository,
    LowStockRecord,
)
from app.schemas.inventory import (
    CreateInventoryItemSchema,
    CreateInventoryLocationSchema,
    InventoryBalanceListResponse,
    InventoryItemListResponse,
    InventoryLocationListResponse,
    LowStockItemResponse,
    LowStockListResponse,
    UpdateInventoryItemSchema,
    UpdateInventoryLocationSchema,
)


class InventoryService:
    """
    Handle organization-scoped inventory catalogue operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.inventory = InventoryRepository(db)

    def _rollback_and_raise_conflict(
        self,
        exc: IntegrityError,
        detail: str,
    ) -> None:
        """
        Roll back a failed transaction and expose a safe conflict.
        """

        self.db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        ) from exc

    def _rollback_and_reraise(
        self,
        exc: SQLAlchemyError,
    ) -> None:
        """
        Roll back an unexpected database failure and re-raise it.
        """

        self.db.rollback()
        raise exc

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------

    def _get_location_or_404(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> InventoryLocation:
        """
        Retrieve an organization inventory location or raise 404.
        """

        location = (
            self.inventory.get_location_for_organization(
                organization_id=organization_id,
                location_id=location_id,
                include_inactive=include_inactive,
                for_update=for_update,
            )
        )

        if location is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory location not found.",
            )

        return location

    def _ensure_location_code_available(
        self,
        organization_id: uuid.UUID,
        code: str,
        *,
        exclude_location_id: uuid.UUID | None = None,
    ) -> None:
        """
        Ensure a location code is unique in the organization.
        """

        if self.inventory.location_code_exists(
            organization_id=organization_id,
            code=code,
            exclude_location_id=exclude_location_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another inventory location in this "
                    "organization already uses this code."
                ),
            )

    def create_location(
        self,
        organization_id: uuid.UUID,
        payload: CreateInventoryLocationSchema,
    ) -> InventoryLocation:
        """
        Create an inventory location.
        """

        location_data = payload.model_dump()

        self._ensure_location_code_available(
            organization_id=organization_id,
            code=location_data["code"],
        )

        location = InventoryLocation(
            organization_id=organization_id,
            **location_data,
        )

        try:
            created = self.inventory.create_location(
                location
            )
            self.db.commit()
            self.db.refresh(created)

            return created

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                (
                    "The inventory location conflicts with "
                    "an existing organization location."
                ),
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def list_locations(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        location_type: str | None = None,
        include_inactive: bool = False,
    ) -> InventoryLocationListResponse:
        """
        Return a paginated inventory-location collection.
        """

        locations = (
            self.inventory.list_locations_for_organization(
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                search=search,
                location_type=location_type,
                include_inactive=include_inactive,
            )
        )

        total = (
            self.inventory.count_locations_for_organization(
                organization_id=organization_id,
                search=search,
                location_type=location_type,
                include_inactive=include_inactive,
            )
        )

        return InventoryLocationListResponse(
            items=locations,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_location(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> InventoryLocation:
        """
        Return one inventory location.
        """

        return self._get_location_or_404(
            organization_id=organization_id,
            location_id=location_id,
            include_inactive=include_inactive,
        )

    def update_location(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID,
        payload: UpdateInventoryLocationSchema,
    ) -> InventoryLocation:
        """
        Update an active inventory location.
        """

        location = self._get_location_or_404(
            organization_id=organization_id,
            location_id=location_id,
            for_update=True,
        )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        if not update_data:
            return location

        required_fields = {
            "code",
            "name",
            "location_type",
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

        if "code" in update_data:
            self._ensure_location_code_available(
                organization_id=organization_id,
                code=update_data["code"],
                exclude_location_id=location.id,
            )

        for field_name, field_value in update_data.items():
            setattr(
                location,
                field_name,
                field_value,
            )

        try:
            updated = self.inventory.update_location(
                location
            )
            self.db.commit()
            self.db.refresh(updated)

            return updated

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                (
                    "The inventory-location update "
                    "conflicts with an existing record."
                ),
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def deactivate_location(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> None:
        """
        Soft-delete an inventory location with no remaining stock.
        """

        location = self._get_location_or_404(
            organization_id=organization_id,
            location_id=location_id,
            for_update=True,
        )

        if self.inventory.location_has_stock(
            organization_id=organization_id,
            location_id=location.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Inventory locations containing on-hand "
                    "or reserved stock cannot be deactivated."
                ),
            )

        if self.inventory.location_has_active_reservations(
            organization_id=organization_id,
            location_id=location.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Inventory locations with active stock "
                    "reservations cannot be deactivated."
                ),
            )

        try:
            self.inventory.deactivate_location(
                location
            )
            self.db.commit()

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                (
                    "The inventory location could not be "
                    "deactivated because it is still in use."
                ),
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def reactivate_location(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> InventoryLocation:
        """
        Reactivate an inventory location.
        """

        location = self._get_location_or_404(
            organization_id=organization_id,
            location_id=location_id,
            include_inactive=True,
            for_update=True,
        )

        if location.is_active:
            return location

        try:
            reactivated = (
                self.inventory.reactivate_location(
                    location
                )
            )
            self.db.commit()
            self.db.refresh(reactivated)

            return reactivated

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                (
                    "The inventory location could not "
                    "be reactivated."
                ),
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    # ------------------------------------------------------------------
    # Catalogue items
    # ------------------------------------------------------------------

    def _get_item_or_404(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> InventoryItem:
        """
        Retrieve an organization inventory item or raise 404.
        """

        item = self.inventory.get_item_for_organization(
            organization_id=organization_id,
            item_id=item_id,
            include_inactive=include_inactive,
            for_update=for_update,
        )

        if item is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory item not found.",
            )

        return item

    def _reload_item(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> InventoryItem:
        """
        Reload an item with its item-location balances.
        """

        return self._get_item_or_404(
            organization_id=organization_id,
            item_id=item_id,
            include_inactive=include_inactive,
        )

    def _ensure_sku_available(
        self,
        organization_id: uuid.UUID,
        sku: str,
        *,
        exclude_item_id: uuid.UUID | None = None,
    ) -> None:
        """
        Ensure a SKU is unique inside the organization.
        """

        if self.inventory.sku_exists(
            organization_id=organization_id,
            sku=sku,
            exclude_item_id=exclude_item_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another inventory item in this "
                    "organization already uses this SKU."
                ),
            )

    def _ensure_barcode_available(
        self,
        organization_id: uuid.UUID,
        barcode: str | None,
        *,
        exclude_item_id: uuid.UUID | None = None,
    ) -> None:
        """
        Ensure a supplied barcode is unique in the organization.
        """

        if not barcode:
            return

        if self.inventory.barcode_exists(
            organization_id=organization_id,
            barcode=barcode,
            exclude_item_id=exclude_item_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another inventory item in this "
                    "organization already uses this barcode."
                ),
            )

    def create_item(
        self,
        organization_id: uuid.UUID,
        payload: CreateInventoryItemSchema,
    ) -> InventoryItem:
        """
        Create an inventory catalogue item.
        """

        item_data = payload.model_dump()

        self._ensure_sku_available(
            organization_id=organization_id,
            sku=item_data["sku"],
        )

        self._ensure_barcode_available(
            organization_id=organization_id,
            barcode=item_data.get("barcode"),
        )

        item = InventoryItem(
            organization_id=organization_id,
            **item_data,
        )

        try:
            created = self.inventory.create_item(
                item
            )
            created_id = created.id

            self.db.commit()

            return self._reload_item(
                organization_id=organization_id,
                item_id=created_id,
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                (
                    "The inventory item conflicts with "
                    "an existing organization item."
                ),
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def list_items(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        item_type: str | None = None,
        category: str | None = None,
        location_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> InventoryItemListResponse:
        """
        Return a paginated inventory-item collection.
        """

        if location_id is not None:
            self._get_location_or_404(
                organization_id=organization_id,
                location_id=location_id,
                include_inactive=include_inactive,
            )

        items = self.inventory.list_items_for_organization(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            search=search,
            item_type=item_type,
            category=category,
            location_id=location_id,
            include_inactive=include_inactive,
        )

        total = self.inventory.count_items_for_organization(
            organization_id=organization_id,
            search=search,
            item_type=item_type,
            category=category,
            location_id=location_id,
            include_inactive=include_inactive,
        )

        return InventoryItemListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_item(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> InventoryItem:
        """
        Return one inventory catalogue item.
        """

        return self._get_item_or_404(
            organization_id=organization_id,
            item_id=item_id,
            include_inactive=include_inactive,
        )

    def update_item(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        payload: UpdateInventoryItemSchema,
    ) -> InventoryItem:
        """
        Update an active inventory catalogue item.
        """

        item = self._get_item_or_404(
            organization_id=organization_id,
            item_id=item_id,
            for_update=True,
        )

        update_data = payload.model_dump(
            exclude_unset=True
        )

        if not update_data:
            return item

        required_fields = {
            "sku",
            "name",
            "item_type",
            "unit_of_measure",
            "default_unit_cost",
            "currency",
            "reorder_level",
            "details",
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

        if "sku" in update_data:
            self._ensure_sku_available(
                organization_id=organization_id,
                sku=update_data["sku"],
                exclude_item_id=item.id,
            )

        if "barcode" in update_data:
            self._ensure_barcode_available(
                organization_id=organization_id,
                barcode=update_data["barcode"],
                exclude_item_id=item.id,
            )

        for field_name, field_value in update_data.items():
            setattr(
                item,
                field_name,
                field_value,
            )

        try:
            updated = self.inventory.update_item(
                item
            )
            updated_id = updated.id

            self.db.commit()

            return self._reload_item(
                organization_id=organization_id,
                item_id=updated_id,
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                (
                    "The inventory-item update conflicts "
                    "with an existing organization item."
                ),
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def deactivate_item(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> None:
        """
        Soft-delete an inventory item with no remaining stock.
        """

        item = self._get_item_or_404(
            organization_id=organization_id,
            item_id=item_id,
            for_update=True,
        )

        if self.inventory.item_has_stock(
            organization_id=organization_id,
            item_id=item.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Inventory items with on-hand or "
                    "reserved stock cannot be deactivated."
                ),
            )

        if self.inventory.item_has_active_reservations(
            organization_id=organization_id,
            item_id=item.id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Inventory items with active stock "
                    "reservations cannot be deactivated."
                ),
            )

        try:
            self.inventory.deactivate_item(
                item
            )
            self.db.commit()

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                (
                    "The inventory item could not be "
                    "deactivated because it is still in use."
                ),
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def reactivate_item(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> InventoryItem:
        """
        Reactivate an inventory catalogue item.
        """

        item = self._get_item_or_404(
            organization_id=organization_id,
            item_id=item_id,
            include_inactive=True,
            for_update=True,
        )

        if item.is_active:
            return item

        try:
            reactivated = self.inventory.reactivate_item(
                item
            )
            reactivated_id = reactivated.id

            self.db.commit()

            return self._reload_item(
                organization_id=organization_id,
                item_id=reactivated_id,
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                "The inventory item could not be reactivated.",
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    # ------------------------------------------------------------------
    # Balances and low-stock reporting
    # ------------------------------------------------------------------

    def _get_balance_or_404(
        self,
        organization_id: uuid.UUID,
        balance_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> InventoryBalance:
        """
        Retrieve an organization item-location balance.
        """

        balance = (
            self.inventory.get_balance_by_id_for_organization(
                organization_id=organization_id,
                balance_id=balance_id,
                for_update=for_update,
            )
        )

        if balance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory balance not found.",
            )

        return balance

    def list_balances(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        item_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        in_stock_only: bool = False,
        include_inactive_catalogue: bool = False,
    ) -> InventoryBalanceListResponse:
        """
        Return paginated item-location stock balances.
        """

        if item_id is not None:
            self._get_item_or_404(
                organization_id=organization_id,
                item_id=item_id,
                include_inactive=(
                    include_inactive_catalogue
                ),
            )

        if location_id is not None:
            self._get_location_or_404(
                organization_id=organization_id,
                location_id=location_id,
                include_inactive=(
                    include_inactive_catalogue
                ),
            )

        balances = (
            self.inventory.list_balances_for_organization(
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                search=search,
                item_id=item_id,
                location_id=location_id,
                in_stock_only=in_stock_only,
                include_inactive_catalogue=(
                    include_inactive_catalogue
                ),
            )
        )

        total = (
            self.inventory.count_balances_for_organization(
                organization_id=organization_id,
                search=search,
                item_id=item_id,
                location_id=location_id,
                in_stock_only=in_stock_only,
                include_inactive_catalogue=(
                    include_inactive_catalogue
                ),
            )
        )

        return InventoryBalanceListResponse(
            items=balances,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_balance(
        self,
        organization_id: uuid.UUID,
        balance_id: uuid.UUID,
    ) -> InventoryBalance:
        """
        Return one inventory balance by identifier.
        """

        return self._get_balance_or_404(
            organization_id=organization_id,
            balance_id=balance_id,
        )

    def get_item_location_balance(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> InventoryBalance:
        """
        Return the balance for one item at one location.
        """

        self._get_item_or_404(
            organization_id=organization_id,
            item_id=item_id,
            include_inactive=True,
        )

        self._get_location_or_404(
            organization_id=organization_id,
            location_id=location_id,
            include_inactive=True,
        )

        balance = self.inventory.get_balance_for_organization(
            organization_id=organization_id,
            item_id=item_id,
            location_id=location_id,
        )

        if balance is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No inventory balance exists for this "
                    "item and location."
                ),
            )

        return balance

    @staticmethod
    def _build_low_stock_item(
        record: LowStockRecord,
    ) -> LowStockItemResponse:
        """
        Convert an aggregated repository row into its API schema.

        The payload includes both nested and flattened catalogue
        values so it remains compatible with the current low-stock
        response shape while the mutation schemas are added later.
        """

        item = record.item

        reorder_level = Decimal(
            item.reorder_level
        )

        shortage_quantity = max(
            reorder_level
            - Decimal(record.available_quantity),
            Decimal("0"),
        )

        recommended_order_quantity = (
            Decimal(item.reorder_quantity)
            if item.reorder_quantity is not None
            else shortage_quantity
        )

        candidate_values = {
            "item": item,
            "id": item.id,
            "item_id": item.id,
            "organization_id": item.organization_id,
            "sku": item.sku,
            "barcode": item.barcode,
            "name": item.name,
            "item_type": item.item_type,
            "category": item.category,
            "description": item.description,
            "unit_of_measure": item.unit_of_measure,
            "default_unit_cost": item.default_unit_cost,
            "currency": item.currency,
            "reorder_level": item.reorder_level,
            "reorder_quantity": item.reorder_quantity,
            "preferred_supplier": item.preferred_supplier,
            "details": item.details,
            "is_active": item.is_active,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
            "quantity_on_hand": record.quantity_on_hand,
            "quantity_reserved": record.quantity_reserved,
            "available_quantity": record.available_quantity,
            "shortage_quantity": shortage_quantity,
            "reorder_deficit": shortage_quantity,
            "recommended_order_quantity": (
                recommended_order_quantity
            ),
            "suggested_order_quantity": (
                recommended_order_quantity
            ),
        }

        response_fields = (
            LowStockItemResponse.model_fields
        )

        payload = {
            field_name: candidate_values[field_name]
            for field_name in response_fields
            if field_name in candidate_values
        }

        return LowStockItemResponse(
            **payload
        )

    def list_low_stock(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        item_type: str | None = None,
        category: str | None = None,
        location_id: uuid.UUID | None = None,
    ) -> LowStockListResponse:
        """
        Return active items at or below their reorder level.
        """

        if location_id is not None:
            self._get_location_or_404(
                organization_id=organization_id,
                location_id=location_id,
            )

        records = (
            self.inventory.list_low_stock_for_organization(
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                search=search,
                item_type=item_type,
                category=category,
                location_id=location_id,
            )
        )

        total = (
            self.inventory.count_low_stock_for_organization(
                organization_id=organization_id,
                search=search,
                item_type=item_type,
                category=category,
                location_id=location_id,
            )
        )

        return LowStockListResponse(
            items=[
                self._build_low_stock_item(record)
                for record in records
            ],
            total=total,
            skip=skip,
            limit=limit,
        )
