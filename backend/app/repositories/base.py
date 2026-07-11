"""
Base repository.

Provides common CRUD operations that all repositories inherit.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.base import BaseModel


ModelType = TypeVar(
    "ModelType",
    bound=BaseModel,
)


class BaseRepository(Generic[ModelType]):
    """
    Generic repository providing reusable CRUD operations.
    """

    def __init__(
        self,
        db: Session,
        model: type[ModelType],
    ):
        self.db = db
        self.model = model

    def get(
        self,
        object_id: object,
    ) -> ModelType | None:
        """
        Retrieve one record by its primary key.
        """

        return (
            self.db.query(self.model)
            .filter(self.model.id == object_id)
            .first()
        )

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> list[ModelType]:
        """
        Retrieve a paginated list of records.
        """

        return (
            self.db.query(self.model)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(
        self,
        obj: ModelType,
    ) -> ModelType:
        """
        Persist a new database record.
        """

        try:
            self.db.add(obj)
            self.db.commit()
            self.db.refresh(obj)

            return obj

        except SQLAlchemyError:
            self.db.rollback()
            raise

    def update(
        self,
        obj: ModelType,
    ) -> ModelType:
        """
        Commit changes made to an existing record.
        """

        try:
            self.db.add(obj)
            self.db.commit()
            self.db.refresh(obj)

            return obj

        except SQLAlchemyError:
            self.db.rollback()
            raise

    def delete(
        self,
        obj: ModelType,
    ) -> None:
        """
        Delete an existing database record.
        """

        try:
            self.db.delete(obj)
            self.db.commit()

        except SQLAlchemyError:
            self.db.rollback()
            raise