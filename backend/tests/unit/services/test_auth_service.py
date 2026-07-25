"""Focused unit tests for authentication service invariants."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

import app.services.auth_service as auth_service_module
from app.enums.user import UserStatus
from app.schemas.auth import LoginSchema, RegisterSchema
from app.services.auth_service import AuthService


pytestmark = pytest.mark.unit


def make_user(
    *,
    status: UserStatus = UserStatus.ACTIVE,
    email: str = "user@example.com",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        first_name="Test",
        last_name="User",
        email=email,
        password_hash="hashed-password",
        status=status,
    )


@pytest.fixture
def service() -> AuthService:
    instance = AuthService(MagicMock())
    instance.users = MagicMock()
    instance.refresh_tokens = MagicMock()
    return instance


def token_response() -> dict[str, str]:
    return {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "token_type": "Bearer",
    }


def test_register_rejects_duplicate_email(
    service: AuthService,
) -> None:
    service.users.email_exists.return_value = True

    with pytest.raises(HTTPException) as exc_info:
        service.register(
            RegisterSchema(
                first_name="Test",
                last_name="User",
                email="USER@EXAMPLE.COM",
                password="password123",
            )
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Email already exists."


def test_register_normalizes_user_and_issues_tokens(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service.users.email_exists.return_value = False
    service.users.create_user.side_effect = lambda user: user
    monkeypatch.setattr(
        auth_service_module,
        "hash_password",
        lambda password: f"hashed::{password}",
    )
    service._create_tokens_for_user = MagicMock(
        return_value=token_response()
    )

    result = service.register(
        RegisterSchema(
            first_name="  Test  ",
            last_name="  User  ",
            email="USER@EXAMPLE.COM",
            password="password123",
        )
    )

    created_user = service.users.create_user.call_args.args[0]

    assert created_user.first_name == "Test"
    assert created_user.last_name == "User"
    assert created_user.email == "user@example.com"
    assert created_user.password_hash == "hashed::password123"
    assert result["user"] is created_user
    assert result["access_token"] == "access-token"
    service._create_tokens_for_user.assert_called_once_with(
        created_user
    )


@pytest.mark.parametrize(
    ("user", "password_valid"),
    [
        (None, False),
        (make_user(), False),
    ],
)
def test_login_rejects_invalid_credentials(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
    user: SimpleNamespace | None,
    password_valid: bool,
) -> None:
    service.users.get_by_email.return_value = user
    monkeypatch.setattr(
        auth_service_module,
        "verify_password",
        lambda plain, hashed: password_valid,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.login(
            LoginSchema(
                email="USER@EXAMPLE.COM",
                password="wrong-password",
            )
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == (
        "Invalid email or password."
    )
    assert exc_info.value.headers == {
        "WWW-Authenticate": "Bearer"
    }


@pytest.mark.parametrize(
    ("user_status", "expected_detail"),
    [
        (UserStatus.LOCKED, "This account is locked."),
        (UserStatus.INACTIVE, "This account is inactive."),
    ],
)
def test_login_rejects_unavailable_account(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
    user_status: UserStatus,
    expected_detail: str,
) -> None:
    user = make_user(status=user_status)
    service.users.get_by_email.return_value = user
    monkeypatch.setattr(
        auth_service_module,
        "verify_password",
        lambda plain, hashed: True,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.login(
            LoginSchema(
                email=user.email,
                password="password123",
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == expected_detail
    service.users.update_last_login.assert_not_called()


def test_login_updates_last_login_and_issues_tokens(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    service.users.get_by_email.return_value = user
    monkeypatch.setattr(
        auth_service_module,
        "verify_password",
        lambda plain, hashed: True,
    )
    service._create_tokens_for_user = MagicMock(
        return_value=token_response()
    )

    result = service.login(
        LoginSchema(
            email="USER@EXAMPLE.COM",
            password="password123",
        )
    )

    service.users.get_by_email.assert_called_once_with(
        "user@example.com"
    )
    service.users.update_last_login.assert_called_once_with(user)
    service._create_tokens_for_user.assert_called_once_with(user)
    assert result["user"] is user


def test_create_tokens_persists_only_refresh_token_hash(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    expiration = datetime.now(UTC) + timedelta(days=7)

    monkeypatch.setattr(
        auth_service_module,
        "create_access_token",
        lambda data: "raw-access-token",
    )
    monkeypatch.setattr(
        auth_service_module,
        "create_refresh_token",
        lambda data: "raw-refresh-token",
    )
    monkeypatch.setattr(
        auth_service_module,
        "verify_refresh_token",
        lambda token: {
            "sub": str(user.id),
            "exp": int(expiration.timestamp()),
        },
    )

    result = service._create_tokens_for_user(user)

    stored_record = (
        service.refresh_tokens.create_token.call_args.args[0]
    )

    assert result == {
        "access_token": "raw-access-token",
        "refresh_token": "raw-refresh-token",
        "token_type": "Bearer",
    }
    assert stored_record.user_id == user.id
    assert stored_record.token_hash == (
        AuthService._hash_refresh_token(
            "raw-refresh-token"
        )
    )
    assert stored_record.token_hash != "raw-refresh-token"
    assert stored_record.expires_at == datetime.fromtimestamp(
        int(expiration.timestamp()),
        tz=UTC,
    )


def test_refresh_rejects_invalid_jwt(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        auth_service_module,
        "verify_refresh_token",
        lambda token: None,
    )

    with pytest.raises(HTTPException) as exc_info:
        service.refresh("invalid-token")

    assert exc_info.value.status_code == 401
    service.refresh_tokens.get_by_token_hash.assert_not_called()


def test_refresh_rejects_missing_database_record(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    monkeypatch.setattr(
        auth_service_module,
        "verify_refresh_token",
        lambda token: {"sub": str(user_id)},
    )
    service.refresh_tokens.get_by_token_hash.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        service.refresh("refresh-token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == (
        "Refresh token was not found."
    )


def test_refresh_rejects_subject_mismatch(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored_token = SimpleNamespace(
        user_id=uuid.uuid4(),
        revoked=False,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    monkeypatch.setattr(
        auth_service_module,
        "verify_refresh_token",
        lambda token: {"sub": str(uuid.uuid4())},
    )
    service.refresh_tokens.get_by_token_hash.return_value = (
        stored_token
    )

    with pytest.raises(HTTPException) as exc_info:
        service.refresh("refresh-token")

    assert exc_info.value.status_code == 401
    service.refresh_tokens.revoke.assert_not_called()


def test_refresh_replay_revokes_all_user_sessions(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    stored_token = SimpleNamespace(
        user_id=user_id,
        revoked=True,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    monkeypatch.setattr(
        auth_service_module,
        "verify_refresh_token",
        lambda token: {"sub": str(user_id)},
    )
    service.refresh_tokens.get_by_token_hash.return_value = (
        stored_token
    )

    with pytest.raises(HTTPException) as exc_info:
        service.refresh("refresh-token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == (
        "Refresh token has already been revoked."
    )
    (
        service.refresh_tokens.revoke_all_for_user
        .assert_called_once_with(user_id)
    )


def test_refresh_rejects_expired_database_record(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    stored_token = SimpleNamespace(
        user_id=user_id,
        revoked=False,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    monkeypatch.setattr(
        auth_service_module,
        "verify_refresh_token",
        lambda token: {"sub": str(user_id)},
    )
    service.refresh_tokens.get_by_token_hash.return_value = (
        stored_token
    )

    with pytest.raises(HTTPException) as exc_info:
        service.refresh("refresh-token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == (
        "Refresh token has expired."
    )


def test_refresh_rejects_missing_user(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid.uuid4()
    stored_token = SimpleNamespace(
        user_id=user_id,
        revoked=False,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    monkeypatch.setattr(
        auth_service_module,
        "verify_refresh_token",
        lambda token: {"sub": str(user_id)},
    )
    service.refresh_tokens.get_by_token_hash.return_value = (
        stored_token
    )
    service.users.get.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        service.refresh("refresh-token")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == (
        "User associated with this token was not found."
    )


@pytest.mark.parametrize(
    "user_status",
    [
        UserStatus.LOCKED,
        UserStatus.INACTIVE,
    ],
)
def test_refresh_revokes_all_sessions_for_unavailable_user(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
    user_status: UserStatus,
) -> None:
    user = make_user(status=user_status)
    stored_token = SimpleNamespace(
        user_id=user.id,
        revoked=False,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    monkeypatch.setattr(
        auth_service_module,
        "verify_refresh_token",
        lambda token: {"sub": str(user.id)},
    )
    service.refresh_tokens.get_by_token_hash.return_value = (
        stored_token
    )
    service.users.get.return_value = user

    with pytest.raises(HTTPException) as exc_info:
        service.refresh("refresh-token")

    assert exc_info.value.status_code == 403
    (
        service.refresh_tokens.revoke_all_for_user
        .assert_called_once_with(user.id)
    )
    service.refresh_tokens.revoke.assert_not_called()


def test_refresh_rotates_active_token(
    service: AuthService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = make_user()
    stored_token = SimpleNamespace(
        user_id=user.id,
        revoked=False,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    monkeypatch.setattr(
        auth_service_module,
        "verify_refresh_token",
        lambda token: {"sub": str(user.id)},
    )
    service.refresh_tokens.get_by_token_hash.return_value = (
        stored_token
    )
    service.users.get.return_value = user
    service._create_tokens_for_user = MagicMock(
        return_value=token_response()
    )

    result = service.refresh("refresh-token")

    service.refresh_tokens.revoke.assert_called_once_with(
        stored_token
    )
    service._create_tokens_for_user.assert_called_once_with(user)
    assert result == token_response()


def test_logout_revokes_known_active_token(
    service: AuthService,
) -> None:
    stored_token = SimpleNamespace(revoked=False)
    service.refresh_tokens.get_by_token_hash.return_value = (
        stored_token
    )

    result = service.logout("refresh-token")

    service.refresh_tokens.revoke.assert_called_once_with(
        stored_token
    )
    assert result == {
        "message": "Logged out successfully."
    }


@pytest.mark.parametrize(
    "stored_token",
    [
        None,
        SimpleNamespace(revoked=True),
    ],
)
def test_logout_is_idempotent(
    service: AuthService,
    stored_token: SimpleNamespace | None,
) -> None:
    service.refresh_tokens.get_by_token_hash.return_value = (
        stored_token
    )

    result = service.logout("refresh-token")

    service.refresh_tokens.revoke.assert_not_called()
    assert result == {
        "message": "Logged out successfully."
    }
