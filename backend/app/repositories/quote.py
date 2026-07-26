"""
Quote repository.

Contains organization-scoped persistence and reporting operations
for quotes, line items, and immutable quote activities.

Mutation methods flush without committing so the service can keep
each quote operation inside one database transaction.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    case,
    func,
    or_,
)
from sqlalchemy.orm import (
    Session,
    joinedload,
    selectinload,
)

from app.models.quote import (
    Quote,
    QuoteActivity,
    QuoteLineItem,
)


class QuoteRepository:
    """
    Repository for quote and estimate operations.
    """

    def __init__(
        self,
        db: Session,
    ):
        self.db = db

    @staticmethod
    def _quote_options():
        """
        Return relationships needed by quote API responses.
        """

        return (
            selectinload(Quote.line_items),
            joinedload(Quote.created_by),
            joinedload(Quote.sent_by),
            joinedload(Quote.responded_by),
            joinedload(Quote.converted_by),
        )

    def create_quote(
        self,
        quote: Quote,
    ) -> Quote:
        """
        Add a quote to the current transaction.
        """

        quote.quote_number = (
            quote.quote_number.strip().upper()
        )
        quote.title = quote.title.strip()
        quote.currency = quote.currency.strip().upper()

        self.db.add(quote)
        self.db.flush()

        return quote

    def update_quote(
        self,
        quote: Quote,
    ) -> Quote:
        """
        Flush quote changes.
        """

        quote.quote_number = (
            quote.quote_number.strip().upper()
        )
        quote.title = quote.title.strip()
        quote.currency = quote.currency.strip().upper()

        self.db.add(quote)
        self.db.flush()

        return quote

    def get_for_organization(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> Quote | None:
        """
        Retrieve one organization quote.
        """

        query = (
            self.db.query(Quote)
            .options(*self._quote_options())
            .populate_existing()
            .filter(
                Quote.id == quote_id,
                Quote.organization_id == organization_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                Quote.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=Quote,
            )

        return query.first()

    def list_for_organization(
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
    ) -> list[Quote]:
        """
        List organization quotes.
        """

        query = (
            self.db.query(Quote)
            .options(*self._quote_options())
            .populate_existing()
            .filter(
                Quote.organization_id == organization_id
            )
        )

        query = self._apply_list_filters(
            query=query,
            search=search,
            status_filter=status_filter,
            customer_id=customer_id,
            customer_site_id=customer_site_id,
            currency=currency,
            include_inactive=include_inactive,
        )

        return (
            query.order_by(
                Quote.quote_date.desc(),
                Quote.created_at.desc(),
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
        status_filter: str | None = None,
        customer_id: uuid.UUID | None = None,
        customer_site_id: uuid.UUID | None = None,
        currency: str | None = None,
        include_inactive: bool = False,
    ) -> int:
        """
        Count filtered organization quotes.
        """

        query = (
            self.db.query(func.count(Quote.id))
            .filter(
                Quote.organization_id == organization_id
            )
        )

        query = self._apply_list_filters(
            query=query,
            search=search,
            status_filter=status_filter,
            customer_id=customer_id,
            customer_site_id=customer_site_id,
            currency=currency,
            include_inactive=include_inactive,
        )

        return int(query.scalar() or 0)

    @staticmethod
    def _apply_list_filters(
        *,
        query,
        search: str | None,
        status_filter: str | None,
        customer_id: uuid.UUID | None,
        customer_site_id: uuid.UUID | None,
        currency: str | None,
        include_inactive: bool,
    ):
        """
        Apply common quote listing filters.
        """

        if not include_inactive:
            query = query.filter(
                Quote.is_active.is_(True)
            )

        if status_filter:
            query = query.filter(
                Quote.status == status_filter
            )

        if customer_id:
            query = query.filter(
                Quote.customer_id == customer_id
            )

        if customer_site_id:
            query = query.filter(
                Quote.customer_site_id
                == customer_site_id
            )

        if currency:
            query = query.filter(
                Quote.currency
                == currency.strip().upper()
            )

        normalized_search = (
            search.strip()
            if search
            else None
        )

        if normalized_search:
            pattern = f"%{normalized_search}%"

            query = query.filter(
                or_(
                    Quote.quote_number.ilike(pattern),
                    Quote.title.ilike(pattern),
                    Quote.description.ilike(pattern),
                    Quote.customer_name.ilike(pattern),
                    Quote.customer_email.ilike(pattern),
                    Quote.customer_phone.ilike(pattern),
                )
            )

        return query

    def number_exists(
        self,
        organization_id: uuid.UUID,
        quote_number: str,
        *,
        exclude_quote_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check quote-number uniqueness within an organization.
        """

        normalized_number = (
            quote_number.strip().lower()
        )

        query = (
            self.db.query(Quote.id)
            .filter(
                Quote.organization_id == organization_id,
                func.lower(Quote.quote_number)
                == normalized_number,
            )
        )

        if exclude_quote_id:
            query = query.filter(
                Quote.id != exclude_quote_id
            )

        return query.first() is not None

    def add_line_item(
        self,
        line_item: QuoteLineItem,
    ) -> QuoteLineItem:
        """
        Add one quote line to the current transaction.
        """

        line_item.description = (
            line_item.description.strip()
        )

        self.db.add(line_item)
        self.db.flush()

        return line_item

    def update_line_item(
        self,
        line_item: QuoteLineItem,
    ) -> QuoteLineItem:
        """
        Flush quote-line changes.
        """

        line_item.description = (
            line_item.description.strip()
        )

        self.db.add(line_item)
        self.db.flush()

        return line_item

    def get_line_item(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        line_item_id: uuid.UUID,
        *,
        include_inactive: bool = False,
        for_update: bool = False,
    ) -> QuoteLineItem | None:
        """
        Retrieve one line belonging to an organization quote.
        """

        query = (
            self.db.query(QuoteLineItem)
            .join(
                Quote,
                Quote.id == QuoteLineItem.quote_id,
            )
            .filter(
                Quote.organization_id == organization_id,
                Quote.id == quote_id,
                QuoteLineItem.id == line_item_id,
            )
        )

        if not include_inactive:
            query = query.filter(
                QuoteLineItem.is_active.is_(True)
            )

        if for_update:
            query = query.with_for_update(
                of=QuoteLineItem,
            )

        return query.first()

    def next_line_position(
        self,
        quote_id: uuid.UUID,
    ) -> int:
        """
        Return the next unused line position.

        Inactive rows are included because the database uniqueness
        constraint applies to every line, not only active lines.
        """

        maximum = (
            self.db.query(
                func.max(QuoteLineItem.position)
            )
            .filter(
                QuoteLineItem.quote_id == quote_id
            )
            .scalar()
        )

        return int(maximum + 1) if maximum is not None else 0

    def position_exists(
        self,
        quote_id: uuid.UUID,
        position: int,
        *,
        exclude_line_item_id: uuid.UUID | None = None,
    ) -> bool:
        """
        Check whether a quote position is already occupied.
        """

        query = (
            self.db.query(QuoteLineItem.id)
            .filter(
                QuoteLineItem.quote_id == quote_id,
                QuoteLineItem.position == position,
            )
        )

        if exclude_line_item_id:
            query = query.filter(
                QuoteLineItem.id
                != exclude_line_item_id
            )

        return query.first() is not None

    def active_line_items(
        self,
        quote_id: uuid.UUID,
    ) -> list[QuoteLineItem]:
        """
        Return active lines in display order.
        """

        return (
            self.db.query(QuoteLineItem)
            .filter(
                QuoteLineItem.quote_id == quote_id,
                QuoteLineItem.is_active.is_(True),
            )
            .order_by(
                QuoteLineItem.position.asc(),
                QuoteLineItem.created_at.asc(),
            )
            .all()
        )

    def add_activity(
        self,
        activity: QuoteActivity,
    ) -> QuoteActivity:
        """
        Add an immutable quote activity.
        """

        self.db.add(activity)
        self.db.flush()

        return activity

    def list_activities(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 100,
        activity_type: str | None = None,
    ) -> list[QuoteActivity]:
        """
        List quote activities chronologically.
        """

        query = (
            self.db.query(QuoteActivity)
            .options(joinedload(QuoteActivity.actor))
            .filter(
                QuoteActivity.organization_id
                == organization_id,
                QuoteActivity.quote_id == quote_id,
            )
        )

        if activity_type:
            query = query.filter(
                QuoteActivity.activity_type
                == activity_type
            )

        return (
            query.order_by(
                QuoteActivity.created_at.asc()
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_activities(
        self,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        *,
        activity_type: str | None = None,
    ) -> int:
        """
        Count quote activities.
        """

        query = (
            self.db.query(
                func.count(QuoteActivity.id)
            )
            .filter(
                QuoteActivity.organization_id
                == organization_id,
                QuoteActivity.quote_id == quote_id,
            )
        )

        if activity_type:
            query = query.filter(
                QuoteActivity.activity_type
                == activity_type
            )

        return int(query.scalar() or 0)

    def currency_summary(
        self,
        organization_id: uuid.UUID,
        *,
        include_inactive: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Aggregate quote counts and values without mixing currencies.
        """

        query = (
            self.db.query(
                Quote.currency.label("currency"),
                func.count(Quote.id).label("quote_count"),
                func.coalesce(
                    func.sum(Quote.total_amount),
                    0,
                ).label("total_quoted"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Quote.status.in_(
                                    ["accepted", "converted"]
                                ),
                                Quote.total_amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_accepted"),
                func.sum(
                    case(
                        (Quote.status == "draft", 1),
                        else_=0,
                    )
                ).label("draft_count"),
                func.sum(
                    case(
                        (Quote.status == "sent", 1),
                        else_=0,
                    )
                ).label("sent_count"),
                func.sum(
                    case(
                        (Quote.status == "accepted", 1),
                        else_=0,
                    )
                ).label("accepted_count"),
                func.sum(
                    case(
                        (Quote.status == "rejected", 1),
                        else_=0,
                    )
                ).label("rejected_count"),
                func.sum(
                    case(
                        (Quote.status == "expired", 1),
                        else_=0,
                    )
                ).label("expired_count"),
                func.sum(
                    case(
                        (Quote.status == "converted", 1),
                        else_=0,
                    )
                ).label("converted_count"),
            )
            .filter(
                Quote.organization_id == organization_id
            )
        )

        if not include_inactive:
            query = query.filter(
                Quote.is_active.is_(True)
            )

        rows = (
            query.group_by(Quote.currency)
            .order_by(Quote.currency.asc())
            .all()
        )

        return [
            {
                "currency": row.currency,
                "quote_count": int(
                    row.quote_count or 0
                ),
                "total_quoted": row.total_quoted,
                "total_accepted": row.total_accepted,
                "draft_count": int(
                    row.draft_count or 0
                ),
                "sent_count": int(
                    row.sent_count or 0
                ),
                "accepted_count": int(
                    row.accepted_count or 0
                ),
                "rejected_count": int(
                    row.rejected_count or 0
                ),
                "expired_count": int(
                    row.expired_count or 0
                ),
                "converted_count": int(
                    row.converted_count or 0
                ),
            }
            for row in rows
        ]