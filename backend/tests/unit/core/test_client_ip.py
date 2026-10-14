"""Tests for verified proxy IP resolution."""
from types import SimpleNamespace

from starlette.requests import Request

from app.core.client_ip import (
    is_cloudflare_origin_verified,
    resolve_client_ip,
)

TEST_SECRET = "test-origin-verification-secret-32chars-minimum"


def make_request(*, headers=None, client=("198.51.100.10", 1234)):
    raw_headers = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/test",
        "headers": raw_headers,
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": client,
        "app": SimpleNamespace(),
    })


def test_origin_verification_accepts_matching_secret():
    request = make_request(
        headers={"X-Novera-Origin-Verify": TEST_SECRET}
    )
    assert is_cloudflare_origin_verified(request, TEST_SECRET)


def test_origin_verification_rejects_missing_secret():
    assert not is_cloudflare_origin_verified(make_request(), TEST_SECRET)


def test_origin_verification_rejects_wrong_secret():
    request = make_request(
        headers={"X-Novera-Origin-Verify": "incorrect-secret"}
    )
    assert not is_cloudflare_origin_verified(request, TEST_SECRET)


def test_origin_verification_rejects_unconfigured_secret():
    request = make_request(
        headers={"X-Novera-Origin-Verify": TEST_SECRET}
    )
    assert not is_cloudflare_origin_verified(request, None)


def test_deployed_uses_verified_cloudflare_ip_not_forwarded_for():
    request = make_request(headers={
        "X-Novera-Origin-Verify": TEST_SECRET,
        "CF-Connecting-IP": "203.0.113.20",
        "X-Forwarded-For": "203.0.113.99, 198.51.100.10",
    })
    assert resolve_client_ip(
        request,
        trust_cloudflare_header=True,
        origin_secret=TEST_SECRET,
    ) == "203.0.113.20"


def test_deployed_normalizes_verified_cloudflare_ipv6():
    request = make_request(headers={
        "X-Novera-Origin-Verify": TEST_SECRET,
        "CF-Connecting-IP": "2001:0db8:0000:0000:0000:0000:0000:0001",
    })
    assert resolve_client_ip(
        request,
        trust_cloudflare_header=True,
        origin_secret=TEST_SECRET,
    ) == "2001:db8::1"


def test_deployed_rejects_missing_cloudflare_ip():
    request = make_request(headers={
        "X-Novera-Origin-Verify": TEST_SECRET,
        "X-Forwarded-For": "203.0.113.20",
    })
    assert resolve_client_ip(
        request,
        trust_cloudflare_header=True,
        origin_secret=TEST_SECRET,
    ) is None


def test_deployed_rejects_malformed_cloudflare_ip():
    request = make_request(headers={
        "X-Novera-Origin-Verify": TEST_SECRET,
        "CF-Connecting-IP": "not-an-ip",
    })
    assert resolve_client_ip(
        request,
        trust_cloudflare_header=True,
        origin_secret=TEST_SECRET,
    ) is None


def test_deployed_rejects_cloudflare_ip_without_origin_verification():
    request = make_request(headers={
        "CF-Connecting-IP": "203.0.113.20",
        "X-Forwarded-For": "203.0.113.99",
    })
    assert resolve_client_ip(
        request,
        trust_cloudflare_header=True,
        origin_secret=TEST_SECRET,
    ) is None


def test_development_ignores_forwarding_headers():
    request = make_request(headers={
        "X-Novera-Origin-Verify": "irrelevant-in-development",
        "CF-Connecting-IP": "203.0.113.99",
        "X-Forwarded-For": "203.0.113.88",
    })
    assert resolve_client_ip(
        request,
        trust_cloudflare_header=False,
    ) == "198.51.100.10"


def test_missing_direct_peer_returns_none():
    request = make_request(client=None)
    assert resolve_client_ip(
        request,
        trust_cloudflare_header=False,
    ) is None
