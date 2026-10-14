"""Resolve client IP addresses consistently and safely."""
from __future__ import annotations

import hmac
from ipaddress import ip_address

from starlette.requests import Request

ORIGIN_VERIFICATION_HEADER = "x-novera-origin-verify"


def is_cloudflare_origin_verified(
    request: Request,
    secret: str | None,
) -> bool:
    """Return whether the request carries the configured origin secret."""
    if not secret:
        return False

    candidate = request.headers.get(ORIGIN_VERIFICATION_HEADER)
    if not candidate:
        return False

    return hmac.compare_digest(candidate, secret)


def resolve_client_ip(
    request: Request,
    *,
    trust_cloudflare_header: bool,
    origin_secret: str | None = None,
) -> str | None:
    """Trust Cloudflare client IP only after origin verification."""
    if trust_cloudflare_header:
        if not is_cloudflare_origin_verified(request, origin_secret):
            return None

        candidate = request.headers.get("cf-connecting-ip")
        if not candidate:
            return None

        try:
            return str(ip_address(candidate.strip()))
        except ValueError:
            return None

    client = request.client
    return client.host if client is not None else None
