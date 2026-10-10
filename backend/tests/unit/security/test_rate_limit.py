import asyncio
import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError as RedisConnectionError
from starlette.requests import Request

from app.security.rate_limit import rate_limit


class FakeRedis:
    def __init__(self, result=(1, 60), error=None):
        self.result = result
        self.error = error
        self.calls = []

    async def eval(self, script, number_of_keys, key, window_seconds):
        self.calls.append((script, number_of_keys, key, window_seconds))
        if self.error is not None:
            raise self.error
        return self.result


def make_request(
    *,
    enabled=True,
    deployed=False,
    redis_client=None,
    client=("203.0.113.10", 1234),
):
    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=SimpleNamespace(
                RATE_LIMIT_ENABLED=enabled,
                is_deployed_environment=deployed,
            ),
            rate_limit_redis=redis_client,
        )
    )
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/test",
        "headers": [],
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": client,
        "app": app,
    })


def run_limiter(request, scope="login", maximum=5, window=60):
    dependency = rate_limit(scope, maximum, window)
    asyncio.run(dependency(request))


def test_allows_request_within_limit_and_hashes_client_ip():
    redis_client = FakeRedis(result=(2, 57))
    request = make_request(redis_client=redis_client)

    run_limiter(request, scope="login", maximum=5, window=60)

    assert len(redis_client.calls) == 1
    _, number_of_keys, key, window_seconds = redis_client.calls[0]
    expected_hash = hashlib.sha256(
        b"203.0.113.10"
    ).hexdigest()

    assert number_of_keys == 1
    assert key == f"novera:rate-limit:login:{expected_hash}"
    assert "203.0.113.10" not in key
    assert window_seconds == 60


def test_rejects_request_over_limit_with_429_and_retry_after():
    request = make_request(redis_client=FakeRedis(result=(6, 23)))

    with pytest.raises(HTTPException) as exc:
        run_limiter(request, maximum=5)

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "23"


def test_retry_after_is_at_least_one_second():
    request = make_request(redis_client=FakeRedis(result=(6, 0)))

    with pytest.raises(HTTPException) as exc:
        run_limiter(request, maximum=5)

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "1"


def test_disabled_limiter_bypasses_requests_in_development():
    request = make_request(enabled=False, deployed=False)

    run_limiter(request)


def test_disabled_limiter_fails_closed_in_deployed_environment():
    request = make_request(enabled=False, deployed=True)

    with pytest.raises(HTTPException) as exc:
        run_limiter(request)

    assert exc.value.status_code == 503
    assert exc.value.headers["Retry-After"] == "30"


def test_missing_redis_client_fails_closed():
    request = make_request(enabled=True, redis_client=None)

    with pytest.raises(HTTPException) as exc:
        run_limiter(request)

    assert exc.value.status_code == 503


def test_redis_connection_error_fails_closed():
    redis_client = FakeRedis(error=RedisConnectionError("offline"))
    request = make_request(redis_client=redis_client)

    with pytest.raises(HTTPException) as exc:
        run_limiter(request)

    assert exc.value.status_code == 503


def test_missing_client_identity_fails_closed():
    request = make_request(
        redis_client=FakeRedis(),
        client=None,
    )

    with pytest.raises(HTTPException) as exc:
        run_limiter(request)

    assert exc.value.status_code == 503


def test_invalid_limit_configuration_is_rejected():
    with pytest.raises(ValueError):
        rate_limit("login", 0, 60)

    with pytest.raises(ValueError):
        rate_limit("login", 5, 0)
