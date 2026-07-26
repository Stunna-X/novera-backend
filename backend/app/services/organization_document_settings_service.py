"""
Organization document-settings service.

Provides protected retrieval and audited updates for organization tax,
banking, payment, invoice, and quote configuration.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.schemas.audit_log import AuditLogCreate
from app.schemas.organization_document_settings import (
    OrganizationDocumentSettingsResponse,
    UpdateOrganizationDocumentSettingsSchema,
)
from app.services.audit_log_service import AuditLogService


DOCUMENT_SETTING_FIELDS: tuple[str, ...] = (
    "business_address",
    "tax_identification_number",
    "vat_number",
    "bank_name",
    "bank_account_name",
    "bank_account_number",
    "bank_routing_number",
    "payment_instructions",
    "default_invoice_terms",
    "default_quote_terms",
    "invoice_footer",
    "quote_footer",
)


class OrganizationDocumentSettingsService:
    """
    Manage protected organization document configuration.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db
        self.audit_logs = AuditLogService(db)

    @staticmethod
    def _clean_optional_text(
        value: str | None,
    ) -> str | None:
        """
        Trim optional text and normalize blank values to null.
        """

        if value is None:
            return None

        cleaned = value.strip()

        return cleaned or None

    @staticmethod
    def _to_response(
        organization: Organization,
    ) -> OrganizationDocumentSettingsResponse:
        """
        Convert an organization into its protected settings response.
        """

        return OrganizationDocumentSettingsResponse(
            organization_id=organization.id,
            business_address=organization.business_address,
            tax_identification_number=(
                organization.tax_identification_number
            ),
            vat_number=organization.vat_number,
            bank_name=organization.bank_name,
            bank_account_name=organization.bank_account_name,
            bank_account_number=organization.bank_account_number,
            bank_routing_number=organization.bank_routing_number,
            payment_instructions=organization.payment_instructions,
            default_invoice_terms=organization.default_invoice_terms,
            default_quote_terms=organization.default_quote_terms,
            invoice_footer=organization.invoice_footer,
            quote_footer=organization.quote_footer,
            updated_at=organization.updated_at,
        )

    def get_settings(
        self,
        *,
        organization: Organization,
    ) -> OrganizationDocumentSettingsResponse:
        """
        Return protected document settings for one organization.
        """

        return self._to_response(
            organization
        )

    def update_settings(
        self,
        *,
        organization: Organization,
        payload: UpdateOrganizationDocumentSettingsSchema,
        actor_user_id: uuid.UUID,
        actor_membership_id: uuid.UUID,
    ) -> OrganizationDocumentSettingsResponse:
        """
        Update document settings and record one immutable audit event.

        Sensitive before-and-after values are deliberately excluded from
        the audit log. Only changed field names are recorded.
        """

        update_data = payload.model_dump(
            exclude_unset=True,
        )

        changed_fields: list[str] = []

        for field_name in DOCUMENT_SETTING_FIELDS:
            if field_name not in update_data:
                continue

            normalized_value = self._clean_optional_text(
                update_data[field_name]
            )

            if (
                getattr(
                    organization,
                    field_name,
                )
                == normalized_value
            ):
                continue

            setattr(
                organization,
                field_name,
                normalized_value,
            )

            changed_fields.append(
                field_name
            )

        if not changed_fields:
            return self._to_response(
                organization
            )

        try:
            self.db.add(
                organization
            )
            self.db.flush()

            self.audit_logs.record_event(
                organization_id=organization.id,
                payload=AuditLogCreate(
                    actor_user_id=actor_user_id,
                    actor_membership_id=actor_membership_id,
                    action=(
                        "organization_document_settings_updated"
                    ),
                    entity_type=(
                        "organization_document_settings"
                    ),
                    entity_id=organization.id,
                    summary=(
                        "Organization document settings updated."
                    ),
                    status="success",
                    details={
                        "changed_fields": sorted(
                            changed_fields
                        ),
                        "changed_field_count": len(
                            changed_fields
                        ),
                    },
                ),
                commit=False,
            )

            self.db.commit()
            self.db.refresh(
                organization
            )

        except Exception:
            self.db.rollback()
            raise

        return self._to_response(
            organization
        )
