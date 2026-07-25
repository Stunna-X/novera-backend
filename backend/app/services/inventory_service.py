"""
Inventory service.

Contains organization-scoped business logic for inventory locations,
catalogue items, balances, stock operations, reservations, and movement-ledger reporting.

Repository mutations flush without committing. This service owns the
final transaction boundary so every catalogue write is committed or
rolled back as one unit.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.inventory import (
    InventoryBalance,
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    InventoryReservation,
)
from app.models.work_order import WorkOrder
from app.repositories.inventory import (
    ACTIVE_RESERVATION_STATUSES,
    InventoryRepository,
    LowStockRecord,
)
from app.repositories.work_order import WorkOrderRepository
from app.schemas.inventory import (
    AdjustInventoryStockSchema,
    ConsumeInventoryReservationSchema,
    CreateInventoryReservationSchema,
    CreateInventoryItemSchema,
    CreateInventoryLocationSchema,
    InventoryBalanceListResponse,
    InventoryMovementListResponse,
    InventoryReservationConsumptionResponse,
    InventoryReservationListResponse,
    InventoryReservationOperationResponse,
    InventoryStockOperationResponse,
    InventoryTransferResponse,
    InventoryItemListResponse,
    InventoryLocationListResponse,
    LowStockItemResponse,
    IssueInventoryStockSchema,
    LowStockListResponse,
    ReceiveInventoryStockSchema,
    ReleaseInventoryReservationSchema,
    ReturnInventoryStockSchema,
    TransferInventoryStockSchema,
    UpdateInventoryItemSchema,
    UpdateInventoryLocationSchema,
)


QUANTITY_QUANTIZER = Decimal("0.001")
COST_QUANTIZER = Decimal("0.0001")
TERMINAL_WORK_ORDER_STATUSES = {"completed", "cancelled"}


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
        self.work_orders = WorkOrderRepository(db)

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
                        status.HTTP_422_UNPROCESSABLE_CONTENT
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
                        status.HTTP_422_UNPROCESSABLE_CONTENT
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

    # ------------------------------------------------------------------
    # Stock-operation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _utc_now() -> datetime:
        """
        Return a timezone-aware UTC timestamp.
        """

        return datetime.now(timezone.utc)

    @staticmethod
    def _quantity(
        value: Decimal,
    ) -> Decimal:
        """
        Normalize inventory quantities to database precision.
        """

        return Decimal(value).quantize(
            QUANTITY_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )

    @staticmethod
    def _cost(
        value: Decimal,
    ) -> Decimal:
        """
        Normalize unit costs to database precision.
        """

        return Decimal(value).quantize(
            COST_QUANTIZER,
            rounding=ROUND_HALF_UP,
        )

    @classmethod
    def _weighted_average_cost(
        cls,
        *,
        existing_quantity: Decimal,
        existing_unit_cost: Decimal,
        incoming_quantity: Decimal,
        incoming_unit_cost: Decimal,
    ) -> Decimal:
        """
        Calculate a weighted moving-average unit cost.
        """

        final_quantity = (
            Decimal(existing_quantity)
            + Decimal(incoming_quantity)
        )

        if final_quantity <= 0:
            return Decimal("0.0000")

        total_value = (
            Decimal(existing_quantity)
            * Decimal(existing_unit_cost)
            + Decimal(incoming_quantity)
            * Decimal(incoming_unit_cost)
        )

        return cls._cost(
            total_value / final_quantity
        )

    @staticmethod
    def _merge_details(
        base: dict[str, Any],
        **system_values: Any,
    ) -> dict[str, Any]:
        """
        Merge user metadata with authoritative system values.
        """

        return {
            **base,
            **system_values,
        }

    @staticmethod
    def _validate_date_range(
        occurred_from: datetime | None,
        occurred_to: datetime | None,
    ) -> None:
        """
        Reject an inverted movement date range.
        """

        if (
            occurred_from is not None
            and occurred_to is not None
            and occurred_from > occurred_to
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "occurred_from cannot be later than "
                    "occurred_to."
                ),
            )

    def _get_work_order_or_404(
        self,
        organization_id: uuid.UUID,
        work_order_id: uuid.UUID,
        *,
        require_mutable: bool = False,
    ) -> WorkOrder:
        """
        Retrieve an organization work order or raise 404.
        """

        work_order = (
            self.work_orders.get_for_organization(
                organization_id=organization_id,
                work_order_id=work_order_id,
            )
        )

        if work_order is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Work order not found.",
            )

        if (
            require_mutable
            and work_order.status
            in TERMINAL_WORK_ORDER_STATUSES
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Stock cannot be reserved for a completed "
                    "or cancelled work order."
                ),
            )

        return work_order

    @staticmethod
    def _resolve_currency(
        item: InventoryItem,
        supplied_currency: str | None,
    ) -> str:
        """
        Prevent weighted-cost calculations across currencies.
        """

        item_currency = item.currency.strip().upper()

        if (
            supplied_currency is not None
            and supplied_currency.strip().upper()
            != item_currency
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "Stock-operation currency must match the "
                    "inventory item's currency."
                ),
            )

        return item_currency

    def _get_balance_for_update(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        create_if_missing: bool,
    ) -> InventoryBalance:
        """
        Lock one balance or create its zero-value row safely.
        """

        balance = (
            self.inventory.get_balance_for_organization(
                organization_id=organization_id,
                item_id=item_id,
                location_id=location_id,
                for_update=True,
            )
        )

        if balance is not None:
            return balance

        if not create_if_missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No inventory balance exists for this "
                    "item and location."
                ),
            )

        try:
            with self.db.begin_nested():
                balance = self.inventory.create_balance(
                    InventoryBalance(
                        organization_id=organization_id,
                        item_id=item_id,
                        location_id=location_id,
                        quantity_on_hand=Decimal("0"),
                        quantity_reserved=Decimal("0"),
                        average_unit_cost=Decimal("0"),
                    )
                )

            return balance

        except IntegrityError:
            balance = (
                self.inventory.get_balance_for_organization(
                    organization_id=organization_id,
                    item_id=item_id,
                    location_id=location_id,
                    for_update=True,
                )
            )

            if balance is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The inventory balance could not be "
                        "created safely."
                    ),
                )

            return balance

    def _get_reservation_or_404(
        self,
        organization_id: uuid.UUID,
        reservation_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> InventoryReservation:
        """
        Retrieve an organization reservation or raise 404.
        """

        reservation = (
            self.inventory.get_reservation_for_organization(
                organization_id=organization_id,
                reservation_id=reservation_id,
                include_inactive=include_inactive,
                for_update=for_update,
            )
        )

        if reservation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory reservation not found.",
            )

        return reservation

    def _get_movement_or_404(
        self,
        organization_id: uuid.UUID,
        movement_id: uuid.UUID,
    ) -> InventoryMovement:
        """
        Retrieve an immutable movement or raise 404.
        """

        movement = (
            self.inventory.get_movement_for_organization(
                organization_id=organization_id,
                movement_id=movement_id,
            )
        )

        if movement is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Inventory movement not found.",
            )

        return movement

    @staticmethod
    def _ensure_available_quantity(
        balance: InventoryBalance,
        quantity: Decimal,
    ) -> None:
        """
        Ensure an operation does not consume reserved stock.
        """

        if Decimal(balance.available_quantity) < quantity:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Insufficient available inventory at this "
                    "location. Reserved stock cannot be used."
                ),
            )

    def _reload_operation_result(
        self,
        *,
        organization_id: uuid.UUID,
        movement_id: uuid.UUID,
        balance_id: uuid.UUID,
    ) -> InventoryStockOperationResponse:
        """
        Reload a committed one-location stock operation.
        """

        movement = self._get_movement_or_404(
            organization_id=organization_id,
            movement_id=movement_id,
        )

        balance = self._get_balance_or_404(
            organization_id=organization_id,
            balance_id=balance_id,
        )

        return InventoryStockOperationResponse(
            movement=movement,
            balance=balance,
        )

    # ------------------------------------------------------------------
    # Stock receipts, issues, returns, adjustments, and transfers
    # ------------------------------------------------------------------

    def receive_stock(
        self,
        organization_id: uuid.UUID,
        payload: ReceiveInventoryStockSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> InventoryStockOperationResponse:
        """
        Receive stock or establish an opening balance atomically.
        """

        item = self._get_item_or_404(
            organization_id=organization_id,
            item_id=payload.item_id,
        )

        self._get_location_or_404(
            organization_id=organization_id,
            location_id=payload.location_id,
        )

        currency = self._resolve_currency(
            item,
            payload.currency,
        )

        quantity = self._quantity(payload.quantity)
        occurred_at = payload.occurred_at or self._utc_now()

        try:
            balance = self._get_balance_for_update(
                organization_id=organization_id,
                item_id=item.id,
                location_id=payload.location_id,
                create_if_missing=True,
            )

            if payload.movement_type == "opening_balance":
                existing_movement_count = (
                    self.inventory.count_movements_for_organization(
                        organization_id=organization_id,
                        item_id=item.id,
                        location_id=payload.location_id,
                    )
                )

                if (
                    existing_movement_count > 0
                    or Decimal(balance.quantity_on_hand) != 0
                    or Decimal(balance.quantity_reserved) != 0
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "An opening balance can only be "
                            "recorded before the first movement "
                            "for an empty item-location balance."
                        ),
                    )

            unit_cost = self._cost(
                payload.unit_cost
                if payload.unit_cost is not None
                else Decimal(item.default_unit_cost)
            )

            quantity_before = self._quantity(
                Decimal(balance.quantity_on_hand)
            )

            quantity_after = self._quantity(
                quantity_before + quantity
            )

            average_unit_cost = (
                self._weighted_average_cost(
                    existing_quantity=quantity_before,
                    existing_unit_cost=Decimal(
                        balance.average_unit_cost
                    ),
                    incoming_quantity=quantity,
                    incoming_unit_cost=unit_cost,
                )
            )

            balance.quantity_on_hand = quantity_after
            balance.average_unit_cost = average_unit_cost
            balance.last_movement_at = occurred_at

            self.inventory.update_balance(balance)

            movement = self.inventory.create_movement(
                InventoryMovement(
                    organization_id=organization_id,
                    item_id=item.id,
                    location_id=payload.location_id,
                    movement_type=payload.movement_type,
                    quantity=quantity,
                    quantity_delta=quantity,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    unit_cost=unit_cost,
                    currency=currency,
                    reference_type=payload.reference_type,
                    reference_id=payload.reference_id,
                    occurred_at=occurred_at,
                    notes=payload.notes,
                    created_by_user_id=actor_user_id,
                    details=self._merge_details(
                        payload.details,
                        operation="receive_stock",
                    ),
                )
            )

            movement_id = movement.id
            balance_id = balance.id

            self.db.commit()

            return self._reload_operation_result(
                organization_id=organization_id,
                movement_id=movement_id,
                balance_id=balance_id,
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                "The stock receipt could not be recorded.",
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def issue_stock(
        self,
        organization_id: uuid.UUID,
        payload: IssueInventoryStockSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> InventoryStockOperationResponse:
        """
        Issue unreserved stock from one location atomically.
        """

        item = self._get_item_or_404(
            organization_id=organization_id,
            item_id=payload.item_id,
        )

        self._get_location_or_404(
            organization_id=organization_id,
            location_id=payload.location_id,
        )

        if payload.work_order_id is not None:
            self._get_work_order_or_404(
                organization_id=organization_id,
                work_order_id=payload.work_order_id,
            )

        quantity = self._quantity(payload.quantity)
        occurred_at = payload.occurred_at or self._utc_now()

        try:
            balance = self._get_balance_for_update(
                organization_id=organization_id,
                item_id=item.id,
                location_id=payload.location_id,
                create_if_missing=False,
            )

            self._ensure_available_quantity(
                balance,
                quantity,
            )

            quantity_before = self._quantity(
                Decimal(balance.quantity_on_hand)
            )

            quantity_after = self._quantity(
                quantity_before - quantity
            )

            balance.quantity_on_hand = quantity_after
            balance.last_movement_at = occurred_at

            self.inventory.update_balance(balance)

            movement = self.inventory.create_movement(
                InventoryMovement(
                    organization_id=organization_id,
                    item_id=item.id,
                    location_id=payload.location_id,
                    work_order_id=payload.work_order_id,
                    movement_type="issue",
                    quantity=quantity,
                    quantity_delta=-quantity,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    unit_cost=self._cost(
                        Decimal(balance.average_unit_cost)
                    ),
                    currency=item.currency,
                    reference_type=payload.reference_type,
                    reference_id=payload.reference_id,
                    occurred_at=occurred_at,
                    notes=payload.notes,
                    created_by_user_id=actor_user_id,
                    details=self._merge_details(
                        payload.details,
                        operation="issue_stock",
                    ),
                )
            )

            movement_id = movement.id
            balance_id = balance.id

            self.db.commit()

            return self._reload_operation_result(
                organization_id=organization_id,
                movement_id=movement_id,
                balance_id=balance_id,
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                "The stock issue could not be recorded.",
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def return_stock(
        self,
        organization_id: uuid.UUID,
        payload: ReturnInventoryStockSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> InventoryStockOperationResponse:
        """
        Return stock to one location atomically.
        """

        item = self._get_item_or_404(
            organization_id=organization_id,
            item_id=payload.item_id,
        )

        self._get_location_or_404(
            organization_id=organization_id,
            location_id=payload.location_id,
        )

        if payload.work_order_id is not None:
            self._get_work_order_or_404(
                organization_id=organization_id,
                work_order_id=payload.work_order_id,
            )

        currency = self._resolve_currency(
            item,
            payload.currency,
        )

        quantity = self._quantity(payload.quantity)
        occurred_at = payload.occurred_at or self._utc_now()

        try:
            balance = self._get_balance_for_update(
                organization_id=organization_id,
                item_id=item.id,
                location_id=payload.location_id,
                create_if_missing=True,
            )

            quantity_before = self._quantity(
                Decimal(balance.quantity_on_hand)
            )

            fallback_cost = (
                Decimal(balance.average_unit_cost)
                if Decimal(balance.quantity_on_hand) > 0
                else Decimal(item.default_unit_cost)
            )

            unit_cost = self._cost(
                payload.unit_cost
                if payload.unit_cost is not None
                else fallback_cost
            )

            quantity_after = self._quantity(
                quantity_before + quantity
            )

            balance.quantity_on_hand = quantity_after
            balance.average_unit_cost = (
                self._weighted_average_cost(
                    existing_quantity=quantity_before,
                    existing_unit_cost=Decimal(
                        balance.average_unit_cost
                    ),
                    incoming_quantity=quantity,
                    incoming_unit_cost=unit_cost,
                )
            )
            balance.last_movement_at = occurred_at

            self.inventory.update_balance(balance)

            movement = self.inventory.create_movement(
                InventoryMovement(
                    organization_id=organization_id,
                    item_id=item.id,
                    location_id=payload.location_id,
                    work_order_id=payload.work_order_id,
                    movement_type="return",
                    quantity=quantity,
                    quantity_delta=quantity,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    unit_cost=unit_cost,
                    currency=currency,
                    reference_type=payload.reference_type,
                    reference_id=payload.reference_id,
                    occurred_at=occurred_at,
                    notes=payload.notes,
                    created_by_user_id=actor_user_id,
                    details=self._merge_details(
                        payload.details,
                        operation="return_stock",
                    ),
                )
            )

            movement_id = movement.id
            balance_id = balance.id

            self.db.commit()

            return self._reload_operation_result(
                organization_id=organization_id,
                movement_id=movement_id,
                balance_id=balance_id,
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                "The stock return could not be recorded.",
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def adjust_stock(
        self,
        organization_id: uuid.UUID,
        payload: AdjustInventoryStockSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> InventoryStockOperationResponse:
        """
        Apply a signed item-location stock adjustment.
        """

        item = self._get_item_or_404(
            organization_id=organization_id,
            item_id=payload.item_id,
        )

        self._get_location_or_404(
            organization_id=organization_id,
            location_id=payload.location_id,
        )

        currency = self._resolve_currency(
            item,
            payload.currency,
        )

        quantity_delta = self._quantity(
            payload.quantity_delta
        )

        occurred_at = payload.occurred_at or self._utc_now()
        is_increase = quantity_delta > 0

        try:
            balance = self._get_balance_for_update(
                organization_id=organization_id,
                item_id=item.id,
                location_id=payload.location_id,
                create_if_missing=is_increase,
            )

            if not is_increase:
                self._ensure_available_quantity(
                    balance,
                    abs(quantity_delta),
                )

            quantity_before = self._quantity(
                Decimal(balance.quantity_on_hand)
            )

            quantity_after = self._quantity(
                quantity_before + quantity_delta
            )

            if quantity_after < 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The adjustment would make on-hand "
                        "inventory negative."
                    ),
                )

            if is_increase:
                fallback_cost = (
                    Decimal(balance.average_unit_cost)
                    if Decimal(balance.quantity_on_hand) > 0
                    else Decimal(item.default_unit_cost)
                )

                unit_cost = self._cost(
                    payload.unit_cost
                    if payload.unit_cost is not None
                    else fallback_cost
                )

                balance.average_unit_cost = (
                    self._weighted_average_cost(
                        existing_quantity=quantity_before,
                        existing_unit_cost=Decimal(
                            balance.average_unit_cost
                        ),
                        incoming_quantity=quantity_delta,
                        incoming_unit_cost=unit_cost,
                    )
                )

                movement_type = "adjustment_in"

            else:
                unit_cost = self._cost(
                    Decimal(balance.average_unit_cost)
                )
                movement_type = "adjustment_out"

            balance.quantity_on_hand = quantity_after
            balance.last_movement_at = occurred_at

            self.inventory.update_balance(balance)

            movement = self.inventory.create_movement(
                InventoryMovement(
                    organization_id=organization_id,
                    item_id=item.id,
                    location_id=payload.location_id,
                    movement_type=movement_type,
                    quantity=abs(quantity_delta),
                    quantity_delta=quantity_delta,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    unit_cost=unit_cost,
                    currency=currency,
                    reference_type=payload.reference_type,
                    reference_id=payload.reference_id,
                    occurred_at=occurred_at,
                    notes=payload.notes,
                    created_by_user_id=actor_user_id,
                    details=self._merge_details(
                        payload.details,
                        operation="adjust_stock",
                    ),
                )
            )

            movement_id = movement.id
            balance_id = balance.id

            self.db.commit()

            return self._reload_operation_result(
                organization_id=organization_id,
                movement_id=movement_id,
                balance_id=balance_id,
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                "The stock adjustment could not be recorded.",
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def transfer_stock(
        self,
        organization_id: uuid.UUID,
        payload: TransferInventoryStockSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> InventoryTransferResponse:
        """
        Transfer available stock between locations atomically.
        """

        if (
            payload.source_location_id
            == payload.destination_location_id
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "Source and destination locations must "
                    "be different."
                ),
            )

        item = self._get_item_or_404(
            organization_id=organization_id,
            item_id=payload.item_id,
        )

        self._get_location_or_404(
            organization_id=organization_id,
            location_id=payload.source_location_id,
        )

        self._get_location_or_404(
            organization_id=organization_id,
            location_id=payload.destination_location_id,
        )

        if payload.work_order_id is not None:
            self._get_work_order_or_404(
                organization_id=organization_id,
                work_order_id=payload.work_order_id,
            )

        quantity = self._quantity(payload.quantity)
        occurred_at = payload.occurred_at or self._utc_now()
        transfer_group_id = uuid.uuid4()

        try:
            balances: dict[uuid.UUID, InventoryBalance] = {}

            for location_id in sorted(
                {
                    payload.source_location_id,
                    payload.destination_location_id,
                },
                key=str,
            ):
                balances[location_id] = (
                    self._get_balance_for_update(
                        organization_id=organization_id,
                        item_id=item.id,
                        location_id=location_id,
                        create_if_missing=(
                            location_id
                            == payload.destination_location_id
                        ),
                    )
                )

            source_balance = balances[
                payload.source_location_id
            ]

            destination_balance = balances[
                payload.destination_location_id
            ]

            self._ensure_available_quantity(
                source_balance,
                quantity,
            )

            source_before = self._quantity(
                Decimal(source_balance.quantity_on_hand)
            )

            source_after = self._quantity(
                source_before - quantity
            )

            destination_before = self._quantity(
                Decimal(
                    destination_balance.quantity_on_hand
                )
            )

            destination_after = self._quantity(
                destination_before + quantity
            )

            transfer_unit_cost = self._cost(
                Decimal(source_balance.average_unit_cost)
            )

            destination_balance.average_unit_cost = (
                self._weighted_average_cost(
                    existing_quantity=destination_before,
                    existing_unit_cost=Decimal(
                        destination_balance.average_unit_cost
                    ),
                    incoming_quantity=quantity,
                    incoming_unit_cost=transfer_unit_cost,
                )
            )

            source_balance.quantity_on_hand = source_after
            source_balance.last_movement_at = occurred_at

            destination_balance.quantity_on_hand = (
                destination_after
            )
            destination_balance.last_movement_at = occurred_at

            self.inventory.update_balance(source_balance)
            self.inventory.update_balance(destination_balance)

            common_details = self._merge_details(
                payload.details,
                operation="transfer_stock",
                source_location_id=str(
                    payload.source_location_id
                ),
                destination_location_id=str(
                    payload.destination_location_id
                ),
            )

            outbound_movement, inbound_movement = (
                self.inventory.create_movements(
                    [
                        InventoryMovement(
                            organization_id=organization_id,
                            item_id=item.id,
                            location_id=(
                                payload.source_location_id
                            ),
                            work_order_id=(
                                payload.work_order_id
                            ),
                            movement_type="transfer_out",
                            quantity=quantity,
                            quantity_delta=-quantity,
                            quantity_before=source_before,
                            quantity_after=source_after,
                            unit_cost=transfer_unit_cost,
                            currency=item.currency,
                            reference_type=(
                                payload.reference_type
                            ),
                            reference_id=payload.reference_id,
                            transfer_group_id=transfer_group_id,
                            occurred_at=occurred_at,
                            notes=payload.notes,
                            created_by_user_id=actor_user_id,
                            details=common_details,
                        ),
                        InventoryMovement(
                            organization_id=organization_id,
                            item_id=item.id,
                            location_id=(
                                payload.destination_location_id
                            ),
                            work_order_id=(
                                payload.work_order_id
                            ),
                            movement_type="transfer_in",
                            quantity=quantity,
                            quantity_delta=quantity,
                            quantity_before=destination_before,
                            quantity_after=destination_after,
                            unit_cost=transfer_unit_cost,
                            currency=item.currency,
                            reference_type=(
                                payload.reference_type
                            ),
                            reference_id=payload.reference_id,
                            transfer_group_id=transfer_group_id,
                            occurred_at=occurred_at,
                            notes=payload.notes,
                            created_by_user_id=actor_user_id,
                            details=common_details,
                        ),
                    ]
                )
            )

            outbound_id = outbound_movement.id
            inbound_id = inbound_movement.id
            source_balance_id = source_balance.id
            destination_balance_id = destination_balance.id

            self.db.commit()

            return InventoryTransferResponse(
                transfer_group_id=transfer_group_id,
                outbound_movement=(
                    self._get_movement_or_404(
                        organization_id=organization_id,
                        movement_id=outbound_id,
                    )
                ),
                inbound_movement=(
                    self._get_movement_or_404(
                        organization_id=organization_id,
                        movement_id=inbound_id,
                    )
                ),
                source_balance=self._get_balance_or_404(
                    organization_id=organization_id,
                    balance_id=source_balance_id,
                ),
                destination_balance=(
                    self._get_balance_or_404(
                        organization_id=organization_id,
                        balance_id=destination_balance_id,
                    )
                ),
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                "The stock transfer could not be recorded.",
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    # ------------------------------------------------------------------
    # Movement ledger queries
    # ------------------------------------------------------------------

    def list_movements(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        movement_type: str | None = None,
        item_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        work_order_id: uuid.UUID | None = None,
        reservation_id: uuid.UUID | None = None,
        transfer_group_id: uuid.UUID | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> InventoryMovementListResponse:
        """
        Return paginated immutable movement-ledger entries.
        """

        self._validate_date_range(
            occurred_from,
            occurred_to,
        )

        movements = (
            self.inventory.list_movements_for_organization(
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                movement_type=movement_type,
                item_id=item_id,
                location_id=location_id,
                work_order_id=work_order_id,
                reservation_id=reservation_id,
                transfer_group_id=transfer_group_id,
                reference_type=reference_type,
                reference_id=reference_id,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
            )
        )

        total = (
            self.inventory.count_movements_for_organization(
                organization_id=organization_id,
                movement_type=movement_type,
                item_id=item_id,
                location_id=location_id,
                work_order_id=work_order_id,
                reservation_id=reservation_id,
                transfer_group_id=transfer_group_id,
                reference_type=reference_type,
                reference_id=reference_id,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
            )
        )

        return InventoryMovementListResponse(
            items=movements,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_movement(
        self,
        organization_id: uuid.UUID,
        movement_id: uuid.UUID,
    ) -> InventoryMovement:
        """
        Return one immutable stock movement.
        """

        return self._get_movement_or_404(
            organization_id=organization_id,
            movement_id=movement_id,
        )

    # ------------------------------------------------------------------
    # Reservations
    # ------------------------------------------------------------------

    def create_reservation(
        self,
        organization_id: uuid.UUID,
        payload: CreateInventoryReservationSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> InventoryReservationOperationResponse:
        """
        Reserve currently available stock for a work order.
        """

        item = self._get_item_or_404(
            organization_id=organization_id,
            item_id=payload.item_id,
        )

        self._get_location_or_404(
            organization_id=organization_id,
            location_id=payload.location_id,
        )

        self._get_work_order_or_404(
            organization_id=organization_id,
            work_order_id=payload.work_order_id,
            require_mutable=True,
        )

        now = self._utc_now()

        if (
            payload.expires_at is not None
            and payload.expires_at <= now
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail="expires_at must be in the future.",
            )

        quantity = self._quantity(payload.quantity)

        try:
            balance = self._get_balance_for_update(
                organization_id=organization_id,
                item_id=item.id,
                location_id=payload.location_id,
                create_if_missing=False,
            )

            self._ensure_available_quantity(
                balance,
                quantity,
            )

            balance.quantity_reserved = self._quantity(
                Decimal(balance.quantity_reserved)
                + quantity
            )

            self.inventory.update_balance(balance)

            reservation = self.inventory.create_reservation(
                InventoryReservation(
                    organization_id=organization_id,
                    item_id=item.id,
                    location_id=payload.location_id,
                    work_order_id=payload.work_order_id,
                    quantity_reserved=quantity,
                    quantity_consumed=Decimal("0"),
                    status="active",
                    reserved_at=now,
                    expires_at=payload.expires_at,
                    notes=payload.notes,
                    created_by_user_id=actor_user_id,
                    updated_by_user_id=actor_user_id,
                    details=self._merge_details(
                        payload.details,
                        operation="reserve_stock",
                    ),
                    is_active=True,
                )
            )

            reservation_id = reservation.id
            balance_id = balance.id

            self.db.commit()

            return InventoryReservationOperationResponse(
                reservation=self._get_reservation_or_404(
                    organization_id=organization_id,
                    reservation_id=reservation_id,
                ),
                balance=self._get_balance_or_404(
                    organization_id=organization_id,
                    balance_id=balance_id,
                ),
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                "The inventory reservation could not be created.",
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def list_reservations(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        status_filter: str | None = None,
        item_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        work_order_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> InventoryReservationListResponse:
        """
        Return paginated organization stock reservations.
        """

        reservations = (
            self.inventory.list_reservations_for_organization(
                organization_id=organization_id,
                skip=skip,
                limit=limit,
                status_filter=status_filter,
                item_id=item_id,
                location_id=location_id,
                work_order_id=work_order_id,
                include_inactive=include_inactive,
            )
        )

        total = (
            self.inventory.count_reservations_for_organization(
                organization_id=organization_id,
                status_filter=status_filter,
                item_id=item_id,
                location_id=location_id,
                work_order_id=work_order_id,
                include_inactive=include_inactive,
            )
        )

        return InventoryReservationListResponse(
            items=reservations,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_reservation(
        self,
        organization_id: uuid.UUID,
        reservation_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> InventoryReservation:
        """
        Return one organization stock reservation.
        """

        return self._get_reservation_or_404(
            organization_id=organization_id,
            reservation_id=reservation_id,
            include_inactive=include_inactive,
        )

    def consume_reservation(
        self,
        organization_id: uuid.UUID,
        reservation_id: uuid.UUID,
        payload: ConsumeInventoryReservationSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> InventoryReservationConsumptionResponse:
        """
        Consume some or all remaining reserved stock.
        """

        now = self._utc_now()
        occurred_at = payload.occurred_at or now

        try:
            reservation = self._get_reservation_or_404(
                organization_id=organization_id,
                reservation_id=reservation_id,
                for_update=True,
            )

            if reservation.status not in (
                ACTIVE_RESERVATION_STATUSES
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Only active or partially consumed "
                        "reservations can be consumed."
                    ),
                )

            if (
                reservation.expires_at is not None
                and reservation.expires_at <= now
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This reservation has expired and must "
                        "be released before it can be replaced."
                    ),
                )

            remaining_quantity = self._quantity(
                Decimal(reservation.remaining_quantity)
            )

            quantity = (
                remaining_quantity
                if payload.quantity is None
                else self._quantity(payload.quantity)
            )

            if quantity > remaining_quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The requested consumption exceeds the "
                        "reservation's remaining quantity."
                    ),
                )

            balance = self._get_balance_for_update(
                organization_id=organization_id,
                item_id=reservation.item_id,
                location_id=reservation.location_id,
                create_if_missing=False,
            )

            if Decimal(balance.quantity_reserved) < quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The balance no longer contains enough "
                        "reserved quantity for this reservation."
                    ),
                )

            if Decimal(balance.quantity_on_hand) < quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The balance no longer contains enough "
                        "on-hand quantity for this reservation."
                    ),
                )

            quantity_before = self._quantity(
                Decimal(balance.quantity_on_hand)
            )

            quantity_after = self._quantity(
                quantity_before - quantity
            )

            balance.quantity_on_hand = quantity_after
            balance.quantity_reserved = self._quantity(
                Decimal(balance.quantity_reserved)
                - quantity
            )
            balance.last_movement_at = occurred_at

            self.inventory.update_balance(balance)

            reservation.quantity_consumed = self._quantity(
                Decimal(reservation.quantity_consumed)
                + quantity
            )

            if (
                Decimal(reservation.quantity_consumed)
                == Decimal(reservation.quantity_reserved)
            ):
                reservation.status = "consumed"
                reservation.consumed_at = now
            else:
                reservation.status = "partially_consumed"

            reservation.updated_by_user_id = actor_user_id

            if payload.notes is not None:
                reservation.notes = payload.notes

            reservation.details = self._merge_details(
                {
                    **(reservation.details or {}),
                    **payload.details,
                },
                last_operation="consume_reservation",
                last_consumed_quantity=str(quantity),
            )

            self.inventory.update_reservation(reservation)

            movement = self.inventory.create_movement(
                InventoryMovement(
                    organization_id=organization_id,
                    item_id=reservation.item_id,
                    location_id=reservation.location_id,
                    work_order_id=reservation.work_order_id,
                    reservation_id=reservation.id,
                    movement_type="issue",
                    quantity=quantity,
                    quantity_delta=-quantity,
                    quantity_before=quantity_before,
                    quantity_after=quantity_after,
                    unit_cost=self._cost(
                        Decimal(balance.average_unit_cost)
                    ),
                    currency=reservation.item.currency,
                    reference_type="inventory_reservation",
                    reference_id=str(reservation.id),
                    occurred_at=occurred_at,
                    notes=payload.notes,
                    created_by_user_id=actor_user_id,
                    details=self._merge_details(
                        payload.details,
                        operation="consume_reservation",
                    ),
                )
            )

            persisted_reservation_id = reservation.id
            movement_id = movement.id
            balance_id = balance.id

            self.db.commit()

            return InventoryReservationConsumptionResponse(
                reservation=self._get_reservation_or_404(
                    organization_id=organization_id,
                    reservation_id=(
                        persisted_reservation_id
                    ),
                ),
                movement=self._get_movement_or_404(
                    organization_id=organization_id,
                    movement_id=movement_id,
                ),
                balance=self._get_balance_or_404(
                    organization_id=organization_id,
                    balance_id=balance_id,
                ),
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                "The reservation consumption could not be saved.",
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)

    def release_reservation(
        self,
        organization_id: uuid.UUID,
        reservation_id: uuid.UUID,
        payload: ReleaseInventoryReservationSchema,
        *,
        actor_user_id: uuid.UUID,
    ) -> InventoryReservationOperationResponse:
        """
        Release all remaining stock held by a reservation.
        """

        now = self._utc_now()

        try:
            reservation = self._get_reservation_or_404(
                organization_id=organization_id,
                reservation_id=reservation_id,
                for_update=True,
            )

            if reservation.status not in (
                ACTIVE_RESERVATION_STATUSES
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Only active or partially consumed "
                        "reservations can be released."
                    ),
                )

            remaining_quantity = self._quantity(
                Decimal(reservation.remaining_quantity)
            )

            if remaining_quantity <= 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This reservation has no remaining "
                        "quantity to release."
                    ),
                )

            balance = self._get_balance_for_update(
                organization_id=organization_id,
                item_id=reservation.item_id,
                location_id=reservation.location_id,
                create_if_missing=False,
            )

            if (
                Decimal(balance.quantity_reserved)
                < remaining_quantity
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The balance's reserved quantity is "
                        "inconsistent with this reservation."
                    ),
                )

            balance.quantity_reserved = self._quantity(
                Decimal(balance.quantity_reserved)
                - remaining_quantity
            )

            self.inventory.update_balance(balance)

            reservation.status = "released"
            reservation.released_at = now
            reservation.updated_by_user_id = actor_user_id

            if payload.notes is not None:
                reservation.notes = payload.notes

            reservation.details = self._merge_details(
                {
                    **(reservation.details or {}),
                    **payload.details,
                },
                last_operation="release_reservation",
                released_quantity=str(remaining_quantity),
            )

            self.inventory.update_reservation(reservation)

            persisted_reservation_id = reservation.id
            balance_id = balance.id

            self.db.commit()

            return InventoryReservationOperationResponse(
                reservation=self._get_reservation_or_404(
                    organization_id=organization_id,
                    reservation_id=(
                        persisted_reservation_id
                    ),
                ),
                balance=self._get_balance_or_404(
                    organization_id=organization_id,
                    balance_id=balance_id,
                ),
            )

        except IntegrityError as exc:
            self._rollback_and_raise_conflict(
                exc,
                "The reservation release could not be saved.",
            )

        except SQLAlchemyError as exc:
            self._rollback_and_reraise(exc)
