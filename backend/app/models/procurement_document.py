"""
Versioned procurement-document metadata and immutable approval evidence.

File bytes remain in the configured external object store. PostgreSQL keeps
tenant ownership, storage references, SHA-256 integrity data, version history,
and approval evidence.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import BaseModel


if TYPE_CHECKING:
    from app.models.membership import Membership
    from app.models.organization import Organization
    from app.models.user import User


class ProcurementDocument(BaseModel):
    """One logical procurement document with immutable versions."""

    __tablename__ = "procurement_documents"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "document_number",
            name="uq_procurement_documents_organization_number",
        ),
        CheckConstraint(
            """
            entity_type IN (
                'supplier',
                'purchase_requisition',
                'purchase_order',
                'goods_receipt',
                'supplier_bill',
                'supplier_payment',
                'supplier_return',
                'supplier_debit_note'
            )
            """,
            name="entity_type_valid",
        ),
        CheckConstraint(
            """
            document_type IN (
                'supplier_quotation',
                'requisition_support',
                'purchase_order',
                'delivery_note',
                'goods_receipt_evidence',
                'supplier_invoice',
                'payment_evidence',
                'return_evidence',
                'debit_note',
                'supplier_credit_note',
                'approval_memo',
                'other'
            )
            """,
            name="document_type_valid",
        ),
        CheckConstraint(
            "status IN ('active', 'archived')",
            name="status_valid",
        ),
        CheckConstraint(
            "current_version_number >= 0",
            name="current_version_non_negative",
        ),
        CheckConstraint(
            """
            (
                status = 'active'
                AND archived_at IS NULL
                AND archived_by_user_id IS NULL
                AND archive_reason IS NULL
            )
            OR
            (
                status = 'archived'
                AND archived_at IS NOT NULL
                AND archive_reason IS NOT NULL
            )
            """,
            name="archive_state_valid",
        ),
        Index(
            "ix_procurement_documents_organization_entity",
            "organization_id",
            "entity_type",
            "entity_id",
        ),
        Index(
            "ix_procurement_documents_organization_type",
            "organization_id",
            "document_type",
        ),
        Index(
            "ix_procurement_documents_organization_status",
            "organization_id",
            "status",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_number: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
    )

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    document_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(240),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    required_for_action: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        server_default=text("'active'"),
        index=True,
    )

    current_version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    archived_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    archive_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    created_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[created_by_user_id],
        lazy="joined",
    )

    archived_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[archived_by_user_id],
        lazy="joined",
    )

    versions: Mapped[list["ProcurementDocumentVersion"]] = relationship(
        "ProcurementDocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ProcurementDocumentVersion.version_number",
        lazy="selectin",
    )


class ProcurementDocumentVersion(BaseModel):
    """Immutable file metadata for one document version."""

    __tablename__ = "procurement_document_versions"

    __table_args__ = (
        UniqueConstraint(
            "procurement_document_id",
            "version_number",
            name="uq_procurement_document_versions_number",
        ),
        UniqueConstraint(
            "storage_key",
            name="uq_procurement_document_versions_storage_key",
        ),
        CheckConstraint(
            "version_number > 0",
            name="version_number_positive",
        ),
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 26214400",
            name="file_size_valid",
        ),
        CheckConstraint(
            "char_length(sha256_checksum) = 64",
            name="sha256_length_valid",
        ),
        CheckConstraint(
            """
            upload_state IN (
                'available',
                'quarantined',
                'failed'
            )
            """,
            name="upload_state_valid",
        ),
        CheckConstraint(
            """
            integrity_status IN (
                'unverified',
                'verified',
                'mismatch'
            )
            """,
            name="integrity_status_valid",
        ),
        CheckConstraint(
            """
            (
                integrity_status = 'unverified'
                AND verified_at IS NULL
                AND verified_by_user_id IS NULL
            )
            OR
            (
                integrity_status IN ('verified', 'mismatch')
                AND verified_at IS NOT NULL
            )
            """,
            name="verification_state_valid",
        ),
        Index(
            "ix_procurement_document_versions_document_state",
            "procurement_document_id",
            "upload_state",
            "integrity_status",
        ),
    )

    procurement_document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("procurement_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    file_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    storage_key: Mapped[str] = mapped_column(
        String(700),
        nullable=False,
    )

    content_type: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
        index=True,
    )

    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    sha256_checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    upload_state: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="available",
        server_default=text("'available'"),
        index=True,
    )

    integrity_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="unverified",
        server_default=text("'unverified'"),
        index=True,
    )

    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    verified_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    document: Mapped["ProcurementDocument"] = relationship(
        "ProcurementDocument",
        back_populates="versions",
    )

    uploaded_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[uploaded_by_user_id],
        lazy="joined",
    )

    verified_by: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[verified_by_user_id],
        lazy="joined",
    )


class ProcurementApprovalEvidence(BaseModel):
    """Immutable evidence for one procurement decision or action."""

    __tablename__ = "procurement_approval_evidence"

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "evidence_hash",
            name="uq_procurement_approval_evidence_hash",
        ),
        CheckConstraint(
            """
            entity_type IN (
                'purchase_requisition',
                'purchase_order',
                'goods_receipt',
                'supplier_bill',
                'supplier_payment',
                'supplier_return',
                'supplier_debit_note'
            )
            """,
            name="entity_type_valid",
        ),
        CheckConstraint(
            """
            action_type IN (
                'requisition_approval',
                'purchase_order_issue',
                'goods_receipt_posting',
                'supplier_bill_approval',
                'supplier_payment_posting',
                'supplier_return_dispatch',
                'debit_note_issue',
                'credit_settlement',
                'exception_waiver'
            )
            """,
            name="action_type_valid",
        ),
        CheckConstraint(
            """
            decision IN (
                'approved',
                'acknowledged',
                'rejected',
                'waived'
            )
            """,
            name="decision_valid",
        ),
        CheckConstraint(
            "char_length(evidence_hash) = 64",
            name="evidence_hash_length_valid",
        ),
        Index(
            "ix_procurement_approval_evidence_organization_entity",
            "organization_id",
            "entity_type",
            "entity_id",
        ),
        Index(
            "ix_procurement_approval_evidence_organization_action",
            "organization_id",
            "action_type",
            "occurred_at",
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )

    action_type: Mapped[str] = mapped_column(
        String(60),
        nullable=False,
        index=True,
    )

    decision: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        index=True,
    )

    statement: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    procurement_document_version_id: Mapped[uuid.UUID | None] = (
        mapped_column(
            UUID(as_uuid=True),
            ForeignKey(
                "procurement_document_versions.id",
                ondelete="RESTRICT",
            ),
            nullable=True,
            index=True,
        )
    )

    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    actor_membership_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memberships.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    evidence_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    organization: Mapped["Organization"] = relationship(
        "Organization",
        lazy="joined",
    )

    document_version: Mapped["ProcurementDocumentVersion | None"] = (
        relationship(
            "ProcurementDocumentVersion",
            lazy="joined",
        )
    )

    actor: Mapped["User | None"] = relationship(
        "User",
        lazy="joined",
    )

    actor_membership: Mapped["Membership | None"] = relationship(
        "Membership",
        lazy="joined",
    )
