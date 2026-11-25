"""
PostgreSQL tenant-isolation tests for standalone workforce profiles.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session, sessionmaker

from app.models.organization import Organization
from app.models.workforce_profile import WorkforceProfile
from app.schemas.workforce import (
    CreateWorkforceProfileSchema,
    UpdateWorkforceProfileSchema,
)
from app.services.workforce_service import WorkforceService


@dataclass(frozen=True)
class WorkforceIsolationData:
    """Identifiers for a dedicated two-tenant workforce dataset."""

    organization_id: uuid.UUID
    other_organization_id: uuid.UUID


@pytest.fixture
def workforce_isolation_data(
    integration_session_factory: sessionmaker[Session],
) -> Iterator[WorkforceIsolationData]:
    """Create and remove a dedicated workforce isolation dataset."""

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

    with integration_session_factory() as db:
        db.add_all([organization, other_organization])
        db.commit()

    data = WorkforceIsolationData(
        organization_id=organization.id,
        other_organization_id=other_organization.id,
    )

    try:
        yield data

    finally:
        with integration_session_factory() as db:
            organization_ids = [
                data.organization_id,
                data.other_organization_id,
            ]

            db.execute(
                delete(WorkforceProfile).where(
                    WorkforceProfile.organization_id.in_(
                        organization_ids
                    )
                )
            )
            db.execute(
                delete(Organization).where(
                    Organization.id.in_(organization_ids)
                )
            )
            db.commit()


def _assert_not_found(
    error: pytest.ExceptionInfo[HTTPException],
    *,
    detail: str,
) -> None:
    """Assert an information-leak-safe not-found response."""

    assert error.value.status_code == 404
    assert error.value.detail == detail


def test_workforce_profiles_cannot_cross_organization_boundary(
    integration_session_factory: sessionmaker[Session],
    workforce_isolation_data: WorkforceIsolationData,
) -> None:
    """Standalone employees must remain isolated by organization."""

    original_job_title = "Lead Borehole Technician"
    foreign_job_title = "Foreign Field Technician"

    with integration_session_factory() as db:
        service = WorkforceService(db)

        primary_profile = service.create_profile(
            organization_id=workforce_isolation_data.organization_id,
            payload=CreateWorkforceProfileSchema(
                full_name="Primary Technician",
                job_title=original_job_title,
                employment_type="full_time",
                phone="08012345678",
                status="active",
            ),
        )

        standalone_profile = service.create_profile(
            organization_id=workforce_isolation_data.organization_id,
            payload=CreateWorkforceProfileSchema(
                full_name="Standalone Field Technician",
                job_title="Field Technician",
                employment_type="contractor",
                status="active",
            ),
        )

        foreign_profile = service.create_profile(
            organization_id=workforce_isolation_data.other_organization_id,
            payload=CreateWorkforceProfileSchema(
                full_name="Foreign Technician",
                job_title=foreign_job_title,
                employment_type="contractor",
                status="active",
            ),
        )

        primary_profile_id = primary_profile.id
        standalone_profile_id = standalone_profile.id
        foreign_profile_id = foreign_profile.id

        assert primary_profile.full_name == "Primary Technician"
        assert standalone_profile.full_name == (
            "Standalone Field Technician"
        )
        assert foreign_profile.full_name == "Foreign Technician"

    # Use a fresh session for tenant-isolation assertions.
    with integration_session_factory() as db:
        service = WorkforceService(db)

        with pytest.raises(HTTPException) as read_error:
            service.get_profile(
                organization_id=workforce_isolation_data.other_organization_id,
                profile_id=primary_profile_id,
            )

        _assert_not_found(
            read_error,
            detail="Workforce profile not found.",
        )

        with pytest.raises(HTTPException) as standalone_read_error:
            service.get_profile(
                organization_id=workforce_isolation_data.other_organization_id,
                profile_id=standalone_profile_id,
            )

        _assert_not_found(
            standalone_read_error,
            detail="Workforce profile not found.",
        )

        foreign_profiles = service.list_profiles(
            organization_id=workforce_isolation_data.other_organization_id,
        )
        foreign_profile_ids = {
            item.id for item in foreign_profiles.items
        }

        assert foreign_profile_id in foreign_profile_ids
        assert primary_profile_id not in foreign_profile_ids
        assert standalone_profile_id not in foreign_profile_ids

        primary_profiles = service.list_profiles(
            organization_id=workforce_isolation_data.organization_id,
        )
        primary_profile_ids = {
            item.id for item in primary_profiles.items
        }

        assert primary_profile_id in primary_profile_ids
        assert standalone_profile_id in primary_profile_ids
        assert foreign_profile_id not in primary_profile_ids

        with pytest.raises(HTTPException) as update_error:
            service.update_profile(
                organization_id=workforce_isolation_data.other_organization_id,
                profile_id=primary_profile_id,
                payload=UpdateWorkforceProfileSchema(
                    job_title="Cross-tenant overwrite",
                ),
            )

        _assert_not_found(
            update_error,
            detail="Workforce profile not found.",
        )

        with pytest.raises(HTTPException) as deactivate_error:
            service.deactivate_profile(
                organization_id=workforce_isolation_data.other_organization_id,
                profile_id=primary_profile_id,
            )

        _assert_not_found(
            deactivate_error,
            detail="Workforce profile not found.",
        )

        original_profile = service.get_profile(
            organization_id=workforce_isolation_data.organization_id,
            profile_id=primary_profile_id,
        )

        assert original_profile.job_title == original_job_title
        assert original_profile.phone == "08012345678"
        assert original_profile.is_active is True
        assert original_profile.status == "active"

        unchanged_standalone_profile = service.get_profile(
            organization_id=workforce_isolation_data.organization_id,
            profile_id=standalone_profile_id,
        )

        assert unchanged_standalone_profile.full_name == (
            "Standalone Field Technician"
        )
        assert unchanged_standalone_profile.is_active is True

        unchanged_foreign_profile = service.get_profile(
            organization_id=workforce_isolation_data.other_organization_id,
            profile_id=foreign_profile_id,
        )

        assert unchanged_foreign_profile.job_title == foreign_job_title
        assert unchanged_foreign_profile.is_active is True
