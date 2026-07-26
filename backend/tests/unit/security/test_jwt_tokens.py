"""Regression tests for JWT creation and validation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from app.core.config import settings
from app.core.jwt import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    verify_refresh_token,
    verify_token,
)


pytestmark = pytest.mark.unit


def test_access_tokens_have_unique_identifiers() -> None:
    subject = str(uuid.uuid4())

    first = create_access_token({"sub": subject})
    second = create_access_token({"sub": subject})

    first_payload = verify_access_token(first)
    second_payload = verify_access_token(second)

    assert first != second
    assert first_payload is not None
    assert second_payload is not None
    assert first_payload["jti"] != second_payload["jti"]


def test_refresh_tokens_have_unique_identifiers() -> None:
    subject = str(uuid.uuid4())

    first = create_refresh_token({"sub": subject})
    second = create_refresh_token({"sub": subject})

    first_payload = verify_refresh_token(first)
    second_payload = verify_refresh_token(second)

    assert first != second
    assert first_payload is not None
    assert second_payload is not None
    assert first_payload["jti"] != second_payload["jti"]


def test_token_type_helpers_reject_the_wrong_token_type() -> None:
    subject = str(uuid.uuid4())
    access_token = create_access_token({"sub": subject})
    refresh_token = create_refresh_token({"sub": subject})

    assert verify_refresh_token(access_token) is None
    assert verify_access_token(refresh_token) is None


def test_tampered_token_is_rejected() -> None:
    token = create_access_token({"sub": str(uuid.uuid4())})

    header, payload, signature = token.split(".")
    replacement = "a" if signature[0] != "a" else "b"
    tampered_signature = replacement + signature[1:]
    tampered = ".".join(
        (
            header,
            payload,
            tampered_signature,
        )
    )

    assert verify_access_token(tampered) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"type": "access"},
        {"sub": str(uuid.uuid4())},
    ],
)
def test_token_missing_required_claim_is_rejected(
    payload: dict[str, str],
) -> None:
    now = datetime.now(UTC)

    token = jwt.encode(
        {
            **payload,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    assert verify_token(token) is None


def test_expired_token_is_rejected() -> None:
    now = datetime.now(UTC)

    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "type": "access",
            "iat": now - timedelta(minutes=10),
            "exp": now - timedelta(minutes=5),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )

    assert verify_access_token(token) is None
