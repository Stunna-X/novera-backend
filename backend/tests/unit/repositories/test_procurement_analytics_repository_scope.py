"""PostgreSQL tenant-isolation gate for procurement analytics queries."""

from __future__ import annotations

import inspect

from app.repositories.procurement_analytics import (
    ProcurementAnalyticsRepository,
)


def test_public_reporting_queries_require_organization_id() -> None:
    """Every public reporting query must require tenant scope explicitly."""

    method_names = (
        "overview_counts",
        "open_commitments",
        "outstanding_payables",
        "payments_in_period",
        "supplier_spend",
        "purchase_order_commitments",
        "accounts_payable",
        "match_exceptions",
        "receipt_variances",
        "payment_history",
    )

    for method_name in method_names:
        signature = inspect.signature(
            getattr(ProcurementAnalyticsRepository, method_name)
        )
        parameter = signature.parameters.get("organization_id")
        assert parameter is not None
        assert parameter.default is inspect.Parameter.empty
