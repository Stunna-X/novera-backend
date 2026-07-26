"""Shared PostgreSQL integration-test fixtures."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from sqlalchemy import create_engine, delete, inspect, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.models.customer import Customer
from app.models.inventory import InventoryItem, InventoryLocation
from app.models.organization import Organization
from app.models.user import User
from app.models.work_order import WorkOrder


@dataclass(frozen=True)
class InventoryIntegrationData:
    """Identifiers for one isolated integration-test dataset."""

    organization_id: uuid.UUID
    other_organization_id: uuid.UUID
    actor_user_id: uuid.UUID
    item_id: uuid.UUID
    other_item_id: uuid.UUID
    source_location_id: uuid.UUID
    destination_location_id: uuid.UUID
    alternate_location_id: uuid.UUID
    other_location_id: uuid.UUID
    work_order_id: uuid.UUID
    second_work_order_id: uuid.UUID


def _required_test_database_url() -> str:
    """Return and validate the dedicated PostgreSQL test URL."""

    database_url = os.getenv("TEST_DATABASE_URL")

    if not database_url:
        pytest.skip(
            "TEST_DATABASE_URL is required for PostgreSQL "
            "integration tests."
        )

    url = make_url(database_url)
    database_name = (url.database or "").lower()

    if not url.get_backend_name().startswith("postgresql"):
        pytest.fail(
            "TEST_DATABASE_URL must use PostgreSQL.",
            pytrace=False,
        )

    if "test" not in database_name:
        pytest.fail(
            "Refusing to run integration tests against a database "
            "whose name does not contain 'test'.",
            pytrace=False,
        )

    return database_url


@pytest.fixture(scope="session")
def integration_engine() -> Iterator[Engine]:
    """Provide the migrated dedicated PostgreSQL test engine."""

    engine = create_engine(
        _required_test_database_url(),
        pool_pre_ping=True,
    )

    with engine.connect() as connection:
        if not inspect(connection).has_table("alembic_version"):
            pytest.fail(
                "The test database is not migrated. Run Alembic "
                "upgrade head against TEST_DATABASE_URL first.",
                pytrace=False,
            )

        connection.execute(text("SELECT 1"))

    yield engine

    engine.dispose()


@pytest.fixture(scope="session")
def integration_session_factory(
    integration_engine: Engine,
) -> sessionmaker[Session]:
    """Create independent sessions for concurrency testing."""

    return sessionmaker(
        bind=integration_engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture
def inventory_integration_data(
    integration_session_factory: sessionmaker[Session],
) -> Iterator[InventoryIntegrationData]:
    """Create and later remove one tenant-isolated test dataset."""

    token = uuid.uuid4().hex

    organization = Organization(
        id=uuid.uuid4(),
        name=f"Inventory Integration {token}",
        slug=f"inventory-integration-{token}",
        timezone="UTC",
    )
    other_organization = Organization(
        id=uuid.uuid4(),
        name=f"Inventory Isolation {token}",
        slug=f"inventory-isolation-{token}",
        timezone="UTC",
    )
    actor = User(
        id=uuid.uuid4(),
        first_name="Inventory",
        last_name="Tester",
        email=f"inventory-{token}@example.test",
        password_hash="integration-test-password-hash",
        email_verified=True,
    )

    customer = Customer(
        id=uuid.uuid4(),
        organization_id=organization.id,
        name=f"Integration Customer {token}",
    )

    work_order = WorkOrder(
        id=uuid.uuid4(),
        organization_id=organization.id,
        customer_id=customer.id,
        work_order_number=f"INT-{token[:10]}-1",
        title="Inventory integration work order",
        status="draft",
        priority="normal",
    )
    second_work_order = WorkOrder(
        id=uuid.uuid4(),
        organization_id=organization.id,
        customer_id=customer.id,
        work_order_number=f"INT-{token[:10]}-2",
        title="Second inventory integration work order",
        status="draft",
        priority="normal",
    )

    item = InventoryItem(
        id=uuid.uuid4(),
        organization_id=organization.id,
        sku=f"INT-{token[:12]}",
        name="Integration casing pipe",
        item_type="material",
        unit_of_measure="length",
        default_unit_cost="2500.0000",
        currency="NGN",
        reorder_level="5.000",
        details={},
    )
    other_item = InventoryItem(
        id=uuid.uuid4(),
        organization_id=other_organization.id,
        sku=f"ISO-{token[:12]}",
        name="Isolation inventory item",
        item_type="material",
        unit_of_measure="each",
        default_unit_cost="100.0000",
        currency="NGN",
        reorder_level="0.000",
        details={},
    )

    source_location = InventoryLocation(
        id=uuid.uuid4(),
        organization_id=organization.id,
        code=f"SRC-{token[:10]}",
        name="Integration source warehouse",
        location_type="warehouse",
    )
    destination_location = InventoryLocation(
        id=uuid.uuid4(),
        organization_id=organization.id,
        code=f"DST-{token[:10]}",
        name="Integration destination warehouse",
        location_type="warehouse",
    )
    alternate_location = InventoryLocation(
        id=uuid.uuid4(),
        organization_id=organization.id,
        code=f"ALT-{token[:10]}",
        name="Integration alternate warehouse",
        location_type="warehouse",
    )
    other_location = InventoryLocation(
        id=uuid.uuid4(),
        organization_id=other_organization.id,
        code=f"ISO-{token[:10]}",
        name="Isolation warehouse",
        location_type="warehouse",
    )

    with integration_session_factory() as db:
        db.add_all(
            [
                organization,
                other_organization,
                actor,
            ]
        )
        db.flush()

        db.add(customer)
        db.flush()

        db.add_all(
            [
                work_order,
                second_work_order,
                item,
                other_item,
                source_location,
                destination_location,
                alternate_location,
                other_location,
            ]
        )
        db.commit()

    data = InventoryIntegrationData(
        organization_id=organization.id,
        other_organization_id=other_organization.id,
        actor_user_id=actor.id,
        item_id=item.id,
        other_item_id=other_item.id,
        source_location_id=source_location.id,
        destination_location_id=destination_location.id,
        alternate_location_id=alternate_location.id,
        other_location_id=other_location.id,
        work_order_id=work_order.id,
        second_work_order_id=second_work_order.id,
    )

    try:
        yield data

    finally:
        with integration_session_factory() as db:
            db.execute(
                delete(Organization).where(
                    Organization.id.in_(
                        [
                            data.organization_id,
                            data.other_organization_id,
                        ]
                    )
                )
            )
            db.execute(
                delete(User).where(
                    User.id == data.actor_user_id
                )
            )
            db.commit()
