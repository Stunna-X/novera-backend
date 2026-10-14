"""Shared Redis-backed rate limiting for sensitive API routes."""

from __future__ import annotations

import hashlib
import logging

from fastapi import HTTPException, Request, status
from app.core.client_ip import resolve_client_ip
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

_INCREMENT_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {count, ttl}
"""


def rate_limit(scope: str, max_requests: int, window_seconds: int):
    """Create a FastAPI dependency enforcing a shared per-IP limit."""
    if max_requests < 1 or window_seconds < 1:
        raise ValueError("Rate-limit values must be positive.")

    async def enforce_rate_limit(request: Request) -> None:
        settings = request.app.state.settings

        if not settings.RATE_LIMIT_ENABLED:
            if settings.is_deployed_environment:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Authentication protection is temporarily unavailable.",
                    headers={"Retry-After": "30"},
                )
            return

        redis_client = getattr(request.app.state, "rate_limit_redis", None)
        if redis_client is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication protection is temporarily unavailable.",
                headers={"Retry-After": "30"},
            )

        client_ip = resolve_client_ip(
            request,
            trust_cloudflare_header=settings.is_deployed_environment,
            origin_secret=getattr(
                settings,
                "CLOUDFLARE_ORIGIN_VERIFY_SECRET",
                None,
            ),
        )
        if not client_ip:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to establish a safe client identity.",
                headers={"Retry-After": "30"},
            )

        ip_hash = hashlib.sha256(client_ip.encode("utf-8")).hexdigest()
        key = f"novera:rate-limit:{scope}:{ip_hash}"

        try:
            count, ttl = await redis_client.eval(
                _INCREMENT_SCRIPT, 1, key, window_seconds
            )
        except RedisError:
            logger.exception("Redis rate-limit check failed for scope %s.", scope)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication protection is temporarily unavailable.",
                headers={"Retry-After": "30"},
            ) from None

        if int(count) > max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
                headers={"Retry-After": str(max(int(ttl), 1))},
            )

    return enforce_rate_limit
