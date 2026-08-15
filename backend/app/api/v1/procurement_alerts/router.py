"""Organization-scoped procurement workflow alert endpoints."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.database.session import get_db
from app.schemas.procurement_alert import (
    ProcurementAlertDeliveryListResponse,
    ProcurementAlertDispatchRequest,
    ProcurementAlertDispatchResponse,
    ProcurementAlertPreferenceResponse,
    ProcurementAlertPreferenceUpdate,
    ProcurementAlertType,
)
from app.services.procurement_alert_service import (
    ProcurementAlertService,
)


router = APIRouter(
    prefix="/organizations/{organization_id}/procurement-alerts",
    tags=["Procurement Alerts"],
)


@router.get(
    "/preferences",
    response_model=ProcurementAlertPreferenceResponse,
    summary="Get procurement alert preferences",
)
def get_procurement_alert_preferences(
    context: OrganizationContext = Depends(
        require_permission("procurement_alerts.read")
    ),
    db: Session = Depends(get_db),
) -> ProcurementAlertPreferenceResponse:
    service = ProcurementAlertService(db)
    return service.get_preferences(
        context.organization.id,
        context.current_user.id,
    )


@router.put(
    "/preferences",
    response_model=ProcurementAlertPreferenceResponse,
    summary="Update procurement alert preferences",
)
def update_procurement_alert_preferences(
    payload: ProcurementAlertPreferenceUpdate,
    context: OrganizationContext = Depends(
        require_permission("procurement_alerts.update")
    ),
    db: Session = Depends(get_db),
) -> ProcurementAlertPreferenceResponse:
    service = ProcurementAlertService(db)
    return service.update_preferences(
        context.organization.id,
        context.current_user.id,
        payload,
    )


@router.post(
    "/dispatch",
    response_model=ProcurementAlertDispatchResponse,
    summary="Dispatch current user's procurement alerts",
)
def dispatch_procurement_alerts(
    payload: ProcurementAlertDispatchRequest,
    context: OrganizationContext = Depends(
        require_permission("procurement_alerts.dispatch")
    ),
    db: Session = Depends(get_db),
) -> ProcurementAlertDispatchResponse:
    service = ProcurementAlertService(db)
    return service.dispatch(
        context.organization.id,
        context.current_user.id,
        context.permission_names,
        as_of_date=payload.as_of_date or date.today(),
    )


@router.get(
    "/deliveries",
    response_model=ProcurementAlertDeliveryListResponse,
    summary="List procurement alert deliveries",
)
def list_procurement_alert_deliveries(
    alert_type: ProcurementAlertType | None = Query(
        default=None
    ),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    context: OrganizationContext = Depends(
        require_permission("procurement_alerts.read")
    ),
    db: Session = Depends(get_db),
) -> ProcurementAlertDeliveryListResponse:
    service = ProcurementAlertService(db)
    return service.list_deliveries(
        context.organization.id,
        context.current_user.id,
        alert_type=alert_type,
        skip=skip,
        limit=limit,
    )
