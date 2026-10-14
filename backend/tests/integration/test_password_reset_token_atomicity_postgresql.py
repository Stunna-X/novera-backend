from __future__ import annotations

import hashlib
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.models.password_reset_token import PasswordResetToken
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserStatus
from app.services.auth_service import AuthService, ResetPasswordSchema


def test_concurrent_password_resets_only_allow_one_success(
    integration_session_factory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two concurrent requests must not consume the same reset token."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    email = f"atomic-reset-{uuid4().hex}@example.test"
    user_id = None

    with integration_session_factory() as db:
        user = User(
            first_name="Atomic",
            last_name="Reset",
            email=email,
            password_hash="initial-test-password-hash",
            status=UserStatus.ACTIVE,
            email_verified=True,
        )
        db.add(user)
        db.flush()

        user_id = user.id
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
                used_at=None,
            )
        )
        db.commit()

    barrier = Barrier(2, timeout=15)

    def attempt_reset(password: str) -> str:
        with integration_session_factory() as db:
            service = AuthService(db)
            original_get = service.password_reset_tokens.get_by_token_hash

            def synchronized_get(requested_hash: str):
                result = original_get(requested_hash)
                barrier.wait()
                return result

            service.password_reset_tokens.get_by_token_hash = synchronized_get

            try:
                service.reset_password(
                    ResetPasswordSchema(
                        token=raw_token,
                        password=password,
                    )
                )
                return "success"
            except HTTPException as exc:
                if exc.status_code == 400:
                    return "rejected"
                raise

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt_reset, "FirstConcurrentPassword123!"),
                executor.submit(attempt_reset, "SecondConcurrentPassword123!"),
            ]
            outcomes = [future.result(timeout=45) for future in futures]

        assert outcomes.count("success") == 1, outcomes
        assert outcomes.count("rejected") == 1, outcomes

        with integration_session_factory() as db:
            user = db.query(User).filter(User.id == user_id).one()
            token = (
                db.query(PasswordResetToken)
                .filter(PasswordResetToken.token_hash == token_hash)
                .one()
            )

            assert token.used_at is not None
            assert user.password_hash not in {
                "initial-test-password-hash",
            }
    finally:
        with integration_session_factory() as db:
            db.query(PasswordResetToken).filter(
                PasswordResetToken.user_id == user_id,
            ).delete(synchronize_session=False)
            db.query(RefreshToken).filter(
                RefreshToken.user_id == user_id,
            ).delete(synchronize_session=False)
            if user_id is not None:
                db.query(User).filter(User.id == user_id).delete(
                    synchronize_session=False,
                )
            db.commit()
