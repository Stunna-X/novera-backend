"""
Inventory repository.

Provides organization-scoped persistence and query operations for
inventory locations, catalogue items, stock balances, reservations,
and the immutable movement ledger.

Inventory mutations flush without committing so the service layer can
lock balances and persist all related records atomically.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import (
    Query,
    Session,
    selectinload,
)

from app.models.inventory import (
    InventoryBalance,
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    InventoryReservation,
)
from app.repositories.base import BaseRepository


ACTIVE_RESERVATION_STATUSES = (
    "active",
    "partially_consumed",
)


@dataclass(frozen=True, slots=True)
class LowStockRecord:
    """
    Aggregated low-stock result for one inventory item.
    """

    item: InventoryItem
    quantity_on_hand: Decimal
    quantity_reserved: Decimal
    available_quantity: Decimal


class InventoryRepository(
    BaseRepository[InventoryItem]
):
    """
    Repository for the organization-scoped inventory domain.

    Stock-changing workflows must retrieve balances with
    ``for_update=True`` before changing quantities.
    """

    def __init__(
        self,
        db: Session,
    ):
        super().__init__(
            db,
            InventoryItem,
        )

    @staticmethod
    def _item_options():
        """
        Return eager-loading options used by item responses.
        """

        return (
            selectinload(
                InventoryItem.balances
            ).selectinload(
                InventoryBalance.location
            ),
        )

    @staticmethod
    def _normalize_optional_text(
        value: str | None,
    ) -> str | None:
        """
        Strip optional text and convert blank values to null.
        """

        if value is None:
            return None

        normalized = value.strip()

        return normalized or None

    @classmethod
    def _normalize_location(
        cls,
        location: InventoryLocation,
    ) -> None:
        """
        Normalize mutable inventory-location fields.
        """

        location.code = location.code.strip().upper()
        location.name = location.name.strip()
        location.location_type = (
            location.location_type.strip().lower()
        )
        location.address = cls._normalize_optional_text(
            location.address
        )
        location.notes = cls._normalize_optional_text(
            location.notes
        )

    @classmethod
    def _normalize_item(
        cls,
        item: InventoryItem,
    ) -> None:
        """
        Normalize mutable inventory-item fields.
        """

        item.sku = item.sku.strip().upper()
        item.barcode = cls._normalize_optional_text(
            item.barcode
        )
        item.name = item.name.strip()
        item.item_type = item.item_type.strip().lower()
        item.category = cls._normalize_optional_text(
            item.category
        )
        item.description = cls._normalize_optional_text(
            item.description
        )
        item.unit_of_measure = (
            item.unit_of_measure.strip().lower()
        )
        item.currency = item.currency.strip().upper()
        item.preferred_supplier = (
            cls._normalize_optional_text(
                item.preferred_supplier
            )
        )

    @classmethod
    def _normalize_reservation(
        cls,
        reservation: InventoryReservation,
    ) -> None:
        """
        Normalize mutable inventory-reservation fields.
        """

        reservation.status = (
            reservation.status.strip().lower()
        )
        reservation.notes = cls._normalize_optional_text(
            reservation.notes
        )

    @classmethod
    def _normalize_movement(
        cls,
        movement: InventoryMovement,
    ) -> None:
        """
        Normalize immutable movement fields before insertion.
        """

        movement.movement_type = (
            movement.movement_type.strip().lower()
        )
        movement.currency = movement.currency.strip().upper()
        movement.reference_type = (
            cls._normalize_optional_text(
                movement.reference_type
            )
        )
        movement.reference_id = (
            cls._normalize_optional_text(
                movement.reference_id
            )
        )
        movement.notes = cls._normalize_optional_text(
            movement.notes
        )

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------

    def create_location(
        self,
        location: InventoryLocation,
    ) -> InventoryLocation:
        """
        Add an inventory location to the current transaction.
        """

        self._normalize_location(location)

        self.db.add(location)
        self.db.flush()

        return location

    def update_location(
        self,
        location: InventoryLocation,
    ) -> InventoryLocation:
        """
        Flush inventory-location changes.
        """

        self._normalize_location(location)

        self.db.add(location)
        self.db.flush()

        return location

    def get_location_for_organization(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> InventoryLocation | None:
        """
        Retrieve one organization inventory location.
        """

        query = (
            self.db.query(InventoryLocation)
            .populate_existing()
            .filter(
                InventoryLocation.id == location_id,
                InventoryLocation.organization_id
                == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                InventoryLocation.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=InventoryLocation
            )

        return query.first()

    def list_locations_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        location_type: str | None = None,
        include_inactive: bool = False,
    ) -> list[InventoryLocation]:
        """
        List organization inventory locations.
        """

        query = self._location_list_query(
            organization_id=organization_id,
            search=search,
            location_type=location_type,
            include_inactive=include_inactive,
        )

        return (
            query.order_by(
                InventoryLocation.name.asc(),
                InventoryLocation.code.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_locations_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        location_type: str | None = None,
        include_inactive: bool = False,
    ) -> int:
        """
        Count organization inventory locations.
        """

        query = self._location_list_query(
            organization_id=organization_id,
            search=search,
            location_type=location_type,
            include_inactive=include_inactive,
            count_only=True,
        )

        return int(query.scalar() or 0)

    def _location_list_query(
        self,
        *,
        organization_id: uuid.UUID,
        search: str | None,
        location_type: str | None,
        include_inactive: bool,
        count_only: bool = False,
    ) -> Query:
        """
        Build the shared inventory-location list query.
        """

        if count_only:
            query = self.db.query(
                func.count(InventoryLocation.id)
            )
        else:
            query = self.db.query(InventoryLocation)

        query = query.filter(
            InventoryLocation.organization_id
            == organization_id
        )

        if not include_inactive:
            query = query.filter(
                InventoryLocation.is_active.is_(True)
            )

        if location_type:
            query = query.filter(
                InventoryLocation.location_type
                == location_type.strip().lower()
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
                    InventoryLocation.code.ilike(pattern),
                    InventoryLocation.name.ilike(pattern),
                    InventoryLocation.address.ilike(pattern),
                    InventoryLocation.notes.ilike(pattern),
                )
            )

        return query

    def location_code_exists(
        self,
        organization_id: uuid.UUID,
        code: str,
        *,
        exclude_location_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check location-code uniqueness inside an organization.
        """

        normalized_code = code.strip().lower()

        query = self.db.query(
            InventoryLocation.id
        ).filter(
            InventoryLocation.organization_id
            == organization_id,
            func.lower(InventoryLocation.code)
            == normalized_code,
        )

        if exclude_location_id is not None:
            query = query.filter(
                InventoryLocation.id
                != exclude_location_id
            )

        return query.first() is not None

    def location_has_stock(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> bool:
        """
        Return whether a location has on-hand or reserved stock.
        """

        return (
            self.db.query(InventoryBalance.id)
            .filter(
                InventoryBalance.organization_id
                == organization_id,
                InventoryBalance.location_id
                == location_id,
                or_(
                    InventoryBalance.quantity_on_hand
                    > Decimal("0"),
                    InventoryBalance.quantity_reserved
                    > Decimal("0"),
                ),
            )
            .first()
            is not None
        )

    def location_has_active_reservations(
        self,
        organization_id: uuid.UUID,
        location_id: uuid.UUID,
    ) -> bool:
        """
        Return whether a location has an active reservation.
        """

        return (
            self.db.query(InventoryReservation.id)
            .filter(
                InventoryReservation.organization_id
                == organization_id,
                InventoryReservation.location_id
                == location_id,
                InventoryReservation.status.in_(
                    ACTIVE_RESERVATION_STATUSES
                ),
                InventoryReservation.is_active.is_(True),
            )
            .first()
            is not None
        )

    def deactivate_location(
        self,
        location: InventoryLocation,
    ) -> InventoryLocation:
        """
        Soft-delete an inventory location.
        """

        location.is_active = False

        return self.update_location(location)

    def reactivate_location(
        self,
        location: InventoryLocation,
    ) -> InventoryLocation:
        """
        Reactivate an inventory location.
        """

        location.is_active = True

        return self.update_location(location)

    # ------------------------------------------------------------------
    # Catalogue items
    # ------------------------------------------------------------------

    def create_item(
        self,
        item: InventoryItem,
    ) -> InventoryItem:
        """
        Add an inventory catalogue item to the transaction.
        """

        self._normalize_item(item)

        self.db.add(item)
        self.db.flush()

        return item

    def update_item(
        self,
        item: InventoryItem,
    ) -> InventoryItem:
        """
        Flush inventory-item changes.
        """

        self._normalize_item(item)

        self.db.add(item)
        self.db.flush()

        return item

    def get_item_for_organization(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> InventoryItem | None:
        """
        Retrieve one organization inventory item.
        """

        query = (
            self.db.query(InventoryItem)
            .options(*self._item_options())
            .populate_existing()
            .filter(
                InventoryItem.id == item_id,
                InventoryItem.organization_id
                == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                InventoryItem.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=InventoryItem
            )

        return query.first()

    def list_items_for_organization(
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
    ) -> list[InventoryItem]:
        """
        List organization inventory catalogue items.
        """

        query = self._item_list_query(
            organization_id=organization_id,
            search=search,
            item_type=item_type,
            category=category,
            location_id=location_id,
            include_inactive=include_inactive,
        ).options(*self._item_options())

        return (
            query.order_by(
                InventoryItem.name.asc(),
                InventoryItem.sku.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_items_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        item_type: str | None = None,
        category: str | None = None,
        location_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> int:
        """
        Count organization inventory catalogue items.
        """

        query = self._item_list_query(
            organization_id=organization_id,
            search=search,
            item_type=item_type,
            category=category,
            location_id=location_id,
            include_inactive=include_inactive,
            count_only=True,
        )

        return int(query.scalar() or 0)

    def _item_list_query(
        self,
        *,
        organization_id: uuid.UUID,
        search: str | None,
        item_type: str | None,
        category: str | None,
        location_id: uuid.UUID | None,
        include_inactive: bool,
        count_only: bool = False,
    ) -> Query:
        """
        Build the shared inventory-item list query.
        """

        if count_only:
            query = self.db.query(
                func.count(
                    func.distinct(InventoryItem.id)
                )
            )
        else:
            query = self.db.query(InventoryItem)

        if location_id is not None:
            query = query.join(
                InventoryBalance,
                and_(
                    InventoryBalance.item_id
                    == InventoryItem.id,
                    InventoryBalance.organization_id
                    == organization_id,
                    InventoryBalance.location_id
                    == location_id,
                ),
            )

        query = query.filter(
            InventoryItem.organization_id
            == organization_id
        )

        if not include_inactive:
            query = query.filter(
                InventoryItem.is_active.is_(True)
            )

        if item_type:
            query = query.filter(
                InventoryItem.item_type
                == item_type.strip().lower()
            )

        if category:
            query = query.filter(
                func.lower(InventoryItem.category)
                == category.strip().lower()
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
                    InventoryItem.sku.ilike(pattern),
                    InventoryItem.barcode.ilike(pattern),
                    InventoryItem.name.ilike(pattern),
                    InventoryItem.category.ilike(pattern),
                    InventoryItem.description.ilike(pattern),
                    InventoryItem.preferred_supplier.ilike(
                        pattern
                    ),
                )
            )

        return query

    def sku_exists(
        self,
        organization_id: uuid.UUID,
        sku: str,
        *,
        exclude_item_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check SKU uniqueness inside an organization.
        """

        normalized_sku = sku.strip().lower()

        query = self.db.query(
            InventoryItem.id
        ).filter(
            InventoryItem.organization_id
            == organization_id,
            func.lower(InventoryItem.sku)
            == normalized_sku,
        )

        if exclude_item_id is not None:
            query = query.filter(
                InventoryItem.id != exclude_item_id
            )

        return query.first() is not None

    def barcode_exists(
        self,
        organization_id: uuid.UUID,
        barcode: str,
        *,
        exclude_item_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check barcode uniqueness inside an organization.
        """

        normalized_barcode = barcode.strip().lower()

        query = self.db.query(
            InventoryItem.id
        ).filter(
            InventoryItem.organization_id
            == organization_id,
            func.lower(InventoryItem.barcode)
            == normalized_barcode,
        )

        if exclude_item_id is not None:
            query = query.filter(
                InventoryItem.id != exclude_item_id
            )

        return query.first() is not None

    def item_has_stock(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> bool:
        """
        Return whether an item has on-hand or reserved stock.
        """

        return (
            self.db.query(InventoryBalance.id)
            .filter(
                InventoryBalance.organization_id
                == organization_id,
                InventoryBalance.item_id == item_id,
                or_(
                    InventoryBalance.quantity_on_hand
                    > Decimal("0"),
                    InventoryBalance.quantity_reserved
                    > Decimal("0"),
                ),
            )
            .first()
            is not None
        )

    def item_has_active_reservations(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> bool:
        """
        Return whether an item has an active reservation.
        """

        return (
            self.db.query(InventoryReservation.id)
            .filter(
                InventoryReservation.organization_id
                == organization_id,
                InventoryReservation.item_id == item_id,
                InventoryReservation.status.in_(
                    ACTIVE_RESERVATION_STATUSES
                ),
                InventoryReservation.is_active.is_(True),
            )
            .first()
            is not None
        )

    def deactivate_item(
        self,
        item: InventoryItem,
    ) -> InventoryItem:
        """
        Soft-delete an inventory catalogue item.
        """

        item.is_active = False

        return self.update_item(item)

    def reactivate_item(
        self,
        item: InventoryItem,
    ) -> InventoryItem:
        """
        Reactivate an inventory catalogue item.
        """

        item.is_active = True

        return self.update_item(item)

    # ------------------------------------------------------------------
    # Balances
    # ------------------------------------------------------------------

    def create_balance(
        self,
        balance: InventoryBalance,
    ) -> InventoryBalance:
        """
        Add a stock balance to the current transaction.
        """

        self.db.add(balance)
        self.db.flush()

        return balance

    def update_balance(
        self,
        balance: InventoryBalance,
    ) -> InventoryBalance:
        """
        Flush stock-balance changes.
        """

        self.db.add(balance)
        self.db.flush()

        return balance

    def get_balance_for_organization(
        self,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        location_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> InventoryBalance | None:
        """
        Retrieve one item-location stock balance.
        """

        query = (
            self.db.query(InventoryBalance)
            .populate_existing()
            .filter(
                InventoryBalance.organization_id
                == organization_id,
                InventoryBalance.item_id == item_id,
                InventoryBalance.location_id
                == location_id,
            )
        )

        if for_update:
            query = query.with_for_update(
                of=InventoryBalance
            )

        return query.first()

    def get_balance_by_id_for_organization(
        self,
        organization_id: uuid.UUID,
        balance_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> InventoryBalance | None:
        """
        Retrieve one balance by its primary key.
        """

        query = (
            self.db.query(InventoryBalance)
            .populate_existing()
            .filter(
                InventoryBalance.id == balance_id,
                InventoryBalance.organization_id
                == organization_id,
            )
        )

        if for_update:
            query = query.with_for_update(
                of=InventoryBalance
            )

        return query.first()

    def list_balances_for_organization(
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
    ) -> list[InventoryBalance]:
        """
        List organization item-location balances.
        """

        query = self._balance_list_query(
            organization_id=organization_id,
            search=search,
            item_id=item_id,
            location_id=location_id,
            in_stock_only=in_stock_only,
            include_inactive_catalogue=(
                include_inactive_catalogue
            ),
        )

        return (
            query.order_by(
                InventoryLocation.name.asc(),
                InventoryItem.name.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_balances_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        item_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        in_stock_only: bool = False,
        include_inactive_catalogue: bool = False,
    ) -> int:
        """
        Count organization item-location balances.
        """

        query = self._balance_list_query(
            organization_id=organization_id,
            search=search,
            item_id=item_id,
            location_id=location_id,
            in_stock_only=in_stock_only,
            include_inactive_catalogue=(
                include_inactive_catalogue
            ),
            count_only=True,
        )

        return int(query.scalar() or 0)

    def _balance_list_query(
        self,
        *,
        organization_id: uuid.UUID,
        search: str | None,
        item_id: uuid.UUID | None,
        location_id: uuid.UUID | None,
        in_stock_only: bool,
        include_inactive_catalogue: bool,
        count_only: bool = False,
    ) -> Query:
        """
        Build the shared balance list query.
        """

        if count_only:
            query = self.db.query(
                func.count(InventoryBalance.id)
            )
        else:
            query = self.db.query(InventoryBalance)

        query = (
            query.join(
                InventoryItem,
                InventoryItem.id
                == InventoryBalance.item_id,
            )
            .join(
                InventoryLocation,
                InventoryLocation.id
                == InventoryBalance.location_id,
            )
            .filter(
                InventoryBalance.organization_id
                == organization_id,
                InventoryItem.organization_id
                == organization_id,
                InventoryLocation.organization_id
                == organization_id,
            )
        )

        if not include_inactive_catalogue:
            query = query.filter(
                InventoryItem.is_active.is_(True),
                InventoryLocation.is_active.is_(True),
            )

        if item_id is not None:
            query = query.filter(
                InventoryBalance.item_id == item_id
            )

        if location_id is not None:
            query = query.filter(
                InventoryBalance.location_id
                == location_id
            )

        if in_stock_only:
            query = query.filter(
                InventoryBalance.quantity_on_hand
                > Decimal("0")
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
                    InventoryItem.sku.ilike(pattern),
                    InventoryItem.barcode.ilike(pattern),
                    InventoryItem.name.ilike(pattern),
                    InventoryItem.category.ilike(pattern),
                    InventoryLocation.code.ilike(pattern),
                    InventoryLocation.name.ilike(pattern),
                )
            )

        return query

    # ------------------------------------------------------------------
    # Low-stock reporting
    # ------------------------------------------------------------------

    def list_low_stock_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        item_type: str | None = None,
        category: str | None = None,
        location_id: uuid.UUID | None = None,
    ) -> list[LowStockRecord]:
        """
        List active items at or below their reorder level.
        """

        query = self._low_stock_query(
            organization_id=organization_id,
            search=search,
            item_type=item_type,
            category=category,
            location_id=location_id,
        )

        rows = (
            query.order_by(
                (
                    InventoryItem.reorder_level
                    - query.column_descriptions[3][
                        "expr"
                    ]
                ).desc(),
                InventoryItem.name.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

        return [
            LowStockRecord(
                item=row[0],
                quantity_on_hand=Decimal(row[1] or 0),
                quantity_reserved=Decimal(row[2] or 0),
                available_quantity=Decimal(row[3] or 0),
            )
            for row in rows
        ]

    def count_low_stock_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        item_type: str | None = None,
        category: str | None = None,
        location_id: uuid.UUID | None = None,
    ) -> int:
        """
        Count active items at or below their reorder level.
        """

        query = self._low_stock_query(
            organization_id=organization_id,
            search=search,
            item_type=item_type,
            category=category,
            location_id=location_id,
        )

        return int(
            query.order_by(None).count()
        )

    def _low_stock_query(
        self,
        *,
        organization_id: uuid.UUID,
        search: str | None,
        item_type: str | None,
        category: str | None,
        location_id: uuid.UUID | None,
    ) -> Query:
        """
        Build an item-level low-stock aggregation query.
        """

        balance_query = (
            self.db.query(
                InventoryBalance.item_id.label("item_id"),
                func.coalesce(
                    func.sum(
                        InventoryBalance.quantity_on_hand
                    ),
                    Decimal("0"),
                ).label("quantity_on_hand"),
                func.coalesce(
                    func.sum(
                        InventoryBalance.quantity_reserved
                    ),
                    Decimal("0"),
                ).label("quantity_reserved"),
            )
            .join(
                InventoryLocation,
                and_(
                    InventoryLocation.id
                    == InventoryBalance.location_id,
                    InventoryLocation.organization_id
                    == organization_id,
                    InventoryLocation.is_active.is_(True),
                ),
            )
            .filter(
                InventoryBalance.organization_id
                == organization_id
            )
        )

        if location_id is not None:
            balance_query = balance_query.filter(
                InventoryBalance.location_id
                == location_id
            )

        balance_totals = (
            balance_query.group_by(
                InventoryBalance.item_id
            ).subquery()
        )

        quantity_on_hand = func.coalesce(
            balance_totals.c.quantity_on_hand,
            Decimal("0"),
        ).label("quantity_on_hand")

        quantity_reserved = func.coalesce(
            balance_totals.c.quantity_reserved,
            Decimal("0"),
        ).label("quantity_reserved")

        available_quantity = (
            func.coalesce(
                balance_totals.c.quantity_on_hand,
                Decimal("0"),
            )
            - func.coalesce(
                balance_totals.c.quantity_reserved,
                Decimal("0"),
            )
        ).label("available_quantity")

        query = (
            self.db.query(
                InventoryItem,
                quantity_on_hand,
                quantity_reserved,
                available_quantity,
            )
            .outerjoin(
                balance_totals,
                balance_totals.c.item_id
                == InventoryItem.id,
            )
            .filter(
                InventoryItem.organization_id
                == organization_id,
                InventoryItem.is_active.is_(True),
                available_quantity
                <= InventoryItem.reorder_level,
            )
        )

        if item_type:
            query = query.filter(
                InventoryItem.item_type
                == item_type.strip().lower()
            )

        if category:
            query = query.filter(
                func.lower(InventoryItem.category)
                == category.strip().lower()
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
                    InventoryItem.sku.ilike(pattern),
                    InventoryItem.barcode.ilike(pattern),
                    InventoryItem.name.ilike(pattern),
                    InventoryItem.category.ilike(pattern),
                    InventoryItem.description.ilike(pattern),
                )
            )

        return query

    # ------------------------------------------------------------------
    # Reservations
    # ------------------------------------------------------------------

    def create_reservation(
        self,
        reservation: InventoryReservation,
    ) -> InventoryReservation:
        """
        Add a stock reservation to the transaction.
        """

        self._normalize_reservation(reservation)

        self.db.add(reservation)
        self.db.flush()

        return reservation

    def update_reservation(
        self,
        reservation: InventoryReservation,
    ) -> InventoryReservation:
        """
        Flush reservation changes.
        """

        self._normalize_reservation(reservation)

        self.db.add(reservation)
        self.db.flush()

        return reservation

    def get_reservation_for_organization(
        self,
        organization_id: uuid.UUID,
        reservation_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> InventoryReservation | None:
        """
        Retrieve one organization stock reservation.
        """

        query = (
            self.db.query(InventoryReservation)
            .populate_existing()
            .filter(
                InventoryReservation.id
                == reservation_id,
                InventoryReservation.organization_id
                == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                InventoryReservation.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=InventoryReservation
            )

        return query.first()

    def list_reservations_for_organization(
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
    ) -> list[InventoryReservation]:
        """
        List organization stock reservations.
        """

        query = self._reservation_list_query(
            organization_id=organization_id,
            status_filter=status_filter,
            item_id=item_id,
            location_id=location_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
        )

        return (
            query.order_by(
                InventoryReservation.created_at.desc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_reservations_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        status_filter: str | None = None,
        item_id: uuid.UUID | None = None,
        location_id: uuid.UUID | None = None,
        work_order_id: uuid.UUID | None = None,
        include_inactive: bool = False,
    ) -> int:
        """
        Count organization stock reservations.
        """

        query = self._reservation_list_query(
            organization_id=organization_id,
            status_filter=status_filter,
            item_id=item_id,
            location_id=location_id,
            work_order_id=work_order_id,
            include_inactive=include_inactive,
            count_only=True,
        )

        return int(query.scalar() or 0)

    def _reservation_list_query(
        self,
        *,
        organization_id: uuid.UUID,
        status_filter: str | None,
        item_id: uuid.UUID | None,
        location_id: uuid.UUID | None,
        work_order_id: uuid.UUID | None,
        include_inactive: bool,
        count_only: bool = False,
    ) -> Query:
        """
        Build the shared reservation list query.
        """

        if count_only:
            query = self.db.query(
                func.count(InventoryReservation.id)
            )
        else:
            query = self.db.query(InventoryReservation)

        query = query.filter(
            InventoryReservation.organization_id
            == organization_id
        )

        if not include_inactive:
            query = query.filter(
                InventoryReservation.is_active.is_(True)
            )

        if status_filter:
            query = query.filter(
                InventoryReservation.status
                == status_filter.strip().lower()
            )

        if item_id is not None:
            query = query.filter(
                InventoryReservation.item_id == item_id
            )

        if location_id is not None:
            query = query.filter(
                InventoryReservation.location_id
                == location_id
            )

        if work_order_id is not None:
            query = query.filter(
                InventoryReservation.work_order_id
                == work_order_id
            )

        return query

    def list_expired_active_reservations(
        self,
        organization_id: uuid.UUID,
        *,
        expired_at: datetime,
        limit: int = 100,
        for_update: bool = False,
    ) -> list[InventoryReservation]:
        """
        Return active reservations whose expiry time has passed.
        """

        query = (
            self.db.query(InventoryReservation)
            .populate_existing()
            .filter(
                InventoryReservation.organization_id
                == organization_id,
                InventoryReservation.status.in_(
                    ACTIVE_RESERVATION_STATUSES
                ),
                InventoryReservation.is_active.is_(True),
                InventoryReservation.expires_at.is_not(None),
                InventoryReservation.expires_at
                <= expired_at,
            )
            .order_by(
                InventoryReservation.expires_at.asc(),
                InventoryReservation.created_at.asc(),
            )
            .limit(limit)
        )

        if for_update:
            query = query.with_for_update(
                of=InventoryReservation,
                skip_locked=True,
            )

        return query.all()

    # ------------------------------------------------------------------
    # Movement ledger
    # ------------------------------------------------------------------

    def create_movement(
        self,
        movement: InventoryMovement,
    ) -> InventoryMovement:
        """
        Add one immutable stock movement to the transaction.
        """

        self._normalize_movement(movement)

        self.db.add(movement)
        self.db.flush()

        return movement

    def create_movements(
        self,
        movements: Iterable[InventoryMovement],
    ) -> list[InventoryMovement]:
        """
        Add multiple correlated movements atomically.
        """

        movement_list = list(movements)

        for movement in movement_list:
            self._normalize_movement(movement)

        self.db.add_all(movement_list)
        self.db.flush()

        return movement_list

    def get_movement_for_organization(
        self,
        organization_id: uuid.UUID,
        movement_id: uuid.UUID,
    ) -> InventoryMovement | None:
        """
        Retrieve one immutable stock movement.
        """

        return (
            self.db.query(InventoryMovement)
            .filter(
                InventoryMovement.id == movement_id,
                InventoryMovement.organization_id
                == organization_id,
            )
            .first()
        )

    def list_movements_for_organization(
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
    ) -> list[InventoryMovement]:
        """
        List organization stock-movement ledger entries.
        """

        query = self._movement_list_query(
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

        return (
            query.order_by(
                InventoryMovement.occurred_at.desc(),
                InventoryMovement.created_at.desc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_movements_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
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
    ) -> int:
        """
        Count organization stock-movement ledger entries.
        """

        query = self._movement_list_query(
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
            count_only=True,
        )

        return int(query.scalar() or 0)

    def _movement_list_query(
        self,
        *,
        organization_id: uuid.UUID,
        movement_type: str | None,
        item_id: uuid.UUID | None,
        location_id: uuid.UUID | None,
        work_order_id: uuid.UUID | None,
        reservation_id: uuid.UUID | None,
        transfer_group_id: uuid.UUID | None,
        reference_type: str | None,
        reference_id: str | None,
        occurred_from: datetime | None,
        occurred_to: datetime | None,
        count_only: bool = False,
    ) -> Query:
        """
        Build the shared movement-ledger list query.
        """

        if count_only:
            query = self.db.query(
                func.count(InventoryMovement.id)
            )
        else:
            query = self.db.query(InventoryMovement)

        query = query.filter(
            InventoryMovement.organization_id
            == organization_id
        )

        if movement_type:
            query = query.filter(
                InventoryMovement.movement_type
                == movement_type.strip().lower()
            )

        if item_id is not None:
            query = query.filter(
                InventoryMovement.item_id == item_id
            )

        if location_id is not None:
            query = query.filter(
                InventoryMovement.location_id
                == location_id
            )

        if work_order_id is not None:
            query = query.filter(
                InventoryMovement.work_order_id
                == work_order_id
            )

        if reservation_id is not None:
            query = query.filter(
                InventoryMovement.reservation_id
                == reservation_id
            )

        if transfer_group_id is not None:
            query = query.filter(
                InventoryMovement.transfer_group_id
                == transfer_group_id
            )

        if reference_type:
            query = query.filter(
                func.lower(
                    InventoryMovement.reference_type
                )
                == reference_type.strip().lower()
            )

        if reference_id:
            query = query.filter(
                InventoryMovement.reference_id
                == reference_id.strip()
            )

        if occurred_from is not None:
            query = query.filter(
                InventoryMovement.occurred_at
                >= occurred_from
            )

        if occurred_to is not None:
            query = query.filter(
                InventoryMovement.occurred_at
                <= occurred_to
            )

        return query
