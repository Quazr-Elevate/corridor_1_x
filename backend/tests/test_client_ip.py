"""client_ip() must not be spoofable through X-Forwarded-For."""
from __future__ import annotations

import pytest
from starlette.requests import Request

from app.ratelimit import deps
from app.ratelimit.limiter import RateLimiter
from app.ratelimit.memory import MemoryRateLimitBackend


@pytest.fixture(autouse=True)
def _restore_limiter():
    saved = (deps._limiter, deps._trusted_proxies)
    yield
    deps._limiter, deps._trusted_proxies = saved


def _req(xff: str | None, peer: str = "10.0.0.9") -> Request:
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


def _use(proxies: int) -> None:
    deps.configure_limiter(RateLimiter(MemoryRateLimitBackend()), trusted_proxies=proxies)


def test_zero_proxies_ignores_header():
    _use(0)
    assert deps.client_ip(_req("6.6.6.6")) == "10.0.0.9"


def test_one_proxy_takes_rightmost_not_spoofed_leftmost():
    _use(1)
    # attacker sent "6.6.6.6"; our edge appended the real client 203.0.113.7
    assert deps.client_ip(_req("6.6.6.6, 203.0.113.7")) == "203.0.113.7"
    assert deps.client_ip(_req("203.0.113.7")) == "203.0.113.7"


def test_two_proxies_skip_our_own_hop():
    _use(2)
    # attacker value, real client (added by edge), edge address (added by /api proxy)
    assert deps.client_ip(_req("6.6.6.6, 203.0.113.7, 100.64.0.2")) == "203.0.113.7"


def test_short_header_falls_back_to_socket_peer():
    _use(2)
    assert deps.client_ip(_req("203.0.113.7")) == "10.0.0.9"
    assert deps.client_ip(_req(None)) == "10.0.0.9"


def test_rotating_spoofed_values_share_one_budget():
    _use(1)
    ips = {deps.client_ip(_req(f"1.1.1.{i}, 203.0.113.7")) for i in range(20)}
    assert ips == {"203.0.113.7"}
