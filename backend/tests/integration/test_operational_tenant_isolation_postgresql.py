"""
PostgreSQL tenant-isolation tests for operational resources.
"""

from __future__ import annotations

import uuid
from typing import Protocol

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session, sessionmaker

from app.schemas.customer import CreateCustomerSchema
from app.schemas.customer_site import (
    CreateCustomerSiteSchema,
    UpdateCustomerSiteSchema,
)
from app.schemas.work_order import (
    CreateWorkOrderSchema,
    UpdateWorkOrderSchema,
)
from app.services.customer_service import CustomerService
from app.services.customer_site_service import CustomerSiteService
from app.services.work_order_service import WorkOrderService


class TenantIntegrationData(Protocol):
    """
    Minimum fixture contract required by these tests.
    """

    organization_id: uuid.UUID
    other_organization_id: uuid.UUID
    actor_user_id: uuid.UUID


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


def test_customer_site_ids_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    A foreign organization must not read or mutate a customer site.
    """

    token = uuid.uuid4().hex
    original_name = f"Tenant Borehole Site {token[:10]}"

    with integration_session_factory() as db:
        customers = CustomerService(db)

        primary_customer = customers.create_customer(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            payload=CreateCustomerSchema(
                name=f"Primary Site Customer {token[:10]}",
                email=f"primary-site-{token}@example.com",
            ),
        )

        foreign_customer = customers.create_customer(
            organization_id=(
                inventory_integration_data
                .other_organization_id
            ),
            payload=CreateCustomerSchema(
                name=f"Foreign Site Customer {token[:10]}",
                email=f"foreign-site-{token}@example.com",
            ),
        )

        site = CustomerSiteService(db).create_site(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            customer_id=primary_customer.id,
            payload=CreateCustomerSiteSchema(
                name=original_name,
                site_code=f"SITE-{token[:10]}",
                address_line_1="12 Tenant Isolation Road",
                city="Abuja",
                country="Nigeria",
            ),
        )

        primary_customer_id = primary_customer.id
        foreign_customer_id = foreign_customer.id
        site_id = site.id

    with integration_session_factory() as db:
        service = CustomerSiteService(db)

        with pytest.raises(HTTPException) as read_error:
            service.get_site(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                customer_id=foreign_customer_id,
                site_id=site_id,
            )

        _assert_not_found(
            read_error,
            detail="Customer site not found.",
        )

        foreign_sites = service.list_sites(
            organization_id=(
                inventory_integration_data
                .other_organization_id
            ),
            customer_id=foreign_customer_id,
        )

        assert all(
            item.id != site_id
            for item in foreign_sites.items
        )

        with pytest.raises(HTTPException) as update_error:
            service.update_site(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                customer_id=foreign_customer_id,
                site_id=site_id,
                payload=UpdateCustomerSiteSchema(
                    name="Cross-tenant site overwrite",
                ),
            )

        _assert_not_found(
            update_error,
            detail="Customer site not found.",
        )

        with pytest.raises(
            HTTPException
        ) as deactivate_error:
            service.deactivate_site(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                customer_id=foreign_customer_id,
                site_id=site_id,
            )

        _assert_not_found(
            deactivate_error,
            detail="Customer site not found.",
        )

        original_site = service.get_site(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            customer_id=primary_customer_id,
            site_id=site_id,
        )

        assert original_site.name == original_name
        assert original_site.is_active is True


def test_work_order_ids_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    inventory_integration_data: TenantIntegrationData,
) -> None:
    """
    A foreign organization must not read or mutate a work order.
    """

    token = uuid.uuid4().hex
    original_title = f"Tenant Borehole Job {token[:10]}"

    with integration_session_factory() as db:
        customer = CustomerService(db).create_customer(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            payload=CreateCustomerSchema(
                name=f"Work Order Customer {token[:10]}",
                email=f"work-order-{token}@example.com",
            ),
        )

        work_order = WorkOrderService(db).create_work_order(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            payload=CreateWorkOrderSchema(
                customer_id=customer.id,
                work_order_number=f"TEN-{token[:10]}",
                title=original_title,
                priority="normal",
                status="draft",
            ),
            actor_user_id=(
                inventory_integration_data.actor_user_id
            ),
        )

        work_order_id = work_order.id

    with integration_session_factory() as db:
        service = WorkOrderService(db)

        with pytest.raises(HTTPException) as read_error:
            service.get_work_order(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=work_order_id,
            )

        _assert_not_found(
            read_error,
            detail="Work order not found.",
        )

        foreign_work_orders = service.list_work_orders(
            organization_id=(
                inventory_integration_data
                .other_organization_id
            ),
        )

        assert all(
            item.id != work_order_id
            for item in foreign_work_orders.items
        )

        with pytest.raises(HTTPException) as update_error:
            service.update_work_order(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=work_order_id,
                payload=UpdateWorkOrderSchema(
                    title="Cross-tenant job overwrite",
                ),
                actor_user_id=(
                    inventory_integration_data.actor_user_id
                ),
            )

        _assert_not_found(
            update_error,
            detail="Work order not found.",
        )

        with pytest.raises(
            HTTPException
        ) as deactivate_error:
            service.deactivate_work_order(
                organization_id=(
                    inventory_integration_data
                    .other_organization_id
                ),
                work_order_id=work_order_id,
                actor_user_id=(
                    inventory_integration_data.actor_user_id
                ),
            )

        _assert_not_found(
            deactivate_error,
            detail="Work order not found.",
        )

        original_work_order = service.get_work_order(
            organization_id=(
                inventory_integration_data.organization_id
            ),
            work_order_id=work_order_id,
        )

        assert original_work_order.title == original_title
        assert original_work_order.is_active is True
