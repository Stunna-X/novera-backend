"""
PostgreSQL tenant-isolation tests for work-order closeouts.
"""

from __future__ import annotations

import uuid
from typing import Protocol

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.models.work_order import WorkOrder
from app.schemas.work_order_closeout import (
    ApproveWorkOrderCloseoutSchema,
    MarkCloseoutInvoiceReadySchema,
    RejectWorkOrderCloseoutSchema,
    SubmitWorkOrderCloseoutSchema,
    UpdateWorkOrderCloseoutSchema,
)
from app.services.work_order_closeout_service import (
    WorkOrderCloseoutService,
)


class TenantIntegrationData(Protocol):
    """
    Minimum fixture contract required by this test.
    """

    organization_id: uuid.UUID
    other_organization_id: uuid.UUID
    actor_user_id: uuid.UUID
    work_order_id: uuid.UUID


def _assert_not_found(
    error: pytest.ExceptionInfo[HTTPException],
) -> None:
    """
    Assert an information-leak-safe not-found response.
    """

    assert error.value.status_code == 404


def test_closeout_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    A foreign organization must not access a work-order closeout.
    """

    original_summary = (
        "Borehole drilling completed successfully."
    )
    original_work_performed = (
        "Drilled, cased, flushed, and tested the borehole."
    )
    original_materials = (
        "PVC casing, gravel pack, cement, and pump fittings."
    )
    original_internal_notes = (
        "Original closeout notes must remain unchanged."
    )

    primary_organization_id = (
        inventory_integration_data.organization_id
    )
    foreign_organization_id = (
        inventory_integration_data.other_organization_id
    )
    actor_user_id = (
        inventory_integration_data.actor_user_id
    )
    work_order_id = (
        inventory_integration_data.work_order_id
    )

    with integration_session_factory() as db:
        work_order = db.get(
            WorkOrder,
            work_order_id,
        )

        assert work_order is not None
        assert (
            work_order.organization_id
            == primary_organization_id
        )

        work_order.status = "completed"
        db.commit()

        service = WorkOrderCloseoutService(db)

        closeout = service.submit_closeout(
            organization_id=primary_organization_id,
            work_order_id=work_order_id,
            payload=SubmitWorkOrderCloseoutSchema(
                completion_summary=original_summary,
                work_performed=original_work_performed,
                materials_used=original_materials,
                customer_notes=(
                    "Customer confirmed the system is operational."
                ),
                internal_notes=original_internal_notes,
                note="Legitimate closeout submission.",
            ),
            actor_user_id=actor_user_id,
        )

        closeout_id = closeout.id

        assert closeout.status == "submitted"
        assert closeout.is_invoice_ready is False

    with integration_session_factory() as db:
        service = WorkOrderCloseoutService(db)

        with pytest.raises(
            HTTPException
        ) as foreign_submit_error:
            service.submit_closeout(
                organization_id=foreign_organization_id,
                work_order_id=work_order_id,
                payload=SubmitWorkOrderCloseoutSchema(
                    completion_summary=(
                        "Unauthorized foreign submission."
                    ),
                    work_performed=(
                        "Unauthorized cross-tenant work."
                    ),
                    internal_notes=(
                        "This must never overwrite the closeout."
                    ),
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(
            foreign_submit_error
        )

        with pytest.raises(
            HTTPException
        ) as foreign_read_error:
            service.get_closeout(
                organization_id=foreign_organization_id,
                work_order_id=work_order_id,
            )

        _assert_not_found(
            foreign_read_error
        )

        with pytest.raises(
            HTTPException
        ) as foreign_update_error:
            service.update_closeout(
                organization_id=foreign_organization_id,
                work_order_id=work_order_id,
                payload=UpdateWorkOrderCloseoutSchema(
                    completion_summary=(
                        "Cross-tenant summary overwrite."
                    ),
                    work_performed=(
                        "Cross-tenant work overwrite."
                    ),
                    materials_used=(
                        "Cross-tenant materials overwrite."
                    ),
                    internal_notes=(
                        "Unauthorized mutation attempt."
                    ),
                    note=(
                        "Foreign update must not be recorded."
                    ),
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(
            foreign_update_error
        )

        with pytest.raises(
            HTTPException
        ) as foreign_approve_error:
            service.approve_closeout(
                organization_id=foreign_organization_id,
                work_order_id=work_order_id,
                payload=ApproveWorkOrderCloseoutSchema(
                    customer_name="Unauthorized Approver",
                    customer_email=(
                        "unauthorized.approver@example.com"
                    ),
                    customer_rating=1,
                    customer_feedback=(
                        "Unauthorized approval attempt."
                    ),
                    ready_for_invoice=True,
                    note=(
                        "Foreign approval must not be recorded."
                    ),
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(
            foreign_approve_error
        )

        with pytest.raises(
            HTTPException
        ) as foreign_reject_error:
            service.reject_closeout(
                organization_id=foreign_organization_id,
                work_order_id=work_order_id,
                payload=RejectWorkOrderCloseoutSchema(
                    rejection_reason=(
                        "Unauthorized rejection attempt."
                    ),
                    note=(
                        "Foreign rejection must not be recorded."
                    ),
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(
            foreign_reject_error
        )

        with pytest.raises(
            HTTPException
        ) as foreign_invoice_ready_error:
            service.mark_invoice_ready(
                organization_id=foreign_organization_id,
                work_order_id=work_order_id,
                payload=MarkCloseoutInvoiceReadySchema(
                    note=(
                        "Foreign invoice-ready mutation "
                        "must not be recorded."
                    ),
                ),
                actor_user_id=actor_user_id,
            )

        _assert_not_found(
            foreign_invoice_ready_error
        )

        unchanged_closeout = service.get_closeout(
            organization_id=primary_organization_id,
            work_order_id=work_order_id,
        )

        assert unchanged_closeout.id == closeout_id
        assert unchanged_closeout.status == "submitted"
        assert (
            unchanged_closeout.completion_summary
            == original_summary
        )
        assert (
            unchanged_closeout.work_performed
            == original_work_performed
        )
        assert (
            unchanged_closeout.materials_used
            == original_materials
        )
        assert (
            unchanged_closeout.internal_notes
            == original_internal_notes
        )
        assert unchanged_closeout.customer_name is None
        assert unchanged_closeout.customer_rating is None
        assert unchanged_closeout.rejection_reason is None
        assert unchanged_closeout.approved_at is None
        assert unchanged_closeout.rejected_at is None
        assert unchanged_closeout.is_invoice_ready is False
        assert unchanged_closeout.invoice_ready_at is None
