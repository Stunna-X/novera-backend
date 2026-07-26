"""
PostgreSQL tenant-isolation tests for organization audit logs.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Protocol

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.schemas.audit_log import AuditLogCreate
from app.services.audit_log_service import AuditLogService


class TenantIntegrationData(Protocol):
    """
    Minimum shared fixture contract required by this test.
    """

    organization_id: uuid.UUID
    other_organization_id: uuid.UUID
    actor_user_id: uuid.UUID


def _read_csv(content: str) -> list[dict[str, str]]:
    """
    Parse an audit CSV export into rows.
    """

    return list(
        csv.DictReader(
            io.StringIO(content)
        )
    )


def _assert_not_found(
    error: pytest.ExceptionInfo[HTTPException],
) -> None:
    """
    Assert an information-leak-safe not-found response.
    """

    assert error.value.status_code == 404
    assert error.value.detail == "Audit log not found."


def test_audit_logs_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    Foreign organizations must not read or export audit records.
    """

    token = uuid.uuid4().hex

    primary_organization_id = (
        inventory_integration_data.organization_id
    )
    foreign_organization_id = (
        inventory_integration_data.other_organization_id
    )
    actor_user_id = (
        inventory_integration_data.actor_user_id
    )

    primary_entity_id = uuid.uuid4()
    foreign_entity_id = uuid.uuid4()

    primary_summary = (
        f"Primary sensitive audit event {token}"
    )
    foreign_summary = (
        f"Foreign organization audit event {token}"
    )

    primary_secret = (
        f"PRIMARY-CONFIDENTIAL-{token}"
    )
    foreign_secret = (
        f"FOREIGN-CONFIDENTIAL-{token}"
    )

    primary_details = {
        "secret_reference": primary_secret,
        "customer_email": (
            f"primary-{token}@example.com"
        ),
        "financial_value": "875000.00",
        "nested": {
            "internal_reference": (
                f"INT-PRIMARY-{token}"
            ),
        },
    }

    foreign_details = {
        "secret_reference": foreign_secret,
        "system_event": True,
    }

    with integration_session_factory() as db:
        service = AuditLogService(db)

        primary_log = service.record_event(
            organization_id=primary_organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                action="customer.viewed",
                entity_type="Customer",
                entity_id=primary_entity_id,
                summary=primary_summary,
                status="success",
                request_method="get",
                request_path=(
                    f"/api/v1/customers/{primary_entity_id}"
                ),
                ip_address="203.0.113.10",
                user_agent=(
                    f"Novera-Isolation-Test/{token}"
                ),
                details=primary_details,
            ),
            commit=True,
        )

        foreign_log = service.record_event(
            organization_id=foreign_organization_id,
            payload=AuditLogCreate(
                actor_user_id=None,
                action="customer.viewed",
                entity_type="Customer",
                entity_id=foreign_entity_id,
                summary=foreign_summary,
                status="info",
                request_method="get",
                request_path=(
                    f"/api/v1/customers/{foreign_entity_id}"
                ),
                ip_address="198.51.100.20",
                user_agent=(
                    f"Novera-Foreign-Test/{token}"
                ),
                details=foreign_details,
            ),
            commit=True,
        )

        primary_log_id = primary_log.id
        foreign_log_id = foreign_log.id

    with integration_session_factory() as db:
        service = AuditLogService(db)

        with pytest.raises(
            HTTPException
        ) as foreign_read_error:
            service.get_audit_log(
                organization_id=foreign_organization_id,
                audit_log_id=primary_log_id,
            )

        _assert_not_found(
            foreign_read_error
        )

        foreign_logs = service.list_audit_logs(
            organization_id=foreign_organization_id,
            limit=1000,
        )

        foreign_ids = {
            item.id
            for item in foreign_logs.items
        }

        assert foreign_log_id in foreign_ids
        assert primary_log_id not in foreign_ids

        filtered_foreign_logs = (
            service.list_audit_logs(
                organization_id=foreign_organization_id,
                entity_type=" CUSTOMER ",
                entity_id=primary_entity_id,
                limit=1000,
            )
        )

        assert filtered_foreign_logs.total == 0
        assert filtered_foreign_logs.items == []

        foreign_csv = service.export_audit_logs_csv(
            organization_id=foreign_organization_id,
        )
        foreign_rows = _read_csv(
            foreign_csv
        )

        foreign_rows_by_id = {
            row["id"]: row
            for row in foreign_rows
        }

        assert str(foreign_log_id) in foreign_rows_by_id
        assert str(primary_log_id) not in foreign_rows_by_id

        assert primary_summary not in foreign_csv
        assert str(primary_entity_id) not in foreign_csv
        assert primary_secret not in foreign_csv
        assert (
            primary_details["customer_email"]
            not in foreign_csv
        )
        assert (
            primary_details["nested"][
                "internal_reference"
            ]
            not in foreign_csv
        )

        foreign_row = foreign_rows_by_id[
            str(foreign_log_id)
        ]

        assert (
            json.loads(
                foreign_row["details_json"]
            )
            == foreign_details
        )

        filtered_foreign_csv = (
            service.export_audit_logs_csv(
                organization_id=foreign_organization_id,
                entity_type="customer",
                entity_id=primary_entity_id,
            )
        )

        assert _read_csv(
            filtered_foreign_csv
        ) == []

        unchanged_primary_log = (
            service.get_audit_log(
                organization_id=primary_organization_id,
                audit_log_id=primary_log_id,
            )
        )

        assert (
            unchanged_primary_log.organization_id
            == primary_organization_id
        )
        assert (
            unchanged_primary_log.actor_user_id
            == actor_user_id
        )
        assert (
            unchanged_primary_log.action
            == "customer.viewed"
        )
        assert (
            unchanged_primary_log.entity_type
            == "customer"
        )
        assert (
            unchanged_primary_log.entity_id
            == primary_entity_id
        )
        assert (
            unchanged_primary_log.summary
            == primary_summary
        )
        assert (
            unchanged_primary_log.request_method
            == "GET"
        )
        assert (
            unchanged_primary_log.details
            == primary_details
        )

        primary_logs = service.list_audit_logs(
            organization_id=primary_organization_id,
            action=" CUSTOMER.VIEWED ",
            entity_type=" CUSTOMER ",
            entity_id=primary_entity_id,
            limit=1000,
        )

        primary_ids = {
            item.id
            for item in primary_logs.items
        }

        assert primary_log_id in primary_ids
        assert foreign_log_id not in primary_ids

        primary_csv = service.export_audit_logs_csv(
            organization_id=primary_organization_id,
            entity_id=primary_entity_id,
        )
        primary_rows = _read_csv(
            primary_csv
        )

        assert len(primary_rows) == 1

        primary_row = primary_rows[0]

        assert primary_row["id"] == str(primary_log_id)
        assert (
            primary_row["organization_id"]
            == str(primary_organization_id)
        )
        assert (
            primary_row["entity_id"]
            == str(primary_entity_id)
        )
        assert (
            primary_row["summary"]
            == primary_summary
        )
        assert (
            json.loads(
                primary_row["details_json"]
            )
            == primary_details
        )

        assert foreign_summary not in primary_csv
        assert str(foreign_entity_id) not in primary_csv
        assert foreign_secret not in primary_csv
