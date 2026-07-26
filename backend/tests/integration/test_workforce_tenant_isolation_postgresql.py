"""
PostgreSQL tenant-isolation tests for workforce profiles.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.enums.user import UserStatus
from app.models.membership import Membership
from app.models.organization import Organization
from app.models.role import Role
from app.models.user import User
from app.models.workforce_profile import WorkforceProfile
from app.schemas.workforce import (
    CreateWorkforceProfileSchema,
    UpdateWorkforceProfileSchema,
)
from app.services.workforce_service import WorkforceService


@dataclass(frozen=True)
class WorkforceIsolationData:
    """
    Identifiers for a dedicated two-tenant workforce dataset.
    """

    organization_id: uuid.UUID
    other_organization_id: uuid.UUID
    membership_id: uuid.UUID
    other_membership_id: uuid.UUID
    user_id: uuid.UUID
    other_user_id: uuid.UUID
    role_id: uuid.UUID


@pytest.fixture
def workforce_isolation_data(
    integration_session_factory: sessionmaker[Session],
) -> Iterator[WorkforceIsolationData]:
    """
    Create and remove a dedicated workforce isolation dataset.
    """

    token = uuid.uuid4().hex

    organization = Organization(
        id=uuid.uuid4(),
        name=f"Workforce Primary {token}",
        slug=f"workforce-primary-{token}",
        timezone="UTC",
    )
    other_organization = Organization(
        id=uuid.uuid4(),
        name=f"Workforce Foreign {token}",
        slug=f"workforce-foreign-{token}",
        timezone="UTC",
    )

    role = Role(
        id=uuid.uuid4(),
        name=f"Workforce Isolation Role {token}",
        description="Dedicated workforce isolation test role.",
        is_system=False,
    )

    user = User(
        id=uuid.uuid4(),
        first_name="Primary",
        last_name="Technician",
        email=f"workforce-primary-{token}@example.com",
        password_hash="integration-test-password-hash",
        status=UserStatus.ACTIVE,
        email_verified=True,
    )
    other_user = User(
        id=uuid.uuid4(),
        first_name="Foreign",
        last_name="Technician",
        email=f"workforce-foreign-{token}@example.com",
        password_hash="integration-test-password-hash",
        status=UserStatus.ACTIVE,
        email_verified=True,
    )

    membership = Membership(
        id=uuid.uuid4(),
        organization_id=organization.id,
        user_id=user.id,
        role_id=role.id,
    )
    other_membership = Membership(
        id=uuid.uuid4(),
        organization_id=other_organization.id,
        user_id=other_user.id,
        role_id=role.id,
    )

    with integration_session_factory() as db:
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
                membership,
                other_membership,
            ]
        )
        db.commit()

    data = WorkforceIsolationData(
        organization_id=organization.id,
        other_organization_id=other_organization.id,
        membership_id=membership.id,
        other_membership_id=other_membership.id,
        user_id=user.id,
        other_user_id=other_user.id,
        role_id=role.id,
    )

    try:
        yield data

    finally:
        with integration_session_factory() as db:
            organization_ids = [
                data.organization_id,
                data.other_organization_id,
            ]
            membership_ids = [
                data.membership_id,
                data.other_membership_id,
            ]
            user_ids = [
                data.user_id,
                data.other_user_id,
            ]

            db.execute(
                delete(WorkforceProfile).where(
                    WorkforceProfile.organization_id.in_(
                        organization_ids
                    )
                )
            )
            db.execute(
                delete(Membership).where(
                    Membership.id.in_(membership_ids)
                )
            )
            db.execute(
                delete(Organization).where(
                    Organization.id.in_(organization_ids)
                )
            )
            db.execute(
                delete(User).where(
                    User.id.in_(user_ids)
                )
            )
            db.execute(
                delete(Role).where(
                    Role.id == data.role_id
                )
            )
            db.commit()


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


def test_workforce_profiles_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    workforce_isolation_data: WorkforceIsolationData,
) -> None:
    """
    Foreign memberships and profile IDs must remain tenant-isolated.
    """

    token = uuid.uuid4().hex
    original_job_title = "Lead Borehole Technician"
    foreign_job_title = "Foreign Field Technician"

    with integration_session_factory() as db:
        service = WorkforceService(db)

        with pytest.raises(
            HTTPException
        ) as foreign_membership_error:
            service.create_profile(
                organization_id=(
                    workforce_isolation_data.organization_id
                ),
                payload=CreateWorkforceProfileSchema(
                    membership_id=(
                        workforce_isolation_data
                        .other_membership_id
                    ),
                    employee_code=f"INVALID-{token[:10]}",
                    job_title="Cross-tenant technician",
                    employment_type="full_time",
                    skills=["drilling"],
                ),
            )

        _assert_not_found(
            foreign_membership_error,
            detail="Organization membership not found.",
        )

        profile = service.create_profile(
            organization_id=(
                workforce_isolation_data.organization_id
            ),
            payload=CreateWorkforceProfileSchema(
                membership_id=(
                    workforce_isolation_data.membership_id
                ),
                employee_code=f"PRI-{token[:10]}",
                job_title=original_job_title,
                employment_type="full_time",
                skills=[
                    "borehole drilling",
                    "pump installation",
                ],
                status="active",
                is_available=True,
            ),
        )

        foreign_profile = service.create_profile(
            organization_id=(
                workforce_isolation_data
                .other_organization_id
            ),
            payload=CreateWorkforceProfileSchema(
                membership_id=(
                    workforce_isolation_data
                    .other_membership_id
                ),
                employee_code=f"FOR-{token[:10]}",
                job_title=foreign_job_title,
                employment_type="contractor",
                skills=["field inspection"],
                status="active",
                is_available=True,
            ),
        )

        profile_id = profile.id
        foreign_profile_id = foreign_profile.id

    with integration_session_factory() as db:
        service = WorkforceService(db)

        with pytest.raises(HTTPException) as read_error:
            service.get_profile(
                organization_id=(
                    workforce_isolation_data
                    .other_organization_id
                ),
                profile_id=profile_id,
            )

        _assert_not_found(
            read_error,
            detail="Workforce profile not found.",
        )

        foreign_profiles = service.list_profiles(
            organization_id=(
                workforce_isolation_data.other_organization_id
            ),
        )

        foreign_profile_ids = {
            item.id
            for item in foreign_profiles.items
        }

        assert foreign_profile_id in foreign_profile_ids
        assert profile_id not in foreign_profile_ids

        with pytest.raises(HTTPException) as update_error:
            service.update_profile(
                organization_id=(
                    workforce_isolation_data
                    .other_organization_id
                ),
                profile_id=profile_id,
                payload=UpdateWorkforceProfileSchema(
                    job_title="Cross-tenant overwrite",
                    skills=["unauthorized skill"],
                ),
            )

        _assert_not_found(
            update_error,
            detail="Workforce profile not found.",
        )

        with pytest.raises(
            HTTPException
        ) as deactivate_error:
            service.deactivate_profile(
                organization_id=(
                    workforce_isolation_data
                    .other_organization_id
                ),
                profile_id=profile_id,
            )

        _assert_not_found(
            deactivate_error,
            detail="Workforce profile not found.",
        )

        original_profile = service.get_profile(
            organization_id=(
                workforce_isolation_data.organization_id
            ),
            profile_id=profile_id,
        )

        assert (
            original_profile.job_title
            == original_job_title
        )
        assert original_profile.skills == [
            "borehole drilling",
            "pump installation",
        ]
        assert original_profile.is_active is True
        assert original_profile.is_available is True

        unchanged_foreign_profile = service.get_profile(
            organization_id=(
                workforce_isolation_data
                .other_organization_id
            ),
            profile_id=foreign_profile_id,
        )

        assert (
            unchanged_foreign_profile.job_title
            == foreign_job_title
        )
        assert unchanged_foreign_profile.is_active is True
