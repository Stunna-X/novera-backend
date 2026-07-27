"""PostgreSQL tenant-isolation tests for procurement alert preferences."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from app.models.membership import Membership
from app.models.organization import Organization
from app.models.procurement_alert import ProcurementAlertPreference
from app.models.role import Role
from app.models.user import User
from app.enums.user import UserStatus
from app.repositories.procurement_alert import ProcurementAlertRepository


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason=(
        "TEST_DATABASE_URL is required for PostgreSQL "
        "integration tests."
    ),
)


def test_preferences_cannot_cross_organization_boundary() -> None:
    engine = create_engine(TEST_DATABASE_URL)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    token = uuid.uuid4().hex
    organization = Organization(
        name=f"Alert Primary {token}",
        slug=f"alert-primary-{token}",
    )
    other_organization = Organization(
        name=f"Alert Foreign {token}",
        slug=f"alert-foreign-{token}",
    )
    role = Role(
        name=f"Alert Role {token}",
        description="Procurement alert integration role.",
        is_system=False,
    )
    user = User(
        first_name="Primary",
        last_name="Alert",
        email=f"alert-primary-{token}@example.com",
        password_hash="integration-test-password-hash",
        status=UserStatus.ACTIVE,
        email_verified=True,
    )
    other_user = User(
        first_name="Foreign",
        last_name="Alert",
        email=f"alert-foreign-{token}@example.com",
        password_hash="integration-test-password-hash",
        status=UserStatus.ACTIVE,
        email_verified=True,
    )
    try:
        with SessionLocal() as db:
            db.add_all(
                [
                    organization,
                    other_organization,
                    role,
                    user,
                    other_user,
                ]
            )
            db.flush()
            db.add_all(
                [
                    Membership(
                        organization_id=organization.id,
                        user_id=user.id,
                        role_id=role.id,
                    ),
                    Membership(
                        organization_id=other_organization.id,
                        user_id=other_user.id,
                        role_id=role.id,
                    ),
                    ProcurementAlertPreference(
                        organization_id=organization.id,
                        user_id=user.id,
                    ),
                    ProcurementAlertPreference(
                        organization_id=other_organization.id,
                        user_id=other_user.id,
                    ),
                ]
            )
            db.commit()
        with SessionLocal() as db:
            repository = ProcurementAlertRepository(db)
            assert repository.get_preference(
                organization.id,
                user.id,
            ) is not None
            assert repository.get_preference(
                organization.id,
                other_user.id,
            ) is None
            assert repository.get_preference(
                other_organization.id,
                user.id,
            ) is None
    finally:
        with SessionLocal() as db:
            db.execute(
                delete(ProcurementAlertPreference).where(
                    ProcurementAlertPreference.organization_id.in_(
                        [organization.id, other_organization.id]
                    )
                )
            )
            db.execute(
                delete(Membership).where(
                    Membership.organization_id.in_(
                        [organization.id, other_organization.id]
                    )
                )
            )
            db.execute(
                delete(Organization).where(
                    Organization.id.in_(
                        [organization.id, other_organization.id]
                    )
                )
            )
            db.execute(
                delete(User).where(
                    User.id.in_([user.id, other_user.id])
                )
            )
            db.execute(delete(Role).where(Role.id == role.id))
            db.commit()
        engine.dispose()
