"""
Authentication dependencies.

Provides reusable FastAPI dependencies for protected routes.
"""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app.core.jwt import verify_access_token
from app.database.session import get_db
from app.enums.user import UserStatus
from app.models.user import User
from app.repositories.user import UserRepository


bearer_scheme = HTTPBearer(
    auto_error=False,
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate a bearer access token and return the current user.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )

    if credentials is None:
        raise credentials_exception

    if credentials.scheme.lower() != "bearer":
        raise credentials_exception

    payload = verify_access_token(
        credentials.credentials
    )

    if payload is None:
        raise credentials_exception

    subject = payload.get("sub")

    if not subject:
        raise credentials_exception

    try:
        user_id = uuid.UUID(str(subject))
    except (ValueError, TypeError, AttributeError):
        raise credentials_exception

    users = UserRepository(db)

    user = users.get(user_id)

    if user is None:
        raise credentials_exception

    if user.status == UserStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is locked.",
        )

    if user.status == UserStatus.INACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive.",
        )

    return user
