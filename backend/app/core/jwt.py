"""
JWT token utilities.

Creates and validates access and refresh tokens.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.core.config import settings


def create_access_token(
    data: dict[str, Any],
) -> str:
    """
    Create a signed access token.
    """

    now = datetime.now(UTC)

    payload = {
        **data,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now
        + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        ),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_refresh_token(
    data: dict[str, Any],
) -> str:
    """
    Create a signed refresh token.
    """

    now = datetime.now(UTC)

    payload = {
        **data,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now
        + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS,
        ),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "type": "refresh",
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def verify_token(
    token: str,
    expected_type: str | None = None,
) -> dict[str, Any] | None:
    """
    Decode and validate a JWT.

    Optionally validates the expected token type.
    """

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
        )

        subject = payload.get("sub")
        token_type = payload.get("type")

        if not subject or not token_type:
            return None

        if expected_type is not None and token_type != expected_type:
            return None

        return payload

    except JWTError:
        return None


def verify_access_token(
    token: str,
) -> dict[str, Any] | None:
    """
    Validate an access token.
    """

    return verify_token(
        token,
        expected_type="access",
    )


def verify_refresh_token(
    token: str,
) -> dict[str, Any] | None:
    """
    Validate a refresh token.
    """

    return verify_token(
        token,
        expected_type="refresh",
    )
