"""
Organization-scoped work-order material readiness routes.
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
    require_all_permissions,
)
from app.database.session import get_db
from app.schemas.work_order_material import (
    WorkOrderMaterialCreate,
    WorkOrderMaterialListResponse,
    WorkOrderMaterialPurchaseRequestCreate,
    WorkOrderMaterialPurchaseRequestResponse,
    WorkOrderMaterialResponse,
    WorkOrderMaterialUpdate,
)
from app.services.work_order_material_service import (
    WorkOrderMaterialService,
)


router = APIRouter(
    prefix="/organizations/{organization_id}/work-orders",
    tags=["Work Order Materials"],
)


@router.post(
    "/{work_order_id}/materials",
    response_model=WorkOrderMaterialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add work-order material",
)
def create_work_order_material(
    work_order_id: uuid.UUID,
    payload: WorkOrderMaterialCreate,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.update",
            "inventory.read",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialResponse:
    service = WorkOrderMaterialService(db)

    return service.create_requirement(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.get(
    "/{work_order_id}/materials",
    response_model=WorkOrderMaterialListResponse,
    summary="List work-order materials and readiness",
)
def list_work_order_materials(
    work_order_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    include_inactive: bool = Query(default=False),
    include_inactive_work_order: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.read",
            "inventory.read",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialListResponse:
    service = WorkOrderMaterialService(db)

    return service.list_requirements(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        skip=skip,
        limit=limit,
        include_inactive=include_inactive,
        include_inactive_work_order=(
            include_inactive_work_order
        ),
    )


@router.post(
    "/{work_order_id}/materials/request-missing",
    response_model=WorkOrderMaterialPurchaseRequestResponse,
    summary="Request missing work-order materials",
)
def request_missing_work_order_materials(
    work_order_id: uuid.UUID,
    payload: WorkOrderMaterialPurchaseRequestCreate | None = None,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.read",
            "inventory.read",
            "purchase_requisitions.create",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialPurchaseRequestResponse:
    service = WorkOrderMaterialService(db)

    return service.request_missing_materials(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=(
            payload
            or WorkOrderMaterialPurchaseRequestCreate()
        ),
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "/{work_order_id}/materials/{requirement_id}",
    response_model=WorkOrderMaterialResponse,
    summary="Get work-order material readiness",
)
def get_work_order_material(
    work_order_id: uuid.UUID,
    requirement_id: uuid.UUID,
    include_inactive: bool = Query(default=False),
    include_inactive_work_order: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.read",
            "inventory.read",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialResponse:
    service = WorkOrderMaterialService(db)

    return service.get_requirement(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        requirement_id=requirement_id,
        include_inactive=include_inactive,
        include_inactive_work_order=(
            include_inactive_work_order
        ),
    )


@router.patch(
    "/{work_order_id}/materials/{requirement_id}",
    response_model=WorkOrderMaterialResponse,
    summary="Update work-order material",
)
def update_work_order_material(
    work_order_id: uuid.UUID,
    requirement_id: uuid.UUID,
    payload: WorkOrderMaterialUpdate,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.update",
            "inventory.read",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialResponse:
    service = WorkOrderMaterialService(db)

    return service.update_requirement(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        requirement_id=requirement_id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.delete(
    "/{work_order_id}/materials/{requirement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove work-order material",
)
def deactivate_work_order_material(
    work_order_id: uuid.UUID,
    requirement_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.update",
            "inventory.read",
        )
    ),
    db: Session = Depends(get_db),
) -> Response:
    service = WorkOrderMaterialService(db)
    service.deactivate_requirement(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        requirement_id=requirement_id,
        actor_user_id=context.current_user.id,
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{work_order_id}/materials/{requirement_id}/reactivate",
    response_model=WorkOrderMaterialResponse,
    summary="Restore work-order material",
)
def reactivate_work_order_material(
    work_order_id: uuid.UUID,
    requirement_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.update",
            "inventory.read",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialResponse:
    service = WorkOrderMaterialService(db)

    return service.reactivate_requirement(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        requirement_id=requirement_id,
        actor_user_id=context.current_user.id,
    )
