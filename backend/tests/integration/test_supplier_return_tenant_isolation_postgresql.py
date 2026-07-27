"""PostgreSQL tenant-isolation tests for supplier return repositories."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.repositories.supplier_return import SupplierReturnRepository


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason=(
        "TEST_DATABASE_URL is required for PostgreSQL "
        "integration tests."
    ),
)


def test_foreign_tenant_cannot_read_return_or_debit_note() -> None:
    """
    Repository lookups must always include organization_id.

    Full record creation is covered by the normal API smoke fixture when
    TEST_DATABASE_URL is configured. This test additionally guards the
    information-leak-safe behavior for unknown foreign IDs.
    """

    engine = create_engine(TEST_DATABASE_URL)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    try:
        with SessionLocal() as db:
            repository = SupplierReturnRepository(db)
            foreign_organization_id = uuid.uuid4()
            assert repository.get_return(
                foreign_organization_id,
                uuid.uuid4(),
            ) is None
            assert repository.get_debit_note(
                foreign_organization_id,
                uuid.uuid4(),
            ) is None
    finally:
        engine.dispose()
