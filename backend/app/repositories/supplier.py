"""
Supplier repository.

Provides organization-scoped persistence and query operations for
supplier records. Mutations flush without committing so the service
layer owns the transaction boundary and audit event atomically.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.supplier import Supplier
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    """Repository for tenant-isolated supplier operations."""

    def __init__(self, db: Session):
        super().__init__(db, Supplier)

    @staticmethod
    def _normalize_optional_text(
        value: str | None,
    ) -> str | None:
        """Strip optional text and convert blanks to null."""

        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @classmethod
    def _normalize_supplier(cls, supplier: Supplier) -> None:
        """Normalize mutable supplier fields before persistence."""

        supplier.code = supplier.code.strip().upper()
        supplier.name = supplier.name.strip()
        supplier.supplier_type = (
            supplier.supplier_type.strip().lower()
        )
        supplier.category = cls._normalize_optional_text(
            supplier.category
        )
        supplier.contact_name = cls._normalize_optional_text(
            supplier.contact_name
        )
        supplier.email = cls._normalize_optional_text(
            supplier.email
        )
        if supplier.email:
            supplier.email = supplier.email.lower()
        supplier.phone = cls._normalize_optional_text(
            supplier.phone
        )
        supplier.alternate_phone = cls._normalize_optional_text(
            supplier.alternate_phone
        )
        supplier.tax_id = cls._normalize_optional_text(
            supplier.tax_id
        )
        if supplier.tax_id:
            supplier.tax_id = supplier.tax_id.upper()
        supplier.registration_number = cls._normalize_optional_text(
            supplier.registration_number
        )
        if supplier.registration_number:
            supplier.registration_number = (
                supplier.registration_number.upper()
            )
        supplier.currency = supplier.currency.strip().upper()
        supplier.address_line_1 = cls._normalize_optional_text(
            supplier.address_line_1
        )
        supplier.address_line_2 = cls._normalize_optional_text(
            supplier.address_line_2
        )
        supplier.city = cls._normalize_optional_text(
            supplier.city
        )
        supplier.state = cls._normalize_optional_text(
            supplier.state
        )
        supplier.postal_code = cls._normalize_optional_text(
            supplier.postal_code
        )
        supplier.country = cls._normalize_optional_text(
            supplier.country
        )
        supplier.notes = cls._normalize_optional_text(
            supplier.notes
        )

    def create_supplier(self, supplier: Supplier) -> Supplier:
        """Add a supplier to the current transaction."""

        self._normalize_supplier(supplier)
        self.db.add(supplier)
        self.db.flush()
        return supplier

    def update_supplier(self, supplier: Supplier) -> Supplier:
        """Flush supplier changes in the current transaction."""

        self._normalize_supplier(supplier)
        self.db.add(supplier)
        self.db.flush()
        return supplier

    def get_for_organization(
        self,
        organization_id: uuid.UUID,
        supplier_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> Supplier | None:
        """Retrieve one organization supplier."""

        query = (
            self.db.query(Supplier)
            .populate_existing()
            .filter(
                Supplier.id == supplier_id,
                Supplier.organization_id == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                Supplier.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=Supplier
            )

        return query.first()

    def _list_query(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        supplier_type: str | None = None,
        category: str | None = None,
        include_inactive: bool = False,
    ):
        """Build the shared supplier list/count query."""

        query = self.db.query(Supplier).filter(
            Supplier.organization_id == organization_id
        )

        if not include_inactive:
            query = query.filter(
                Supplier.is_active.is_(True)
            )

        if supplier_type:
            query = query.filter(
                Supplier.supplier_type
                == supplier_type.strip().lower()
            )

        if category:
            query = query.filter(
                func.lower(Supplier.category)
                == category.strip().lower()
            )

        normalized_search = search.strip() if search else None

        if normalized_search:
            pattern = f"%{normalized_search}%"
            query = query.filter(
                or_(
                    Supplier.code.ilike(pattern),
                    Supplier.name.ilike(pattern),
                    Supplier.category.ilike(pattern),
                    Supplier.contact_name.ilike(pattern),
                    Supplier.email.ilike(pattern),
                    Supplier.phone.ilike(pattern),
                    Supplier.tax_id.ilike(pattern),
                    Supplier.registration_number.ilike(pattern),
                    Supplier.city.ilike(pattern),
                    Supplier.state.ilike(pattern),
                )
            )

        return query

    def list_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        supplier_type: str | None = None,
        category: str | None = None,
        include_inactive: bool = False,
    ) -> list[Supplier]:
        """List suppliers belonging to an organization."""

        return (
            self._list_query(
                organization_id,
                search=search,
                supplier_type=supplier_type,
                category=category,
                include_inactive=include_inactive,
            )
            .order_by(
                Supplier.name.asc(),
                Supplier.code.asc(),
                Supplier.created_at.asc(),
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_organization(
        self,
        organization_id: uuid.UUID,
        *,
        search: str | None = None,
        supplier_type: str | None = None,
        category: str | None = None,
        include_inactive: bool = False,
    ) -> int:
        """Count suppliers belonging to an organization."""

        query = self._list_query(
            organization_id,
            search=search,
            supplier_type=supplier_type,
            category=category,
            include_inactive=include_inactive,
        )

        return (
            query.with_entities(func.count(Supplier.id)).scalar()
            or 0
        )

    def code_exists(
        self,
        organization_id: uuid.UUID,
        code: str,
        *,
        exclude_supplier_id: uuid.UUID | None = None,
    ) -> bool:
        """Check whether a supplier code is already used."""

        query = self.db.query(Supplier.id).filter(
            Supplier.organization_id == organization_id,
            Supplier.code == code.strip().upper(),
        )

        if exclude_supplier_id is not None:
            query = query.filter(
                Supplier.id != exclude_supplier_id
            )

        return query.first() is not None

    def tax_id_exists(
        self,
        organization_id: uuid.UUID,
        tax_id: str,
        *,
        exclude_supplier_id: uuid.UUID | None = None,
    ) -> bool:
        """Check whether a supplier tax ID is already used."""

        query = self.db.query(Supplier.id).filter(
            Supplier.organization_id == organization_id,
            Supplier.tax_id == tax_id.strip().upper(),
        )

        if exclude_supplier_id is not None:
            query = query.filter(
                Supplier.id != exclude_supplier_id
            )

        return query.first() is not None

    def registration_number_exists(
        self,
        organization_id: uuid.UUID,
        registration_number: str,
        *,
        exclude_supplier_id: uuid.UUID | None = None,
    ) -> bool:
        """Check whether a registration number is already used."""

        query = self.db.query(Supplier.id).filter(
            Supplier.organization_id == organization_id,
            Supplier.registration_number
            == registration_number.strip().upper(),
        )

        if exclude_supplier_id is not None:
            query = query.filter(
                Supplier.id != exclude_supplier_id
            )

        return query.first() is not None

    def deactivate_supplier(self, supplier: Supplier) -> Supplier:
        """Soft-delete a supplier."""

        supplier.is_active = False
        return self.update_supplier(supplier)

    def reactivate_supplier(self, supplier: Supplier) -> Supplier:
        """Reactivate a supplier."""

        supplier.is_active = True
        return self.update_supplier(supplier)
