"""
Organization-scoped work-order material shortage allowance routes.
"""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_all_permissions,
)
from app.database.session import get_db
from app.schemas.work_order_material_shortage_allowance import (
    WorkOrderMaterialShortageAllowanceApprove,
    WorkOrderMaterialShortageAllowanceCancel,
    WorkOrderMaterialShortageAllowanceCreate,
    WorkOrderMaterialShortageAllowanceListResponse,
    WorkOrderMaterialShortageAllowanceReject,
    WorkOrderMaterialShortageAllowanceResponse,
    WorkOrderMaterialShortageAllowanceUpdate,
)
from app.services.work_order_material_shortage_allowance_service import (
    WorkOrderMaterialShortageAllowanceService,
)


router = APIRouter(
    prefix=(
        "/organizations/{organization_id}/work-orders"
        "/{work_order_id}/material-shortage-allowances"
    ),
    tags=["Work Order Material Shortage Allowances"],
)


@router.post(
    "",
    response_model=WorkOrderMaterialShortageAllowanceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create material shortage allowance",
)
def create_material_shortage_allowance(
    work_order_id: uuid.UUID,
    payload: WorkOrderMaterialShortageAllowanceCreate,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.update",
            "work_order_material_shortage_allowances.create",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialShortageAllowanceResponse:
    service = WorkOrderMaterialShortageAllowanceService(db)

    return service.create_allowance(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.get(
    "",
    response_model=WorkOrderMaterialShortageAllowanceListResponse,
    summary="List material shortage allowances",
)
def list_material_shortage_allowances(
    work_order_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    allowance_status: str | None = Query(
        default=None,
        alias="status",
    ),
    include_inactive: bool = Query(default=False),
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.read",
            "work_order_material_shortage_allowances.read",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialShortageAllowanceListResponse:
    service = WorkOrderMaterialShortageAllowanceService(db)

    return service.list_allowances(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        skip=skip,
        limit=limit,
        allowance_status=allowance_status,
        include_inactive=include_inactive,
    )


@router.get(
    "/{allowance_id}",
    response_model=WorkOrderMaterialShortageAllowanceResponse,
    summary="Get material shortage allowance",
)
def get_material_shortage_allowance(
    work_order_id: uuid.UUID,
    allowance_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.read",
            "work_order_material_shortage_allowances.read",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialShortageAllowanceResponse:
    service = WorkOrderMaterialShortageAllowanceService(db)

    return service.get_allowance(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        allowance_id=allowance_id,
    )


@router.patch(
    "/{allowance_id}",
    response_model=WorkOrderMaterialShortageAllowanceResponse,
    summary="Update material shortage allowance",
)
def update_material_shortage_allowance(
    work_order_id: uuid.UUID,
    allowance_id: uuid.UUID,
    payload: WorkOrderMaterialShortageAllowanceUpdate,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.update",
            "work_order_material_shortage_allowances.update",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialShortageAllowanceResponse:
    service = WorkOrderMaterialShortageAllowanceService(db)

    return service.update_allowance(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        allowance_id=allowance_id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.post(
    "/{allowance_id}/submit",
    response_model=WorkOrderMaterialShortageAllowanceResponse,
    summary="Submit material shortage allowance",
)
def submit_material_shortage_allowance(
    work_order_id: uuid.UUID,
    allowance_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.update",
            "work_order_material_shortage_allowances.submit",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialShortageAllowanceResponse:
    service = WorkOrderMaterialShortageAllowanceService(db)

    return service.submit_allowance(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        allowance_id=allowance_id,
        actor_user_id=context.current_user.id,
    )


@router.post(
    "/{allowance_id}/approve",
    response_model=WorkOrderMaterialShortageAllowanceResponse,
    summary="Approve material shortage allowance",
)
def approve_material_shortage_allowance(
    work_order_id: uuid.UUID,
    allowance_id: uuid.UUID,
    payload: WorkOrderMaterialShortageAllowanceApprove,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.update",
            "work_order_material_shortage_allowances.approve",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialShortageAllowanceResponse:
    service = WorkOrderMaterialShortageAllowanceService(db)

    return service.approve_allowance(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        allowance_id=allowance_id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.post(
    "/{allowance_id}/reject",
    response_model=WorkOrderMaterialShortageAllowanceResponse,
    summary="Reject material shortage allowance",
)
def reject_material_shortage_allowance(
    work_order_id: uuid.UUID,
    allowance_id: uuid.UUID,
    payload: WorkOrderMaterialShortageAllowanceReject,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.update",
            "work_order_material_shortage_allowances.approve",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialShortageAllowanceResponse:
    service = WorkOrderMaterialShortageAllowanceService(db)

    return service.reject_allowance(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        allowance_id=allowance_id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )


@router.post(
    "/{allowance_id}/cancel",
    response_model=WorkOrderMaterialShortageAllowanceResponse,
    summary="Cancel material shortage allowance",
)
def cancel_material_shortage_allowance(
    work_order_id: uuid.UUID,
    allowance_id: uuid.UUID,
    payload: WorkOrderMaterialShortageAllowanceCancel,
    context: OrganizationContext = Depends(
        require_all_permissions(
            "work_orders.update",
            "work_order_material_shortage_allowances.cancel",
        )
    ),
    db: Session = Depends(get_db),
) -> WorkOrderMaterialShortageAllowanceResponse:
    service = WorkOrderMaterialShortageAllowanceService(db)

    return service.cancel_allowance(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        allowance_id=allowance_id,
        payload=payload,
        actor_user_id=context.current_user.id,
    )
