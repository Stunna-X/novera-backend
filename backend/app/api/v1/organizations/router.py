"""
Organization routes.

Provides authenticated endpoints for creating, viewing, updating, and
deactivating organizations, plus protected document settings.
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    status,
)
from sqlalchemy.orm import Session

from app.api.deps import (
    OrganizationContext,
    require_permission,
)
from app.auth.dependencies import get_current_user
from app.database.session import get_db
from app.models.organization import Organization
from app.models.user import User
from app.schemas.organization import (
    CreateOrganizationSchema,
    OrganizationResponse,
    UpdateOrganizationSchema,
)
from app.schemas.organization_document_settings import (
    OrganizationDocumentSettingsResponse,
    UpdateOrganizationDocumentSettingsSchema,
)
from app.services.organization_document_settings_service import (
    OrganizationDocumentSettingsService,
)
from app.services.organization_service import OrganizationService


router = APIRouter(
    prefix="/organizations",
    tags=["Organizations"],
)


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create organization",
)
def create_organization(
    payload: CreateOrganizationSchema,
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
) -> Organization:
    """
    Create a new organization.

    The authenticated user automatically becomes the Owner.
    """

    service = OrganizationService(db)

    return service.create_organization(
        payload=payload,
        current_user=current_user,
    )


@router.get(
    "",
    response_model=list[OrganizationResponse],
    summary="List my organizations",
)
def list_organizations(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    ),
) -> list[Organization]:
    """
    Return active organizations belonging to the current user.

    Sensitive document settings are excluded.
    """

    service = OrganizationService(db)

    return service.list_user_organizations(
        current_user=current_user,
    )


@router.get(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Get organization",
)
def get_organization(
    context: OrganizationContext = Depends(
        require_permission(
            "organizations.read"
        )
    ),
) -> Organization:
    """
    Return safe general organization details.

    Requires:
    - organizations.read
    """

    return context.organization


@router.patch(
    "/{organization_id}",
    response_model=OrganizationResponse,
    summary="Update organization",
)
def update_organization(
    payload: UpdateOrganizationSchema,
    context: OrganizationContext = Depends(
        require_permission(
            "organizations.update"
        )
    ),
    db: Session = Depends(
        get_db
    ),
) -> Organization:
    """
    Update general organization details.

    Sensitive document settings must use the dedicated endpoint.

    Requires:
    - organizations.update
    """

    service = OrganizationService(db)

    return service.update_organization(
        organization=context.organization,
        payload=payload,
    )


@router.get(
    "/{organization_id}/document-settings",
    response_model=OrganizationDocumentSettingsResponse,
    summary="Get organization document settings",
)
def get_organization_document_settings(
    context: OrganizationContext = Depends(
        require_permission(
            "organizations.update"
        )
    ),
    db: Session = Depends(
        get_db
    ),
) -> OrganizationDocumentSettingsResponse:
    """
    Return protected tax, banking, payment, invoice, and quote settings.

    Requires:
    - organizations.update
    """

    service = OrganizationDocumentSettingsService(
        db
    )

    return service.get_settings(
        organization=context.organization,
    )


@router.patch(
    "/{organization_id}/document-settings",
    response_model=OrganizationDocumentSettingsResponse,
    summary="Update organization document settings",
)
def update_organization_document_settings(
    payload: UpdateOrganizationDocumentSettingsSchema,
    context: OrganizationContext = Depends(
        require_permission(
            "organizations.update"
        )
    ),
    db: Session = Depends(
        get_db
    ),
) -> OrganizationDocumentSettingsResponse:
    """
    Update protected organization document settings.

    An audit event records the changed field names without storing
    sensitive banking or tax values.

    Requires:
    - organizations.update
    """

    service = OrganizationDocumentSettingsService(
        db
    )

    return service.update_settings(
        organization=context.organization,
        payload=payload,
        actor_user_id=context.current_user.id,
        actor_membership_id=context.membership.id,
    )


@router.patch(
    "/{organization_id}/deactivate",
    response_model=OrganizationResponse,
    summary="Deactivate organization",
)
def deactivate_organization(
    context: OrganizationContext = Depends(
        require_permission(
            "organizations.deactivate"
        )
    ),
    db: Session = Depends(
        get_db
    ),
) -> Organization:
    """
    Deactivate an organization.

    Requires:
    - organizations.deactivate
    """

    service = OrganizationService(db)

    return service.deactivate_organization(
        organization=context.organization,
    )
