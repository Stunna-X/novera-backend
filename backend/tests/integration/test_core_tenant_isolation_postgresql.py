"""
PostgreSQL tenant-isolation tests for core operational domains.
"""

from __future__ import annotations

import uuid
from typing import Protocol

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.schemas.asset import (
    CreateAssetSchema,
    UpdateAssetSchema,
)
from app.schemas.customer import (
    CreateCustomerSchema,
    UpdateCustomerSchema,
)
from app.services.asset_service import AssetService
from app.services.customer_service import CustomerService


class TenantIntegrationData(Protocol):
    """
    Minimum fixture contract required by these tests.
    """

    organization_id: uuid.UUID
    other_organization_id: uuid.UUID


def _assert_not_found(
    error: pytest.ExceptionInfo[HTTPException],
    *,
    detail: str,
) -> None:
    """
    Assert an information-leak-safe not-found response.
    """

    assert error.value.status_code == 404
    assert error.value.detail == detail


def test_customer_ids_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    A foreign organization must not read or mutate a customer.
    """

    token = uuid.uuid4().hex
    original_name = f"Tenant Customer {token[:10]}"

    with integration_session_factory() as db:
        customer = CustomerService(db).create_customer(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            payload=CreateCustomerSchema(
                name=original_name,
                email=f"tenant-{token}@example.com",
            ),
        )

        customer_id = customer.id

    with integration_session_factory() as db:
        service = CustomerService(db)

        with pytest.raises(HTTPException) as read_error:
            service.get_customer(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                customer_id=customer_id,
            )

        _assert_not_found(
            read_error,
            detail="Customer not found.",
        )

        foreign_customers = service.list_customers(
            organization_id=(
                inventory_integration_data
                .other_organization_id
            ),
        )

        assert all(
            item.id != customer_id
            for item in foreign_customers.items
        )

        with pytest.raises(HTTPException) as update_error:
            service.update_customer(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                customer_id=customer_id,
                payload=UpdateCustomerSchema(
                    name="Cross-tenant overwrite",
                ),
            )

        _assert_not_found(
            update_error,
            detail="Customer not found.",
        )

        with pytest.raises(
            HTTPException
        ) as deactivate_error:
            service.deactivate_customer(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                customer_id=customer_id,
            )

        _assert_not_found(
            deactivate_error,
            detail="Customer not found.",
        )

        original_customer = service.get_customer(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            customer_id=customer_id,
        )

        assert original_customer.name == original_name
        assert original_customer.is_active is True


def test_asset_ids_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    A foreign organization must not read or mutate an asset.
    """

    token = uuid.uuid4().hex
    original_name = f"Tenant Drill Rig {token[:10]}"

    with integration_session_factory() as db:
        asset = AssetService(db).create_asset(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            payload=CreateAssetSchema(
                asset_code=f"TEN-{token[:10]}",
                name=original_name,
                asset_type="equipment",
            ),
        )

        asset_id = asset.id

    with integration_session_factory() as db:
        service = AssetService(db)

        with pytest.raises(HTTPException) as read_error:
            service.get_asset(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                asset_id=asset_id,
            )

        _assert_not_found(
            read_error,
            detail="Asset not found.",
        )

        foreign_assets = service.list_assets(
            organization_id=(
                inventory_integration_data
                .other_organization_id
            ),
        )

        assert all(
            item.id != asset_id
            for item in foreign_assets.items
        )

        with pytest.raises(HTTPException) as update_error:
            service.update_asset(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                asset_id=asset_id,
                payload=UpdateAssetSchema(
                    name="Cross-tenant overwrite",
                ),
            )

        _assert_not_found(
            update_error,
            detail="Asset not found.",
        )

        with pytest.raises(
            HTTPException
        ) as deactivate_error:
            service.deactivate_asset(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                asset_id=asset_id,
            )

        _assert_not_found(
            deactivate_error,
            detail="Asset not found.",
        )

        original_asset = service.get_asset(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            asset_id=asset_id,
        )

        assert original_asset.name == original_name
        assert original_asset.is_active is True
