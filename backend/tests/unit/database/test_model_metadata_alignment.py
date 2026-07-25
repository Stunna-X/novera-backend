"""
Regression tests for SQLAlchemy metadata alignment.

These tests ensure the model metadata continues to match the
already-applied Alembic migration chain.
"""

from __future__ import annotations

from sqlalchemy import UniqueConstraint

from app.models.audit_log import AuditLog
from app.models.document_delivery import DocumentDelivery
from app.models.email_outbox import EmailOutbox
from app.models.work_order_closeout import WorkOrderCloseout


def _indexes_for(
    model,
    *column_names: str,
):
    expected_columns = list(column_names)

    return [
        index
        for index in model.__table__.indexes
        if [
            expression.name
            for expression in index.expressions
        ]
        == expected_columns
    ]


def test_audit_log_status_indexes_match_migration() -> None:
    single_column_indexes = _indexes_for(
        AuditLog,
        "status",
    )

    composite_indexes = _indexes_for(
        AuditLog,
        "organization_id",
        "status",
    )

    assert len(single_column_indexes) == 1
    assert single_column_indexes[0].name == (
        "ix_audit_logs_status"
    )

    assert len(composite_indexes) == 1
    assert composite_indexes[0].name == (
        "ix_audit_logs_status_composite"
    )


def test_document_delivery_recipient_index_is_not_duplicated() -> None:
    indexes = _indexes_for(
        DocumentDelivery,
        "recipient_email",
    )

    assert len(indexes) == 1
    assert indexes[0].name == (
        "ix_document_deliveries_recipient_email"
    )


def test_email_outbox_delivery_uniqueness_matches_migration() -> None:
    unique_constraints = [
        constraint
        for constraint
        in EmailOutbox.__table__.constraints
        if isinstance(
            constraint,
            UniqueConstraint,
        )
        and [
            column.name
            for column in constraint.columns
        ]
        == ["document_delivery_id"]
    ]

    assert len(unique_constraints) == 1
    assert unique_constraints[0].name == (
        "uq_email_outbox_document_delivery"
    )

    delivery_id_indexes = _indexes_for(
        EmailOutbox,
        "document_delivery_id",
    )

    assert {
        index.name
        for index in delivery_id_indexes
    } == {
        "ix_email_outbox_document_delivery_id",
        "ix_email_outbox_delivery",
    }

    assert all(
        not index.unique
        for index in delivery_id_indexes
    )


def test_email_outbox_to_email_index_is_not_duplicated() -> None:
    indexes = _indexes_for(
        EmailOutbox,
        "to_email",
    )

    assert len(indexes) == 1
    assert indexes[0].name == (
        "ix_email_outbox_to_email"
    )


def test_database_timestamp_defaults_match_migrations() -> None:
    timestamp_columns = [
        AuditLog.__table__.c.created_at,
        AuditLog.__table__.c.updated_at,
        DocumentDelivery.__table__.c.created_at,
        DocumentDelivery.__table__.c.updated_at,
        EmailOutbox.__table__.c.queued_at,
        EmailOutbox.__table__.c.created_at,
        EmailOutbox.__table__.c.updated_at,
    ]

    assert all(
        column.server_default is not None
        for column in timestamp_columns
    )


def test_closeout_defaults_match_migration() -> None:
    status_column = (
        WorkOrderCloseout.__table__.c.status
    )

    invoice_ready_column = (
        WorkOrderCloseout
        .__table__
        .c
        .is_invoice_ready
    )

    assert status_column.server_default is not None
    assert invoice_ready_column.server_default is not None
