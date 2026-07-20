"""Work-order closeout routes."""

from __future__ import annotations

import uuid

from fastapi import (
    APIRouter,
    Depends,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.database.session import get_db
from app.schemas.work_order_closeout import (
    ApproveWorkOrderCloseoutSchema,
    MarkCloseoutInvoiceReadySchema,
    RejectWorkOrderCloseoutSchema,
    SubmitWorkOrderCloseoutSchema,
    UpdateWorkOrderCloseoutSchema,
    WorkOrderCloseoutResponse,
)
from app.services.work_order_closeout_service import (
    WorkOrderCloseoutService,
)


router = APIRouter(
    prefix=(
        "/organizations/{organization_id}/work-orders/"
        "{work_order_id}/closeout"
    ),
    tags=["Work Order Closeouts"],
)


@router.post(
    "",
    response_model=WorkOrderCloseoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit work-order closeout",
)
def submit_work_order_closeout(
    work_order_id: uuid.UUID,
    payload: SubmitWorkOrderCloseoutSchema,
    context: OrganizationContext = Depends(
        require_permission("closeouts.create")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderCloseoutResponse:
    """Submit a completed work order for customer closeout."""

    service = WorkOrderCloseoutService(db)

    return service.submit_closeout(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.get(
    "",
    response_model=WorkOrderCloseoutResponse,
    summary="Get work-order closeout",
)
def get_work_order_closeout(
    work_order_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("closeouts.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderCloseoutResponse:
    """Return the closeout for one work order."""

    service = WorkOrderCloseoutService(db)

    return service.get_closeout(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
    )


@router.patch(
    "",
    response_model=WorkOrderCloseoutResponse,
    summary="Update work-order closeout",
)
def update_work_order_closeout(
    work_order_id: uuid.UUID,
    payload: UpdateWorkOrderCloseoutSchema,
    context: OrganizationContext = Depends(
        require_permission("closeouts.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderCloseoutResponse:
    """Update a submitted or rejected closeout report."""

    service = WorkOrderCloseoutService(db)

    return service.update_closeout(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/approve",
    response_model=WorkOrderCloseoutResponse,
    summary="Approve work-order closeout",
)
def approve_work_order_closeout(
    work_order_id: uuid.UUID,
    payload: ApproveWorkOrderCloseoutSchema,
    context: OrganizationContext = Depends(
        require_permission("closeouts.approve")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderCloseoutResponse:
    """Capture customer approval and optional invoice readiness."""

    service = WorkOrderCloseoutService(db)

    return service.approve_closeout(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/reject",
    response_model=WorkOrderCloseoutResponse,
    summary="Reject work-order closeout",
)
def reject_work_order_closeout(
    work_order_id: uuid.UUID,
    payload: RejectWorkOrderCloseoutSchema,
    context: OrganizationContext = Depends(
        require_permission("closeouts.reject")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderCloseoutResponse:
    """Reject a submitted closeout for revision."""

    service = WorkOrderCloseoutService(db)

    return service.reject_closeout(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/invoice-ready",
    response_model=WorkOrderCloseoutResponse,
    summary="Mark closeout invoice-ready",
)
def mark_work_order_closeout_invoice_ready(
    work_order_id: uuid.UUID,
    payload: MarkCloseoutInvoiceReadySchema,
    context: OrganizationContext = Depends(
        require_permission("closeouts.invoice_ready")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderCloseoutResponse:
    """Mark an approved closeout ready for final invoice."""

    service = WorkOrderCloseoutService(db)

    return service.mark_invoice_ready(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )
