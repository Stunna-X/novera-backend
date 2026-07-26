"""
Inventory routes.

Provides organization-scoped endpoints for inventory locations,
catalogue items, stock operations, reservations, balances, and movement-ledger reporting.
"""

from __future__ import annotations

import uuid
from datetime import datetime

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
from app.models.inventory import (
    InventoryBalance,
    InventoryItem,
    InventoryLocation,
    InventoryMovement,
    InventoryReservation,
)
from app.schemas.inventory import (
    AdjustInventoryStockSchema,
    ConsumeInventoryReservationSchema,
    CreateInventoryReservationSchema,
    CreateInventoryItemSchema,
    CreateInventoryLocationSchema,
    InventoryBalanceListResponse,
    InventoryBalanceResponse,
    InventoryMovementListResponse,
    InventoryMovementResponse,
    InventoryMovementType,
    InventoryReservationConsumptionResponse,
    InventoryReservationListResponse,
    InventoryReservationOperationResponse,
    InventoryReservationResponse,
    InventoryReservationStatus,
    InventoryStockOperationResponse,
    InventoryTransferResponse,
    InventoryItemListResponse,
    InventoryItemResponse,
    InventoryItemType,
    InventoryLocationListResponse,
    InventoryLocationResponse,
    InventoryLocationType,
    IssueInventoryStockSchema,
    LowStockListResponse,
    ReceiveInventoryStockSchema,
    ReleaseInventoryReservationSchema,
    ReturnInventoryStockSchema,
    TransferInventoryStockSchema,
    UpdateInventoryItemSchema,
    UpdateInventoryLocationSchema,
)
from app.services.inventory_service import InventoryService


router = APIRouter(
    prefix="/organizations/{organization_id}/inventory",
    tags=["Inventory"],
)


# ------------------------------------------------------------------
# Inventory locations
# ------------------------------------------------------------------


@router.post(
    "/locations",
    response_model=InventoryLocationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create inventory location",
)
def create_inventory_location(
    payload: CreateInventoryLocationSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.create")
    ),
    db: Session = Depends(get_db),
) -> InventoryLocation:
    """
    Create an inventory location inside the organization.

    Requires:
    - inventory.create
    """

    service = InventoryService(db)

    return service.create_location(
        organization_id=context.organization.id,
        payload=payload,
    )


@router.get(
    "/locations",
    response_model=InventoryLocationListResponse,
    summary="List inventory locations",
)
def list_inventory_locations(
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
    location_type: InventoryLocationType | None = Query(
        default=None,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryLocationListResponse:
    """
    List inventory locations belonging to the organization.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.list_locations(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        location_type=location_type,
        include_inactive=include_inactive,
    )


@router.get(
    "/locations/{location_id}",
    response_model=InventoryLocationResponse,
    summary="Get inventory location",
)
def get_inventory_location(
    location_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryLocation:
    """
    Return one organization inventory location.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.get_location(
        organization_id=context.organization.id,
        location_id=location_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/locations/{location_id}",
    response_model=InventoryLocationResponse,
    summary="Update inventory location",
)
def update_inventory_location(
    location_id: uuid.UUID,
    payload: UpdateInventoryLocationSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryLocation:
    """
    Update an active inventory location.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.update_location(
        organization_id=context.organization.id,
        location_id=location_id,
        payload=payload,
    )


@router.delete(
    "/locations/{location_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate inventory location",
)
def deactivate_inventory_location(
    location_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("inventory.delete")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Soft-delete an empty inventory location.

    Requires:
    - inventory.delete
    """

    service = InventoryService(db)

    service.deactivate_location(
        organization_id=context.organization.id,
        location_id=location_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/locations/{location_id}/reactivate",
    response_model=InventoryLocationResponse,
    summary="Reactivate inventory location",
)
def reactivate_inventory_location(
    location_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryLocation:
    """
    Reactivate a previously deactivated inventory location.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.reactivate_location(
        organization_id=context.organization.id,
        location_id=location_id,
    )


# ------------------------------------------------------------------
# Inventory catalogue items
# ------------------------------------------------------------------


@router.post(
    "/items",
    response_model=InventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create inventory item",
)
def create_inventory_item(
    payload: CreateInventoryItemSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.create")
    ),
    db: Session = Depends(get_db),
) -> InventoryItem:
    """
    Create an inventory catalogue item.

    Requires:
    - inventory.create
    """

    service = InventoryService(db)

    return service.create_item(
        organization_id=context.organization.id,
        payload=payload,
    )


@router.get(
    "/items",
    response_model=InventoryItemListResponse,
    summary="List inventory items",
)
def list_inventory_items(
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
    item_type: InventoryItemType | None = Query(
        default=None,
    ),
    category: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
    ),
    location_id: uuid.UUID | None = Query(
        default=None,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryItemListResponse:
    """
    List inventory catalogue items.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.list_items(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        item_type=item_type,
        category=category,
        location_id=location_id,
        include_inactive=include_inactive,
    )


@router.get(
    "/items/{item_id}",
    response_model=InventoryItemResponse,
    summary="Get inventory item",
)
def get_inventory_item(
    item_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryItem:
    """
    Return one organization inventory item.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.get_item(
        organization_id=context.organization.id,
        item_id=item_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/items/{item_id}",
    response_model=InventoryItemResponse,
    summary="Update inventory item",
)
def update_inventory_item(
    item_id: uuid.UUID,
    payload: UpdateInventoryItemSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryItem:
    """
    Update an active inventory catalogue item.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.update_item(
        organization_id=context.organization.id,
        item_id=item_id,
        payload=payload,
    )


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate inventory item",
)
def deactivate_inventory_item(
    item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("inventory.delete")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Soft-delete an inventory item with no remaining stock.

    Requires:
    - inventory.delete
    """

    service = InventoryService(db)

    service.deactivate_item(
        organization_id=context.organization.id,
        item_id=item_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/items/{item_id}/reactivate",
    response_model=InventoryItemResponse,
    summary="Reactivate inventory item",
)
def reactivate_inventory_item(
    item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryItem:
    """
    Reactivate a previously deactivated inventory item.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.reactivate_item(
        organization_id=context.organization.id,
        item_id=item_id,
    )


# ------------------------------------------------------------------
# Stock balances and low-stock reporting
# ------------------------------------------------------------------


@router.get(
    "/balances",
    response_model=InventoryBalanceListResponse,
    summary="List inventory balances",
)
def list_inventory_balances(
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
    item_id: uuid.UUID | None = Query(
        default=None,
    ),
    location_id: uuid.UUID | None = Query(
        default=None,
    ),
    in_stock_only: bool = Query(
        default=False,
    ),
    include_inactive_catalogue: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryBalanceListResponse:
    """
    List item-location inventory balances.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.list_balances(
        organization_id=context.organization.id,
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


@router.get(
    "/balances/{balance_id}",
    response_model=InventoryBalanceResponse,
    summary="Get inventory balance",
)
def get_inventory_balance(
    balance_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryBalance:
    """
    Return one item-location inventory balance.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.get_balance(
        organization_id=context.organization.id,
        balance_id=balance_id,
    )


@router.get(
    "/items/{item_id}/locations/{location_id}/balance",
    response_model=InventoryBalanceResponse,
    summary="Get item-location balance",
)
def get_item_location_balance(
    item_id: uuid.UUID,
    location_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryBalance:
    """
    Return the balance for one item at one location.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.get_item_location_balance(
        organization_id=context.organization.id,
        item_id=item_id,
        location_id=location_id,
    )


@router.get(
    "/low-stock",
    response_model=LowStockListResponse,
    summary="List low-stock items",
)
def list_low_stock_items(
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
    item_type: InventoryItemType | None = Query(
        default=None,
    ),
    category: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
    ),
    location_id: uuid.UUID | None = Query(
        default=None,
    ),
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> LowStockListResponse:
    """
    List active inventory items at or below reorder level.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.list_low_stock(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        search=search,
        item_type=item_type,
        category=category,
        location_id=location_id,
    )

# ------------------------------------------------------------------
# Stock operations
# ------------------------------------------------------------------


@router.post(
    "/movements/receipts",
    response_model=InventoryStockOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Receive inventory stock",
)
def receive_inventory_stock(
    payload: ReceiveInventoryStockSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryStockOperationResponse:
    """
    Receive stock or create an opening balance.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.receive_stock(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.post(
    "/movements/issues",
    response_model=InventoryStockOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue inventory stock",
)
def issue_inventory_stock(
    payload: IssueInventoryStockSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryStockOperationResponse:
    """
    Issue available, unreserved stock from a location.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.issue_stock(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.post(
    "/movements/returns",
    response_model=InventoryStockOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Return inventory stock",
)
def return_inventory_stock(
    payload: ReturnInventoryStockSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryStockOperationResponse:
    """
    Return stock to an inventory location.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.return_stock(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.post(
    "/movements/adjustments",
    response_model=InventoryStockOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Adjust inventory stock",
)
def adjust_inventory_stock(
    payload: AdjustInventoryStockSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryStockOperationResponse:
    """
    Apply a signed stock-count adjustment.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.adjust_stock(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.post(
    "/movements/transfers",
    response_model=InventoryTransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transfer inventory stock",
)
def transfer_inventory_stock(
    payload: TransferInventoryStockSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryTransferResponse:
    """
    Transfer stock between two organization locations atomically.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.transfer_stock(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.get(
    "/movements",
    response_model=InventoryMovementListResponse,
    summary="List inventory movements",
)
def list_inventory_movements(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    movement_type: InventoryMovementType | None = Query(
        default=None,
    ),
    item_id: uuid.UUID | None = Query(
        default=None,
    ),
    location_id: uuid.UUID | None = Query(
        default=None,
    ),
    work_order_id: uuid.UUID | None = Query(
        default=None,
    ),
    reservation_id: uuid.UUID | None = Query(
        default=None,
    ),
    transfer_group_id: uuid.UUID | None = Query(
        default=None,
    ),
    reference_type: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
    ),
    reference_id: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
    ),
    occurred_from: datetime | None = Query(
        default=None,
    ),
    occurred_to: datetime | None = Query(
        default=None,
    ),
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryMovementListResponse:
    """
    List immutable organization stock movements.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.list_movements(
        organization_id=context.organization.id,
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


@router.get(
    "/movements/{movement_id}",
    response_model=InventoryMovementResponse,
    summary="Get inventory movement",
)
def get_inventory_movement(
    movement_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryMovement:
    """
    Return one immutable organization stock movement.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.get_movement(
        organization_id=context.organization.id,
        movement_id=movement_id,
    )


# ------------------------------------------------------------------
# Work-order inventory reservations
# ------------------------------------------------------------------


@router.post(
    "/reservations",
    response_model=InventoryReservationOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reserve inventory stock",
)
def create_inventory_reservation(
    payload: CreateInventoryReservationSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryReservationOperationResponse:
    """
    Reserve currently available stock for a work order.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.create_reservation(
        organization_id=context.organization.id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.get(
    "/reservations",
    response_model=InventoryReservationListResponse,
    summary="List inventory reservations",
)
def list_inventory_reservations(
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    reservation_status: InventoryReservationStatus | None = Query(
        default=None,
        alias="status",
    ),
    item_id: uuid.UUID | None = Query(
        default=None,
    ),
    location_id: uuid.UUID | None = Query(
        default=None,
    ),
    work_order_id: uuid.UUID | None = Query(
        default=None,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryReservationListResponse:
    """
    List organization work-order stock reservations.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.list_reservations(
        organization_id=context.organization.id,
        skip=skip,
        limit=limit,
        status_filter=reservation_status,
        item_id=item_id,
        location_id=location_id,
        work_order_id=work_order_id,
        include_inactive=include_inactive,
    )


@router.get(
    "/reservations/{reservation_id}",
    response_model=InventoryReservationResponse,
    summary="Get inventory reservation",
)
def get_inventory_reservation(
    reservation_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("inventory.read")
    ),
    db: Session = Depends(get_db),
) -> InventoryReservation:
    """
    Return one organization work-order stock reservation.

    Requires:
    - inventory.read
    """

    service = InventoryService(db)

    return service.get_reservation(
        organization_id=context.organization.id,
        reservation_id=reservation_id,
        include_inactive=include_inactive,
    )


@router.post(
    "/reservations/{reservation_id}/consume",
    response_model=InventoryReservationConsumptionResponse,
    summary="Consume inventory reservation",
)
def consume_inventory_reservation(
    reservation_id: uuid.UUID,
    payload: ConsumeInventoryReservationSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryReservationConsumptionResponse:
    """
    Consume some or all remaining reserved stock.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.consume_reservation(
        organization_id=context.organization.id,
        reservation_id=reservation_id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.post(
    "/reservations/{reservation_id}/release",
    response_model=InventoryReservationOperationResponse,
    summary="Release inventory reservation",
)
def release_inventory_reservation(
    reservation_id: uuid.UUID,
    payload: ReleaseInventoryReservationSchema,
    context: OrganizationContext = Depends(
        require_permission("inventory.update")
    ),
    db: Session = Depends(get_db),
) -> InventoryReservationOperationResponse:
    """
    Release all unconsumed stock held by a reservation.

    Requires:
    - inventory.update
    """

    service = InventoryService(db)

    return service.release_reservation(
        organization_id=context.organization.id,
        reservation_id=reservation_id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )
