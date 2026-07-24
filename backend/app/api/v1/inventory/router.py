"""
Inventory routes.

Provides organization-scoped endpoints for inventory locations,
catalogue items, stock balances, and low-stock reporting.
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
from app.models.inventory import (
    InventoryBalance,
    InventoryItem,
    InventoryLocation,
)
from app.schemas.inventory import (
    CreateInventoryItemSchema,
    CreateInventoryLocationSchema,
    InventoryBalanceListResponse,
    InventoryBalanceResponse,
    InventoryItemListResponse,
    InventoryItemResponse,
    InventoryItemType,
    InventoryLocationListResponse,
    InventoryLocationResponse,
    InventoryLocationType,
    LowStockListResponse,
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
