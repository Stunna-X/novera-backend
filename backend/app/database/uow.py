"""
Unit of Work.

Provides transactional boundaries for business operations.

Every business workflow should execute inside a UnitOfWork
to guarantee atomicity.

Example:

    with UnitOfWork(db):

        organization = ...

        membership = ...

        audit_log = ...

If an exception occurs:
    -> rollback()

Otherwise:
    -> commit()

The UnitOfWork does NOT close the database session.
Session lifecycle is managed by FastAPI's dependency injection.
"""

from __future__ import annotations

from sqlalchemy.orm import Session


class UnitOfWork:
    """
    Coordinates a single database transaction.

    Responsibilities:
        - Commit successful transactions
        - Roll back failed transactions

    Does NOT:
        - Create sessions
        - Close sessions
    """

    def __init__(
        self,
        db: Session,
    ) -> None:
        self.db = db

    def __enter__(self) -> "UnitOfWork":
        """
        Begin a transactional context.
        """
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        """
        Automatically commit or rollback.

        If an exception occurred inside the context,
        rollback the transaction.

        Otherwise commit it.
        """

        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    def commit(self) -> None:
        """
        Commit the current transaction.
        """
        self.db.commit()

    def rollback(self) -> None:
        """
        Roll back the current transaction.
        """
        self.db.rollback()