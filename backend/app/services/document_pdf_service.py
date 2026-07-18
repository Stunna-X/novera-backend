"""
PDF document service.

Generates customer-facing invoice and quote PDFs.
"""

from __future__ import annotations

import html
import io
import re
import uuid
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.quote import Quote


class DocumentPDFService:
    """
    Builds PDF documents for invoices and quotes.
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db
        self.styles = getSampleStyleSheet()
        self.body_style = ParagraphStyle(
            "NoveraBody",
            parent=self.styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            spaceAfter=4,
        )
        self.small_style = ParagraphStyle(
            "NoveraSmall",
            parent=self.styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        )
        self.heading_style = ParagraphStyle(
            "NoveraHeading",
            parent=self.styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            spaceAfter=10,
        )
        self.section_style = ParagraphStyle(
            "NoveraSection",
            parent=self.styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            spaceBefore=10,
            spaceAfter=6,
        )
        self.right_style = ParagraphStyle(
            "NoveraRight",
            parent=self.body_style,
            alignment=TA_RIGHT,
        )

    def build_invoice_pdf(
        self,
        *,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> tuple[bytes, str]:
        """
        Build one invoice PDF and return bytes plus filename.
        """

        invoice = self._get_invoice_or_404(
            organization_id=organization_id,
            invoice_id=invoice_id,
            include_inactive=include_inactive,
        )

        story = [
            self._title_row(
                title="INVOICE",
                document_number=invoice.invoice_number,
                status_value=invoice.status,
            ),
            Spacer(1, 6),
            self._party_table(
                organization=invoice.organization,
                customer_name=invoice.customer_name,
                customer_email=invoice.customer_email,
                customer_phone=invoice.customer_phone,
                billing_address=invoice.billing_address,
            ),
            Spacer(1, 8),
            self._details_table(
                [
                    ("Invoice Date", self._date(invoice.invoice_date)),
                    ("Due Date", self._date(invoice.due_date)),
                    ("Currency", invoice.currency),
                    (
                        "Work Order",
                        self._work_order_label(invoice.work_order),
                    ),
                ]
            ),
            self._section("Line Items"),
            self._line_items_table(
                items=[
                    item
                    for item in invoice.line_items
                    if item.is_active
                ],
                currency=invoice.currency,
            ),
            Spacer(1, 8),
            self._totals_table(
                currency=invoice.currency,
                rows=[
                    ("Subtotal", invoice.subtotal),
                    ("Discount", invoice.discount_amount),
                    ("Tax", invoice.tax_amount),
                    ("Total", invoice.total_amount),
                    ("Paid", invoice.amount_paid),
                    ("Balance Due", invoice.balance_due),
                ],
            ),
        ]

        active_payments = [
            payment
            for payment in invoice.payments
            if not payment.is_reversed
        ]

        if active_payments:
            story.extend(
                [
                    self._section("Payments"),
                    self._payments_table(
                        payments=active_payments,
                        currency=invoice.currency,
                    ),
                ]
            )

        self._append_payment_details(
            story=story,
            organization=invoice.organization,
        )

        self._append_notes_terms(
            story=story,
            notes=invoice.notes,
            terms=(
                invoice.terms
                or getattr(
                    invoice.organization,
                    "default_invoice_terms",
                    None,
                )
            ),
            footer=getattr(
                invoice.organization,
                "invoice_footer",
                None,
            ),
        )

        return (
            self._build_pdf(story),
            self._filename(
                prefix="novera-invoice",
                number=invoice.invoice_number,
            ),
        )

    def build_quote_pdf(
        self,
        *,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        include_inactive: bool = False,
    ) -> tuple[bytes, str]:
        """
        Build one quote/estimate PDF and return bytes plus filename.
        """

        quote = self._get_quote_or_404(
            organization_id=organization_id,
            quote_id=quote_id,
            include_inactive=include_inactive,
        )

        story = [
            self._title_row(
                title="QUOTE / ESTIMATE",
                document_number=quote.quote_number,
                status_value=quote.status,
            ),
            Spacer(1, 6),
            self._party_table(
                organization=quote.organization,
                customer_name=quote.customer_name,
                customer_email=quote.customer_email,
                customer_phone=quote.customer_phone,
                billing_address=quote.billing_address,
                service_address=quote.service_address,
            ),
            Spacer(1, 8),
            self._details_table(
                [
                    ("Quote Date", self._date(quote.quote_date)),
                    ("Valid Until", self._date(quote.valid_until)),
                    ("Currency", quote.currency),
                    ("Title", quote.title),
                ]
            ),
        ]

        if quote.description:
            story.extend(
                [
                    self._section("Description"),
                    self._paragraph(quote.description),
                ]
            )

        story.extend(
            [
                self._section("Line Items"),
                self._line_items_table(
                    items=[
                        item
                        for item in quote.line_items
                        if item.is_active
                    ],
                    currency=quote.currency,
                ),
                Spacer(1, 8),
                self._totals_table(
                    currency=quote.currency,
                    rows=[
                        ("Subtotal", quote.subtotal),
                        ("Discount", quote.discount_amount),
                        ("Tax", quote.tax_amount),
                        ("Total", quote.total_amount),
                    ],
                ),
            ]
        )

        if quote.converted_work_order is not None:
            story.extend(
                [
                    self._section("Converted Work Order"),
                    self._paragraph(
                        self._work_order_label(
                            quote.converted_work_order
                        )
                    ),
                ]
            )

        self._append_payment_details(
            story=story,
            organization=quote.organization,
        )

        self._append_notes_terms(
            story=story,
            notes=quote.notes,
            terms=(
                quote.terms
                or getattr(
                    quote.organization,
                    "default_quote_terms",
                    None,
                )
            ),
            footer=getattr(
                quote.organization,
                "quote_footer",
                None,
            ),
        )

        return (
            self._build_pdf(story),
            self._filename(
                prefix="novera-quote",
                number=quote.quote_number,
            ),
        )

    def _get_invoice_or_404(
        self,
        *,
        organization_id: uuid.UUID,
        invoice_id: uuid.UUID,
        include_inactive: bool,
    ) -> Invoice:
        query = self.db.query(Invoice).filter(
            Invoice.organization_id == organization_id,
            Invoice.id == invoice_id,
        )

        if not include_inactive:
            query = query.filter(
                Invoice.is_active.is_(True)
            )

        invoice = query.first()

        if invoice is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice not found.",
            )

        return invoice

    def _get_quote_or_404(
        self,
        *,
        organization_id: uuid.UUID,
        quote_id: uuid.UUID,
        include_inactive: bool,
    ) -> Quote:
        query = self.db.query(Quote).filter(
            Quote.organization_id == organization_id,
            Quote.id == quote_id,
        )

        if not include_inactive:
            query = query.filter(
                Quote.is_active.is_(True)
            )

        quote = query.first()

        if quote is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Quote not found.",
            )

        return quote

    def _build_pdf(
        self,
        story,
    ) -> bytes:
        buffer = io.BytesIO()

        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=16 * mm,
            leftMargin=16 * mm,
            topMargin=14 * mm,
            bottomMargin=14 * mm,
            title="Novera Document",
            author="Novera",
        )

        document.build(story)

        return buffer.getvalue()

    def _title_row(
        self,
        *,
        title: str,
        document_number: str,
        status_value: str,
    ) -> Table:
        table = Table(
            [
                [
                    Paragraph(
                        self._escape(title),
                        self.heading_style,
                    ),
                    Paragraph(
                        (
                            f"<b>{self._escape(document_number)}</b><br/>"
                            f"Status: {self._escape(status_value.upper())}"
                        ),
                        self.right_style,
                    ),
                ]
            ],
            colWidths=[105 * mm, 70 * mm],
        )

        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                    ("LINEBELOW", (0, 0), (-1, -1), 1, colors.black),
                ]
            )
        )

        return table

    def _party_table(
        self,
        *,
        organization,
        customer_name: str,
        customer_email: str | None,
        customer_phone: str | None,
        billing_address: str | None,
        service_address: str | None = None,
    ) -> Table:
        organization_lines = [
            f"<b>{self._escape(getattr(organization, 'name', 'Novera'))}</b>",
        ]

        for value in [
            getattr(organization, "business_address", None),
            getattr(organization, "email", None),
            getattr(organization, "phone", None),
            getattr(organization, "country", None),
        ]:
            if value:
                organization_lines.append(
                    self._escape(value)
                )

        tax_id = getattr(
            organization,
            "tax_identification_number",
            None,
        )
        vat_number = getattr(
            organization,
            "vat_number",
            None,
        )

        if tax_id:
            organization_lines.append(
                f"Tax ID: {self._escape(tax_id)}"
            )

        if vat_number:
            organization_lines.append(
                f"VAT: {self._escape(vat_number)}"
            )

        customer_lines = [
            f"<b>{self._escape(customer_name)}</b>",
        ]

        for value in [
            customer_email,
            customer_phone,
            billing_address,
        ]:
            if value:
                customer_lines.append(
                    self._escape(value)
                )

        if service_address:
            customer_lines.append(
                "<br/><b>Service Address</b>"
            )
            customer_lines.append(
                self._escape(service_address)
            )

        table = Table(
            [
                [
                    Paragraph(
                        "<b>From</b><br/>"
                        + "<br/>".join(organization_lines),
                        self.body_style,
                    ),
                    Paragraph(
                        "<b>Bill To</b><br/>"
                        + "<br/>".join(customer_lines),
                        self.body_style,
                    ),
                ]
            ],
            colWidths=[85 * mm, 90 * mm],
        )

        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.whitesmoke),
                    ("PADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )

        return table

    def _details_table(
        self,
        rows: list[tuple[str, Any]],
    ) -> Table:
        table_rows = [
            [
                Paragraph(
                    f"<b>{self._escape(label)}</b>",
                    self.small_style,
                ),
                Paragraph(
                    self._escape(self._value(value)),
                    self.small_style,
                ),
            ]
            for label, value in rows
        ]

        table = Table(
            table_rows,
            colWidths=[42 * mm, 133 * mm],
        )

        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )

        return table

    def _line_items_table(
        self,
        *,
        items,
        currency: str,
    ) -> Table:
        rows = [
            [
                Paragraph("<b>#</b>", self.small_style),
                Paragraph("<b>Description</b>", self.small_style),
                Paragraph("<b>Qty</b>", self.small_style),
                Paragraph("<b>Unit Price</b>", self.small_style),
                Paragraph("<b>Amount</b>", self.small_style),
            ]
        ]

        for index, item in enumerate(items, start=1):
            rows.append(
                [
                    Paragraph(str(index), self.small_style),
                    Paragraph(
                        self._escape(item.description),
                        self.small_style,
                    ),
                    Paragraph(
                        self._quantity(item.quantity),
                        self.small_style,
                    ),
                    Paragraph(
                        self._money(item.unit_price, currency),
                        self.small_style,
                    ),
                    Paragraph(
                        self._money(item.line_total, currency),
                        self.small_style,
                    ),
                ]
            )

        if len(rows) == 1:
            rows.append(
                [
                    "",
                    Paragraph(
                        "No active line items.",
                        self.small_style,
                    ),
                    "",
                    "",
                    "",
                ]
            )

        table = Table(
            rows,
            colWidths=[
                10 * mm,
                77 * mm,
                20 * mm,
                33 * mm,
                35 * mm,
            ],
            repeatRows=1,
        )

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.black),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ]
            )
        )

        return table

    def _payments_table(
        self,
        *,
        payments,
        currency: str,
    ) -> Table:
        rows = [
            [
                Paragraph("<b>Date</b>", self.small_style),
                Paragraph("<b>Method</b>", self.small_style),
                Paragraph("<b>Reference</b>", self.small_style),
                Paragraph("<b>Amount</b>", self.small_style),
            ]
        ]

        for payment in payments:
            rows.append(
                [
                    Paragraph(
                        self._date(payment.payment_date),
                        self.small_style,
                    ),
                    Paragraph(
                        self._escape(payment.payment_method),
                        self.small_style,
                    ),
                    Paragraph(
                        self._escape(payment.reference_number or ""),
                        self.small_style,
                    ),
                    Paragraph(
                        self._money(payment.amount, currency),
                        self.small_style,
                    ),
                ]
            )

        table = Table(
            rows,
            colWidths=[
                32 * mm,
                40 * mm,
                65 * mm,
                38 * mm,
            ],
            repeatRows=1,
        )

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.black),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                ]
            )
        )

        return table

    def _totals_table(
        self,
        *,
        currency: str,
        rows: list[tuple[str, Decimal]],
    ) -> Table:
        table_rows = [
            [
                Paragraph(
                    f"<b>{self._escape(label)}</b>",
                    self.small_style,
                ),
                Paragraph(
                    self._money(value, currency),
                    self.right_style,
                ),
            ]
            for label, value in rows
        ]

        table = Table(
            table_rows,
            colWidths=[45 * mm, 45 * mm],
            hAlign="RIGHT",
        )

        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                    ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
                ]
            )
        )

        return table

    def _append_payment_details(
        self,
        *,
        story: list,
        organization,
    ) -> None:
        """
        Add organization bank/payment details to the document.
        """

        rows: list[tuple[str, str]] = []

        for label, attribute in [
            ("Bank", "bank_name"),
            ("Account Name", "bank_account_name"),
            ("Account Number", "bank_account_number"),
            ("Routing / Sort Code", "bank_routing_number"),
        ]:
            value = getattr(
                organization,
                attribute,
                None,
            )

            if value:
                rows.append(
                    (
                        label,
                        str(value),
                    )
                )

        payment_instructions = getattr(
            organization,
            "payment_instructions",
            None,
        )

        if not rows and not payment_instructions:
            return

        story.append(
            self._section("Payment Details")
        )

        if rows:
            story.append(
                self._details_table(rows)
            )

        if payment_instructions:
            story.append(
                self._paragraph(payment_instructions)
            )

    def _append_notes_terms(
        self,
        *,
        story: list,
        notes: str | None,
        terms: str | None,
        footer: str | None = None,
    ) -> None:
        if notes:
            story.extend(
                [
                    self._section("Notes"),
                    self._paragraph(notes),
                ]
            )

        if terms:
            story.extend(
                [
                    self._section("Terms"),
                    self._paragraph(terms),
                ]
            )

        if footer:
            story.extend(
                [
                    self._section("Footer"),
                    self._paragraph(footer),
                ]
            )

        story.extend(
            [
                Spacer(1, 12),
                Paragraph(
                    "Generated by Novera.",
                    self.small_style,
                ),
            ]
        )

    def _section(
        self,
        text: str,
    ) -> Paragraph:
        return Paragraph(
            self._escape(text),
            self.section_style,
        )

    def _paragraph(
        self,
        text: str,
    ) -> Paragraph:
        return Paragraph(
            self._escape(text),
            self.body_style,
        )

    @staticmethod
    def _escape(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return html.escape(str(value)).replace(
            "\n",
            "<br/>",
        )

    @staticmethod
    def _value(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        return str(value)

    @staticmethod
    def _date(
        value: Any,
    ) -> str:
        if value is None:
            return ""

        if hasattr(value, "isoformat"):
            return value.isoformat()

        return str(value)

    @staticmethod
    def _money(
        value: Any,
        currency: str,
    ) -> str:
        amount = Decimal(value or 0)
        return f"{currency} {amount:,.2f}"

    @staticmethod
    def _quantity(
        value: Any,
    ) -> str:
        quantity = Decimal(value or 0)
        return f"{quantity:,.3f}"

    @staticmethod
    def _work_order_label(
        work_order,
    ) -> str:
        if work_order is None:
            return ""

        number = getattr(
            work_order,
            "work_order_number",
            "",
        )
        title = getattr(
            work_order,
            "title",
            "",
        )

        if number and title:
            return f"{number} - {title}"

        return number or title or ""

    @staticmethod
    def _filename(
        *,
        prefix: str,
        number: str,
    ) -> str:
        safe_number = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "-",
            number.strip(),
        ).strip("-")

        if not safe_number:
            safe_number = "document"

        return f"{prefix}-{safe_number}.pdf"
