"""
Work-order note routes.

Provides organization-scoped endpoints for operational notes,
field updates, attachment metadata, editing, filtering,
deactivation, and reactivation.
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
from app.enums.work_order_note import (
    WorkOrderNoteType,
    WorkOrderNoteVisibility,
)
from app.schemas.work_order_note import (
    WorkOrderNoteAttachmentCreate,
    WorkOrderNoteCreate,
    WorkOrderNoteListResponse,
    WorkOrderNoteResponse,
    WorkOrderNoteUpdate,
)
from app.services.work_order_note_service import (
    WorkOrderNoteService,
)


router = APIRouter(
    prefix="/organizations/{organization_id}/work-orders",
    tags=["Work Order Notes"],
)


@router.post(
    "/{work_order_id}/notes",
    response_model=WorkOrderNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create work-order note",
)
def create_work_order_note(
    work_order_id: uuid.UUID,
    payload: WorkOrderNoteCreate,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderNoteResponse:
    """
    Create an operational note or field update.
    """

    service = WorkOrderNoteService(db)

    return service.create_note(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.get(
    "/{work_order_id}/notes",
    response_model=WorkOrderNoteListResponse,
    summary="List work-order notes",
)
def list_work_order_notes(
    work_order_id: uuid.UUID,
    skip: int = Query(
        default=0,
        ge=0,
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
    ),
    note_type: WorkOrderNoteType | None = Query(
        default=None,
    ),
    visibility: WorkOrderNoteVisibility | None = Query(
        default=None,
    ),
    is_pinned: bool | None = Query(
        default=None,
    ),
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderNoteListResponse:
    """
    List work-order notes with optional filters.
    """

    service = WorkOrderNoteService(db)

    return service.list_notes(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        skip=skip,
        limit=limit,
        note_type=note_type,
        visibility=visibility,
        is_pinned=is_pinned,
        include_inactive=include_inactive,
    )


@router.get(
    "/{work_order_id}/notes/{note_id}",
    response_model=WorkOrderNoteResponse,
    summary="Get work-order note",
)
def get_work_order_note(
    work_order_id: uuid.UUID,
    note_id: uuid.UUID,
    include_inactive: bool = Query(
        default=False,
    ),
    context: OrganizationContext = Depends(
        require_permission("work_orders.read")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderNoteResponse:
    """
    Return one work-order note.
    """

    service = WorkOrderNoteService(db)

    return service.get_note(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        note_id=note_id,
        include_inactive=include_inactive,
    )


@router.patch(
    "/{work_order_id}/notes/{note_id}",
    response_model=WorkOrderNoteResponse,
    summary="Update work-order note",
)
def update_work_order_note(
    work_order_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: WorkOrderNoteUpdate,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderNoteResponse:
    """
    Edit a work-order note.
    """

    service = WorkOrderNoteService(db)

    return service.update_note(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        note_id=note_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.delete(
    "/{work_order_id}/notes/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate work-order note",
)
def deactivate_work_order_note(
    work_order_id: uuid.UUID,
    note_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Soft-delete a work-order note.
    """

    service = WorkOrderNoteService(db)

    service.deactivate_note(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        note_id=note_id,
        actor_user_id=context.membership.user_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )


@router.patch(
    "/{work_order_id}/notes/{note_id}/reactivate",
    response_model=WorkOrderNoteResponse,
    summary="Reactivate work-order note",
)
def reactivate_work_order_note(
    work_order_id: uuid.UUID,
    note_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderNoteResponse:
    """
    Reactivate a soft-deleted work-order note.
    """

    service = WorkOrderNoteService(db)

    return service.reactivate_note(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        note_id=note_id,
        actor_user_id=context.membership.user_id,
    )


@router.post(
    "/{work_order_id}/notes/{note_id}/attachments",
    response_model=WorkOrderNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add note attachment metadata",
)
def add_work_order_note_attachment(
    work_order_id: uuid.UUID,
    note_id: uuid.UUID,
    payload: WorkOrderNoteAttachmentCreate,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> WorkOrderNoteResponse:
    """
    Add attachment metadata to an existing note.
    """

    service = WorkOrderNoteService(db)

    return service.add_attachment(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        note_id=note_id,
        payload=payload,
        actor_user_id=context.membership.user_id,
    )


@router.delete(
    "/{work_order_id}/notes/{note_id}/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove note attachment metadata",
)
def remove_work_order_note_attachment(
    work_order_id: uuid.UUID,
    note_id: uuid.UUID,
    attachment_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("work_orders.update")
    ),
    db: Session = Depends(get_db),
) -> Response:
    """
    Remove attachment metadata from a work-order note.
    """

    service = WorkOrderNoteService(db)

    service.remove_attachment(
        organization_id=context.organization.id,
        work_order_id=work_order_id,
        note_id=note_id,
        attachment_id=attachment_id,
        actor_user_id=context.membership.user_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )