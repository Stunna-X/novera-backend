"""
Outbound email provider implementations.
"""

from app.email.providers.base import (
    EmailAttachment,
    EmailProvider,
    EmailProviderConfigurationError,
    EmailProviderError,
    EmailSendResult,
    OutboundEmailMessage,
)
from app.email.providers.factory import build_email_provider


__all__ = [
    "EmailAttachment",
    "EmailProvider",
    "EmailProviderConfigurationError",
    "EmailProviderError",
    "EmailSendResult",
    "OutboundEmailMessage",
    "build_email_provider",
]