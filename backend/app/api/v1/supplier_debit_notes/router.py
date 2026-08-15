"""Organization-scoped supplier debit-note and credit endpoints."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import OrganizationContext, require_permission
from app.database.session import get_db
from app.schemas.supplier_return import (
    AcknowledgeSupplierDebitNoteSchema,
    CreateSupplierDebitNoteSchema,
    ReverseSupplierCreditSettlementSchema,
    SettleSupplierDebitNoteSchema,
    SupplierCreditSettlementResponse,
    SupplierDebitNoteLineCreate,
    SupplierDebitNoteLineUpdate,
    SupplierDebitNoteListResponse,
    SupplierDebitNoteResponse,
    SupplierDebitNoteStatus,
    UpdateSupplierDebitNoteSchema,
    VoidSupplierDebitNoteSchema,
)
from app.services.supplier_return_service import SupplierReturnService


router = APIRouter(
    prefix="/organizations/{organization_id}/supplier-debit-notes",
    tags=["Supplier Debit Notes"],
)


@router.post(
    "",
    response_model=SupplierDebitNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create supplier debit note",
)
def create_supplier_debit_note(
    payload: CreateSupplierDebitNoteSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.create")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).create_debit_note(
        context.organization.id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "",
    response_model=SupplierDebitNoteListResponse,
    summary="List supplier debit notes",
)
def list_supplier_debit_notes(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    supplier_id: uuid.UUID | None = Query(default=None),
    status_filter: SupplierDebitNoteStatus | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteListResponse:
    return SupplierReturnService(db).list_debit_notes(
        context.organization.id,
        skip=skip,
        limit=limit,
        supplier_id=supplier_id,
        status_filter=(
            status_filter.value
            if status_filter is not None
            else None
        ),
        search=search,
    )


@router.get(
    "/{debit_note_id}",
    response_model=SupplierDebitNoteResponse,
    summary="Get supplier debit note",
)
def get_supplier_debit_note(
    debit_note_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.read")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).get_debit_note(
        context.organization.id,
        debit_note_id,
    )


@router.patch(
    "/{debit_note_id}",
    response_model=SupplierDebitNoteResponse,
    summary="Update supplier debit note",
)
def update_supplier_debit_note(
    debit_note_id: uuid.UUID,
    payload: UpdateSupplierDebitNoteSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).update_debit_note(
        context.organization.id,
        debit_note_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{debit_note_id}/line-items",
    response_model=SupplierDebitNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add supplier debit-note line",
)
def add_supplier_debit_note_line(
    debit_note_id: uuid.UUID,
    payload: SupplierDebitNoteLineCreate,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).add_debit_note_line(
        context.organization.id,
        debit_note_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.patch(
    "/{debit_note_id}/line-items/{line_item_id}",
    response_model=SupplierDebitNoteResponse,
    summary="Update supplier debit-note line",
)
def update_supplier_debit_note_line(
    debit_note_id: uuid.UUID,
    line_item_id: uuid.UUID,
    payload: SupplierDebitNoteLineUpdate,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).update_debit_note_line(
        context.organization.id,
        debit_note_id,
        line_item_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.delete(
    "/{debit_note_id}/line-items/{line_item_id}",
    response_model=SupplierDebitNoteResponse,
    summary="Remove supplier debit-note line",
)
def delete_supplier_debit_note_line(
    debit_note_id: uuid.UUID,
    line_item_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.update")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).delete_debit_note_line(
        context.organization.id,
        debit_note_id,
        line_item_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{debit_note_id}/issue",
    response_model=SupplierDebitNoteResponse,
    summary="Issue supplier debit note",
)
def issue_supplier_debit_note(
    debit_note_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.issue")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).issue_debit_note(
        context.organization.id,
        debit_note_id,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{debit_note_id}/acknowledge",
    response_model=SupplierDebitNoteResponse,
    summary="Acknowledge supplier debit note as credit",
)
def acknowledge_supplier_debit_note(
    debit_note_id: uuid.UUID,
    payload: AcknowledgeSupplierDebitNoteSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.acknowledge")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).acknowledge_debit_note(
        context.organization.id,
        debit_note_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{debit_note_id}/void",
    response_model=SupplierDebitNoteResponse,
    summary="Void supplier debit note",
)
def void_supplier_debit_note(
    debit_note_id: uuid.UUID,
    payload: VoidSupplierDebitNoteSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.void")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).void_debit_note(
        context.organization.id,
        debit_note_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.post(
    "/{debit_note_id}/settlements",
    response_model=SupplierDebitNoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Settle supplier debit-note credit",
)
def settle_supplier_debit_note(
    debit_note_id: uuid.UUID,
    payload: SettleSupplierDebitNoteSchema,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.settle")
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).settle_debit_note(
        context.organization.id,
        debit_note_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.get(
    "/{debit_note_id}/settlements",
    response_model=list[SupplierCreditSettlementResponse],
    summary="List supplier credit settlements",
)
def list_supplier_credit_settlements(
    debit_note_id: uuid.UUID,
    context: OrganizationContext = Depends(
        require_permission("supplier_debit_notes.read")
    ),
    db: Session = Depends(get_db),
) -> list[SupplierCreditSettlementResponse]:
    return SupplierReturnService(db).list_credit_settlements(
        context.organization.id,
        debit_note_id,
    )


@router.post(
    "/{debit_note_id}/settlements/{settlement_id}/reverse",
    response_model=SupplierDebitNoteResponse,
    summary="Reverse supplier credit settlement",
)
def reverse_supplier_credit_settlement(
    debit_note_id: uuid.UUID,
    settlement_id: uuid.UUID,
    payload: ReverseSupplierCreditSettlementSchema,
    context: OrganizationContext = Depends(
        require_permission(
            "supplier_debit_notes.reverse_settlement"
        )
    ),
    db: Session = Depends(get_db),
) -> SupplierDebitNoteResponse:
    return SupplierReturnService(db).reverse_credit_settlement(
        context.organization.id,
        debit_note_id,
        settlement_id,
        payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )
