"""
Request context helpers.

Stores request metadata in a context variable so deep service-layer
code can write audit logs with the real HTTP method, path, client IP,
and user-agent without passing Request through every service method.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestAuditContext:
    """
    Minimal request metadata safe for audit logging.
    """

    method: str | None
    path: str | None
    ip_address: str | None
    user_agent: str | None


_request_audit_context: ContextVar[RequestAuditContext | None] = (
    ContextVar(
        "request_audit_context",
        default=None,
    )
)


def _clean(
    value: str | None,
    *,
    max_length: int,
) -> str | None:
    """
    Trim empty strings and limit stored metadata length.
    """

    if value is None:
        return None

    cleaned = value.strip()

    if not cleaned:
        return None

    return cleaned[:max_length]


def set_request_context(
    *,
    method: str | None,
    path: str | None,
    ip_address: str | None,
    user_agent: str | None,
) -> Token[RequestAuditContext | None]:
    """
    Set request metadata for the current request execution context.
    """

    context = RequestAuditContext(
        method=_clean(
            method.upper() if method else None,
            max_length=12,
        ),
        path=_clean(
            path,
            max_length=500,
        ),
        ip_address=_clean(
            ip_address,
            max_length=80,
        ),
        user_agent=_clean(
            user_agent,
            max_length=1000,
        ),
    )

    return _request_audit_context.set(context)


def get_request_audit_context() -> RequestAuditContext | None:
    """
    Return the request audit context for the current execution.
    """

    return _request_audit_context.get()


def reset_request_context(
    token: Token[RequestAuditContext | None],
) -> None:
    """
    Clear request metadata after a request finishes.
    """

    _request_audit_context.reset(token)
