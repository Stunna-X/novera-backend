"""Metadata checks for work-order material requirements."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, UniqueConstraint

from app.models.work_order_material import (
    WorkOrderMaterialRequirement,
)


def test_work_order_material_unique_item_constraint() -> None:
    constraints = [
        constraint
        for constraint
        in WorkOrderMaterialRequirement.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
        and [
            column.name
            for column in constraint.columns
        ]
        == ["work_order_id", "inventory_item_id"]
    ]

    assert len(constraints) == 1
    assert constraints[0].name == (
        "uq_work_order_material_requirements_item"
    )


def test_work_order_material_positive_quantity_constraint() -> None:
    names = {
        constraint.name
        for constraint
        in WorkOrderMaterialRequirement.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert (
        "ck_work_order_material_requirements_required_quantity_positive"
        in names
    )


def test_work_order_material_stock_indexes_exist() -> None:
    index_columns = {
        tuple(
            expression.name
            for expression in index.expressions
        )
        for index in WorkOrderMaterialRequirement.__table__.indexes
    }

    assert (
        "organization_id",
        "work_order_id",
    ) in index_columns
    assert (
        "organization_id",
        "inventory_item_id",
    ) in index_columns
    assert (
        "work_order_id",
        "is_active",
    ) in index_columns
