"""
Authentication email service.

Handles emails related to authentication flows, including
password-reset instructions.
"""

from __future__ import annotations

from html import escape
import uuid

from app.core.config import Settings, settings
from app.email.providers.base import (
    EmailProviderError,
    OutboundEmailMessage,
)
from app.email.providers.factory import build_email_provider


class AuthEmailService:
    """
    Service responsible for authentication-related emails.
    """

    def __init__(
        self,
        *,
        application_settings: Settings = settings,
    ):
        self.settings = application_settings
        self.provider = build_email_provider(
            self.settings.EMAIL_PROVIDER,
            application_settings=self.settings,
        )

    def send_password_reset_email(
        self,
        *,
        email: str,
        first_name: str,
        token: str,
    ) -> None:
        """
        Send password-reset instructions to a user.
        """

        frontend_url = self.settings.FRONTEND_URL.rstrip("/")
        reset_url = f"{frontend_url}/reset-password?token={token}"

        subject = "Reset your Novera password"

        body_text = (
            f"Hi {first_name},\n\n"
            "We received a request to reset your Novera password.\n\n"
            "Use the link below to choose a new password:\n\n"
            f"{reset_url}\n\n"
            "This link expires in 1 hour and can only be used once.\n\n"
            "If you did not request a password reset, you can safely "
            "ignore this email.\n\n"
            "— Novera"
        )

        body_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Reset your Novera password</title>
</head>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <h2>Reset your Novera password</h2>

    <p>Hi {first_name},</p>

    <p>
        We received a request to reset your Novera password.
    </p>

    <p>
        Click the button below to choose a new password.
    </p>

    <p>
        <a
            href="{reset_url}"
            style="
                display: inline-block;
                padding: 12px 20px;
                background: #10b981;
                color: #ffffff;
                text-decoration: none;
                border-radius: 6px;
            "
        >
            Reset Password
        </a>
    </p>

    <p>
        Or copy and paste this link into your browser:
    </p>

    <p>
        <a href="{reset_url}">{reset_url}</a>
    </p>

    <p>
        This link expires in <strong>1 hour</strong> and can only be
        used once.
    </p>

    <p>
        If you did not request a password reset, you can safely
        ignore this email.
    </p>

    <p>— Novera</p>
</body>
</html>
""".strip()

        message = OutboundEmailMessage(
            from_email=self.settings.EMAIL_FROM_EMAIL,
            from_name=self.settings.EMAIL_FROM_NAME,
            to_email=email,
            to_name=first_name,
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            reply_to_email=self.settings.EMAIL_REPLY_TO_EMAIL,
            message_id=f"<password-reset-{uuid.uuid4()}@novera>",
        )

        try:
            self.provider.send(message)
        except EmailProviderError:
            raise