"""The suite's hermetic refusal of a LIVE provider request.

The caam rotation pass sends TWO read-only requests per account per pass -- the
usage poll and the capacity read -- and each resolves a real HTTPS connection
unless the test seams it. A pass test that seamed only the usage fetcher would
therefore reach `api.anthropic.com` once per account: slowly, against the
maintainer's own quota, and reported as a flake.

`tests/conftest.py`'s `refuse_live_provider_requests` is what makes forgetting
one LOUD rather than slow. It is pinned here for the same reason the
operator-herdr guard in the root `conftest.py` exposes its verdict as a fixture:
a guard whose refusing branch nothing exercises is a guard nobody knows still
works. BOTH DIRECTIONS are asserted, because a guard that refused every host
would satisfy the refusal legs on its own.

It is asserted from the OUTSIDE -- through the attribute the product actually
reaches for -- rather than by importing the guard. Two `conftest` modules are
loaded by this suite and `import conftest` resolves to whichever landed in
`sys.modules` first, so an import here would pin the wrong thing about half the
time. What matters is the behaviour at the boundary anyway.
"""

from __future__ import annotations

import http.client

import pytest

__all__: list[str] = []

REFUSED_HOST = "api.anthropic.com"


def test_a_live_provider_host_is_refused_rather_than_connected_to() -> None:
    """THE REFUSING BRANCH. The autouse fixture has already patched the class."""
    with pytest.raises(RuntimeError) as raised:
        _ = http.client.HTTPSConnection(REFUSED_HOST, timeout=1.0)

    assert type(raised.value).__name__ == "ProviderRequestRefusedError"
    assert not isinstance(raised.value, OSError), (
        "an OSError would be swallowed by the provider boundary's own fail-closed "
        "handling and reported as an ordinary unreadable response"
    )
    assert REFUSED_HOST in str(raised.value)
    assert "capacity source" in str(raised.value), (
        "the refusal must name the seams to inject, because the test that trips "
        "it is usually one that seamed the usage fetcher and stopped there"
    )


def test_a_port_qualified_provider_host_is_refused_too() -> None:
    """The host is compared without its port, so `host:443` cannot route around it."""
    with pytest.raises(RuntimeError):
        _ = http.client.HTTPSConnection(f"{REFUSED_HOST}:443", timeout=1.0)


def test_every_other_host_still_reaches_the_real_initializer() -> None:
    """THE CONTROL. A guard that refused every host would pass the legs above.

    Constructing an `HTTPSConnection` opens no socket, so the pass-through is
    asserted without reaching the network at all -- and it asserts the real
    initializer RAN, which is the half a wrapper around the whole class breaks:
    `HTTPSConnection.__init__` reaches its base through `super(HTTPSConnection,
    self)`, so rebinding that global to a function raises `super() argument 1
    must be type, not function` for every legitimate host.
    """
    connection = http.client.HTTPSConnection("localhost:9", timeout=1.0)

    assert connection.host == "localhost"
    assert connection.port == 9
    assert connection.timeout == 1.0
