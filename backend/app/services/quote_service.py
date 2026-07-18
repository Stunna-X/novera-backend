"""
Quote service.

Implements quote creation, pricing, lifecycle transitions,
reporting, activity auditing, and accepted-quote conversion
into draft work orders.

Every mutation is committed as one transaction. Repository
methods only flush, preventing partially completed quote,
activity, or conversion records.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import (
    Decimal,
    InvalidOperation,
    ROUND_HALF_UP,
)
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.customer_site import CustomerSite
from app.models.quote import (
    Quote,
    QuoteActivity,
    QuoteLineItem,
)
from app.models.work_order import WorkOrder
from app.models.work_order_activity import WorkOrderActivity
from app.repositories.quote import QuoteRepository
from app.services.auto_notification_service import AutoNotificationService
from app.services.auto_audit_service import AutoAuditService
from app.schemas.quote import (
    QuoteActivityListResponse,
    QuoteActivityResponse,
    QuoteConversionResponse,
    QuoteConvertRequest,
    QuoteCreate,
    QuoteCurrencySummary,
    QuoteLifecycleNote,
    QuoteLineItemCreate,
    QuoteLineItemResponse,
    QuoteLineItemUpdate,
    QuoteListResponse,
    QuoteRejectRequest,
    QuoteResponse,
    QuoteSummaryResponse,
    QuoteUpdate,
)


MONEY_QUANTUM = Decimal("0.01")
QUANTITY_QUANTUM = Decimal("0.001")
ZERO_MONEY = Decimal("0.00")
MAX_MONEY = Decimal("999999999999.99")


class QuoteService:
    """
    Handles quote and estimate business logic.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db
        self.quotes = QuoteRepository(db)
        self.auto_notifications = AutoNotificationService(db)
        self.auto_audit = AutoAuditService(db)

    @staticmethod
    def _money(
        value: Decimal | int | str,
    ) -> Decimal:
        """
        Convert a value to safe two-decimal money.
        """

        try:
            amount = Decimal(value).quantize(
                MONEY_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid monetary value.",
            ) from exc

        if amount < ZERO_MONEY:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Monetary values cannot be negative.",
            )

        if amount > MAX_MONEY:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Monetary value exceeds the supported limit.",
            )

        return amount

    @staticmethod
    def _quantity(
        value: Decimal | int | str,
    ) -> Decimal:
        """
        Convert a value to a positive three-decimal quantity.
        """

        try:
            quantity = Decimal(value).quantize(
                QUANTITY_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid quantity.",
            ) from exc

        if quantity <= Decimal("0.000"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Quantity must be greater than zero.",
            )

        return quantity

    @classmethod
    def _line_total(
        cls,
        quantity: Decimal,
        unit_price: Decimal,
    ) -> Decimal:
        """
        Calculate one rounded line total.
        """

        total = (
            cls._quantity(quantity)
            * cls._money(unit_price)
        ).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

        if total > MAX_MONEY:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Quote line total exceeds the supported limit.",
            )

        return total

    @staticmethod
    def _actor_fields(
        user,
        *,
        prefix: str,
    ) -> dict[str, object]:
        """
        Build flattened actor fields for an API response.
        """

        return {
            f"{prefix}_user_id": (
                user.id
                if user is not None
                else None
            ),
            f"{prefix}_first_name": (
                user.first_name
                if user is not None
                else None
            ),
            f"{prefix}_last_name": (
                user.last_name
                if user is not None
                else None
            ),
            f"{prefix}_email": (
                user.email
                if user is not None
                else None
            ),
        }

    @classmethod
    def _build_line_response(
        cls,
        line_item: QuoteLineItem,
    ) -> QuoteLineItemResponse:
        """
        Convert a quote line into an API response.
        """

        return QuoteLineItemResponse(
            id=line_item.id,
            quote_id=line_item.quote_id,
            description=line_item.description,
            quantity=line_item.quantity,
            unit_price=line_item.unit_price,
            line_total=line_item.line_total,
            position=line_item.position,
            is_active=line_item.is_active,
            created_at=line_item.created_at,
            updated_at=line_item.updated_at,
        )

    @classmethod
    def _build_quote_response(
        cls,
        quote: Quote,
    ) -> QuoteResponse:
        """
        Convert a quote model into an API response.
        """

        return QuoteResponse(
            id=quote.id,
            organization_id=quote.organization_id,
            customer_id=quote.customer_id,
            customer_site_id=quote.customer_site_id,
            converted_work_order_id=(
                quote.converted_work_order_id
            ),
            **cls._actor_fields(
                quote.created_by,
                prefix="created_by",
            ),
            **cls._actor_fields(
                quote.sent_by,
                prefix="sent_by",
            ),
            **cls._actor_fields(
                quote.responded_by,
                prefix="responded_by",
            ),
            **cls._actor_fields(
                quote.converted_by,
                prefix="converted_by",
            ),
            quote_number=quote.quote_number,
            title=quote.title,
            description=quote.description,
            currency=quote.currency,
            status=quote.status,
            quote_date=quote.quote_date,
            valid_until=quote.valid_until,
            subtotal=quote.subtotal,
            discount_amount=quote.discount_amount,
            tax_amount=quote.tax_amount,
            total_amount=quote.total_amount,
            customer_name=quote.customer_name,
            customer_email=quote.customer_email,
            customer_phone=quote.customer_phone,
            billing_address=quote.billing_address,
            service_address=quote.service_address,
            notes=quote.notes,
            terms=quote.terms,
            sent_at=quote.sent_at,
            accepted_at=quote.accepted_at,
            rejected_at=quote.rejected_at,
            expired_at=quote.expired_at,
            converted_at=quote.converted_at,
            response_note=quote.response_note,
            is_active=quote.is_active,
            line_items=[
                cls._build_line_response(item)
                for item in sorted(
                    quote.line_items,
                    key=lambda line: (
                        line.position,
                        line.created_at,
                    ),
                )
            ],
            created_at=quote.created_at,
            updated_at=quote.updated_at,
        )

    @staticmethod
    def _build_activity_response(
        activity: QuoteActivity,
    ) -> QuoteActivityResponse:
        """
        Convert an immutable activity into an API response.
        """

        actor = activity.actor

        return QuoteActivityResponse(
            id=activity.id,
            organization_id=activity.organization_id,
            quote_id=activity.quote_id,
            actor_user_id=activity.actor_user_id,
            actor_first_name=(
                actor.first_name
                if actor is not None
                else None
            ),
            actor_last_name=(
                actor.last_name
                if actor is not None
                else None
            ),
            actor_email=(
                actor.email
                if actor is not None
                else None
            ),
            activity_type=activity.activity_type,
            summary=activity.summary,
            from_status=activity.from_status,
            to_status=activity.to_status,
            note=activity.note,
            details=activity.details or {},
            created_at=activity.created_at,
        )

    def _get_quote_or_404(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> Quote:
        """
        Retrieve an organization quote or raise 404.
        """

        quote = self.quotes.get_for_organization(
            organization_id=organization_id,
            quote_id=quote_id,
            include_inactive=include_inactive,
            for_update=for_update,
        )

        if quote is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quote not found.",
            )

        return quote

    def _reload_quote(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> Quote:
        """
        Reload a quote after committing.
        """

        self.db.expire_all()

        quote = self.quotes.get_for_organization(
            organization_id=organization_id,
            quote_id=quote_id,
            include_inactive=include_inactive,
        )

        if quote is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load the saved quote.",
            )

        return quote

    def _get_customer_or_404(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
    ) -> Customer:
        """
        Retrieve an active organization customer.
        """

        customer = (
            self.db.query(Customer)
            .filter(
                Customer.id == customer_id,
                Customer.organization_id
                == organization_id,
                Customer.is_active.is_(True),
            )
            .first()
        )

        if customer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Active customer not found.",
            )

        return customer

    def _get_site_or_404(
        self,
        organization_id: uuid.UUID,
        customer_id: uuid.UUID,
        customer_site_id: uuid.UUID | None,
    ) -> CustomerSite | None:
        """
        Validate an optional active customer site.
        """

        if customer_site_id is None:
            return None

        site = (
            self.db.query(CustomerSite)
            .filter(
                CustomerSite.id == customer_site_id,
                CustomerSite.organization_id
                == organization_id,
                CustomerSite.customer_id
                == customer_id,
                CustomerSite.is_active.is_(True),
            )
            .first()
        )

        if site is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "Active customer site not found "
                    "for the selected customer."
                ),
            )

        return site

    @staticmethod
    def _format_address(
        source,
        *,
        include_name: bool = False,
    ) -> str | None:
        """
        Build a stable address snapshot from a model.
        """

        values: list[str] = []

        if include_name:
            name = getattr(source, "name", None)

            if isinstance(name, str) and name.strip():
                values.append(name.strip())

        for field_name in (
            "address_line_1",
            "address_line_2",
            "city",
            "state",
            "postal_code",
            "country",
        ):
            value = getattr(source, field_name, None)

            if isinstance(value, str) and value.strip():
                values.append(value.strip())

        return ", ".join(values) or None

    @classmethod
    def _customer_snapshot(
        cls,
        customer: Customer,
        site: CustomerSite | None,
    ) -> dict[str, object]:
        """
        Build historical customer and service snapshots.
        """

        return {
            "customer_name": customer.name.strip(),
            "customer_email": (
                customer.email.strip().lower()
                if customer.email
                else None
            ),
            "customer_phone": (
                customer.phone.strip()
                if customer.phone
                else None
            ),
            "billing_address": cls._format_address(
                customer
            ),
            "service_address": (
                cls._format_address(
                    site,
                    include_name=True,
                )
                if site is not None
                else None
            ),
        }

    def _generate_quote_number(
        self,
        organization_id: uuid.UUID,
    ) -> str:
        """
        Generate an organization-safe quote number.
        """

        date_part = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d")

        for _ in range(10):
            suffix = uuid.uuid4().hex[:6].upper()
            candidate = f"QUO-{date_part}-{suffix}"

            if not self.quotes.number_exists(
                organization_id=organization_id,
                quote_number=candidate,
            ):
                return candidate

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to generate a unique quote number.",
        )

    def _ensure_quote_number_available(
        self,
        organization_id: uuid.UUID,
        quote_number: str,
        *,
        exclude_quote_id: uuid.UUID | None = None,
    ) -> None:
        """
        Enforce quote-number uniqueness.
        """

        if self.quotes.number_exists(
            organization_id=organization_id,
            quote_number=quote_number,
            exclude_quote_id=exclude_quote_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Another quote already uses "
                    "this quote number."
                ),
            )

    def _generate_work_order_number(
        self,
        organization_id: uuid.UUID,
    ) -> str:
        """
        Generate a unique work-order number transactionally.
        """

        date_part = datetime.now(
            timezone.utc
        ).strftime("%Y%m%d")

        for _ in range(10):
            suffix = uuid.uuid4().hex[:6].upper()
            candidate = f"WO-{date_part}-{suffix}"

            exists = (
                self.db.query(WorkOrder.id)
                .filter(
                    WorkOrder.organization_id
                    == organization_id,
                    func.lower(
                        WorkOrder.work_order_number
                    )
                    == candidate.lower(),
                )
                .first()
            )

            if exists is None:
                return candidate

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Unable to generate a unique "
                "work-order number."
            ),
        )

    @staticmethod
    def _ensure_draft(
        quote: Quote,
    ) -> None:
        """
        Ensure a quote is editable.
        """

        if quote.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Only draft quotes can be edited.",
            )

    @staticmethod
    def _ensure_sent(
        quote: Quote,
    ) -> None:
        """
        Ensure a quote is awaiting a response.
        """

        if quote.status != "sent":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Only sent quotes can receive "
                    "a customer response."
                ),
            )

    @staticmethod
    def _ensure_not_past_validity(
        quote: Quote,
    ) -> None:
        """
        Block responses after a quote's validity date.
        """

        if (
            quote.valid_until is not None
            and quote.valid_until < date.today()
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The quote validity date has passed. "
                    "Mark the quote as expired."
                ),
            )

    def _record_activity(
        self,
        *,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        actor_user_id: uuid.UUID | None,
        activity_type: str,
        summary: str,
        from_status: str | None = None,
        to_status: str | None = None,
        note: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> QuoteActivity:
        """
        Add one immutable quote activity.
        """

        activity = QuoteActivity(
            organization_id=organization_id,
            quote_id=quote_id,
            actor_user_id=actor_user_id,
            activity_type=activity_type,
            summary=summary,
            from_status=from_status,
            to_status=to_status,
            note=note,
            details=details or {},
        )

        return self.quotes.add_activity(
            activity
        )

    def _recalculate(
        self,
        quote: Quote,
    ) -> None:
        """
        Recalculate quote totals from active lines.
        """

        lines = self.quotes.active_line_items(
            quote.id
        )

        subtotal = sum(
            (
                self._money(line.line_total)
                for line in lines
            ),
            ZERO_MONEY,
        ).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

        discount = self._money(
            quote.discount_amount
        )

        tax = self._money(
            quote.tax_amount
        )

        if discount > subtotal:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Discount amount cannot exceed "
                    "the quote subtotal."
                ),
            )

        total = (
            subtotal
            - discount
            + tax
        ).quantize(
            MONEY_QUANTUM,
            rounding=ROUND_HALF_UP,
        )

        if total > MAX_MONEY:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Quote total exceeds the supported limit.",
            )

        quote.subtotal = subtotal
        quote.discount_amount = discount
        quote.tax_amount = tax
        quote.total_amount = total

        self.quotes.update_quote(quote)

    @staticmethod
    def _position_plan(
        line_items: list[QuoteLineItemCreate],
    ) -> list[int]:
        """
        Assign deterministic unique positions to new lines.
        """

        used = {
            item.position
            for item in line_items
            if item.position is not None
        }

        positions: list[int] = []
        cursor = 0

        for item in line_items:
            if item.position is not None:
                positions.append(item.position)
                continue

            while cursor in used:
                cursor += 1

            positions.append(cursor)
            used.add(cursor)
            cursor += 1

        return positions

    def create_quote(
        self,
        organization_id: uuid.UUID,
        payload: QuoteCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> QuoteResponse:
        """
        Create a draft quote with optional initial lines.
        """

        try:
            customer = self._get_customer_or_404(
                organization_id=organization_id,
                customer_id=payload.customer_id,
            )

            site = self._get_site_or_404(
                organization_id=organization_id,
                customer_id=payload.customer_id,
                customer_site_id=(
                    payload.customer_site_id
                ),
            )

            quote_number = (
                payload.quote_number
                or self._generate_quote_number(
                    organization_id
                )
            )

            self._ensure_quote_number_available(
                organization_id=organization_id,
                quote_number=quote_number,
            )

            quote = Quote(
                organization_id=organization_id,
                customer_id=payload.customer_id,
                customer_site_id=(
                    payload.customer_site_id
                ),
                created_by_user_id=actor_user_id,
                quote_number=quote_number,
                title=payload.title,
                description=payload.description,
                currency=payload.currency,
                status="draft",
                quote_date=payload.quote_date,
                valid_until=payload.valid_until,
                subtotal=ZERO_MONEY,
                discount_amount=self._money(
                    payload.discount_amount
                ),
                tax_amount=self._money(
                    payload.tax_amount
                ),
                total_amount=ZERO_MONEY,
                notes=payload.notes,
                terms=payload.terms,
                **self._customer_snapshot(
                    customer,
                    site,
                ),
            )

            self.quotes.create_quote(quote)

            positions = self._position_plan(
                payload.line_items
            )

            for item, position in zip(
                payload.line_items,
                positions,
                strict=True,
            ):
                quantity = self._quantity(
                    item.quantity
                )
                unit_price = self._money(
                    item.unit_price
                )

                self.quotes.add_line_item(
                    QuoteLineItem(
                        quote_id=quote.id,
                        description=item.description,
                        quantity=quantity,
                        unit_price=unit_price,
                        line_total=self._line_total(
                            quantity,
                            unit_price,
                        ),
                        position=position,
                        is_active=True,
                    )
                )

            self._recalculate(quote)

            self._record_activity(
                organization_id=organization_id,
                quote_id=quote.id,
                actor_user_id=actor_user_id,
                activity_type="quote_created",
                summary=(
                    f"Quote {quote.quote_number} created."
                ),
                to_status="draft",
                details={
                    "customer_id": str(
                        quote.customer_id
                    ),
                    "customer_site_id": (
                        str(quote.customer_site_id)
                        if quote.customer_site_id
                        else None
                    ),
                    "currency": quote.currency,
                    "line_item_count": len(
                        payload.line_items
                    ),
                    "subtotal": str(
                        quote.subtotal
                    ),
                    "total_amount": str(
                        quote.total_amount
                    ),
                },
            )

            self.db.commit()

            loaded = self._reload_quote(
                organization_id,
                quote.id,
            )

            return self._build_quote_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The quote conflicts with "
                    "an existing record."
                ),
            ) from exc

        except HTTPException:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def list_quotes(
        self,
        organization_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status_filter: str | None = None,
        customer_id: uuid.UUID | None = None,
        customer_site_id: uuid.UUID | None = None,
        currency: str | None = None,
        include_inactive: bool = False,
    ) -> QuoteListResponse:
        """
        List organization quotes.
        """

        quotes = self.quotes.list_for_organization(
            organization_id=organization_id,
            skip=skip,
            limit=limit,
            search=search,
            status_filter=status_filter,
            customer_id=customer_id,
            customer_site_id=customer_site_id,
            currency=currency,
            include_inactive=include_inactive,
        )

        total = self.quotes.count_for_organization(
            organization_id=organization_id,
            search=search,
            status_filter=status_filter,
            customer_id=customer_id,
            customer_site_id=customer_site_id,
            currency=currency,
            include_inactive=include_inactive,
        )

        return QuoteListResponse(
            items=[
                self._build_quote_response(quote)
                for quote in quotes
            ],
            total=total,
            skip=skip,
            limit=limit,
        )

    def get_quote(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> QuoteResponse:
        """
        Return one quote.
        """

        quote = self._get_quote_or_404(
            organization_id,
            quote_id,
            include_inactive=include_inactive,
        )

        return self._build_quote_response(
            quote
        )

    def update_quote(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        payload: QuoteUpdate,
        *,
        actor_user_id: uuid.UUID,
    ) -> QuoteResponse:
        """
        Update draft quote details and totals.
        """

        try:
            quote = self._get_quote_or_404(
                organization_id,
                quote_id,
                for_update=True,
            )

            self._ensure_draft(quote)

            update_data = payload.model_dump(
                exclude_unset=True
            )

            if not update_data:
                return self._build_quote_response(
                    quote
                )

            required_fields = {
                "customer_id",
                "quote_number",
                "title",
                "currency",
                "quote_date",
                "discount_amount",
                "tax_amount",
            }

            for field_name in required_fields:
                if (
                    field_name in update_data
                    and update_data[field_name] is None
                ):
                    raise HTTPException(
                        status_code=(
                            status.HTTP_422_UNPROCESSABLE_ENTITY
                        ),
                        detail=(
                            f"{field_name.replace('_', ' ').title()} "
                            "cannot be null."
                        ),
                    )

            if (
                "customer_id" in update_data
                and "customer_site_id"
                not in update_data
                and update_data["customer_id"]
                != quote.customer_id
            ):
                update_data[
                    "customer_site_id"
                ] = None

            final_customer_id = update_data.get(
                "customer_id",
                quote.customer_id,
            )

            final_site_id = update_data.get(
                "customer_site_id",
                quote.customer_site_id,
            )

            customer = self._get_customer_or_404(
                organization_id,
                final_customer_id,
            )

            site = self._get_site_or_404(
                organization_id,
                final_customer_id,
                final_site_id,
            )

            final_quote_date = update_data.get(
                "quote_date",
                quote.quote_date,
            )

            final_valid_until = update_data.get(
                "valid_until",
                quote.valid_until,
            )

            if (
                final_valid_until is not None
                and final_valid_until
                < final_quote_date
            ):
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        "Valid-until date cannot be "
                        "before quote date."
                    ),
                )

            if "quote_number" in update_data:
                self._ensure_quote_number_available(
                    organization_id,
                    update_data["quote_number"],
                    exclude_quote_id=quote.id,
                )

            changed_fields = sorted(
                update_data.keys()
            )

            snapshot_fields = self._customer_snapshot(
                customer,
                site,
            )

            update_data.update(
                snapshot_fields
            )

            for field_name, field_value in (
                update_data.items()
            ):
                setattr(
                    quote,
                    field_name,
                    field_value,
                )

            self._recalculate(quote)

            self._record_activity(
                organization_id=organization_id,
                quote_id=quote.id,
                actor_user_id=actor_user_id,
                activity_type="quote_updated",
                summary="Quote details updated.",
                details={
                    "changed_fields": changed_fields,
                    "currency": quote.currency,
                    "subtotal": str(
                        quote.subtotal
                    ),
                    "total_amount": str(
                        quote.total_amount
                    ),
                },
            )

            self.db.commit()

            loaded = self._reload_quote(
                organization_id,
                quote.id,
            )

            return self._build_quote_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The quote conflicts with "
                    "an existing record."
                ),
            ) from exc

        except HTTPException:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def add_line_item(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        payload: QuoteLineItemCreate,
        *,
        actor_user_id: uuid.UUID,
    ) -> QuoteResponse:
        """
        Add a line to a draft quote.
        """

        try:
            quote = self._get_quote_or_404(
                organization_id,
                quote_id,
                for_update=True,
            )

            self._ensure_draft(quote)

            position = (
                payload.position
                if payload.position is not None
                else self.quotes.next_line_position(
                    quote.id
                )
            )

            if self.quotes.position_exists(
                quote.id,
                position,
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Another quote line already uses "
                        "this position."
                    ),
                )

            quantity = self._quantity(
                payload.quantity
            )
            unit_price = self._money(
                payload.unit_price
            )

            line_item = QuoteLineItem(
                quote_id=quote.id,
                description=payload.description,
                quantity=quantity,
                unit_price=unit_price,
                line_total=self._line_total(
                    quantity,
                    unit_price,
                ),
                position=position,
                is_active=True,
            )

            self.quotes.add_line_item(
                line_item
            )

            self._recalculate(quote)

            self._record_activity(
                organization_id=organization_id,
                quote_id=quote.id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "quote_line_item_added"
                ),
                summary=(
                    "Quote line item added."
                ),
                details={
                    "line_item_id": str(
                        line_item.id
                    ),
                    "description": (
                        line_item.description
                    ),
                    "quantity": str(
                        line_item.quantity
                    ),
                    "unit_price": str(
                        line_item.unit_price
                    ),
                    "line_total": str(
                        line_item.line_total
                    ),
                    "position": (
                        line_item.position
                    ),
                    "quote_total": str(
                        quote.total_amount
                    ),
                },
            )

            self.db.commit()

            loaded = self._reload_quote(
                organization_id,
                quote.id,
            )

            return self._build_quote_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The quote line conflicts with "
                    "an existing record."
                ),
            ) from exc

        except HTTPException:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def update_line_item(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        line_item_id: uuid.UUID,
        payload: QuoteLineItemUpdate,
        *,
        actor_user_id: uuid.UUID,
    ) -> QuoteResponse:
        """
        Update one active draft quote line.
        """

        try:
            quote = self._get_quote_or_404(
                organization_id,
                quote_id,
                for_update=True,
            )

            self._ensure_draft(quote)

            line_item = self.quotes.get_line_item(
                organization_id,
                quote_id,
                line_item_id,
                for_update=True,
            )

            if line_item is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Active quote line item not found.",
                )

            update_data = payload.model_dump(
                exclude_unset=True
            )

            if not update_data:
                return self._build_quote_response(
                    quote
                )

            required_fields = {
                "description",
                "quantity",
                "unit_price",
                "position",
            }

            for field_name in required_fields:
                if (
                    field_name in update_data
                    and update_data[field_name] is None
                ):
                    raise HTTPException(
                        status_code=(
                            status.HTTP_422_UNPROCESSABLE_ENTITY
                        ),
                        detail=(
                            f"{field_name.replace('_', ' ').title()} "
                            "cannot be null."
                        ),
                    )

            if "position" in update_data:
                if self.quotes.position_exists(
                    quote.id,
                    update_data["position"],
                    exclude_line_item_id=(
                        line_item.id
                    ),
                ):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Another quote line already "
                            "uses this position."
                        ),
                    )

            changed_fields = sorted(
                update_data.keys()
            )

            if "description" in update_data:
                line_item.description = (
                    update_data["description"]
                )

            if "quantity" in update_data:
                line_item.quantity = self._quantity(
                    update_data["quantity"]
                )

            if "unit_price" in update_data:
                line_item.unit_price = self._money(
                    update_data["unit_price"]
                )

            if "position" in update_data:
                line_item.position = (
                    update_data["position"]
                )

            line_item.line_total = self._line_total(
                line_item.quantity,
                line_item.unit_price,
            )

            self.quotes.update_line_item(
                line_item
            )

            self._recalculate(quote)

            self._record_activity(
                organization_id=organization_id,
                quote_id=quote.id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "quote_line_item_updated"
                ),
                summary=(
                    "Quote line item updated."
                ),
                details={
                    "line_item_id": str(
                        line_item.id
                    ),
                    "changed_fields": (
                        changed_fields
                    ),
                    "description": (
                        line_item.description
                    ),
                    "quantity": str(
                        line_item.quantity
                    ),
                    "unit_price": str(
                        line_item.unit_price
                    ),
                    "line_total": str(
                        line_item.line_total
                    ),
                    "position": (
                        line_item.position
                    ),
                    "quote_total": str(
                        quote.total_amount
                    ),
                },
            )

            self.db.commit()

            loaded = self._reload_quote(
                organization_id,
                quote.id,
            )

            return self._build_quote_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The quote line conflicts with "
                    "an existing record."
                ),
            ) from exc

        except HTTPException:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def remove_line_item(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        actor_user_id: uuid.UUID,
    ) -> QuoteResponse:
        """
        Soft-remove one active draft quote line.
        """

        try:
            quote = self._get_quote_or_404(
                organization_id,
                quote_id,
                for_update=True,
            )

            self._ensure_draft(quote)

            line_item = self.quotes.get_line_item(
                organization_id,
                quote_id,
                line_item_id,
                for_update=True,
            )

            if line_item is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Active quote line item not found.",
                )

            line_item.is_active = False

            self.quotes.update_line_item(
                line_item
            )

            self._recalculate(quote)

            self._record_activity(
                organization_id=organization_id,
                quote_id=quote.id,
                actor_user_id=actor_user_id,
                activity_type=(
                    "quote_line_item_removed"
                ),
                summary=(
                    "Quote line item removed."
                ),
                details={
                    "line_item_id": str(
                        line_item.id
                    ),
                    "description": (
                        line_item.description
                    ),
                    "line_total": str(
                        line_item.line_total
                    ),
                    "quote_total": str(
                        quote.total_amount
                    ),
                },
            )

            self.db.commit()

            loaded = self._reload_quote(
                organization_id,
                quote.id,
            )

            return self._build_quote_response(
                loaded
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The quote line could not be removed."
                ),
            ) from exc

        except HTTPException:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def send_quote(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        payload: QuoteLifecycleNote,
        *,
        actor_user_id: uuid.UUID,
    ) -> QuoteResponse:
        """
        Issue a draft quote to its customer.
        """

        try:
            quote = self._get_quote_or_404(
                organization_id,
                quote_id,
                for_update=True,
            )

            self._ensure_draft(quote)

            lines = self.quotes.active_line_items(
                quote.id
            )

            if not lines:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "A quote must contain at least "
                        "one active line item before sending."
                    ),
                )

            self._recalculate(quote)

            if quote.total_amount <= ZERO_MONEY:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Quote total must be greater "
                        "than zero before sending."
                    ),
                )

            if (
                quote.valid_until is not None
                and quote.valid_until < date.today()
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The quote validity date has passed."
                    ),
                )

            previous_status = quote.status
            now = datetime.now(timezone.utc)

            quote.status = "sent"
            quote.sent_by_user_id = actor_user_id
            quote.sent_at = now

            self.quotes.update_quote(quote)

            self._record_activity(
                organization_id=organization_id,
                quote_id=quote.id,
                actor_user_id=actor_user_id,
                activity_type="quote_sent",
                summary=(
                    f"Quote {quote.quote_number} sent."
                ),
                from_status=previous_status,
                to_status="sent",
                note=payload.note,
                details={
                    "currency": quote.currency,
                    "valid_until": (
                        quote.valid_until.isoformat()
                        if quote.valid_until
                        else None
                    ),
                    "subtotal": str(
                        quote.subtotal
                    ),
                    "discount_amount": str(
                        quote.discount_amount
                    ),
                    "tax_amount": str(
                        quote.tax_amount
                    ),
                    "total_amount": str(
                        quote.total_amount
                    ),
                },
            )

            self.db.commit()

            loaded = self._reload_quote(
                organization_id,
                quote.id,
            )

            return self._build_quote_response(
                loaded
            )

        except HTTPException:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def accept_quote(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        payload: QuoteLifecycleNote,
        *,
        actor_user_id: uuid.UUID,
    ) -> QuoteResponse:
        """
        Record customer acceptance of a sent quote.
        """

        try:
            quote = self._get_quote_or_404(
                organization_id,
                quote_id,
                for_update=True,
            )

            self._ensure_sent(quote)
            self._ensure_not_past_validity(quote)

            previous_status = quote.status
            now = datetime.now(timezone.utc)

            quote.status = "accepted"
            quote.accepted_at = now
            quote.rejected_at = None
            quote.responded_by_user_id = actor_user_id
            quote.response_note = payload.note

            self.quotes.update_quote(quote)

            self._record_activity(
                organization_id=organization_id,
                quote_id=quote.id,
                actor_user_id=actor_user_id,
                activity_type="quote_accepted",
                summary=(
                    f"Quote {quote.quote_number} accepted."
                ),
                from_status=previous_status,
                to_status="accepted",
                note=payload.note,
                details={
                    "currency": quote.currency,
                    "total_amount": str(
                        quote.total_amount
                    ),
                },
            )

            # Auto notification: quote accepted.
            self.auto_notifications.notify_quote_accepted(
                organization_id=organization_id,
                quote=quote,
                actor_user_id=actor_user_id,
            )

            self.auto_audit.quote_accepted(

                organization_id=organization_id,

                quote=quote,

                actor_user_id=actor_user_id,

            )


            self.db.commit()

            loaded = self._reload_quote(
                organization_id,
                quote.id,
            )

            return self._build_quote_response(
                loaded
            )

        except HTTPException:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def reject_quote(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        payload: QuoteRejectRequest,
        *,
        actor_user_id: uuid.UUID,
    ) -> QuoteResponse:
        """
        Record customer rejection of a sent quote.
        """

        try:
            quote = self._get_quote_or_404(
                organization_id,
                quote_id,
                for_update=True,
            )

            self._ensure_sent(quote)
            self._ensure_not_past_validity(quote)

            previous_status = quote.status
            now = datetime.now(timezone.utc)

            quote.status = "rejected"
            quote.rejected_at = now
            quote.accepted_at = None
            quote.responded_by_user_id = actor_user_id
            quote.response_note = payload.reason

            self.quotes.update_quote(quote)

            self._record_activity(
                organization_id=organization_id,
                quote_id=quote.id,
                actor_user_id=actor_user_id,
                activity_type="quote_rejected",
                summary=(
                    f"Quote {quote.quote_number} rejected."
                ),
                from_status=previous_status,
                to_status="rejected",
                note=payload.reason,
                details={
                    "currency": quote.currency,
                    "total_amount": str(
                        quote.total_amount
                    ),
                },
            )

            self.db.commit()

            loaded = self._reload_quote(
                organization_id,
                quote.id,
            )

            return self._build_quote_response(
                loaded
            )

        except HTTPException:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def expire_quote(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        payload: QuoteLifecycleNote,
        *,
        actor_user_id: uuid.UUID,
    ) -> QuoteResponse:
        """
        Mark a sent quote expired after its validity date.
        """

        try:
            quote = self._get_quote_or_404(
                organization_id,
                quote_id,
                for_update=True,
            )

            self._ensure_sent(quote)

            if quote.valid_until is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "A quote without a validity date "
                        "cannot be marked expired."
                    ),
                )

            if quote.valid_until >= date.today():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "The quote has not reached "
                        "its expiry date."
                    ),
                )

            previous_status = quote.status
            now = datetime.now(timezone.utc)

            quote.status = "expired"
            quote.expired_at = now
            quote.responded_by_user_id = actor_user_id
            quote.response_note = payload.note

            self.quotes.update_quote(quote)

            self._record_activity(
                organization_id=organization_id,
                quote_id=quote.id,
                actor_user_id=actor_user_id,
                activity_type="quote_expired",
                summary=(
                    f"Quote {quote.quote_number} expired."
                ),
                from_status=previous_status,
                to_status="expired",
                note=payload.note,
                details={
                    "valid_until": (
                        quote.valid_until.isoformat()
                    ),
                    "currency": quote.currency,
                    "total_amount": str(
                        quote.total_amount
                    ),
                },
            )

            self.db.commit()

            loaded = self._reload_quote(
                organization_id,
                quote.id,
            )

            return self._build_quote_response(
                loaded
            )

        except HTTPException:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def convert_quote(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        payload: QuoteConvertRequest,
        *,
        actor_user_id: uuid.UUID,
    ) -> QuoteConversionResponse:
        """
        Convert one accepted quote into a draft work order.

        The work order, work-order activity, quote transition,
        and quote activity are committed together.
        """

        try:
            quote = self._get_quote_or_404(
                organization_id,
                quote_id,
                for_update=True,
            )

            if quote.status == "converted":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This quote has already been "
                        "converted into a work order."
                    ),
                )

            if quote.status != "accepted":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Only accepted quotes can be "
                        "converted into work orders."
                    ),
                )

            if quote.converted_work_order_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This quote is already linked "
                        "to a work order."
                    ),
                )

            self._get_customer_or_404(
                organization_id,
                quote.customer_id,
            )

            self._get_site_or_404(
                organization_id,
                quote.customer_id,
                quote.customer_site_id,
            )

            work_order_number = (
                self._generate_work_order_number(
                    organization_id
                )
            )

            source_note = (
                f"Created from accepted quote "
                f"{quote.quote_number} "
                f"({quote.currency} "
                f"{quote.total_amount})."
            )

            instructions = payload.instructions

            if instructions:
                instructions = (
                    f"{instructions}\n\n{source_note}"
                )
            else:
                instructions = source_note

            work_order = WorkOrder(
                organization_id=organization_id,
                customer_id=quote.customer_id,
                customer_site_id=(
                    quote.customer_site_id
                ),
                work_order_number=(
                    work_order_number
                ),
                title=(
                    payload.title
                    or quote.title
                ),
                description=(
                    payload.description
                    if payload.description is not None
                    else quote.description
                ),
                job_type=payload.job_type,
                customer_reference=(
                    payload.customer_reference
                    or quote.quote_number
                ),
                priority=payload.priority,
                status="draft",
                scheduled_start=(
                    payload.scheduled_start
                ),
                scheduled_end=(
                    payload.scheduled_end
                ),
                estimated_cost=(
                    quote.total_amount
                ),
                instructions=instructions,
                is_active=True,
            )

            self.db.add(work_order)
            self.db.flush()

            self.db.add(
                WorkOrderActivity(
                    organization_id=organization_id,
                    work_order_id=work_order.id,
                    actor_user_id=actor_user_id,
                    activity_type="created",
                    summary=(
                        f"Work order "
                        f"{work_order.work_order_number} "
                        "created from accepted quote."
                    ),
                    to_status="draft",
                    details={
                        "customer_id": str(
                            work_order.customer_id
                        ),
                        "customer_site_id": (
                            str(
                                work_order.customer_site_id
                            )
                            if work_order.customer_site_id
                            else None
                        ),
                        "source_quote_id": str(
                            quote.id
                        ),
                        "source_quote_number": (
                            quote.quote_number
                        ),
                        "quote_currency": (
                            quote.currency
                        ),
                        "quoted_total": str(
                            quote.total_amount
                        ),
                    },
                )
            )
            self.db.flush()

            previous_status = quote.status
            now = datetime.now(timezone.utc)

            quote.status = "converted"
            quote.converted_work_order_id = (
                work_order.id
            )
            quote.converted_by_user_id = (
                actor_user_id
            )
            quote.converted_at = now

            self.quotes.update_quote(quote)

            self._record_activity(
                organization_id=organization_id,
                quote_id=quote.id,
                actor_user_id=actor_user_id,
                activity_type="quote_converted",
                summary=(
                    f"Quote {quote.quote_number} "
                    "converted into work order "
                    f"{work_order.work_order_number}."
                ),
                from_status=previous_status,
                to_status="converted",
                details={
                    "work_order_id": str(
                        work_order.id
                    ),
                    "work_order_number": (
                        work_order.work_order_number
                    ),
                    "currency": quote.currency,
                    "total_amount": str(
                        quote.total_amount
                    ),
                },
            )

            # Auto notification: quote converted.
            self.auto_notifications.notify_quote_converted(
                organization_id=organization_id,
                quote=quote,
                work_order=work_order,
                actor_user_id=actor_user_id,
            )

            self.auto_audit.quote_converted(

                organization_id=organization_id,

                quote=quote,

                work_order=work_order,

                actor_user_id=actor_user_id,

            )


            self.db.commit()

            loaded = self._reload_quote(
                organization_id,
                quote.id,
            )

            return QuoteConversionResponse(
                quote=self._build_quote_response(
                    loaded
                ),
                work_order_id=work_order.id,
                work_order_number=(
                    work_order.work_order_number
                ),
            )

        except IntegrityError as exc:
            self.db.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The quote conversion conflicts "
                    "with an existing record."
                ),
            ) from exc

        except HTTPException:
            self.db.rollback()
            raise

        except Exception:
            self.db.rollback()
            raise

    def get_summary(
        self,
        organization_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> QuoteSummaryResponse:
        """
        Return quote totals separated by currency.
        """

        rows = self.quotes.currency_summary(
            organization_id,
            include_inactive=include_inactive,
        )

        return QuoteSummaryResponse(
            currencies=[
                QuoteCurrencySummary(**row)
                for row in rows
            ]
        )

    def list_activities(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        activity_type: str | None = None,
        include_inactive_quote: bool = False,
    ) -> QuoteActivityListResponse:
        """
        Return one quote's immutable activity history.
        """

        self._get_quote_or_404(
            organization_id,
            quote_id,
            include_inactive=(
                include_inactive_quote
            ),
        )

        activities = self.quotes.list_activities(
            organization_id,
            quote_id,
            skip=skip,
            limit=limit,
            activity_type=activity_type,
        )

        total = self.quotes.count_activities(
            organization_id,
            quote_id,
            activity_type=activity_type,
        )

        return QuoteActivityListResponse(
            items=[
                self._build_activity_response(
                    activity
                )
                for activity in activities
            ],
            total=total,
            skip=skip,
            limit=limit,
        )
