"""
Supplier service.

Contains tenant-isolated supplier business logic. Supplier writes and
immutable audit events share one database transaction.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.supplier import Supplier
from app.repositories.supplier import SupplierRepository
from app.schemas.audit_log import AuditLogCreate
from app.schemas.supplier import (
    CreateSupplierSchema,
    SupplierListResponse,
    UpdateSupplierSchema,
)
from app.services.audit_log_service import AuditLogService


class SupplierService:
    """Handle organization-scoped supplier operations."""

    def __init__(self, db: Session):
        self.db = db
        self.suppliers = SupplierRepository(db)
        self.audit_logs = AuditLogService(db)

    def _get_supplier_or_404(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> Supplier:
        """Retrieve an organization supplier or raise 404."""

        supplier = self.suppliers.get_for_organization(
            organization_id=organization_id,
            supplier_id=supplier_id,
            include_inactive=include_inactive,
            for_update=for_update,
        )

        if supplier is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Supplier not found.",
            )

        return supplier

    def _ensure_unique_identifiers(
        self,
        organization_id: uuid.UUID,
        *,
        code: str | None = None,
        tax_id: str | None = None,
        registration_number: str | None = None,
        exclude_supplier_id: uuid.UUID | None = None,
    ) -> None:
        """Enforce tenant-scoped supplier identifiers."""

        if code and self.suppliers.code_exists(
            organization_id,
            code,
            exclude_supplier_id=exclude_supplier_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another supplier in this organization "
                    "already uses this code."
                ),
            )

        if tax_id and self.suppliers.tax_id_exists(
            organization_id,
            tax_id,
            exclude_supplier_id=exclude_supplier_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another supplier in this organization "
                    "already uses this tax ID."
                ),
            )

        if (
            registration_number
            and self.suppliers.registration_number_exists(
                organization_id,
                registration_number,
                exclude_supplier_id=exclude_supplier_id,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another supplier in this organization already "
                    "uses this registration number."
                ),
            )

    @staticmethod
    def _audit_details(**values: Any) -> dict[str, Any]:
        """Build a JSON-safe audit payload."""

        details: dict[str, Any] = {}

        for key, value in values.items():
            if value is None:
                continue

            details[key] = (
                str(value)
                if isinstance(value, uuid.UUID)
                else value
            )

        return details

    def _record_audit_event(
        self,
        *,
        organization_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        actor_membership_id: uuid.UUID | None,
        action: str,
        supplier: Supplier,
        summary: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Add one immutable supplier audit event."""

        self.audit_logs.record_event(
            organization_id=organization_id,
            payload=AuditLogCreate(
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action=action,
                entity_type="supplier",
                entity_id=supplier.id,
                summary=summary,
                status="success",
                details=details or {},
            ),
            commit=False,
        )

    def _rollback_conflict(
        self,
        exc: IntegrityError,
    ) -> None:
        """Roll back an integrity failure and expose a safe error."""

        self.db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The supplier conflicts with an existing "
                "organization supplier."
            ),
        ) from exc

    def create_supplier(
        self,
        organization_id: uuid.UUID,
        payload: CreateSupplierSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> Supplier:
        """Create a supplier inside an organization."""

        supplier_data = payload.model_dump()

        self._ensure_unique_identifiers(
            organization_id,
            code=supplier_data["code"],
            tax_id=supplier_data.get("tax_id"),
            registration_number=supplier_data.get(
                "registration_number"
            ),
        )

        supplier = Supplier(
            organization_id=organization_id,
            **supplier_data,
        )

        try:
            created = self.suppliers.create_supplier(supplier)
            self._record_audit_event(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_created",
                supplier=created,
                summary="Supplier created.",
                details=self._audit_details(
                    supplier_type=created.supplier_type,
                    category=created.category,
                ),
            )
            self.db.commit()
            self.db.refresh(created)
            return created

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def list_suppliers(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        supplier_type: str | None = None,
        category: str | None = None,
        include_inactive: bool = False,
    ) -> SupplierListResponse:
        """Return a paginated supplier collection."""

        suppliers = self.suppliers.list_for_organization(
            organization_id,
            skip=skip,
            limit=limit,
            search=search,
            supplier_type=supplier_type,
            category=category,
            include_inactive=include_inactive,
        )
        total = self.suppliers.count_for_organization(
            organization_id,
            search=search,
            supplier_type=supplier_type,
            category=category,
            include_inactive=include_inactive,
        )

        return SupplierListResponse(
            items=suppliers,
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_supplier(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Supplier:
        """Return one organization supplier."""

        return self._get_supplier_or_404(
            organization_id,
            supplier_id,
            include_inactive=include_inactive,
        )

    def update_supplier(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        payload: UpdateSupplierSchema,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> Supplier:
        """Update an active organization supplier."""

        supplier = self._get_supplier_or_404(
            organization_id,
            supplier_id,
            for_update=True,
        )
        update_data = payload.model_dump(exclude_unset=True)

        if not update_data:
            return supplier

        self._ensure_unique_identifiers(
            organization_id,
            code=update_data.get("code"),
            tax_id=update_data.get("tax_id"),
            registration_number=update_data.get(
                "registration_number"
            ),
            exclude_supplier_id=supplier.id,
        )

        for field_name, field_value in update_data.items():
            setattr(supplier, field_name, field_value)

        try:
            updated = self.suppliers.update_supplier(supplier)
            self._record_audit_event(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_updated",
                supplier=updated,
                summary="Supplier updated.",
                details=self._audit_details(
                    changed_fields=sorted(update_data),
                ),
            )
            self.db.commit()
            self.db.refresh(updated)
            return updated

        except IntegrityError as exc:
            self._rollback_conflict(exc)

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def deactivate_supplier(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> None:
        """Soft-delete an active organization supplier."""

        supplier = self._get_supplier_or_404(
            organization_id,
            supplier_id,
            for_update=True,
        )

        try:
            deactivated = self.suppliers.deactivate_supplier(
                supplier
            )
            self._record_audit_event(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_deactivated",
                supplier=deactivated,
                summary="Supplier deactivated.",
            )
            self.db.commit()

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def reactivate_supplier(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID | None = None,
        actor_membership_id: uuid.UUID | None = None,
    ) -> Supplier:
        """Reactivate a previously deactivated supplier."""

        supplier = self._get_supplier_or_404(
            organization_id,
            supplier_id,
            include_inactive=True,
            for_update=True,
        )

        if supplier.is_active:
            return supplier

        try:
            reactivated = self.suppliers.reactivate_supplier(
                supplier
            )
            self._record_audit_event(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                actor_membership_id=actor_membership_id,
                action="supplier_reactivated",
                supplier=reactivated,
                summary="Supplier reactivated.",
            )
            self.db.commit()
            self.db.refresh(reactivated)
            return reactivated

        except SQLAlchemyError:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise
